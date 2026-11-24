"""Typed HTTPX client for the speech-audio-gpu sidecar (:8001).

Docker bridge-only; every request carries X-Internal-Service-Token so a
compromised public-facing container can't directly drive GPU inference.
"""

import base64

import httpx
from pydantic import BaseModel

from sonavault.config import get_settings

TIMEOUT_SECONDS = 120.0


class TranscriptSegment(BaseModel):
    start_sec: float
    end_sec: float
    text: str
    language: str | None = None


class TranscribeResponse(BaseModel):
    segments: list[TranscriptSegment]
    detected_language: str


class DiarizationTurn(BaseModel):
    start_sec: float
    end_sec: float
    speaker_label: str


class DiarizeResponse(BaseModel):
    turns: list[DiarizationTurn]


class AcousticEvent(BaseModel):
    window_start_sec: float
    window_end_sec: float
    labels: dict[str, float]  # AudioSet label -> sigmoid confidence


class AstEventsResponse(BaseModel):
    events: list[AcousticEvent]


class ClapEmbeddingResponse(BaseModel):
    embedding: list[float]  # 512-d, L2-normalized


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {"X-Internal-Service-Token": settings.internal_service_token}


def _client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(base_url=settings.speech_sidecar_url, timeout=TIMEOUT_SECONDS)


async def healthz() -> bool:
    async with _client() as client:
        try:
            resp = await client.get("/healthz")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False


async def transcribe(audio_bytes: bytes, *, language_hint: str | None = None) -> TranscribeResponse:
    async with _client() as client:
        resp = await client.post(
            "/v1/transcribe",
            headers=_headers(),
            json={
                "audio_b64": base64.b64encode(audio_bytes).decode(),
                "language_hint": language_hint,
            },
        )
        resp.raise_for_status()
        return TranscribeResponse.model_validate(resp.json())


async def diarize(audio_bytes: bytes) -> DiarizeResponse:
    async with _client() as client:
        resp = await client.post(
            "/v1/diarize",
            headers=_headers(),
            json={"audio_b64": base64.b64encode(audio_bytes).decode()},
        )
        resp.raise_for_status()
        return DiarizeResponse.model_validate(resp.json())


async def ast_events(audio_bytes: bytes) -> AstEventsResponse:
    async with _client() as client:
        resp = await client.post(
            "/v1/events/ast",
            headers=_headers(),
            json={"audio_b64": base64.b64encode(audio_bytes).decode()},
        )
        resp.raise_for_status()
        return AstEventsResponse.model_validate(resp.json())


async def embed_clap_audio(audio_bytes: bytes) -> ClapEmbeddingResponse:
    async with _client() as client:
        resp = await client.post(
            "/v1/embed/clap-audio",
            headers=_headers(),
            json={"audio_b64": base64.b64encode(audio_bytes).decode()},
        )
        resp.raise_for_status()
        return ClapEmbeddingResponse.model_validate(resp.json())


async def embed_clap_text(text: str) -> ClapEmbeddingResponse:
    async with _client() as client:
        resp = await client.post("/v1/embed/clap-text", headers=_headers(), json={"text": text})
        resp.raise_for_status()
        return ClapEmbeddingResponse.model_validate(resp.json())
