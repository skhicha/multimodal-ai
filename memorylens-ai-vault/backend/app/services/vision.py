"""
Computer-vision helpers: face detection (Haar cascade, ships with OpenCV --
no model download, no GPU), thumbnailing, keyframe extraction for video, and
simple brightness/color heuristics used for honest auto-tagging.

These are intentionally simple, classical CV techniques (no claimed deep
learning) -- a lightweight stand-in for the YOLO face/object detectors used
in the original internship project, chosen here because they run instantly
on a CPU-only MacBook Air with zero setup.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


@dataclass
class FaceBox:
    x: int
    y: int
    w: int
    h: int
    frame_time: float = 0.0


@dataclass
class VideoMeta:
    width: Optional[int] = None
    height: Optional[int] = None
    duration_s: Optional[float] = None
    fps: Optional[float] = None
    taken_at: Optional[str] = None


_DETECT_MAX_DIM = 1024  # working resolution for the cascade, see note below


def detect_faces(bgr_image: np.ndarray) -> List[Tuple[int, int, int, int]]:
    # Run the cascade on a downscaled copy, then scale boxes back up.
    # Haar cascades are tuned for modest resolutions; run directly on a
    # multi-thousand-pixel phone/DSLR photo, the sliding window visits many
    # more candidate scales/positions and throws noticeably more spurious
    # false-positive boxes (confirmed: a single-subject 2687x3356 portrait
    # produced 1 correct box + 6 false positives on the background/suit at
    # full resolution). Downscaling first is the standard mitigation and
    # also makes detection faster on large uploads.
    h, w = bgr_image.shape[:2]
    scale = _DETECT_MAX_DIM / max(h, w)
    if scale < 1:
        small = cv2.resize(bgr_image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        small = bgr_image
        scale = 1.0

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    try:
        boxes = _face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=8, minSize=(40, 40)
        )
    except cv2.error:
        # Upstream OpenCV bug: detectMultiScale's internal rectangle
        # grouping can segfault-as-exception on certain low-feature/uniform
        # images (e.g. a flat-color test frame). No faces is the correct
        # answer for such an image anyway, so treat the crash as "none found".
        return []
    return [(int(x / scale), int(y / scale), int(w / scale), int(h / scale)) for (x, y, w, h) in boxes]


def draw_face_boxes(bgr_image: np.ndarray, boxes: List[Tuple[int, int, int, int]]) -> np.ndarray:
    annotated = bgr_image.copy()
    for (x, y, w, h) in boxes:
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 210, 120), 2)
    return annotated


def make_thumbnail(bgr_image: np.ndarray, max_dim: int = 480) -> np.ndarray:
    h, w = bgr_image.shape[:2]
    scale = max_dim / max(h, w)
    if scale >= 1:
        return bgr_image
    return cv2.resize(bgr_image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def brightness_and_color(bgr_image: np.ndarray) -> Tuple[float, float]:
    """Returns (mean brightness 0-255, mean saturation 0-255) used for the
    honest time-of-day / outdoor heuristics -- not a scene classifier."""
    hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
    brightness = float(np.mean(hsv[:, :, 2]))
    saturation = float(np.mean(hsv[:, :, 1]))
    return brightness, saturation


def guess_time_of_day(brightness: float) -> str:
    if brightness < 70:
        return "night"
    if brightness < 130:
        return "evening/indoor"
    return "day"


def guess_outdoor(saturation: float, brightness: float) -> str:
    # Rough heuristic only: bright + saturated frames (sky/foliage/sun) tend
    # to be outdoors; dim, low-saturation frames tend to be indoors. This is
    # deliberately labelled a "guess" everywhere it surfaces in the UI.
    if saturation > 70 and brightness > 90:
        return "likely outdoor"
    return "likely indoor"


def _video_creation_time(path: str) -> Optional[str]:
    """Reads the container-level creation_time tag (e.g. QuickTime/MP4's
    com.apple.quicktime.creationdate or the generic format-level
    creation_time most phones/cameras write) via a second, cheap ffprobe
    call -- separate from probe_video_ffprobe's stream-level query since
    this tag lives under "format", not "streams"."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format_tags=creation_time",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=15,
        )
        value = proc.stdout.strip()
        if not value:
            return None
        # Normalize to the same bare ISO-8601 format photo EXIF taken_at
        # uses (exif.py's dt.isoformat()) rather than whatever variant
        # ffprobe hands back (commonly "...Z" UTC with microseconds).
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.isoformat()
        except ValueError:
            return value  # unparseable but non-empty -- keep it rather than discard real data
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def probe_video_ffprobe(path: str) -> Optional[VideoMeta]:
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,avg_frame_rate,duration",
                "-of", "json", path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            return None
        info = json.loads(proc.stdout)
        streams = info.get("streams") or []
        if not streams:
            return None
        s = streams[0]
        fps = None
        if s.get("avg_frame_rate") and s["avg_frame_rate"] != "0/0":
            num, _, den = s["avg_frame_rate"].partition("/")
            fps = float(num) / float(den) if float(den or 1) else None
        duration = float(s["duration"]) if s.get("duration") else None
        taken_at = _video_creation_time(path)
        return VideoMeta(width=s.get("width"), height=s.get("height"), duration_s=duration, fps=fps, taken_at=taken_at)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, KeyError):
        return None


def probe_video_opencv(path: str) -> VideoMeta:
    cap = cv2.VideoCapture(path)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = (frame_count / fps) if fps else None
        return VideoMeta(width=width or None, height=height or None, duration_s=duration, fps=fps or None)
    finally:
        cap.release()


def probe_video(path: str) -> VideoMeta:
    """ffprobe first (richer/faster), OpenCV as a guaranteed fallback when
    ffmpeg isn't installed on the machine."""
    meta = probe_video_ffprobe(path)
    if meta and meta.width and meta.duration_s:
        return meta
    return probe_video_opencv(path)


@dataclass
class KeyframeResult:
    frame_time: float
    path: str
    faces: List[Tuple[int, int, int, int]] = field(default_factory=list)


def extract_keyframes_with_faces(
    video_path: str, out_dir: Path, media_id: str, interval_s: float = 2.0
) -> List[KeyframeResult]:
    """Pulls one frame every `interval_s` seconds, runs face detection on
    it, draws boxes, and saves the annotated keyframe to disk."""
    cap = cv2.VideoCapture(video_path)
    results: List[KeyframeResult] = []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = frame_count / fps if fps else 0
        step_frames = max(int(fps * interval_s), 1)

        frame_idx = 0
        saved = 0
        max_keyframes = 40  # cap so a long video doesn't flood the disk
        while saved < max_keyframes:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if not ok:
                break
            boxes = detect_faces(frame)
            annotated = draw_face_boxes(frame, boxes)
            annotated = make_thumbnail(annotated, max_dim=640)
            t = frame_idx / fps if fps else frame_idx * interval_s
            fname = f"{media_id}_kf_{saved:03d}.jpg"
            fpath = out_dir / fname
            cv2.imwrite(str(fpath), annotated)
            results.append(KeyframeResult(frame_time=round(t, 2), path=str(fpath), faces=boxes))
            saved += 1
            frame_idx += step_frames
            if duration and frame_idx / fps > duration:
                break
    finally:
        cap.release()
    return results
