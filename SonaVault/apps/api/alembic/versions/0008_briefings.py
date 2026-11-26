"""briefings table (model existed but migration was never added)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "briefings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("sanctuary_scope", sa.String(64), nullable=True),
        sa.Column("markdown_body", sa.Text, nullable=False),
        sa.Column("cited_sha256s", sa.JSON, server_default="[]"),
        sa.Column("model_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_briefings_user_id", "briefings", ["user_id"])


def downgrade() -> None:
    op.drop_table("briefings")
