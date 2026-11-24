from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.assets.scoping import AssetAccessError, raise_http_for_asset_error
from sonavault.core.security.deps import require_auth
from sonavault.core.security.rbac import CurrentUser
from sonavault.db import get_db
from sonavault.slices.documents.schemas import (
    DocumentChunkOut,
    DocumentChunksResponse,
    SplReadingOut,
    TelemetryXmlResponse,
)
from sonavault.slices.documents.service import (
    WrongAssetTypeError,
    get_document_chunks,
    get_telemetry_readings,
)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("/{sha256}/chunks", response_model=DocumentChunksResponse)
async def chunks(
    sha256: str, user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    try:
        chunk_list = await get_document_chunks(db, sha256=sha256, user=user)
    except AssetAccessError as exc:
        raise_http_for_asset_error(exc)
    except WrongAssetTypeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return DocumentChunksResponse(
        sha256=sha256, chunks=[DocumentChunkOut.model_validate(c) for c in chunk_list]
    )


@router.get("/{sha256}/telemetry-xml", response_model=TelemetryXmlResponse)
async def telemetry_xml(
    sha256: str, user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    try:
        readings = await get_telemetry_readings(db, sha256=sha256, user=user)
    except AssetAccessError as exc:
        raise_http_for_asset_error(exc)
    except WrongAssetTypeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return TelemetryXmlResponse(
        sha256=sha256, readings=[SplReadingOut.model_validate(r) for r in readings]
    )
