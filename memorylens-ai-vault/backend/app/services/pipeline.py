"""
Background processing pipeline run by a single long-lived worker thread that
drains a queue (no task queue service / no Docker needed -- fine at the
scale of a personal vault).

For photos: EXIF -> face detect -> thumbnail -> tag -> index.
For videos: probe metadata -> keyframes+faces -> ASR (best-effort) ->
            thumbnail -> tag -> index.

Every step is wrapped so a single failure (corrupt file, missing codec,
whisper model unavailable, ...) marks that step skipped/failed instead of
taking down the whole item; only a truly unreadable file ends as 'failed'.

IMPORTANT: uploads are processed one at a time by a single worker thread,
never concurrently. OpenCV's Haar cascade (`detectMultiScale`) and
faster-whisper/ctranslate2 are native-extension libraries whose internal
thread pools are not safe to invoke concurrently from multiple Python
threads in one process -- running them in parallel (one thread per upload)
reliably segfaults the whole server. Serializing all processing through one
worker thread eliminates that by construction: only one native call happens
at a time, ever. `cv2.setNumThreads(1)` below and `cpu_threads=1` on the
whisper model are defense-in-depth on top of that, not a substitute for it.
"""
from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path
from typing import List

import cv2

from app.db import KEYFRAMES_DIR, THUMBS_DIR, db_cursor
from app.services import asr, captioning, exif, vision
from app.services.search import reindex_media

# A video's keyframes already extract every ~2s for face detection; running
# the (CPU-bound, ~1-2s each) captioning model on every single one of them
# would make a long video's processing time scale with its length for a
# non-essential step. Sampling a small, fixed number spread across the clip
# gives a representative sense of what it shows without that cost.
MAX_VIDEO_CAPTIONS = 3

# Defense in depth: keep OpenCV's own internal thread pool from adding any
# concurrency of its own on top of our single-worker serialization.
cv2.setNumThreads(1)

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}

_queue: "queue.Queue[tuple[str, str, str]]" = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def _worker_loop() -> None:
    while True:
        media_id, file_path, media_type = _queue.get()
        try:
            _process_media(media_id, file_path, media_type)
        finally:
            _queue.task_done()


def start_worker() -> None:
    """Starts the single background worker thread, if not already running.
    Idempotent -- safe to call from FastAPI's startup hook even if
    `uvicorn --reload` reimports this module more than once per process."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(target=_worker_loop, daemon=True, name="media-pipeline-worker")
        t.start()
        _worker_started = True


def classify_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in VIDEO_EXTS:
        return "video"
    return "photo"  # default to photo; unknown exts are rejected at upload time


def _set_status(media_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with db_cursor() as cur:
        cur.execute(f"UPDATE media SET {cols} WHERE id = ?", (*fields.values(), media_id))


def process_media_async(media_id: str, file_path: str, media_type: str) -> None:
    """Enqueues an item for processing. Returns immediately -- the actual
    work happens on the single background worker thread, one item at a
    time, so the upload HTTP response never blocks on processing."""
    start_worker()  # idempotent; also started at app startup
    _queue.put((media_id, file_path, media_type))


def _process_media(media_id: str, file_path: str, media_type: str) -> None:
    try:
        _set_status(media_id, status="processing")
        if media_type == "photo":
            _process_photo(media_id, file_path)
        else:
            _process_video(media_id, file_path)
        _set_status(media_id, status="ready")
    except Exception as exc:  # noqa: BLE001 - last-resort guard for the whole item
        traceback.print_exc()
        _set_status(media_id, status="failed", error=str(exc))


def _process_photo(media_id: str, file_path: str) -> None:
    meta = exif.extract_exif(file_path)

    img = cv2.imread(file_path)
    face_boxes: List[tuple] = []
    if img is not None:
        face_boxes = vision.detect_faces(img)
        annotated = vision.draw_face_boxes(img, face_boxes) if face_boxes else img
        thumb = vision.make_thumbnail(annotated, max_dim=640)
        thumb_path = THUMBS_DIR / f"{media_id}.jpg"
        cv2.imwrite(str(thumb_path), thumb)
        for (x, y, w, h) in face_boxes:
            with db_cursor() as cur:
                cur.execute(
                    "INSERT INTO faces (media_id, frame_time, x, y, w, h) VALUES (?, 0, ?, ?, ?, ?)",
                    (media_id, x, y, w, h),
                )
        brightness, saturation = vision.brightness_and_color(img)
        time_of_day = vision.guess_time_of_day(brightness)
        outdoor_guess = vision.guess_outdoor(saturation, brightness)
        width, height = img.shape[1], img.shape[0]
        thumb_path_str = str(thumb_path)
    else:
        time_of_day = None
        outdoor_guess = None
        width, height = meta.width, meta.height
        thumb_path_str = None

    tags = _build_tags(has_faces=bool(face_boxes), time_of_day=time_of_day, outdoor_guess=outdoor_guess)
    _save_tags(media_id, tags)

    # Best-effort scene captioning: never allowed to fail the whole item
    # (same contract as ASR below), and the only source of a textual
    # description this app has for a photo at all, since photos have no
    # transcript.
    captions = []
    if img is not None:
        try:
            caption_text = captioning.caption_image(img)
            if caption_text:
                captions.append(_Caption(frame_time=0.0, caption=caption_text))
        except Exception as exc:  # noqa: BLE001
            print(f"[pipeline] captioning step raised unexpectedly, skipping: {exc}")
    _save_captions(media_id, captions)

    _set_status(
        media_id,
        thumb_path=thumb_path_str,
        width=width,
        height=height,
        camera_model=meta.camera_model,
        gps_lat=meta.gps_lat,
        gps_lon=meta.gps_lon,
        taken_at=meta.taken_at,
        has_faces=1 if face_boxes else 0,
        face_count=len(face_boxes),
        time_of_day=time_of_day,
        outdoor_guess=outdoor_guess,
        asr_status="skipped",
    )

    with db_cursor() as cur:
        cur.execute("SELECT filename FROM media WHERE id = ?", (media_id,))
        filename = cur.fetchone()["filename"]
    reindex_media(media_id, filename, tags, None, captions=captions)


def _process_video(media_id: str, file_path: str) -> None:
    vmeta = vision.probe_video(file_path)

    keyframes = vision.extract_keyframes_with_faces(file_path, KEYFRAMES_DIR, media_id, interval_s=2.0)
    total_faces = 0
    any_faces = False
    brightness_samples = []
    saturation_samples = []
    thumb_path_str = None

    for kf in keyframes:
        if kf.faces:
            any_faces = True
            total_faces += len(kf.faces)
            for (x, y, w, h) in kf.faces:
                with db_cursor() as cur:
                    cur.execute(
                        "INSERT INTO faces (media_id, frame_time, x, y, w, h, keyframe_path) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (media_id, kf.frame_time, x, y, w, h, kf.path),
                    )
        frame = cv2.imread(kf.path)
        if frame is not None:
            brightness, saturation = vision.brightness_and_color(frame)
            brightness_samples.append(brightness)
            saturation_samples.append(saturation)

    if keyframes:
        thumb_src = cv2.imread(keyframes[0].path)
        if thumb_src is not None:
            thumb_path = THUMBS_DIR / f"{media_id}.jpg"
            cv2.imwrite(str(thumb_path), thumb_src)
            thumb_path_str = str(thumb_path)

    avg_brightness = sum(brightness_samples) / len(brightness_samples) if brightness_samples else 128
    avg_saturation = sum(saturation_samples) / len(saturation_samples) if saturation_samples else 0
    time_of_day = vision.guess_time_of_day(avg_brightness)
    outdoor_guess = vision.guess_outdoor(avg_saturation, avg_brightness)

    # Best-effort ASR: never allowed to fail the whole item.
    transcript = None
    asr_status = "skipped"
    try:
        transcript = asr.transcribe(file_path)
        asr_status = "done" if transcript is not None else "skipped"
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline] ASR step raised unexpectedly, skipping: {exc}")
        transcript = None
        asr_status = "skipped"

    if transcript:
        with db_cursor() as cur:
            for seg in transcript:
                cur.execute(
                    "INSERT INTO transcript_segments (media_id, start_time, end_time, text) VALUES (?, ?, ?, ?)",
                    (media_id, seg.start, seg.end, seg.text),
                )

    # Best-effort scene captioning over a small, evenly-spaced sample of
    # this video's keyframes (see MAX_VIDEO_CAPTIONS) -- never allowed to
    # fail the whole item. Distinct from the transcript: this describes
    # what the footage visually SHOWS at a few points in time, which
    # matters most for videos with no speech at all (the "has-speech" tag
    # above would otherwise be the only signal this app has for them).
    captions: List[_Caption] = []
    if keyframes:
        step = max(1, len(keyframes) // MAX_VIDEO_CAPTIONS)
        sampled = keyframes[::step][:MAX_VIDEO_CAPTIONS]
        for kf in sampled:
            frame = cv2.imread(kf.path)
            if frame is None:
                continue
            try:
                caption_text = captioning.caption_image(frame)
                if caption_text:
                    captions.append(_Caption(frame_time=kf.frame_time, caption=caption_text))
            except Exception as exc:  # noqa: BLE001
                print(f"[pipeline] captioning step raised unexpectedly, skipping: {exc}")
    _save_captions(media_id, captions)

    tags = _build_tags(has_faces=any_faces, time_of_day=time_of_day, outdoor_guess=outdoor_guess)
    if transcript:
        tags.append("has-speech")
    _save_tags(media_id, tags)

    _set_status(
        media_id,
        thumb_path=thumb_path_str,
        width=vmeta.width,
        height=vmeta.height,
        duration_s=vmeta.duration_s,
        fps=vmeta.fps,
        taken_at=vmeta.taken_at,
        has_faces=1 if any_faces else 0,
        face_count=total_faces,
        time_of_day=time_of_day,
        outdoor_guess=outdoor_guess,
        asr_status=asr_status,
    )

    with db_cursor() as cur:
        cur.execute("SELECT filename FROM media WHERE id = ?", (media_id,))
        filename = cur.fetchone()["filename"]
    reindex_media(media_id, filename, tags, transcript, captions=captions)


class _Caption:
    """Plain attribute holder, not a dataclass, to match the shape
    reindex_media() already expects (a .frame_time/.caption object) --
    mirrors asr.TranscriptSegment's role for transcript rows."""

    def __init__(self, frame_time: float, caption: str):
        self.frame_time = frame_time
        self.caption = caption


def _save_captions(media_id: str, captions: List["_Caption"]) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM media_captions WHERE media_id = ?", (media_id,))
        for cap in captions:
            cur.execute(
                "INSERT INTO media_captions (media_id, frame_time, caption) VALUES (?, ?, ?)",
                (media_id, cap.frame_time, cap.caption),
            )


def _build_tags(has_faces: bool, time_of_day, outdoor_guess) -> List[str]:
    tags = []
    if has_faces:
        tags.append("has-faces")
    if time_of_day:
        tags.append(time_of_day)
    if outdoor_guess:
        tags.append(outdoor_guess)
    return tags


def _save_tags(media_id: str, tags: List[str]) -> None:
    with db_cursor() as cur:
        cur.execute("DELETE FROM tags WHERE media_id = ?", (media_id,))
        for tag in tags:
            cur.execute("INSERT OR IGNORE INTO tags (media_id, tag) VALUES (?, ?)", (media_id, tag))


def reindex_all() -> int:
    """Rebuilds the FTS index for every item currently in the DB -- used by
    the Settings page's "Re-index" button."""
    with db_cursor() as cur:
        cur.execute("SELECT id, filename FROM media")
        items = cur.fetchall()

    count = 0
    for item in items:
        media_id, filename = item["id"], item["filename"]
        with db_cursor() as cur:
            cur.execute("SELECT tag FROM tags WHERE media_id = ?", (media_id,))
            tags = [r["tag"] for r in cur.fetchall()]
            cur.execute(
                "SELECT start_time, end_time, text FROM transcript_segments WHERE media_id = ? ORDER BY start_time",
                (media_id,),
            )
            transcript = [
                asr.TranscriptSegment(start=r["start_time"], end=r["end_time"], text=r["text"])
                for r in cur.fetchall()
            ]
            cur.execute(
                "SELECT frame_time, caption FROM media_captions WHERE media_id = ? ORDER BY frame_time",
                (media_id,),
            )
            captions = [_Caption(frame_time=r["frame_time"], caption=r["caption"]) for r in cur.fetchall()]
        reindex_media(media_id, filename, tags, transcript, captions=captions)
        count += 1
    return count
