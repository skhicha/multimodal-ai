"""hydrophone_streams table (model existed but migration was never added)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hydrophone_streams",
        sa.Column("station_code", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sanctuary_id", sa.String(64), nullable=True),
        sa.Column("rtsp_url", sa.String(512), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("hydrophone_streams")
