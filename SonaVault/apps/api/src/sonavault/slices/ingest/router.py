from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.assets.scoping import AssetAccessError, raise_http_for_asset_error
from sonavault.core.security.deps import require_auth
from sonavault.core.security.rbac import CurrentUser, require_min_tier
from sonavault.db import get_db
from sonavault.slices.ingest.schemas import AssetOut, IngestResponse
from sonavault.slices.ingest.service import (
    UploadValidationError,
    get_asset,
    ingest_asset,
    list_assets,
)

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])

_can_upload = require_min_tier("field_contributor")


async def _ingest(
    *,
    data: bytes,
    declared_type: str,
    original_filename: str | None,
    user: CurrentUser,
    db: AsyncSession,
    sanctuary_id: str | None,
    station_code: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> IngestResponse:
    try:
        asset, deduplicated, job_id = await ingest_asset(
            db,
            data=data,
            declared_type=declared_type,
            original_filename=original_filename,
            uploaded_by=user.user_id,
            sanctuary_id=sanctuary_id,
            station_code=station_code,
            latitude=latitude,
            longitude=longitude,
        )
        await db.commit()
    except UploadValidationError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return IngestResponse(
        sha256=asset.sha256,
        asset_type=asset.asset_type,
        deduplicated=deduplicated,
        geo_qa_flag=asset.geo_qa_flag,
        job_id=job_id,
    )


@router.post("/audio", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_audio(
    file: UploadFile = File(...),
    sanctuary_id: str | None = Form(None),
    station_code: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    user: CurrentUser = Depends(_can_upload),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    return await _ingest(
        data=data,
        declared_type="audio",
        original_filename=file.filename,
        user=user,
        db=db,
        sanctuary_id=sanctuary_id,
        station_code=station_code,
        latitude=latitude,
        longitude=longitude,
    )


@router.post("/document", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),  # "pdf" | "docx" | "xml"
    sanctuary_id: str | None = Form(None),
    user: CurrentUser = Depends(_can_upload),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    return await _ingest(
        data=data,
        declared_type=doc_type,
        original_filename=file.filename,
        user=user,
        db=db,
        sanctuary_id=sanctuary_id,
    )


@router.get("/assets", response_model=list[AssetOut])
async def get_assets(
    asset_type: str | None = None,
    limit: int = 50,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    assets = await list_assets(db, user=user, asset_type=asset_type, limit=limit)
    return [AssetOut.model_validate(a, from_attributes=True) for a in assets]


@router.get("/assets/{sha256}", response_model=AssetOut)
async def get_single_asset(
    sha256: str, user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    try:
        asset = await get_asset(db, sha256=sha256, user=user)
    except AssetAccessError as exc:
        raise_http_for_asset_error(exc)
    return AssetOut.model_validate(asset, from_attributes=True)
