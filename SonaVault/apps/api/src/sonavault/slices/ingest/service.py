"""Chunked-upload-ready ingest: magic-byte verification, SHA-256 dedup,
content-addressed blob storage, geospatial QA, and provenance logging.

Upload validation deliberately checks true file magic bytes rather than
trusting the client-supplied Content-Type or file extension — a core web
security control (prevents e.g. an .exe renamed to .wav from being stored
and later served as audio).
"""

import hashlib
import uuid

import magic
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.adapters.storage import blob_nvme
from sonavault.core.assets.scoping import get_scoped_asset
from sonavault.core.provenance.ledger import NewEvent, append_event
from sonavault.core.security.rbac import ROLE_TIERS, CurrentUser
from sonavault.models.assets import Asset
from sonavault.models.pipeline import PipelineJob
from sonavault.slices.ingest.geo_qa import check_coordinates

ALLOWED_MIME_BY_TYPE: dict[str, set[str]] = {
    "audio": {"audio/x-wav", "audio/wav", "audio/x-flac", "audio/flac", "audio/mpeg", "audio/ogg"},
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",  # docx is a zip; some libmagic builds can't see inside it
    },
    "xml": {"application/xml", "text/xml"},
}

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB


class UploadValidationError(ValueError):
    pass


def detect_asset_type(data: bytes, *, declared_type: str) -> str:
    if declared_type not in ALLOWED_MIME_BY_TYPE:
        raise UploadValidationError(f"Unsupported asset_type: {declared_type}")

    mime = magic.from_buffer(data[:4096], mime=True)
    allowed = ALLOWED_MIME_BY_TYPE[declared_type]
    if mime not in allowed:
        raise UploadValidationError(
            f"File content ({mime}) does not match declared type {declared_type}"
        )
    return mime


async def ingest_asset(
    session: AsyncSession,
    *,
    data: bytes,
    declared_type: str,
    original_filename: str | None,
    uploaded_by: str | None,
    sanctuary_id: str | None = None,
    station_code: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[Asset, bool, str | None]:
    if len(data) == 0:
        raise UploadValidationError("Empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadValidationError("Upload exceeds maximum allowed size")

    mime = detect_asset_type(data, declared_type=declared_type)
    sha256 = hashlib.sha256(data).hexdigest()

    existing = await session.get(Asset, sha256)
    if existing is not None:
        return existing, True, None  # content-addressed dedup: identical bytes already ingested

    blob_nvme.put(data)

    geo_qa_flag = None
    if latitude is not None and longitude is not None:
        geo_qa_flag = check_coordinates(
            latitude=latitude, longitude=longitude, station_code=station_code
        ).flag

    asset = Asset(
        sha256=sha256,
        asset_type=declared_type,
        original_filename=original_filename,
        mime_type=mime,
        size_bytes=len(data),
        sanctuary_id=sanctuary_id,
        station_code=station_code,
        latitude=latitude,
        longitude=longitude,
        geo_qa_flag=geo_qa_flag,
        uploaded_by=uuid.UUID(uploaded_by) if uploaded_by else None,
    )
    session.add(asset)
    await session.flush()

    await append_event(
        session,
        NewEvent(
            object_sha256=sha256,
            event_type="ingest",
            agent_id=uploaded_by or "anonymous",
            payload_sha256=sha256,
            metadata={"original_filename": original_filename, "geo_qa_flag": geo_qa_flag},
        ),
    )

    job = PipelineJob(asset_sha256=sha256)
    session.add(job)
    await session.flush()

    return asset, False, str(job.job_id)


async def list_assets(
    session: AsyncSession, *, user: CurrentUser, asset_type: str | None, limit: int
) -> list[Asset]:
    query = select(Asset).order_by(Asset.created_at.desc()).limit(min(limit, 500))
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    if user.tier < ROLE_TIERS["archivist"]:
        # Always see unscoped assets, plus any within the user's own
        # sanctuary scopes.
        query = query.where(
            or_(Asset.sanctuary_id.is_(None), Asset.sanctuary_id.in_(user.sanctuary_scopes))
        )
    result = await session.execute(query)
    return list(result.scalars())


async def get_asset(session: AsyncSession, *, sha256: str, user: CurrentUser) -> Asset:
    return await get_scoped_asset(session, sha256=sha256, user=user)
