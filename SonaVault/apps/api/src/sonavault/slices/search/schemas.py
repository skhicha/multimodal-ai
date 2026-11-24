from pydantic import BaseModel


class HybridSearchRequest(BaseModel):
    query: str
    collection: str = "transcript_segments"  # "transcript_segments" | "document_chunks"
    limit: int = 10
    rerank: bool = True


class AcousticTextSearchRequest(BaseModel):
    query: str
    limit: int = 10


class SearchResult(BaseModel):
    asset_sha256: str
    score: float
    rerank_score: float | None = None
    payload: dict


class SearchResponse(BaseModel):
    results: list[SearchResult]
