"""fix users.sanctuary_scopes column type to match ORM (JSON, not ARRAY)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN sanctuary_scopes DROP DEFAULT")
    op.execute(
        "ALTER TABLE users ALTER COLUMN sanctuary_scopes TYPE JSON USING to_json(sanctuary_scopes)"
    )
    op.execute("ALTER TABLE users ALTER COLUMN sanctuary_scopes SET DEFAULT '[]'")


def downgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN sanctuary_scopes DROP DEFAULT")
    op.execute(
        "ALTER TABLE users ALTER COLUMN sanctuary_scopes TYPE VARCHAR[] "
        "USING array(SELECT json_array_elements_text(sanctuary_scopes))"
    )
    op.execute("ALTER TABLE users ALTER COLUMN sanctuary_scopes SET DEFAULT '{}'")
