from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.security.deps import require_auth
from sonavault.core.security.rbac import CurrentUser, require_min_tier
from sonavault.db import get_db
from sonavault.slices.streams.schemas import (
    MediaMtxAuthRequest,
    StreamCaptureRequest,
    StreamCaptureResponse,
    StreamCreateRequest,
    StreamItem,
    StreamTokenResponse,
)
from sonavault.slices.streams.service import (
    OutOfScopeError,
    StreamAuthError,
    StreamNotFoundError,
    authorize_mediamtx_request,
    capture_stream_clip,
    create_or_update_stream,
    delete_stream,
    get_stream,
    issue_stream_token,
    list_streams,
)

router = APIRouter(prefix="/api/v1/streams", tags=["streams"])

_can_publish = require_min_tier("field_contributor")
_can_capture = require_min_tier("acoustic_analyst")


def _to_stream_item(stream) -> StreamItem:
    return StreamItem(
        station_code=stream.station_code,
        name=stream.name,
        description=stream.description,
        sanctuary_id=stream.sanctuary_id,
        rtsp_url=stream.rtsp_url,
        hls_url=f"/hls/hydrophone/{stream.station_code}/index.m3u8",
        is_active=stream.is_active,
        latitude=stream.latitude,
        longitude=stream.longitude,
        created_at=stream.created_at,
    )


@router.get("", response_model=list[StreamItem])
async def get_streams(
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    streams = await list_streams(db, user=user)
    return [_to_stream_item(s) for s in streams]


@router.post("", response_model=StreamItem, status_code=status.HTTP_201_CREATED)
async def create_stream(
    body: StreamCreateRequest,
    user: CurrentUser = Depends(_can_publish),
    db: AsyncSession = Depends(get_db),
):
    try:
        stream = await create_or_update_stream(db, req=body, user=user)
    except OutOfScopeError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return _to_stream_item(stream)


@router.get("/{station_code}", response_model=StreamItem)
async def get_single_stream(
    station_code: str,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        stream = await get_stream(db, station_code=station_code, user=user)
    except OutOfScopeError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except StreamNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _to_stream_item(stream)


@router.delete("/{station_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_single_stream(
    station_code: str,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_stream(db, station_code=station_code, user=user)
    except OutOfScopeError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except StreamNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/{station_code}/token", response_model=StreamTokenResponse)
async def mint_token(station_code: str, user: CurrentUser = Depends(require_auth)):
    try:
        token, expires_in = issue_stream_token(user, station_code=station_code)
    except StreamAuthError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return StreamTokenResponse(token=token, expires_in=expires_in)


@router.post("/{station_code}/capture", response_model=StreamCaptureResponse)
async def capture_stream(
    station_code: str,
    body: StreamCaptureRequest = StreamCaptureRequest(),
    user: CurrentUser = Depends(_can_capture),
    db: AsyncSession = Depends(get_db),
):
    try:
        sha256, asset_type, sanctuary_id, job_id = await capture_stream_clip(
            db, station_code=station_code, req=body, user=user
        )
    except OutOfScopeError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except StreamNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return StreamCaptureResponse(
        sha256=sha256,
        asset_type=asset_type,
        station_code=station_code,
        sanctuary_id=sanctuary_id,
        job_id=job_id,
        message=(
            f"Captured {body.duration_sec}s rolling clip from {station_code} "
            "and enqueued for ingestion"
        ),
    )


@router.post("/mediamtx-auth")
async def mediamtx_auth(body: MediaMtxAuthRequest):
    try:
        authorize_mediamtx_request(password=body.password, path=body.path)
    except StreamAuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return {"status": "authorized"}
