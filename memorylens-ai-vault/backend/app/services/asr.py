"""
Audio transcription using faster-whisper (CPU, "tiny"/"base" model).

First run downloads the model weights from Hugging Face -- this needs
internet access once; after that it's cached locally and works offline.
If the download fails (no internet, blocked network, disk issue) or the
model otherwise can't load, transcription is skipped and the rest of the
processing pipeline continues normally -- a media item with no audio or a
silent video should never fail to upload because ASR couldn't run.
"""
from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from typing import List, Optional

_model_lock = threading.Lock()
_model = None
_model_load_failed = False


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


def _get_model():
    global _model, _model_load_failed
    if _model is not None:
        return _model
    if _model_load_failed:
        return None
    with _model_lock:
        if _model is not None or _model_load_failed:
            return _model
        try:
            from faster_whisper import WhisperModel

            size = os.environ.get("WHISPER_MODEL", "tiny")
            # Defense in depth: pin ctranslate2's own internal thread pool to
            # 1 on top of the single-worker pipeline serialization (see
            # pipeline.py) so no remaining internal concurrency can race
            # against OpenCV's native calls.
            _model = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=1, num_workers=1)
        except Exception as exc:  # noqa: BLE001 - must never crash the pipeline
            print(f"[asr] whisper model unavailable, skipping ASR step: {exc}")
            _model_load_failed = True
            _model = None
    return _model


def _has_audio_stream(path: str) -> bool:
    """Some real-world video files (observed: HEVC clips with no audio
    track at all) make faster-whisper's own ffmpeg-based audio loader raise
    a bare "tuple index out of range" when it tries to read a nonexistent
    audio stream. That's not a transcription failure -- there is genuinely
    nothing to transcribe -- so it's detected up front and skipped cleanly
    rather than relying on catching that unhelpful exception message."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10,
        )
        return bool(result.stdout.strip())
    except Exception:
        # If ffprobe itself is unavailable or errors, don't block ASR on
        # that -- fall through and let the real transcribe attempt decide.
        return True


def transcribe(audio_or_video_path: str) -> Optional[List[TranscriptSegment]]:
    """Returns None (meaning "skipped") if the model can't be loaded, the
    file has no audio stream, or transcription otherwise fails; returns a
    (possibly empty) list of segments on success, including
    success-with-no-speech-detected."""
    model = _get_model()
    if model is None:
        return None
    if not _has_audio_stream(audio_or_video_path):
        return None

    def _run(vad_filter: bool):
        segments, _info = model.transcribe(audio_or_video_path, vad_filter=vad_filter)
        return [
            TranscriptSegment(start=round(s.start, 2), end=round(s.end, 2), text=s.text.strip())
            for s in segments
            if s.text and s.text.strip()
        ]

    try:
        return _run(vad_filter=True)
    except Exception as exc:  # noqa: BLE001
        # faster-whisper's VAD (voice-activity-detection) pre-filter can raise
        # "tuple index out of range" on some real-world audio (observed on
        # several short/quiet real video clips) -- not a problem with the
        # audio itself, since it transcribes fine without VAD. Retry once
        # with VAD disabled before giving up, rather than silently returning
        # an empty transcript for audio that actually has speech in it.
        print(f"[asr] vad_filter transcription failed for {audio_or_video_path}: {exc} -- retrying without VAD")
        try:
            return _run(vad_filter=False)
        except Exception as exc2:  # noqa: BLE001
            print(f"[asr] transcription failed for {audio_or_video_path}: {exc2}")
            return None
