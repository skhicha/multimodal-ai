import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from sonavault.db import Base


class ProvenanceEvent(Base):
    """Append-only (BEFORE UPDATE OR DELETE trigger). See
    sonavault.core.provenance.ledger for hash-chain semantics.

    `metadata_json` is supplementary context (e.g. original filename,
    geo-QA flag) and is deliberately excluded from the event_hash
    computation: it's informational, not part of the integrity chain."""

    __tablename__ = "provenance_events"

    event_uuid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    object_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
