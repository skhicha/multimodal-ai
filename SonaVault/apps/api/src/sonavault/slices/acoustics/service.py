import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.assets.scoping import get_scoped_asset
from sonavault.core.security.rbac import CurrentUser
from sonavault.models.acoustics import AcousticEvent


class EventNotFoundError(Exception):
    pass


async def list_events(db: AsyncSession, *, sha256: str, user: CurrentUser) -> list[AcousticEvent]:
    await get_scoped_asset(db, sha256=sha256, user=user)
    result = await db.execute(
        select(AcousticEvent)
        .where(AcousticEvent.asset_sha256 == sha256)
        .order_by(AcousticEvent.window_start_sec)
    )
    return list(result.scalars())


async def get_spl_timeline(db: AsyncSession, *, sha256: str, user: CurrentUser) -> list[float]:
    await get_scoped_asset(db, sha256=sha256, user=user)
    result = await db.execute(
        select(AcousticEvent.spl_db_broadband)
        .where(AcousticEvent.asset_sha256 == sha256, AcousticEvent.spl_db_broadband.is_not(None))
        .order_by(AcousticEvent.window_start_sec)
    )
    return [row[0] for row in result.all()]


async def edit_event(
    db: AsyncSession,
    *,
    sha256: str,
    event_id: uuid.UUID,
    user: CurrentUser,
    audioset_label: str | None,
    confidence: float | None,
) -> AcousticEvent:
    await get_scoped_asset(db, sha256=sha256, user=user)
    event = await db.get(AcousticEvent, event_id)
    if event is None or event.asset_sha256 != sha256:
        raise EventNotFoundError(f"Event {event_id} not found on asset {sha256}")

    if audioset_label is not None:
        event.audioset_label = audioset_label
    if confidence is not None:
        event.confidence = confidence
    event.is_hitl_override = True

    await db.commit()
    return event
