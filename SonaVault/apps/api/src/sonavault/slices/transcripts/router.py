import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.assets.scoping import AssetAccessError, raise_http_for_asset_error
from sonavault.core.security.deps import require_auth
from sonavault.core.security.rbac import CurrentUser, require_min_tier
from sonavault.db import get_db
from sonavault.slices.transcripts.schemas import (
    SegmentEditRequest,
    TranscriptResponse,
    TranscriptSegmentOut,
    TranslateRequest,
)
from sonavault.slices.transcripts.service import (
    SegmentNotFoundError,
    edit_segment,
    get_transcript,
    translate_transcript,
)

router = APIRouter(prefix="/api/v1/transcripts", tags=["transcripts"])

_can_edit = require_min_tier("acoustic_analyst")


def _to_response(sha256: str, segments) -> TranscriptResponse:
    return TranscriptResponse(
        asset_sha256=sha256,
        segments=[TranscriptSegmentOut.model_validate(s, from_attributes=True) for s in segments],
    )


@router.get("/{sha256}", response_model=TranscriptResponse)
async def get(
    sha256: str, user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    try:
        segments = await get_transcript(db, sha256=sha256, user=user)
    except AssetAccessError as exc:
        raise_http_for_asset_error(exc)
    return _to_response(sha256, segments)


@router.post("/{sha256}/translate", response_model=TranscriptResponse)
async def translate(
    sha256: str,
    body: TranslateRequest,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        segments = await translate_transcript(
            db, sha256=sha256, user=user, target_lang=body.target_lang
        )
    except AssetAccessError as exc:
        raise_http_for_asset_error(exc)
    return _to_response(sha256, segments)


@router.patch("/{sha256}/segments/{seg_id}", response_model=TranscriptSegmentOut)
async def edit(
    sha256: str,
    seg_id: uuid.UUID,
    body: SegmentEditRequest,
    user: CurrentUser = Depends(_can_edit),
    db: AsyncSession = Depends(get_db),
):
    try:
        segment = await edit_segment(
            db,
            sha256=sha256,
            seg_id=seg_id,
            user=user,
            text_redacted=body.text_redacted,
            speaker_label=body.speaker_label,
        )
    except AssetAccessError as exc:
        raise_http_for_asset_error(exc)
    except SegmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return TranscriptSegmentOut.model_validate(segment, from_attributes=True)
