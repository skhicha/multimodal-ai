import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from sonavault.db import Base


class TranscriptSegment(Base):
    """Deterministic Qdrant point ID =
    UUIDv5(NS, f"{asset_sha256}:{seg_index}:{model_version}") so re-indexing
    the same (asset, segment, model) overwrites rather than duplicates."""

    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_sha256: Mapped[str] = mapped_column(ForeignKey("assets.sha256", ondelete="CASCADE"))
    seg_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_sec: Mapped[float] = mapped_column(Float, nullable=False)
    end_sec: Mapped[float] = mapped_column(Float, nullable=False)
    speaker_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_lang: Mapped[str | None] = mapped_column(String(8), nullable=True)
    text_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    translations_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    entities_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), default="v1")
    is_hitl_override: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AcousticEvent(Base):
    __tablename__ = "acoustic_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_sha256: Mapped[str] = mapped_column(ForeignKey("assets.sha256", ondelete="CASCADE"))
    window_start_sec: Mapped[float] = mapped_column(Float, nullable=False)
    window_end_sec: Mapped[float] = mapped_column(Float, nullable=False)
    audioset_label: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    spl_db_broadband: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_hitl_override: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
