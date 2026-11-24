"""initial schema: users, mfa, sessions, audit, feature flags, provenance

Revision ID: 0001
Revises:
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

ROLES = ("viewer", "field_contributor", "acoustic_analyst", "archivist", "security_admin")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("sanctuary_scopes", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("mfa_enabled", sa.Boolean, server_default=sa.false()),
        sa.Column("failed_login_count", sa.Integer, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(f"role IN {ROLES}", name="ck_users_role"),
    )

    op.create_table(
        "user_mfa_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")
        ),
        sa.Column("method_type", sa.String(16), server_default="totp"),
        sa.Column("secret_enc", sa.LargeBinary, nullable=False),
        sa.Column("last_used_step", sa.BigInteger, nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "webauthn_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")
        ),
        sa.Column("credential_id", sa.LargeBinary, nullable=False, unique=True),
        sa.Column("public_key", sa.LargeBinary, nullable=False),
        sa.Column("sign_count", sa.Integer, server_default="0"),
        sa.Column("transports", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("device_name", sa.String(128), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("sign_count >= 0", name="ck_webauthn_sign_count_nonneg"),
    )

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")
        ),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")
        ),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_jti", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_addr", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("amr", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_sessions_family_id", "user_sessions", ["family_id"])

    op.create_table(
        "security_audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("ip_addr", sa.String(64), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "feature_flags",
        sa.Column("flag_key", sa.String(64), primary_key=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.false()),
        sa.Column("allowed_roles", postgresql.ARRAY(sa.String), server_default="{}"),
    )

    op.create_table(
        "provenance_events",
        sa.Column("event_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("object_sha256", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("prev_event_hash", sa.String(64), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_provenance_events_object_sha256", "provenance_events", ["object_sha256"])


def downgrade() -> None:
    op.drop_table("provenance_events")
    op.drop_table("feature_flags")
    op.drop_table("security_audit_logs")
    op.drop_table("user_sessions")
    op.drop_table("mfa_recovery_codes")
    op.drop_table("webauthn_credentials")
    op.drop_table("user_mfa_methods")
    op.drop_table("users")
