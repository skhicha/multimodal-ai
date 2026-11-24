from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user, require_permission
from app.db import UPLOADS_DIR, db_cursor
from app.services.pipeline import PHOTO_EXTS, VIDEO_EXTS, classify_media_type, process_media_async

router = APIRouter(prefix="/api/media", tags=["media"])

ALLOWED_EXTS = PHOTO_EXTS | VIDEO_EXTS
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200MB

# Magic-byte signatures for the file types we accept. Checked against the
# actual bytes on disk, not the client-supplied filename/extension/mimetype,
# so a renamed/relabelled file can't slip through.
_MAGIC_SIGNATURES: list[tuple[bytes, int]] = [
    (b"\xff\xd8\xff", 0),  # JPEG
    (b"\x89PNG\r\n\x1a\n", 0),  # PNG
    (b"RIFF", 0),  # WEBP (RIFF....WEBP) / AVI (RIFF....AVI )
    (b"BM", 0),  # BMP
    (b"ftyp", 4),  # MP4/MOV/M4V/HEIC (ISO base media file format)
    (b"\x00\x00\x00\x18ftyp", 0),
    (b"\x1aE\xdf\xa3", 0),  # MKV/WEBM (EBML)
]


def _looks_like_known_media(header: bytes) -> bool:
    for sig, offset in _MAGIC_SIGNATURES:
        if len(header) >= offset + len(sig) and header[offset : offset + len(sig)] == sig:
            return True
    return False


class FaceOut(BaseModel):
    frame_time: float
    x: int
    y: int
    w: int
    h: int
    keyframe_url: Optional[str] = None


class TranscriptOut(BaseModel):
    start_time: float
    end_time: float
    text: str


class CaptionOut(BaseModel):
    frame_time: float
    caption: str


class MediaOut(BaseModel):
    id: str
    filename: str
    media_type: str
    status: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_s: Optional[float] = None
    fps: Optional[float] = None
    camera_model: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    taken_at: Optional[str] = None
    created_at: str
    has_faces: bool
    face_count: int
    time_of_day: Optional[str] = None
    outdoor_guess: Optional[str] = None
    asr_status: str
    error: Optional[str] = None
    tags: List[str] = []
    thumb_url: Optional[str] = None
    is_favorite: bool = False
    duplicate_count: int = 0


class MediaDetailOut(MediaOut):
    faces: List[FaceOut] = []
    transcript: List[TranscriptOut] = []
    captions: List[CaptionOut] = []


def _row_to_media_out(row, tags: List[str], duplicate_count: int = 0) -> MediaOut:
    return MediaOut(
        id=row["id"],
        filename=row["filename"],
        media_type=row["media_type"],
        status=row["status"],
        width=row["width"],
        height=row["height"],
        duration_s=row["duration_s"],
        fps=row["fps"],
        camera_model=row["camera_model"],
        gps_lat=row["gps_lat"],
        gps_lon=row["gps_lon"],
        taken_at=row["taken_at"],
        created_at=row["created_at"],
        has_faces=bool(row["has_faces"]),
        face_count=row["face_count"],
        time_of_day=row["time_of_day"],
        outdoor_guess=row["outdoor_guess"],
        asr_status=row["asr_status"],
        error=row["error"],
        tags=tags,
        thumb_url=f"/api/media/{row['id']}/thumbnail" if row["thumb_path"] else None,
        is_favorite=bool(row["is_favorite"]),
        duplicate_count=duplicate_count,
    )


@router.post("/upload", response_model=MediaOut)
async def upload_media(
    file: UploadFile = File(...), current_user: CurrentUser = Depends(require_permission("media.upload"))
) -> MediaOut:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTS)}")

    # Read into memory in bounded chunks so we can reject oversized/invalid
    # uploads cleanly (4xx) before ever writing a byte to disk. The sha256
    # of the actual bytes is computed in the same pass (powers exact-
    # duplicate detection below) rather than re-reading the file again
    # afterward.
    header = b""
    total = 0
    chunks: List[bytes] = []
    hasher = hashlib.sha256()
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"File too large. Max allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")
        if len(header) < 64:
            header += chunk[: 64 - len(header)]
        hasher.update(chunk)
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(400, "Uploaded file is empty")
    if not _looks_like_known_media(header):
        raise HTTPException(400, "File content does not match a supported image/video format")

    # Always generate the on-disk filename ourselves -- the client-supplied
    # filename is only ever stored as metadata, never used as a path.
    media_id = uuid.uuid4().hex[:16]
    media_type = classify_media_type(file.filename or "")
    dest_path = UPLOADS_DIR / f"{media_id}{ext}"

    with dest_path.open("wb") as out:
        for chunk in chunks:
            out.write(chunk)
    size_bytes = dest_path.stat().st_size

    sha256 = hasher.hexdigest()
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO media (id, user_id, filename, media_type, status, file_path, mime_type, size_bytes, sha256)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (media_id, current_user.id, file.filename, media_type, str(dest_path), file.content_type, size_bytes, sha256),
        )
        cur.execute("SELECT * FROM media WHERE id = ?", (media_id,))
        row = cur.fetchone()
        dup_count = cur.execute(
            "SELECT COUNT(*) c FROM media WHERE user_id = ? AND sha256 = ? AND id != ? AND deleted_at IS NULL",
            (current_user.id, sha256, media_id),
        ).fetchone()["c"]

    process_media_async(media_id, str(dest_path), media_type)
    return _row_to_media_out(row, [], duplicate_count=dup_count)


@router.get("", response_model=List[MediaOut])
def list_media(
    media_type: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[MediaOut]:
    # Trashed items (deleted_at set) never appear in the normal library --
    # only GET /api/media/trash lists those.
    clauses = ["user_id = ?", "deleted_at IS NULL"]
    params: list = [current_user.id]
    if media_type:
        clauses.append("media_type = ?")
        params.append(media_type)
    if date_from:
        clauses.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("created_at <= ?")
        params.append(date_to)
    if tag:
        clauses.append("id IN (SELECT media_id FROM tags WHERE tag = ?)")
        params.append(tag)

    where = f"WHERE {' AND '.join(clauses)}"
    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM media {where} ORDER BY created_at DESC", params)
        rows = cur.fetchall()
        # One grouped query for every non-null hash this user owns, rather
        # than a per-row duplicate lookup -- O(1) queries instead of O(n).
        cur.execute(
            "SELECT sha256, COUNT(*) c FROM media WHERE user_id = ? AND sha256 IS NOT NULL AND deleted_at IS NULL "
            "GROUP BY sha256 HAVING COUNT(*) > 1",
            (current_user.id,),
        )
        dup_counts = {r["sha256"]: r["c"] for r in cur.fetchall()}
        out = []
        for row in rows:
            cur.execute("SELECT tag FROM tags WHERE media_id = ?", (row["id"],))
            tags = [r["tag"] for r in cur.fetchall()]
            dup = dup_counts.get(row["sha256"], 1) - 1 if row["sha256"] else 0
            out.append(_row_to_media_out(row, tags, duplicate_count=dup))
    return out


@router.get("/trash", response_model=List[MediaOut])
def list_trash(current_user: CurrentUser = Depends(require_permission("media.delete"))) -> List[MediaOut]:
    """Items this user has soft-deleted -- gated on media.delete (the same
    permission that can move something into Trash in the first place),
    not just media.view, since seeing what's in the trash is part of
    managing deletions, not plain browsing."""
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM media WHERE user_id = ? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC",
            (current_user.id,),
        )
        rows = cur.fetchall()
        out = []
        for row in rows:
            cur.execute("SELECT tag FROM tags WHERE media_id = ?", (row["id"],))
            tags = [r["tag"] for r in cur.fetchall()]
            out.append(_row_to_media_out(row, tags))
    return out


def _get_owned_media_row(media_id: str, user_id: str, cur):
    cur.execute("SELECT * FROM media WHERE id = ? AND user_id = ?", (media_id, user_id))
    return cur.fetchone()


@router.get("/{media_id}", response_model=MediaDetailOut)
def get_media(media_id: str, current_user: CurrentUser = Depends(get_current_user)) -> MediaDetailOut:
    with db_cursor() as cur:
        row = _get_owned_media_row(media_id, current_user.id, cur)
        if not row:
            raise HTTPException(404, "Media not found")
        cur.execute("SELECT tag FROM tags WHERE media_id = ?", (media_id,))
        tags = [r["tag"] for r in cur.fetchall()]
        cur.execute(
            "SELECT frame_time, x, y, w, h, keyframe_path FROM faces WHERE media_id = ? ORDER BY frame_time",
            (media_id,),
        )
        faces = []
        for r in cur.fetchall():
            d = dict(r)
            kf_path = d.pop("keyframe_path", None)
            d["keyframe_url"] = f"/api/media/keyframe/{Path(kf_path).name}" if kf_path else None
            faces.append(FaceOut(**d))
        cur.execute(
            "SELECT start_time, end_time, text FROM transcript_segments WHERE media_id = ? ORDER BY start_time",
            (media_id,),
        )
        transcript = [TranscriptOut(**dict(r)) for r in cur.fetchall()]
        cur.execute(
            "SELECT frame_time, caption FROM media_captions WHERE media_id = ? ORDER BY frame_time",
            (media_id,),
        )
        captions = [CaptionOut(**dict(r)) for r in cur.fetchall()]
        dup_count = cur.execute(
            "SELECT COUNT(*) c FROM media WHERE user_id = ? AND sha256 = ? AND id != ? AND deleted_at IS NULL",
            (current_user.id, row["sha256"], media_id),
        ).fetchone()["c"] if row["sha256"] else 0

    base = _row_to_media_out(row, tags, duplicate_count=dup_count)
    return MediaDetailOut(**base.model_dump(), faces=faces, transcript=transcript, captions=captions)


class DuplicateOut(BaseModel):
    id: str
    filename: str
    thumb_url: Optional[str] = None
    created_at: str


@router.get("/{media_id}/duplicates", response_model=List[DuplicateOut])
def get_duplicates(media_id: str, current_user: CurrentUser = Depends(get_current_user)) -> List[DuplicateOut]:
    """Other media OWNED BY THE SAME USER with byte-identical content (same
    sha256) -- never cross-user, so this can never reveal that some other
    account happens to have uploaded the same file."""
    with db_cursor() as cur:
        row = _get_owned_media_row(media_id, current_user.id, cur)
        if not row:
            raise HTTPException(404, "Media not found")
        if not row["sha256"]:
            return []
        cur.execute(
            "SELECT id, filename, thumb_path, created_at FROM media "
            "WHERE user_id = ? AND sha256 = ? AND id != ? AND deleted_at IS NULL",
            (current_user.id, row["sha256"], media_id),
        )
        return [
            DuplicateOut(
                id=r["id"],
                filename=r["filename"],
                thumb_url=f"/api/media/{r['id']}/thumbnail" if r["thumb_path"] else None,
                created_at=r["created_at"],
            )
            for r in cur.fetchall()
        ]


class FavoriteIn(BaseModel):
    is_favorite: bool


@router.post("/{media_id}/favorite", response_model=MediaOut)
def set_favorite(
    media_id: str, body: FavoriteIn, current_user: CurrentUser = Depends(require_permission("media.edit"))
) -> MediaOut:
    with db_cursor() as cur:
        row = _get_owned_media_row(media_id, current_user.id, cur)
        if not row:
            raise HTTPException(404, "Media not found")
        cur.execute(
            "UPDATE media SET is_favorite = ? WHERE id = ?",
            (1 if body.is_favorite else 0, media_id),
        )
        cur.execute("SELECT * FROM media WHERE id = ?", (media_id,))
        row = cur.fetchone()
        cur.execute("SELECT tag FROM tags WHERE media_id = ?", (media_id,))
        tags = [r["tag"] for r in cur.fetchall()]
    return _row_to_media_out(row, tags)


@router.delete("/{media_id}")
def delete_media(media_id: str, current_user: CurrentUser = Depends(require_permission("media.delete"))) -> dict:
    """Soft-delete: moves the item to Trash (GET /api/media/trash) rather
    than removing its row/files immediately. It also drops out of search
    results right away (removed from search_index below) since a trashed
    item showing up in Search/Ask AI would be confusing, even though its
    row and files are kept until restored or purged."""
    with db_cursor() as cur:
        row = _get_owned_media_row(media_id, current_user.id, cur)
        if not row:
            raise HTTPException(404, "Media not found")
        if row["deleted_at"]:
            raise HTTPException(400, "Already in Trash")
        cur.execute("DELETE FROM search_index WHERE media_id = ?", (media_id,))
        cur.execute("UPDATE media SET deleted_at = datetime('now') WHERE id = ?", (media_id,))
    return {"ok": True}


@router.post("/{media_id}/restore")
def restore_media(media_id: str, current_user: CurrentUser = Depends(require_permission("media.delete"))) -> dict:
    with db_cursor() as cur:
        row = _get_owned_media_row(media_id, current_user.id, cur)
        if not row:
            raise HTTPException(404, "Media not found")
        if not row["deleted_at"]:
            raise HTTPException(400, "Not in Trash")
        cur.execute("UPDATE media SET deleted_at = NULL WHERE id = ?", (media_id,))
    # Restoring an item should make it findable in Search/Ask AI again --
    # re-run the same indexing step the processing pipeline uses, using
    # whatever tags/transcript/captions it already has on file.
    from types import SimpleNamespace

    from app.services.search import reindex_media

    with db_cursor() as cur:
        cur.execute("SELECT filename FROM media WHERE id = ?", (media_id,))
        filename = cur.fetchone()["filename"]
        tags = [r["tag"] for r in cur.execute("SELECT tag FROM tags WHERE media_id = ?", (media_id,)).fetchall()]
        transcript_rows = cur.execute(
            "SELECT start_time, end_time, text FROM transcript_segments WHERE media_id = ? ORDER BY start_time",
            (media_id,),
        ).fetchall()
        caption_rows = cur.execute(
            "SELECT frame_time, caption FROM media_captions WHERE media_id = ? ORDER BY frame_time",
            (media_id,),
        ).fetchall()
    transcript = [SimpleNamespace(start=r["start_time"], end=r["end_time"], text=r["text"]) for r in transcript_rows]
    captions = [SimpleNamespace(frame_time=r["frame_time"], caption=r["caption"]) for r in caption_rows]
    reindex_media(media_id, filename, tags, transcript or None, captions=captions or None)
    return {"ok": True}


@router.delete("/{media_id}/purge")
def purge_media(media_id: str, current_user: CurrentUser = Depends(require_permission("media.delete"))) -> dict:
    """Permanent delete -- only meaningful from within Trash (an item must
    already be soft-deleted), since this is the point of no return the
    Trash UI's confirmation dialog warns about; purging something that was
    never moved to Trash first would skip that safety step entirely."""
    with db_cursor() as cur:
        row = _get_owned_media_row(media_id, current_user.id, cur)
        if not row:
            raise HTTPException(404, "Media not found")
        if not row["deleted_at"]:
            raise HTTPException(400, "Move to Trash before permanently deleting")
        cur.execute("DELETE FROM search_index WHERE media_id = ?", (media_id,))
        cur.execute("DELETE FROM media WHERE id = ?", (media_id,))
    for p in (row["file_path"], row["thumb_path"]):
        if p and Path(p).exists():
            Path(p).unlink(missing_ok=True)
    return {"ok": True}


@router.get("/{media_id}/file")
def get_media_file(media_id: str, current_user: CurrentUser = Depends(get_current_user)):
    with db_cursor() as cur:
        row = _get_owned_media_row(media_id, current_user.id, cur)
    if not row or not Path(row["file_path"]).exists():
        raise HTTPException(404, "File not found")
    return FileResponse(row["file_path"], media_type=row["mime_type"] or None)


@router.get("/{media_id}/thumbnail")
def get_media_thumbnail(media_id: str, current_user: CurrentUser = Depends(get_current_user)):
    with db_cursor() as cur:
        row = _get_owned_media_row(media_id, current_user.id, cur)
    if not row or not row["thumb_path"] or not Path(row["thumb_path"]).exists():
        raise HTTPException(404, "Thumbnail not found")
    return FileResponse(row["thumb_path"], media_type="image/jpeg")


@router.get("/keyframe/{filename}")
def get_keyframe(filename: str, current_user: CurrentUser = Depends(get_current_user)):
    from app.db import KEYFRAMES_DIR

    # Keyframes are only ever requested via a media detail response we've
    # already scoped to this user, but double-check ownership via the
    # faces table so the keyframe path itself can't be guessed cross-user.
    with db_cursor() as cur:
        cur.execute(
            "SELECT f.media_id FROM faces f JOIN media m ON m.id = f.media_id "
            "WHERE f.keyframe_path LIKE ? AND m.user_id = ? LIMIT 1",
            (f"%{filename}", current_user.id),
        )
        if not cur.fetchone():
            raise HTTPException(404, "Keyframe not found")

    path = KEYFRAMES_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Keyframe not found")
    return FileResponse(path, media_type="image/jpeg")
