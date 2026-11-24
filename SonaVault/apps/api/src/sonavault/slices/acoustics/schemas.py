import uuid
from datetime import datetime

from pydantic import BaseModel


class AcousticEventOut(BaseModel):
    id: uuid.UUID
    window_start_sec: float
    window_end_sec: float
    audioset_label: str
    confidence: float
    spl_db_broadband: float | None
    is_hitl_override: bool
    created_at: datetime


class EventsResponse(BaseModel):
    asset_sha256: str
    events: list[AcousticEventOut]


class EventEditRequest(BaseModel):
    audioset_label: str | None = None
    confidence: float | None = None
