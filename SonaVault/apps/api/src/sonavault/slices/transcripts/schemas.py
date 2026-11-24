import uuid
from datetime import datetime

from pydantic import BaseModel


class TranscriptSegmentOut(BaseModel):
    id: uuid.UUID
    seg_index: int
    start_sec: float
    end_sec: float
    speaker_label: str | None
    source_lang: str | None
    text_redacted: str
    translations_json: dict | None
    entities_json: dict | None
    is_hitl_override: bool
    created_at: datetime


class TranscriptResponse(BaseModel):
    asset_sha256: str
    segments: list[TranscriptSegmentOut]


class TranslateRequest(BaseModel):
    target_lang: str


class SegmentEditRequest(BaseModel):
    text_redacted: str | None = None
    speaker_label: str | None = None
