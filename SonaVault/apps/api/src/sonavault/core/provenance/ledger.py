"""OAIS/PREMIS-inspired append-only, hash-chained provenance ledger.

Every ingest/transform/HITL-edit/export event is written here. Each event's
event_hash = SHA256(prev_event_hash || canonical_json(event_fields)), forming
a tamper-evident chain per object (object_sha256). The database additionally
enforces immutability via BEFORE UPDATE OR DELETE triggers on
provenance_events (see alembic migration) — this module is defense-in-depth,
not the sole guarantee.

`created_at` is deliberately excluded from the hashed fields: chain order is
already fully determined by prev_event_hash linkage, and a DateTime column's
value is not guaranteed to round-trip byte-for-byte through every dialect
(SQLite returns naive datetimes, Postgres TIMESTAMPTZ returns aware ones, and
serialization/offset formatting can differ) — hashing it would make
verification fragile across database backends for no integrity benefit.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.models.provenance import ProvenanceEvent

GENESIS_HASH = "0" * 64


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_event_hash(*, prev_event_hash: str, event_fields: dict) -> str:
    digest_input = prev_event_hash + _canonical_json(event_fields)
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


@dataclass
class NewEvent:
    object_sha256: str
    event_type: str
    agent_id: str
    payload_sha256: str
    metadata: dict | None = None


async def append_event(session: AsyncSession, event: NewEvent) -> ProvenanceEvent:
    result = await session.execute(
        select(ProvenanceEvent)
        .where(ProvenanceEvent.object_sha256 == event.object_sha256)
        .order_by(ProvenanceEvent.created_at.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    prev_hash = last.event_hash if last else GENESIS_HASH

    event_fields = {
        "object_sha256": event.object_sha256,
        "event_type": event.event_type,
        "agent_id": event.agent_id,
        "payload_sha256": event.payload_sha256,
    }
    event_hash = compute_event_hash(prev_event_hash=prev_hash, event_fields=event_fields)

    row = ProvenanceEvent(
        event_uuid=uuid.uuid4(),
        object_sha256=event.object_sha256,
        event_type=event.event_type,
        agent_id=event.agent_id,
        payload_sha256=event.payload_sha256,
        prev_event_hash=prev_hash,
        event_hash=event_hash,
        metadata_json=event.metadata,
    )
    session.add(row)
    await session.flush()
    return row


async def verify_chain(session: AsyncSession, object_sha256: str) -> tuple[bool, str | None]:
    """Replays the chain for one object and confirms every event_hash matches
    its recomputation. Returns (is_valid, first_broken_event_uuid)."""
    result = await session.execute(
        select(ProvenanceEvent)
        .where(ProvenanceEvent.object_sha256 == object_sha256)
        .order_by(ProvenanceEvent.created_at.asc())
    )
    events = result.scalars().all()
    prev_hash = GENESIS_HASH
    for ev in events:
        if ev.prev_event_hash != prev_hash:
            return False, str(ev.event_uuid)
        expected = compute_event_hash(
            prev_event_hash=prev_hash,
            event_fields={
                "object_sha256": ev.object_sha256,
                "event_type": ev.event_type,
                "agent_id": ev.agent_id,
                "payload_sha256": ev.payload_sha256,
            },
        )
        if expected != ev.event_hash:
            return False, str(ev.event_uuid)
        prev_hash = ev.event_hash
    return True, None
