"""Typed HTTPX client for the nlp-retrieval-gpu sidecar (:8002)."""

import httpx
from pydantic import BaseModel

from sonavault.config import get_settings

TIMEOUT_SECONDS = 60.0


class SparseVector(BaseModel):
    indices: list[int]
    values: list[float]


class BgeM3EmbedResponse(BaseModel):
    dense: list[float]  # 1024-d
    sparse: SparseVector


class RerankResult(BaseModel):
    index: int
    score: float  # sigmoid-applied [0,1]


class RerankResponse(BaseModel):
    results: list[RerankResult]


class NerEntity(BaseModel):
    text: str
    label: str
    start: int
    end: int
    score: float


class GlinerResponse(BaseModel):
    entities: list[NerEntity]


class TranslateResponse(BaseModel):
    translated_text: str
    detected_source_lang: str | None = None


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {"X-Internal-Service-Token": settings.internal_service_token}


def _client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(base_url=settings.nlp_sidecar_url, timeout=TIMEOUT_SECONDS)


async def healthz() -> bool:
    async with _client() as client:
        try:
            resp = await client.get("/healthz")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False


async def embed_bge_m3(texts: list[str]) -> list[BgeM3EmbedResponse]:
    async with _client() as client:
        resp = await client.post("/v1/embed/bge-m3", headers=_headers(), json={"texts": texts})
        resp.raise_for_status()
        return [BgeM3EmbedResponse.model_validate(item) for item in resp.json()["embeddings"]]


async def rerank(query: str, documents: list[str]) -> RerankResponse:
    async with _client() as client:
        resp = await client.post(
            "/v1/rerank", headers=_headers(), json={"query": query, "documents": documents}
        )
        resp.raise_for_status()
        return RerankResponse.model_validate(resp.json())


async def ner_gliner(text: str, labels: list[str]) -> GlinerResponse:
    async with _client() as client:
        resp = await client.post(
            "/v1/ner/gliner", headers=_headers(), json={"text": text, "labels": labels}
        )
        resp.raise_for_status()
        return GlinerResponse.model_validate(resp.json())


async def translate(text: str, *, target_lang: str) -> TranslateResponse:
    async with _client() as client:
        resp = await client.post(
            "/v1/translate", headers=_headers(), json={"text": text, "target_lang": target_lang}
        )
        resp.raise_for_status()
        return TranslateResponse.model_validate(resp.json())
