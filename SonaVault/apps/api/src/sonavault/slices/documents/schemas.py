from pydantic import BaseModel


class DocumentChunkOut(BaseModel):
    index: int
    text: str
    page_or_section: int


class DocumentChunksResponse(BaseModel):
    sha256: str
    chunks: list[DocumentChunkOut]


class SplReadingOut(BaseModel):
    timestamp: str
    station_code: str
    broadband_db: float
    bands: dict[str, float]


class TelemetryXmlResponse(BaseModel):
    sha256: str
    readings: list[SplReadingOut]
