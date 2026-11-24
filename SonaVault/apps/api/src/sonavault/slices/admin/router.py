"""SecurityAdmin-only slice: user/role management, feature flags, audit log
search, and audited PII unmasking. Every mutating/sensitive action is
step-up-MFA gated; see service.py for the audit-logging domain logic."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.security.rbac import CurrentUser, require_min_tier, require_recent_mfa
from sonavault.db import get_db
from sonavault.slices.admin import service
from sonavault.slices.admin.schemas import (
    AuditLogOut,
    FeatureFlagOut,
    FeatureFlagUpdate,
    PiiUnmaskRequest,
    UpdateRoleRequest,
    UserOut,
)
from sonavault.slices.admin.service import (
    InsufficientTierError,
    UnknownRoleError,
    UserNotFoundError,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

_admin_only = require_min_tier("security_admin")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/users", response_model=list[UserOut])
async def get_users(user: CurrentUser = Depends(_admin_only), db: AsyncSession = Depends(get_db)):
    users = await service.list_users(db)
    return [UserOut.model_validate(u, from_attributes=True) for u in users]


@router.patch("/users/{target_id}/role")
async def update_role(
    target_id: uuid.UUID,
    body: UpdateRoleRequest,
    request: Request,
    user: CurrentUser = Depends(require_recent_mfa()),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.update_role(
            db,
            actor=user,
            target_id=target_id,
            new_role=body.role,
            sanctuary_scopes=body.sanctuary_scopes,
            ip_addr=_client_ip(request),
        )
    except InsufficientTierError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except UnknownRoleError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return {"status": "updated"}


@router.post("/users/{target_id}/unlock")
async def unlock_user(
    target_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(_admin_only),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.unlock_user(db, actor=user, target_id=target_id, ip_addr=_client_ip(request))
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return {"status": "unlocked"}


@router.get("/feature-flags", response_model=list[FeatureFlagOut])
async def get_feature_flags(
    user: CurrentUser = Depends(_admin_only), db: AsyncSession = Depends(get_db)
):
    flags = await service.list_feature_flags(db)
    return [FeatureFlagOut.model_validate(f, from_attributes=True) for f in flags]


@router.put("/feature-flags/{flag_key}", response_model=FeatureFlagOut)
async def put_feature_flag(
    flag_key: str,
    body: FeatureFlagUpdate,
    request: Request,
    user: CurrentUser = Depends(require_recent_mfa()),
    db: AsyncSession = Depends(get_db),
):
    try:
        flag = await service.update_feature_flag(
            db,
            actor=user,
            flag_key=flag_key,
            enabled=body.enabled,
            allowed_roles=body.allowed_roles,
            ip_addr=_client_ip(request),
        )
    except InsufficientTierError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return FeatureFlagOut.model_validate(flag, from_attributes=True)


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def get_audit_logs(
    action: str | None = None,
    limit: int = 100,
    user: CurrentUser = Depends(_admin_only),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.search_audit_logs(db, action=action, limit=limit)
    return [
        AuditLogOut(
            id=row.id,
            actor_user_id=str(row.actor_user_id) if row.actor_user_id else None,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            outcome=row.outcome,
            reason=row.reason,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/pii/unmask")
async def unmask_pii(
    body: PiiUnmaskRequest,
    request: Request,
    user: CurrentUser = Depends(require_recent_mfa()),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.authorize_pii_unmask(
            db,
            actor=user,
            resource_type=body.resource_type,
            resource_id=body.resource_id,
            reason=body.reason,
            ip_addr=_client_ip(request),
        )
    except InsufficientTierError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return {"status": "authorized"}
