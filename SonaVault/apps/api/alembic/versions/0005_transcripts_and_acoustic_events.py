"""transcript_segments, acoustic_events

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transcript_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_sha256", sa.String(64), sa.ForeignKey("assets.sha256", ondelete="CASCADE")
        ),
        sa.Column("seg_index", sa.Integer, nullable=False),
        sa.Column("start_sec", sa.Float, nullable=False),
        sa.Column("end_sec", sa.Float, nullable=False),
        sa.Column("speaker_label", sa.String(32), nullable=True),
        sa.Column("source_lang", sa.String(8), nullable=True),
        sa.Column("text_redacted", sa.Text, nullable=False),
        sa.Column("translations_json", postgresql.JSONB, nullable=True),
        sa.Column("entities_json", postgresql.JSONB, nullable=True),
        sa.Column("model_version", sa.String(32), server_default="v1"),
        sa.Column("is_hitl_override", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_transcript_segments_asset_sha256", "transcript_segments", ["asset_sha256"])

    op.create_table(
        "acoustic_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_sha256", sa.String(64), sa.ForeignKey("assets.sha256", ondelete="CASCADE")
        ),
        sa.Column("window_start_sec", sa.Float, nullable=False),
        sa.Column("window_end_sec", sa.Float, nullable=False),
        sa.Column("audioset_label", sa.String(128), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("spl_db_broadband", sa.Float, nullable=True),
        sa.Column("is_hitl_override", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_acoustic_events_asset_sha256", "acoustic_events", ["asset_sha256"])


def downgrade() -> None:
    op.drop_table("acoustic_events")
    op.drop_table("transcript_segments")
