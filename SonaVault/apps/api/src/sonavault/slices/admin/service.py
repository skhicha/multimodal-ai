"""SecurityAdmin-only domain logic: user/role management, feature flags,
audit log search, and the audited PII-unmask gateway. Every mutating/
sensitive action is written to the append-only security_audit_log."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.security.audit_log import write_audit_log
from sonavault.core.security.rbac import ROLE_TIERS, CurrentUser
from sonavault.models.audit import FeatureFlag, SecurityAuditLog
from sonavault.models.auth import User


class UserNotFoundError(Exception):
    pass


class UnknownRoleError(Exception):
    pass


class InsufficientTierError(Exception):
    pass


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars())


async def update_role(
    db: AsyncSession,
    *,
    actor: CurrentUser,
    target_id: uuid.UUID,
    new_role: str,
    sanctuary_scopes: list[str] | None,
    ip_addr: str | None,
) -> None:
    if actor.tier < ROLE_TIERS["security_admin"]:
        raise InsufficientTierError("Insufficient role tier")
    if new_role not in ROLE_TIERS:
        raise UnknownRoleError(f"Unknown role: {new_role}")

    target = await db.get(User, target_id)
    if target is None:
        raise UserNotFoundError(f"User {target_id} not found")

    previous_role = target.role
    target.role = new_role
    if sanctuary_scopes is not None:
        target.sanctuary_scopes = sanctuary_scopes

    await write_audit_log(
        db,
        actor_user_id=uuid.UUID(actor.user_id),
        action="role_change",
        outcome="success",
        resource_type="user",
        resource_id=str(target_id),
        ip_addr=ip_addr,
        reason=f"{previous_role} -> {new_role}",
    )
    await db.commit()


async def unlock_user(
    db: AsyncSession, *, actor: CurrentUser, target_id: uuid.UUID, ip_addr: str | None
) -> None:
    target = await db.get(User, target_id)
    if target is None:
        raise UserNotFoundError(f"User {target_id} not found")
    target.locked_until = None
    target.failed_login_count = 0

    await write_audit_log(
        db,
        actor_user_id=uuid.UUID(actor.user_id),
        action="account_unlock",
        outcome="success",
        resource_type="user",
        resource_id=str(target_id),
        ip_addr=ip_addr,
    )
    await db.commit()


async def list_feature_flags(db: AsyncSession) -> list[FeatureFlag]:
    result = await db.execute(select(FeatureFlag))
    return list(result.scalars())


async def update_feature_flag(
    db: AsyncSession,
    *,
    actor: CurrentUser,
    flag_key: str,
    enabled: bool,
    allowed_roles: list[str],
    ip_addr: str | None,
) -> FeatureFlag:
    if actor.tier < ROLE_TIERS["security_admin"]:
        raise InsufficientTierError("Insufficient role tier")

    flag = await db.get(FeatureFlag, flag_key)
    if flag is None:
        flag = FeatureFlag(flag_key=flag_key)
        db.add(flag)
    flag.enabled = enabled
    flag.allowed_roles = allowed_roles

    await write_audit_log(
        db,
        actor_user_id=uuid.UUID(actor.user_id),
        action="feature_flag_update",
        outcome="success",
        resource_type="feature_flag",
        resource_id=flag_key,
        ip_addr=ip_addr,
    )
    await db.commit()
    return flag


async def search_audit_logs(
    db: AsyncSession, *, action: str | None, limit: int
) -> list[SecurityAuditLog]:
    query = (
        select(SecurityAuditLog).order_by(SecurityAuditLog.created_at.desc()).limit(min(limit, 500))
    )
    if action:
        query = query.where(SecurityAuditLog.action == action)
    result = await db.execute(query)
    return list(result.scalars())


async def authorize_pii_unmask(
    db: AsyncSession,
    *,
    actor: CurrentUser,
    resource_type: str,
    resource_id: str,
    reason: str,
    ip_addr: str | None,
) -> None:
    """Decryption of the actual PII field happens in the owning slice
    (acoustics/documents/ingest); this is the mandatory audited gateway every
    such decryption must call through first (Archivist+, step-up MFA, reason
    required)."""
    if actor.tier < ROLE_TIERS["archivist"]:
        raise InsufficientTierError("Insufficient role tier")

    await write_audit_log(
        db,
        actor_user_id=uuid.UUID(actor.user_id),
        action="pii_unmask",
        outcome="success",
        resource_type=resource_type,
        resource_id=resource_id,
        ip_addr=ip_addr,
        reason=reason,
    )
    await db.commit()
