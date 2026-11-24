import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.adapters.sidecars import nlp_client
from sonavault.adapters.storage.json_cache import write_projection
from sonavault.core.assets.scoping import get_scoped_asset
from sonavault.core.security.rbac import CurrentUser
from sonavault.models.acoustics import TranscriptSegment


class SegmentNotFoundError(Exception):
    pass


async def list_segments(db: AsyncSession, *, sha256: str) -> list[TranscriptSegment]:
    result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.asset_sha256 == sha256)
        .order_by(TranscriptSegment.seg_index)
    )
    return list(result.scalars())


async def get_transcript(
    db: AsyncSession, *, sha256: str, user: CurrentUser
) -> list[TranscriptSegment]:
    await get_scoped_asset(db, sha256=sha256, user=user)
    return await list_segments(db, sha256=sha256)


async def translate_transcript(
    db: AsyncSession, *, sha256: str, user: CurrentUser, target_lang: str
) -> list[TranscriptSegment]:
    await get_scoped_asset(db, sha256=sha256, user=user)
    segments = await list_segments(db, sha256=sha256)

    for seg in segments:
        translations = seg.translations_json or {}
        if target_lang not in translations:
            result = await nlp_client.translate(seg.text_redacted, target_lang=target_lang)
            translations[target_lang] = result.translated_text
            seg.translations_json = translations

    await db.commit()
    return await list_segments(db, sha256=sha256)


async def edit_segment(
    db: AsyncSession,
    *,
    sha256: str,
    seg_id: uuid.UUID,
    user: CurrentUser,
    text_redacted: str | None,
    speaker_label: str | None,
) -> TranscriptSegment:
    """Human-in-the-loop correction of a transcript segment. Invalidates the
    Atomic JSON Write Cache projection for this asset so the next read
    rebuilds it from the corrected database rows."""
    await get_scoped_asset(db, sha256=sha256, user=user)
    segment = await db.get(TranscriptSegment, seg_id)
    if segment is None or segment.asset_sha256 != sha256:
        raise SegmentNotFoundError(f"Segment {seg_id} not found on asset {sha256}")

    if text_redacted is not None:
        segment.text_redacted = text_redacted
    if speaker_label is not None:
        segment.speaker_label = speaker_label
    segment.is_hitl_override = True

    await db.commit()

    # Invalidate cache: write a fresh (now-stale-until-next-build) marker so
    # downstream readers don't serve pre-edit data from the projection cache.
    write_projection(asset_sha256=sha256, view="transcript_dirty", payload={"dirty": True})

    return segment
