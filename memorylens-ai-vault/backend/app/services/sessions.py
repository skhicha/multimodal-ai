"""
Session tracking + a tiny in-memory pub/sub broker for cross-device logout.

Each login creates a `sessions` row; its id is embedded as the "sid" claim
in that login's access/refresh JWTs (app/auth.py). Logging out, or an admin
deactivating/deleting the account, revokes the row -- every subsequent
request re-checks it (stateless JWTs alone can't be revoked), and this
module's broker pushes an immediate SSE "logout" event to that device's
open /api/auth/events connection so it doesn't have to wait for its next
request to find out.

In-memory and per-process: fine for this single-process capstone deployment
(uvicorn with one worker). A multi-worker/multi-instance deployment would
need a shared broker (e.g. Redis pub/sub) instead.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Optional

from app.db import db_cursor

# session_id -> set of asyncio.Queue, one per open SSE connection for that
# session (normally just one tab, but nothing stops two).
_subscribers: dict[str, set[asyncio.Queue]] = {}

# Short-lived, single-use tickets for the SSE endpoint. EventSource can't
# set an Authorization header, so the browser can't open that connection
# with a normal bearer token -- but putting the real (long-lived) access
# token directly in the URL means it ends up in browser history, server
# access logs, and any intermediate proxy's logs for as long as that token
# is valid. Instead, an authenticated request (normal Authorization header)
# mints a random ticket good for ~20s and exactly one use, and only that
# ticket goes in the SSE URL.
_SSE_TICKET_TTL_SECONDS = 20
_sse_tickets: dict[str, tuple[str, float]] = {}  # ticket -> (session_id, expires_at)


def issue_sse_ticket(session_id: str) -> str:
    ticket = uuid.uuid4().hex
    _sse_tickets[ticket] = (session_id, time.monotonic() + _SSE_TICKET_TTL_SECONDS)
    return ticket


def consume_sse_ticket(ticket: str) -> Optional[str]:
    """Returns the session id for a valid, unused, unexpired ticket, and
    invalidates it immediately (single use) -- or None if the ticket is
    missing, already used, or expired."""
    entry = _sse_tickets.pop(ticket, None)
    if entry is None:
        return None
    session_id, expires_at = entry
    if time.monotonic() > expires_at:
        return None
    return session_id


def label_from_user_agent(user_agent: Optional[str]) -> Optional[str]:
    """
    Turns a User-Agent header into a short "Browser on OS" label for the
    Settings sessions list -- e.g. "Chrome on Windows", "Safari on iPhone".
    A deliberately small manual sniff (order matters: Edge/OPR/Chrome all
    contain "Safari" in their UA, and Chrome's UA contains "Safari" too) --
    good enough for a human-readable device list, not for real UA parsing
    or browser-sniffing logic. No UA-parsing dependency is in
    requirements.txt, so this avoids adding one for a cosmetic label.
    """
    if not user_agent:
        return None
    ua = user_agent

    if "Edg/" in ua or "EdgA/" in ua or "EdgiOS/" in ua:
        browser = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        browser = "Opera"
    elif "Firefox/" in ua or "FxiOS/" in ua:
        browser = "Firefox"
    elif "CriOS/" in ua or ("Chrome/" in ua and "Chromium/" not in ua):
        browser = "Chrome"
    elif "Chromium/" in ua:
        browser = "Chromium"
    elif "Safari/" in ua and "Version/" in ua:
        browser = "Safari"
    else:
        browser = None

    if "iPhone" in ua:
        os_name = "iPhone"
    elif "iPad" in ua:
        os_name = "iPad"
    elif "Android" in ua:
        os_name = "Android"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        os_name = "macOS"
    elif "Windows" in ua:
        os_name = "Windows"
    elif "Linux" in ua:
        os_name = "Linux"
    else:
        os_name = None

    if browser and os_name:
        return f"{browser} on {os_name}"
    if browser:
        return browser
    if os_name:
        return os_name
    return None


def create_session(user_id: str, device_label: Optional[str] = None) -> str:
    session_id = uuid.uuid4().hex
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO sessions (id, user_id, device_label) VALUES (?, ?, ?)",
            (session_id, user_id, device_label),
        )
    return session_id


def is_session_valid(session_id: Optional[str]) -> bool:
    """A missing sid (tokens minted before this feature existed) is treated
    as valid so already-issued tokens keep working until they naturally
    expire, instead of logging everyone out the moment this ships."""
    if not session_id:
        return True
    with db_cursor() as cur:
        cur.execute("SELECT revoked_at FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
    return bool(row) and row["revoked_at"] is None


def revoke_session(session_id: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE sessions SET revoked_at = datetime('now') WHERE id = ? AND revoked_at IS NULL",
            (session_id,),
        )
    _publish(session_id, "logout")


def revoke_all_sessions_for_user(user_id: str, except_session_id: Optional[str] = None) -> list[str]:
    """Used on logout-all-other-devices, and whenever an admin deactivates
    or deletes a user. Returns the ids that were revoked."""
    with db_cursor() as cur:
        cur.execute(
            "SELECT id FROM sessions WHERE user_id = ? AND revoked_at IS NULL",
            (user_id,),
        )
        ids = [row["id"] for row in cur.fetchall() if row["id"] != except_session_id]
        if ids:
            cur.executemany(
                "UPDATE sessions SET revoked_at = datetime('now') WHERE id = ?",
                [(sid,) for sid in ids],
            )
    for sid in ids:
        _publish(sid, "logout")
    return ids


def list_sessions(user_id: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, device_label, created_at, revoked_at FROM sessions "
            "WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def subscribe(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(session_id, set()).add(q)
    return q


def unsubscribe(session_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(session_id)
    if subs:
        subs.discard(q)
        if not subs:
            _subscribers.pop(session_id, None)


def _publish(session_id: str, event: str) -> None:
    for q in _subscribers.get(session_id, ()):
        q.put_nowait(event)
