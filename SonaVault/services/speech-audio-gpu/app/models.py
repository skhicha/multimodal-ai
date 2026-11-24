from pydantic import BaseModel


class AudioRequest(BaseModel):
    audio_b64: str
    language_hint: str | None = None


class TranscriptSegmentOut(BaseModel):
    start_sec: float
    end_sec: float
    text: str
    language: str | None = None


class TranscribeResponse(BaseModel):
    segments: list[TranscriptSegmentOut]
    detected_language: str


class DiarizationTurnOut(BaseModel):
    start_sec: float
    end_sec: float
    speaker_label: str


class DiarizeResponse(BaseModel):
    turns: list[DiarizationTurnOut]


class AcousticEventOut(BaseModel):
    window_start_sec: float
    window_end_sec: float
    labels: dict[str, float]


class AstEventsResponse(BaseModel):
    events: list[AcousticEventOut]


class ClapEmbeddingResponse(BaseModel):
    embedding: list[float]


class ClapTextRequest(BaseModel):
    text: str
