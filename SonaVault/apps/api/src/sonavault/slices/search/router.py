from fastapi import APIRouter, Depends, HTTPException, status

from sonavault.core.security.deps import require_auth
from sonavault.core.security.rbac import ROLE_TIERS, CurrentUser
from sonavault.slices.search.schemas import (
    AcousticTextSearchRequest,
    HybridSearchRequest,
    SearchResponse,
    SearchResult,
    SearchScoreDebugItem,
    SearchScoreDebugResponse,
)
from sonavault.slices.search.service import (
    acoustic_text_search,
    debug_hybrid_text_search,
    hybrid_text_search,
)

router = APIRouter(prefix="/api/v1/search", tags=["search"])

_VALID_TEXT_COLLECTIONS = {"transcript_segments", "document_chunks"}


@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(body: HybridSearchRequest, user: CurrentUser = Depends(require_auth)):
    if body.collection not in _VALID_TEXT_COLLECTIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown collection: {body.collection}"
        )

    results = await hybrid_text_search(
        query=body.query,
        collection=body.collection,
        limit=min(body.limit, 100),
        max_tier=user.tier,
        sanctuary_scopes=user.sanctuary_scopes,
        full_access=user.tier >= ROLE_TIERS["archivist"],
        rerank=body.rerank,
    )
    return SearchResponse(results=[SearchResult.model_validate(r) for r in results])


@router.post("/debug", response_model=SearchScoreDebugResponse)
async def debug_search(body: HybridSearchRequest, user: CurrentUser = Depends(require_auth)):
    if body.collection not in _VALID_TEXT_COLLECTIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown collection: {body.collection}"
        )

    result = await debug_hybrid_text_search(
        query=body.query,
        collection=body.collection,
        limit=min(body.limit, 50),
        max_tier=user.tier,
        sanctuary_scopes=user.sanctuary_scopes,
        full_access=user.tier >= ROLE_TIERS["archivist"],
    )
    return SearchScoreDebugResponse(
        query=result["query"],
        collection=result["collection"],
        total_candidates=result["total_candidates"],
        items=[SearchScoreDebugItem.model_validate(it) for it in result["items"]],
    )


@router.post("/acoustic-text", response_model=SearchResponse)
async def acoustic_text(body: AcousticTextSearchRequest, user: CurrentUser = Depends(require_auth)):
    results = await acoustic_text_search(
        query=body.query,
        limit=min(body.limit, 100),
        max_tier=user.tier,
        sanctuary_scopes=user.sanctuary_scopes,
        full_access=user.tier >= ROLE_TIERS["archivist"],
    )
    return SearchResponse(results=[SearchResult.model_validate(r) for r in results])
