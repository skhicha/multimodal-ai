"""Role, sanctuary-scope, ownership & step-up MFA guards.

5-tier RBAC: Viewer(1) < FieldContributor(2) < AcousticAnalyst(3) < Archivist(4)
< SecurityAdmin(5). Every protected endpoint composes role-tier + sanctuary
scope + (optionally) step-up MFA recency via FastAPI dependencies, all
chained on top of `deps.require_auth` (the Bearer-token decoder).
"""

import time
from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from sonavault.core.security.current_user import ROLE_TIERS, CurrentUser
from sonavault.core.security.deps import require_auth

__all__ = [
    "ROLE_TIERS",
    "CurrentUser",
    "require_min_tier",
    "require_sanctuary_scope",
    "require_recent_mfa",
]

STEP_UP_MAX_AGE_SECONDS = 300


def require_min_tier(min_role: str) -> Callable[[CurrentUser], CurrentUser]:
    min_tier = ROLE_TIERS[min_role]

    def _dep(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
        if user.tier < min_tier:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role tier")
        return user

    return _dep


def require_sanctuary_scope(sanctuary_id: str) -> Callable[[CurrentUser], CurrentUser]:
    def _dep(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
        if user.tier >= ROLE_TIERS["archivist"]:
            return user  # Archivist/SecurityAdmin see all sanctuaries
        if sanctuary_id not in user.sanctuary_scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Out of sanctuary scope")
        return user

    return _dep


def require_recent_mfa(max_age_seconds: int = STEP_UP_MAX_AGE_SECONDS):
    """Dependency for critical actions (unmasking PII, role changes, session
    revocation, key rotation, unredacted exports). Returns 403 STEP_UP_REQUIRED
    if mfa_verified_at is stale."""

    def _dep(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
        if user.mfa_verified_at is None or (time.time() - user.mfa_verified_at) > max_age_seconds:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"code": "STEP_UP_REQUIRED"},
            )
        return user

    return _dep
