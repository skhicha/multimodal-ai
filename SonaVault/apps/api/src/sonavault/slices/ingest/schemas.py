from pydantic import BaseModel


class AssetOut(BaseModel):
    sha256: str
    asset_type: str
    original_filename: str | None
    mime_type: str
    size_bytes: int
    sanctuary_id: str | None
    station_code: str | None
    latitude: float | None
    longitude: float | None
    geo_qa_flag: str | None


class IngestResponse(BaseModel):
    sha256: str
    asset_type: str
    deduplicated: bool
    geo_qa_flag: str | None
    job_id: str | None = None
