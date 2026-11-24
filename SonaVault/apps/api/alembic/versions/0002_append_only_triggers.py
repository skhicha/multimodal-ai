"""append-only triggers on security_audit_logs & provenance_events

Tamper-evident audit: PostgreSQL BEFORE UPDATE OR DELETE triggers raise
exceptions, making both tables append-only at the database layer regardless
of application-level bugs or a compromised API credential.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION sv_reject_update_or_delete() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only: % not permitted', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_FUNCTION_SQL)
    for table in ("security_audit_logs", "provenance_events"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION sv_reject_update_or_delete();
            """
        )


def downgrade() -> None:
    for table in ("security_audit_logs", "provenance_events"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table};")
    op.execute("DROP FUNCTION IF EXISTS sv_reject_update_or_delete();")
