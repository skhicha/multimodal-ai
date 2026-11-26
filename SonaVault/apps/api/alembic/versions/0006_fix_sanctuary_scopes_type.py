"""fix string-array columns to match ORM (JSON, not postgresql.ARRAY)

The ORM models declare these as JSON (Mapped[list[str]] = mapped_column(JSON, ...))
but 0001 created them as postgresql ARRAY(String), causing asyncpg
"is of type character varying[] but expression is of type json" errors on
every insert (register, login, webauthn registration, feature flag admin).

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

_COLUMNS = [
    ("users", "sanctuary_scopes"),
    ("webauthn_credentials", "transports"),
    ("user_sessions", "amr"),
    ("feature_flags", "allowed_roles"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE JSON USING to_json({column})"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT '[]'")


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR[] "
            f"USING array(SELECT json_array_elements_text({column}))"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT '{{}}'")
