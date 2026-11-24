from pydantic import BaseModel


class EmbedRequest(BaseModel):
    texts: list[str]


class SparseVector(BaseModel):
    indices: list[int]
    values: list[float]


class BgeM3Embedding(BaseModel):
    dense: list[float]
    sparse: SparseVector


class EmbedResponse(BaseModel):
    embeddings: list[BgeM3Embedding]


class RerankRequest(BaseModel):
    query: str
    documents: list[str]


class RerankResult(BaseModel):
    index: int
    score: float


class RerankResponse(BaseModel):
    results: list[RerankResult]


class NerRequest(BaseModel):
    text: str
    labels: list[str]


class NerEntity(BaseModel):
    text: str
    label: str
    start: int
    end: int
    score: float


class NerResponse(BaseModel):
    entities: list[NerEntity]


class TranslateRequest(BaseModel):
    text: str
    target_lang: str


class TranslateResponse(BaseModel):
    translated_text: str
    detected_source_lang: str | None = None
