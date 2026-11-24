"""Writer for the append-only security_audit_logs table (auth events, MFA
failures, RBAC denials, role changes, PII unmasking). Append-only is enforced
at the database layer by a trigger; this module only ever INSERTs."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.models.audit import SecurityAuditLog


async def write_audit_log(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    outcome: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_addr: str | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> SecurityAuditLog:
    row = SecurityAuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_addr=ip_addr,
        outcome=outcome,
        reason=reason,
        metadata_json=metadata,
    )
    session.add(row)
    await session.flush()
    return row
