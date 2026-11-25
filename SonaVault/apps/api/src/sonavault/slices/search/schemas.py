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


class SearchScoreDebugItem(BaseModel):
    point_id: str
    asset_sha256: str
    dense_score: float | None = None
    dense_rank: int | None = None
    sparse_score: float | None = None
    sparse_rank: int | None = None
    rrf_score: float | None = None
    rrf_rank: int | None = None
    rerank_score: float | None = None
    rerank_rank: int | None = None
    text: str | None = None
    payload: dict


class SearchScoreDebugResponse(BaseModel):
    query: str
    collection: str
    total_candidates: int
    items: list[SearchScoreDebugItem]
