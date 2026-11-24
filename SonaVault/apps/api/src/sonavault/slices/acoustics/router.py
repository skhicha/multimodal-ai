import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.assets.scoping import AssetAccessError, raise_http_for_asset_error
from sonavault.core.security.deps import require_auth
from sonavault.core.security.rbac import CurrentUser, require_min_tier
from sonavault.db import get_db
from sonavault.slices.acoustics.schemas import AcousticEventOut, EventEditRequest, EventsResponse
from sonavault.slices.acoustics.service import (
    EventNotFoundError,
    edit_event,
    get_spl_timeline,
    list_events,
)

router = APIRouter(prefix="/api/v1/acoustics", tags=["acoustics"])

_can_edit = require_min_tier("acoustic_analyst")


@router.get("/{sha256}/events", response_model=EventsResponse)
async def get_events(
    sha256: str, user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    try:
        events = await list_events(db, sha256=sha256, user=user)
    except AssetAccessError as exc:
        raise_http_for_asset_error(exc)
    return EventsResponse(
        asset_sha256=sha256,
        events=[AcousticEventOut.model_validate(e, from_attributes=True) for e in events],
    )


@router.get("/{sha256}/spl", response_model=list[float])
async def get_spl(
    sha256: str, user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    try:
        return await get_spl_timeline(db, sha256=sha256, user=user)
    except AssetAccessError as exc:
        raise_http_for_asset_error(exc)


@router.patch("/{sha256}/events/{event_id}", response_model=AcousticEventOut)
async def edit(
    sha256: str,
    event_id: uuid.UUID,
    body: EventEditRequest,
    user: CurrentUser = Depends(_can_edit),
    db: AsyncSession = Depends(get_db),
):
    try:
        event = await edit_event(
            db,
            sha256=sha256,
            event_id=event_id,
            user=user,
            audioset_label=body.audioset_label,
            confidence=body.confidence,
        )
    except AssetAccessError as exc:
        raise_http_for_asset_error(exc)
    except EventNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return AcousticEventOut.model_validate(event, from_attributes=True)
