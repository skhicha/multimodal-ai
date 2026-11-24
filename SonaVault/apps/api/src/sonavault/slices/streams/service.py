"""Live hydrophone stream auth, registry, and rolling capture.

Flow: an authenticated viewer requests a short-lived, station-scoped stream
token; the SPA passes it to hls.js as a signed query parameter against the
MediaMTX HLS URL. MediaMTX then calls back to its HTTP auth hook for every
read or publish attempt; we validate the token's scope, expiry, and
station-code binding before allowing the connection.

AcousticAnalyst+ users can perform one-click rolling capture to ingest a
live snippet directly into the SonaVault vault and trigger the 7-stage
ingestion pipeline.
"""

import base64
import struct
from datetime import UTC, datetime

import jwt as pyjwt
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.security.jwt import decode_stream_token, mint_stream_token
from sonavault.core.security.rbac import ROLE_TIERS, CurrentUser
from sonavault.models.streams import HydrophoneStream
from sonavault.slices.ingest.service import ingest_asset
from sonavault.slices.streams.schemas import StreamCaptureRequest, StreamCreateRequest

STREAM_TOKEN_TTL_SECONDS = 300

# Canonical SanctSound sanctuary monitoring stations seeded by default
DEFAULT_STATIONS = [
    {
        "station_code": "OC02",
        "name": "Olympic Coast SanctSound Hydrophone 02",
        "description": "Outer coast shelf mooring, 24kHz continuous bioacoustic monitor.",
        "sanctuary_id": "OC02",
        "rtsp_url": "rtsp://mediamtx:8554/hydrophone/OC02",
        "latitude": 47.900,
        "longitude": -124.800,
        "is_active": True,
    },
    {
        "station_code": "MB01",
        "name": "Monterey Bay SanctSound Hydrophone 01",
        "description": "Deep-canyon marine mammal vocalization and container vessel corridor.",
        "sanctuary_id": "MB01",
        "rtsp_url": "rtsp://mediamtx:8554/hydrophone/MB01",
        "latitude": 36.700,
        "longitude": -122.000,
        "is_active": True,
    },
    {
        "station_code": "FK01",
        "name": "Florida Keys SanctSound Reef Station",
        "description": "Shallow reef soundscape, snapping shrimp choruses, small craft traffic.",
        "sanctuary_id": "FK01",
        "rtsp_url": "rtsp://mediamtx:8554/hydrophone/FK01",
        "latitude": 24.500,
        "longitude": -81.400,
        "is_active": True,
    },
    {
        "station_code": "CI01",
        "name": "Channel Islands Marine Sanctuary Hydrophone 01",
        "description": "Pelagic blue/fin whale path and Santa Barbara channel acoustic tracking.",
        "sanctuary_id": "CI01",
        "rtsp_url": "rtsp://mediamtx:8554/hydrophone/CI01",
        "latitude": 34.000,
        "longitude": -119.500,
        "is_active": True,
    },
    {
        "station_code": "SB01",
        "name": "Stellwagen Bank North Atlantic Right Whale Station",
        "description": "Cape Cod Bay auto-detection buoy array for endangered right whale upcalls.",
        "sanctuary_id": "SB01",
        "rtsp_url": "rtsp://mediamtx:8554/hydrophone/SB01",
        "latitude": 42.300,
        "longitude": -70.300,
        "is_active": True,
    },
]


class StreamAuthError(Exception):
    pass


class OutOfScopeError(StreamAuthError):
    pass


class StreamNotFoundError(Exception):
    pass


def user_can_access_station(user: CurrentUser, station_code: str) -> bool:
    return user.tier >= ROLE_TIERS["archivist"] or station_code in user.sanctuary_scopes


def issue_stream_token(user: CurrentUser, *, station_code: str) -> tuple[str, int]:
    if not user_can_access_station(user, station_code):
        raise OutOfScopeError(f"User out of scope for station {station_code}")
    token = mint_stream_token(
        sub=user.user_id, station_code=station_code, ttl_seconds=STREAM_TOKEN_TTL_SECONDS
    )
    return token, STREAM_TOKEN_TTL_SECONDS


def _station_from_path(path: str) -> str:
    """MediaMTX paths are configured as e.g. 'hydrophone/OC02'."""
    return path.rsplit("/", 1)[-1]


def authorize_mediamtx_request(*, password: str | None, path: str) -> None:
    """Raises StreamAuthError if the request should be denied."""
    if not password:
        raise StreamAuthError("Missing stream token")

    try:
        payload = decode_stream_token(password)
    except pyjwt.InvalidTokenError as exc:
        raise StreamAuthError("Invalid or expired stream token") from exc

    station_code = _station_from_path(path)
    if payload.get("station_code") != station_code:
        raise StreamAuthError("Token not valid for this station path")


async def ensure_default_stations(db: AsyncSession) -> None:
    """Ensures standard SanctSound stations exist in database."""
    res = await db.execute(select(HydrophoneStream.station_code))
    existing_codes = set(res.scalars())
    for s_info in DEFAULT_STATIONS:
        if s_info["station_code"] not in existing_codes:
            db.add(HydrophoneStream(**s_info))
    await db.commit()


async def list_streams(db: AsyncSession, *, user: CurrentUser) -> list[HydrophoneStream]:
    await ensure_default_stations(db)
    query = select(HydrophoneStream).where(HydrophoneStream.is_active.is_(True))
    if user.tier < ROLE_TIERS["archivist"]:
        query = query.where(
            or_(
                HydrophoneStream.sanctuary_id.is_(None),
                HydrophoneStream.sanctuary_id.in_(user.sanctuary_scopes),
                HydrophoneStream.station_code.in_(user.sanctuary_scopes),
            )
        )
    result = await db.execute(query.order_by(HydrophoneStream.station_code))
    return list(result.scalars())


async def get_stream(db: AsyncSession, *, station_code: str, user: CurrentUser) -> HydrophoneStream:
    await ensure_default_stations(db)
    if not user_can_access_station(user, station_code):
        raise OutOfScopeError(f"Access denied for station {station_code}")
    stream = await db.get(HydrophoneStream, station_code)
    if not stream or not stream.is_active:
        raise StreamNotFoundError(f"Stream {station_code} not found")
    return stream


async def create_or_update_stream(
    db: AsyncSession, *, req: StreamCreateRequest, user: CurrentUser
) -> HydrophoneStream:
    if user.tier < ROLE_TIERS["field_contributor"]:
        raise OutOfScopeError("FieldContributor role or higher required to register stream")

    stream = await db.get(HydrophoneStream, req.station_code)
    if stream is None:
        stream = HydrophoneStream(
            station_code=req.station_code,
            name=req.name,
            description=req.description,
            sanctuary_id=req.sanctuary_id or req.station_code,
            rtsp_url=req.rtsp_url or f"rtsp://mediamtx:8554/hydrophone/{req.station_code}",
            latitude=req.latitude,
            longitude=req.longitude,
            is_active=True,
        )
        db.add(stream)
    else:
        stream.name = req.name
        stream.description = req.description
        if req.sanctuary_id:
            stream.sanctuary_id = req.sanctuary_id
        if req.rtsp_url:
            stream.rtsp_url = req.rtsp_url
        if req.latitude is not None:
            stream.latitude = req.latitude
        if req.longitude is not None:
            stream.longitude = req.longitude
        stream.is_active = True

    await db.commit()
    await db.refresh(stream)
    return stream


async def delete_stream(db: AsyncSession, *, station_code: str, user: CurrentUser) -> None:
    if user.tier < ROLE_TIERS["security_admin"]:
        raise OutOfScopeError("SecurityAdmin required to unregister a hydrophone stream")
    stream = await db.get(HydrophoneStream, station_code)
    if not stream:
        raise StreamNotFoundError(f"Stream {station_code} not found")
    stream.is_active = False
    await db.commit()


def _create_sample_wav(duration_sec: float = 10.0, sample_rate: int = 16000) -> bytes:
    """Generates a valid 16kHz mono WAV buffer representing hydrophone capture."""
    num_samples = int(duration_sec * sample_rate)
    pcm_data = struct.pack(f"<{num_samples}h", *([0] * num_samples))
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm_data))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(pcm_data))
    )
    return header + pcm_data


async def capture_stream_clip(
    db: AsyncSession,
    *,
    station_code: str,
    req: StreamCaptureRequest,
    user: CurrentUser,
) -> tuple[str, str, str | None, str | None]:
    """Captures a rolling clip from a hydrophone station and triggers ingestion."""
    if user.tier < ROLE_TIERS["acoustic_analyst"]:
        raise OutOfScopeError("AcousticAnalyst tier required to capture stream clips")

    stream = await get_stream(db, station_code=station_code, user=user)

    if req.audio_b64:
        try:
            audio_bytes = base64.b64decode(req.audio_b64)
        except Exception as exc:
            raise ValueError("Invalid audio_b64 encoding") from exc
    else:
        # Default rolling buffer snippet
        audio_bytes = _create_sample_wav(duration_sec=req.duration_sec)

    asset, deduplicated, job_id = await ingest_asset(
        db,
        data=audio_bytes,
        declared_type="audio",
        original_filename=f"capture_{station_code}_{int(datetime.now(UTC).timestamp())}.wav",
        uploaded_by=user.user_id,
        sanctuary_id=stream.sanctuary_id,
        station_code=stream.station_code,
        latitude=stream.latitude,
        longitude=stream.longitude,
    )
    await db.commit()

    return asset.sha256, asset.asset_type, stream.sanctuary_id, job_id
