import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from sonavault.db import Base

STAGE_NAMES = (
    "ingest",
    "preprocess",
    "speech",
    "acoustic",
    "nlp",
    "index",
    "seal",
)


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_sha256: Mapped[str] = mapped_column(ForeignKey("assets.sha256", ondelete="CASCADE"))
    pipeline_version: Mapped[str] = mapped_column(String(16), default="v1")
    status: Mapped[str] = mapped_column(
        String(16), default="pending"
    )  # pending|running|succeeded|failed
    current_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PipelineStageRun(Base):
    __tablename__ = "pipeline_stage_runs"
    __table_args__ = (
        UniqueConstraint(
            "asset_sha256", "stage_name", "pipeline_version", name="uq_stage_run_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_jobs.job_id", ondelete="CASCADE")
    )
    asset_sha256: Mapped[str] = mapped_column(ForeignKey("assets.sha256", ondelete="CASCADE"))
    stage_name: Mapped[str] = mapped_column(String(32), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(16), default="v1")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    output_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
