import uuid
from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    sanctuary_scopes: list[str]
    mfa_enabled: bool
    is_active: bool
    locked_until: datetime | None
    created_at: datetime


class UpdateRoleRequest(BaseModel):
    role: str
    sanctuary_scopes: list[str] | None = None


class FeatureFlagOut(BaseModel):
    flag_key: str
    enabled: bool
    allowed_roles: list[str]


class FeatureFlagUpdate(BaseModel):
    enabled: bool
    allowed_roles: list[str] = []


class AuditLogOut(BaseModel):
    id: int
    actor_user_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    outcome: str
    reason: str | None
    created_at: datetime


class PiiUnmaskRequest(BaseModel):
    resource_type: str
    resource_id: str
    reason: str
