from datetime import datetime

from pydantic import BaseModel, Field


class StreamTokenResponse(BaseModel):
    token: str
    expires_in: int


class MediaMtxAuthRequest(BaseModel):
    """Mirrors MediaMTX's HTTP auth webhook payload (subset of fields we use)."""

    ip: str | None = None
    user: str | None = None
    password: str | None = None
    path: str
    protocol: str | None = None
    action: str  # "read" | "publish" | ...
    query: str | None = None


class StreamItem(BaseModel):
    station_code: str
    name: str
    description: str | None = None
    sanctuary_id: str | None = None
    rtsp_url: str | None = None
    hls_url: str
    is_active: bool = True
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime | None = None


class StreamCreateRequest(BaseModel):
    station_code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=256)
    description: str | None = None
    sanctuary_id: str | None = None
    rtsp_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class StreamCaptureRequest(BaseModel):
    duration_sec: float = Field(default=30.0, ge=1.0, le=300.0)
    audio_b64: str | None = None
    notes: str | None = None


class StreamCaptureResponse(BaseModel):
    sha256: str
    asset_type: str
    station_code: str
    sanctuary_id: str | None
    job_id: str | None
    message: str
