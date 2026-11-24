"""assets, pipeline_jobs, pipeline_stage_runs

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

ASSET_TYPES = ("audio", "pdf", "docx", "xml")


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("sha256", sa.String(64), primary_key=True),
        sa.Column("asset_type", sa.String(16), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sanctuary_id", sa.String(64), nullable=True),
        sa.Column("station_code", sa.String(64), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("geo_qa_flag", sa.String(32), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(f"asset_type IN {ASSET_TYPES}", name="ck_assets_type"),
    )
    op.create_index("ix_assets_sanctuary_id", "assets", ["sanctuary_id"])

    op.create_table(
        "pipeline_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_sha256", sa.String(64), sa.ForeignKey("assets.sha256", ondelete="CASCADE")
        ),
        sa.Column("pipeline_version", sa.String(16), server_default="v1"),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("current_stage", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "pipeline_stage_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_jobs.job_id", ondelete="CASCADE"),
        ),
        sa.Column(
            "asset_sha256", sa.String(64), sa.ForeignKey("assets.sha256", ondelete="CASCADE")
        ),
        sa.Column("stage_name", sa.String(32), nullable=False),
        sa.Column("pipeline_version", sa.String(16), server_default="v1"),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("attempt_count", sa.Integer, server_default="0"),
        sa.Column("output_sha256", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "asset_sha256", "stage_name", "pipeline_version", name="uq_stage_run_idempotency"
        ),
    )


def downgrade() -> None:
    op.drop_table("pipeline_stage_runs")
    op.drop_table("pipeline_jobs")
    op.drop_table("assets")
