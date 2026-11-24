"""add metadata_json to provenance_events

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("provenance_events", sa.Column("metadata_json", postgresql.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("provenance_events", "metadata_json")
