import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from sonavault.db import Base

# Plain Integer on SQLite (gets rowid-alias autoincrement; BigInteger PKs do
# not), BigInteger on Postgres (production) for the full 64-bit key space.
_BigIntPk = BigInteger().with_variant(Integer(), "sqlite")


class SecurityAuditLog(Base):
    """Append-only (enforced by a BEFORE UPDATE OR DELETE trigger, see
    alembic migration 0002_append_only_triggers)."""

    __tablename__ = "security_audit_logs"

    id: Mapped[int] = mapped_column(_BigIntPk, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_addr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)  # success | failure
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    flag_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
