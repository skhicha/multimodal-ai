import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.security.deps import require_auth
from sonavault.core.security.rbac import CurrentUser
from sonavault.db import get_db
from sonavault.slices.briefings.schemas import (
    BriefingExportResponse,
    BriefingListItem,
    BriefingResponse,
    BriefingSynthesizeRequest,
)
from sonavault.slices.briefings.service import (
    export_briefing_dossier,
    get_briefing,
    list_briefings,
    synthesize_briefing_stream,
)

router = APIRouter(prefix="/api/v1/briefings", tags=["briefings"])


@router.post("/synthesize", status_code=status.HTTP_200_OK)
async def synthesize_briefing(
    body: BriefingSynthesizeRequest,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    stream = synthesize_briefing_stream(
        db=db,
        user=user,
        prompt=body.prompt,
        sanctuary_scope=body.sanctuary_scope,
        max_evidence_chunks=body.max_evidence_chunks,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=list[BriefingListItem])
async def get_briefings(
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    items = await list_briefings(db=db, user=user)
    return [
        BriefingListItem(
            id=item.id,
            prompt=item.prompt,
            sanctuary_scope=item.sanctuary_scope,
            model_id=item.model_id,
            created_at=item.created_at,
            excerpt=item.markdown_body[:160] + ("..." if len(item.markdown_body) > 160 else ""),
        )
        for item in items
    ]


@router.get("/{briefing_id}", response_model=BriefingResponse)
async def get_briefing_by_id(
    briefing_id: uuid.UUID,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    briefing = await get_briefing(db=db, briefing_id=briefing_id, user=user)
    return BriefingResponse.model_validate(briefing)


@router.get("/{briefing_id}/export", response_model=BriefingExportResponse)
async def export_briefing(
    briefing_id: uuid.UUID,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    briefing = await get_briefing(db=db, briefing_id=briefing_id, user=user)
    dossier = export_briefing_dossier(briefing, user)
    return BriefingExportResponse.model_validate(dossier)
