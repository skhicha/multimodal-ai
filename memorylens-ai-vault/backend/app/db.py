"""
SQLite access layer for MemoryLens AI.

Deliberately not using an ORM: the schema is small enough that raw SQL plus
FTS5 is simpler to reason about, and it keeps the "lighter form" of the
original forensic-suite's Postgres + full-text-search stack honest for a
local, no-Docker capstone project.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")).resolve()
UPLOADS_DIR = DATA_DIR / "uploads"
THUMBS_DIR = DATA_DIR / "thumbnails"
KEYFRAMES_DIR = DATA_DIR / "keyframes"
DB_PATH = DATA_DIR / "memorylens.db"

for d in (DATA_DIR, UPLOADS_DIR, THUMBS_DIR, KEYFRAMES_DIR):
    d.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS otp_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('login', 'verify_email', 'password_reset')),
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_otp_codes_user ON otp_codes(user_id);

-- One-time recovery codes for authenticator-app MFA, generated once when
-- MFA is enabled and shown to the user a single time.
CREATE TABLE IF NOT EXISTS mfa_backup_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mfa_backup_codes_user ON mfa_backup_codes(user_id);

CREATE TABLE IF NOT EXISTS media (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('photo', 'video')),
    status TEXT NOT NULL DEFAULT 'pending',
    file_path TEXT NOT NULL,
    thumb_path TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    width INTEGER,
    height INTEGER,
    duration_s REAL,
    fps REAL,
    camera_model TEXT,
    gps_lat REAL,
    gps_lon REAL,
    taken_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    has_faces INTEGER NOT NULL DEFAULT 0,
    face_count INTEGER NOT NULL DEFAULT 0,
    time_of_day TEXT,
    outdoor_guess TEXT,
    asr_status TEXT NOT NULL DEFAULT 'skipped',
    error TEXT,
    is_favorite INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    frame_time REAL NOT NULL DEFAULT 0,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    w INTEGER NOT NULL,
    h INTEGER NOT NULL,
    keyframe_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_faces_media ON faces(media_id);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transcript_media ON transcript_segments(media_id);

-- Visual scene captions (what a photo, or a video keyframe, actually
-- SHOWS -- see services/captioning.py), as opposed to transcript_segments
-- (what was SAID). frame_time is 0 for a photo's single caption, or the
-- real keyframe timestamp for one of a video's (capped) sampled frames.
CREATE TABLE IF NOT EXISTS media_captions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    frame_time REAL NOT NULL DEFAULT 0,
    caption TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_captions_media ON media_captions(media_id);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    tag TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tags_media ON tags(media_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_unique ON tags(media_id, tag);

-- External-content FTS5 index: indexes filename, tags and transcript text
-- for every media item, keyed by media_id so search results can resolve
-- straight back to the media detail page.
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    media_id UNINDEXED,
    source UNINDEXED,
    segment_start UNINDEXED,
    text
);

-- One row per logged-in browser/device. The session's id is embedded as
-- the "sid" claim in that login's access+refresh JWTs, so an otherwise
-- stateless, still-unexpired JWT can still be invalidated instantly: logout
-- (or an admin deactivating/deleting the user) sets revoked_at, and every
-- request re-checks the row (see app/auth.py get_current_user), while the
-- SSE stream in app/services/sessions.py pushes an immediate "logout" event
-- to that specific device so it doesn't have to wait for its next request.
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_label TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

-- RBAC: roles/permissions live alongside the existing `users.role` TEXT
-- column rather than replacing it. `users.role` remains the source of
-- truth for "which role slug a user has" (so existing login/require_role
-- guards keep working untouched); these tables add a real, editable
-- permission set per role slug for the new has_permission()/require_permission()
-- checks and the admin Roles UI.
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    is_system INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- Collections (albums): a named grouping of a user's own media, in one of
-- two modes. "Manual" collections (filter_json IS NULL) hold an explicit
-- list of items via collection_items, added/removed one at a time -- a
-- normal album. "Smart" collections (filter_json set) have no items of
-- their own at all; their membership is computed at read time by re-running
-- the same media_type/tag/date filter Library already supports, so a smart
-- collection like "Outdoor videos" always reflects the current vault
-- instead of a stale snapshot.
CREATE TABLE IF NOT EXISTS collections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    filter_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_collections_user ON collections(user_id);

CREATE TABLE IF NOT EXISTS collection_items (
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (collection_id, media_id)
);
"""

# Permission catalogue: resource -> [(action, description), ...]. Codes are
# "<resource>.<action>". Mirrors the reference app's PERMISSION_CATALOGUE
# shape, adapted to this app's actual routers.
PERMISSION_CATALOGUE: dict[str, list[tuple[str, str]]] = {
    "media": [
        ("view", "View media library and detail pages"),
        ("upload", "Upload new photos/videos"),
        ("edit", "Edit tags and favorite status"),
        ("delete", "Delete media"),
        ("download", "Download/stream original media files"),
    ],
    "search": [
        ("view", "Use search"),
    ],
    "ask_ai": [
        ("view", "Use the Ask AI chat"),
    ],
    "dashboard": [
        ("view", "View the dashboard"),
    ],
    "users": [
        ("view", "View the user list"),
        ("create", "Create new users"),
        ("edit", "Edit users (role, name, active status)"),
        ("delete", "Delete users"),
    ],
    "roles": [
        ("view", "View roles and their permissions"),
        ("edit", "Edit role permissions"),
    ],
    "settings": [
        ("view", "View account/appearance settings"),
        ("edit", "Edit account/appearance settings"),
    ],
    "collections": [
        ("view", "View collections/albums"),
        ("create", "Create collections/albums"),
        ("edit", "Rename/edit a collection and add or remove its items"),
        ("delete", "Delete a collection"),
    ],
}

# Permission codes introduced after the initial RBAC release. On an
# existing database, an admin's prior edits to an EXISTING role's grants
# must never be silently overwritten on restart (see the "only seed a
# role's defaults the first time it has zero permissions" rule below) --
# but that same rule would mean a role created before this set of codes
# existed just never gets them at all, forever. This set is backfilled
# per-code instead (see _seed_rbac): granted to a role only if that role
# has no row at all for that specific code yet, which is safe to do
# unconditionally for a code that didn't exist until now.
NEW_PERMISSION_CODES = {"collections.view", "collections.create", "collections.edit", "collections.delete"}

# Default grants per role slug, matching current hard-coded behaviour so
# nothing regresses when this table starts being consulted.
_ALL_CODES = [f"{resource}.{action}" for resource, actions in PERMISSION_CATALOGUE.items() for action, _ in actions]

DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": list(_ALL_CODES),
    "editor": [
        "media.view", "media.upload", "media.edit", "media.delete", "media.download",
        "search.view", "ask_ai.view", "dashboard.view",
        "settings.view", "settings.edit",
        "collections.view", "collections.create", "collections.edit", "collections.delete",
    ],
    "viewer": [
        "media.view", "media.download",
        "search.view", "ask_ai.view", "dashboard.view",
        "settings.view",
        "collections.view",
    ],
}

SYSTEM_ROLES = [
    ("admin", "Admin", "Full access to everything"),
    ("editor", "Editor", "Can manage media, search, and use Ask AI"),
    ("viewer", "Viewer", "Read-only access"),
]


def _seed_rbac(conn: sqlite3.Connection) -> None:
    for slug, name, description in SYSTEM_ROLES:
        conn.execute(
            "INSERT INTO roles (name, slug, description, is_system) VALUES (?, ?, ?, 1) "
            "ON CONFLICT(slug) DO NOTHING",
            (name, slug, description),
        )
    for resource, actions in PERMISSION_CATALOGUE.items():
        for action, description in actions:
            code = f"{resource}.{action}"
            conn.execute(
                "INSERT INTO permissions (code, resource, action, description) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(code) DO NOTHING",
                (code, resource, action, description),
            )
    # Only seed default role_permissions the FIRST time a role has none at
    # all, so re-running init_db() never clobbers permissions an admin has
    # since toggled off/on via the Roles UI.
    for slug in DEFAULT_ROLE_PERMISSIONS:
        role_row = conn.execute("SELECT id FROM roles WHERE slug = ?", (slug,)).fetchone()
        if not role_row:
            continue
        role_id = role_row[0]
        existing = conn.execute(
            "SELECT COUNT(*) FROM role_permissions WHERE role_id = ?", (role_id,)
        ).fetchone()[0]
        if existing:
            continue
        for code in DEFAULT_ROLE_PERMISSIONS[slug]:
            perm_row = conn.execute("SELECT id FROM permissions WHERE code = ?", (code,)).fetchone()
            if perm_row:
                conn.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                    (role_id, perm_row[0]),
                )
    # Backfill permission codes introduced after the initial RBAC release
    # (see NEW_PERMISSION_CODES) onto every role, including ones that
    # already had other permissions and so were skipped by the "only seed
    # a role's defaults the first time it has zero permissions" loop
    # above. This is safe to run unconditionally on every startup: a code
    # that didn't exist before this release can't have been previously
    # removed by an admin, so there's no prior edit to accidentally
    # overwrite -- unlike the loop above, which must never re-grant an
    # OLD code an admin deliberately took away.
    for slug, codes in DEFAULT_ROLE_PERMISSIONS.items():
        role_row = conn.execute("SELECT id FROM roles WHERE slug = ?", (slug,)).fetchone()
        if not role_row:
            continue
        role_id = role_row[0]
        for code in codes:
            if code not in NEW_PERMISSION_CODES:
                continue
            perm_row = conn.execute("SELECT id FROM permissions WHERE code = ?", (code,)).fetchone()
            if perm_row:
                conn.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                    (role_id, perm_row[0]),
                )
    conn.commit()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added to `users` after its initial release. SQLite has no
# "ADD COLUMN IF NOT EXISTS", so each migration is applied with ALTER TABLE
# and the resulting "duplicate column" error (raised on a database that
# already has the column) is swallowed, keeping init_db() safe to run
# against an existing dev database as well as a brand-new one.
USER_COLUMN_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN otp_enabled INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'editor'",
    "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1",
    # Google SSO: nullable, set only for accounts created/linked via
    # "Sign in with Google". A password_hash still exists for these rows
    # (a random, never-typeable value) since the column is NOT NULL --
    # such an account simply can't log in with a password unless it later
    # goes through the normal forgot-password flow to set a real one.
    "ALTER TABLE users ADD COLUMN google_sub TEXT",
    # Real authenticator-app MFA (TOTP, RFC 6238) -- separate from and in
    # addition to the simpler email-OTP login. totp_secret is only set
    # once setup is confirmed; mfa_enabled gates whether login requires it.
    "ALTER TABLE users ADD COLUMN totp_secret TEXT",
    "ALTER TABLE users ADD COLUMN mfa_enabled INTEGER DEFAULT 0",
]

MEDIA_COLUMN_MIGRATIONS = [
    "ALTER TABLE media ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0",
    # sha256 of the file's actual bytes, computed once at upload time --
    # powers exact-duplicate detection (same file uploaded twice, or the
    # same photo saved under two different filenames) without needing any
    # perceptual-hashing library; two rows sharing a hash are provably the
    # same bytes, not just "probably similar."
    "ALTER TABLE media ADD COLUMN sha256 TEXT",
    # Soft-delete: a non-NULL deleted_at moves an item into Trash instead
    # of removing its row/files immediately. list_media() filters these out
    # by default; a separate trash endpoint lists only these, with restore
    # (clear deleted_at) and permanent-purge (the old hard-delete behavior)
    # actions.
    "ALTER TABLE media ADD COLUMN deleted_at TEXT",
]


def _migrate(conn: sqlite3.Connection) -> None:
    for statement in USER_COLUMN_MIGRATIONS + MEDIA_COLUMN_MIGRATIONS:
        try:
            conn.execute(statement)
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise
    # Run after the ALTER TABLEs above since google_sub doesn't exist until
    # then on a pre-existing database. SQLite unique indexes allow any
    # number of NULLs, so plain members (google_sub IS NULL) are unaffected.
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub)")
    # Not unique (NULL sha256 rows exist for media uploaded before this
    # migration, and SQLite's non-unique index happily allows duplicate
    # NULLs as well as duplicate real hashes) -- this is purely a lookup
    # accelerator for "find other rows with this same hash."
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_sha256 ON media(sha256)")
    conn.commit()


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate(conn)
        _seed_rbac(conn)
    finally:
        conn.close()


@contextmanager
def db_cursor() -> Iterator[sqlite3.Cursor]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()
