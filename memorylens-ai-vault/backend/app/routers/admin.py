"""
Admin-only endpoints: user management, RBAC roles/permissions, and simple
aggregate stats. Every route here is gated by app.auth.require_admin.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.auth import CurrentUser, hash_password, require_admin
from app.db import db_cursor
from app.services import sessions

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Permissions an admin role must keep at least one of each group of,
# otherwise every admin could lock themselves (and everyone else) out of
# the admin panel with no way back in short of editing the DB by hand.
_ADMIN_SELF_LOCKOUT_GUARD = ["users.view", "users.edit", "roles.view", "roles.edit"]


class AdminUserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    is_active: bool
    email_verified: bool
    created_at: str
    media_count: int


class AdminUsersResponse(BaseModel):
    users: list[AdminUserOut]


class AdminStatsResponse(BaseModel):
    total_users: int
    total_media: int
    total_admins: int


class SetRoleRequest(BaseModel):
    role: Literal["admin", "editor", "viewer"]


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    role: Literal["admin", "editor", "viewer"] = "editor"


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[Literal["admin", "editor", "viewer"]] = None
    is_active: Optional[bool] = None


class PermissionOut(BaseModel):
    code: str
    resource: str
    action: str
    description: Optional[str] = None


class RoleOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    is_system: bool
    user_count: int
    permissions: list[str]


class RolesResponse(BaseModel):
    roles: list[RoleOut]


class PermissionsResponse(BaseModel):
    permissions: list[PermissionOut]


class UpdateRolePermissionsRequest(BaseModel):
    permissions: list[str]


def _assert_last_admin_safe(cur, user_id: str, row_role: str) -> None:
    if row_role == "admin":
        cur.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")
        if cur.fetchone()["n"] <= 1:
            raise HTTPException(400, "At least one admin must remain")


@router.get("/users", response_model=AdminUsersResponse)
def list_users(_: CurrentUser = Depends(require_admin)) -> AdminUsersResponse:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.email, u.display_name, u.role, u.is_active, u.email_verified, u.created_at,
                   (SELECT COUNT(*) FROM media m WHERE m.user_id = u.id) AS media_count
            FROM users u
            ORDER BY u.created_at ASC
            """
        )
        rows = cur.fetchall()
    return AdminUsersResponse(
        users=[
            AdminUserOut(
                id=row["id"],
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"] or "editor",
                is_active=bool(row["is_active"]),
                email_verified=bool(row["email_verified"]),
                created_at=row["created_at"],
                media_count=row["media_count"],
            )
            for row in rows
        ]
    )


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(req: CreateUserRequest, _: CurrentUser = Depends(require_admin)) -> AdminUserOut:
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = ?", (req.email.lower(),))
        if cur.fetchone():
            raise HTTPException(409, "A user with that email already exists")
        user_id = uuid.uuid4().hex[:16]
        cur.execute(
            """
            INSERT INTO users (id, email, password_hash, display_name, role, is_active, email_verified)
            VALUES (?, ?, ?, ?, ?, 1, 1)
            """,
            (user_id, req.email.lower(), hash_password(req.password), req.display_name, req.role),
        )
    return AdminUserOut(
        id=user_id,
        email=req.email.lower(),
        display_name=req.display_name,
        role=req.role,
        is_active=True,
        email_verified=True,
        created_at="",
        media_count=0,
    )


@router.get("/stats", response_model=AdminStatsResponse)
def stats(_: CurrentUser = Depends(require_admin)) -> AdminStatsResponse:
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM users")
        total_users = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM media")
        total_media = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")
        total_admins = cur.fetchone()["n"]
    return AdminStatsResponse(total_users=total_users, total_media=total_media, total_admins=total_admins)


@router.post("/users/{user_id}/deactivate")
def deactivate_user(user_id: str, current_user: CurrentUser = Depends(require_admin)) -> dict:
    if user_id == current_user.id:
        raise HTTPException(400, "You cannot deactivate your own account")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cur.fetchone():
            raise HTTPException(404, "User not found")
        cur.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    # Every device this user is currently logged in on should be kicked out
    # immediately, not merely once its access token happens to expire.
    sessions.revoke_all_sessions_for_user(user_id)
    return {"ok": True}


@router.post("/users/{user_id}/reactivate")
def reactivate_user(user_id: str, current_user: CurrentUser = Depends(require_admin)) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cur.fetchone():
            raise HTTPException(404, "User not found")
        cur.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
    return {"ok": True}


@router.post("/users/{user_id}/role")
def set_role(user_id: str, req: SetRoleRequest, current_user: CurrentUser = Depends(require_admin)) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT id, role FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "User not found")

        if row["role"] == "admin" and req.role != "admin":
            cur.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")
            if cur.fetchone()["n"] <= 1:
                raise HTTPException(400, "At least one admin must remain")

        cur.execute("UPDATE users SET role = ? WHERE id = ?", (req.role, user_id))
    return {"ok": True}


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str, req: UpdateUserRequest, current_user: CurrentUser = Depends(require_admin)
) -> AdminUserOut:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "User not found")

        new_role = req.role if req.role is not None else row["role"]
        new_active = req.is_active if req.is_active is not None else bool(row["is_active"])
        new_name = req.display_name if req.display_name is not None else row["display_name"]

        if row["role"] == "admin" and (new_role != "admin" or not new_active):
            _assert_last_admin_safe(cur, user_id, row["role"])

        cur.execute(
            "UPDATE users SET display_name = ?, role = ?, is_active = ? WHERE id = ?",
            (new_name, new_role, 1 if new_active else 0, user_id),
        )
        cur.execute(
            """
            SELECT u.id, u.email, u.display_name, u.role, u.is_active, u.email_verified, u.created_at,
                   (SELECT COUNT(*) FROM media m WHERE m.user_id = u.id) AS media_count
            FROM users u WHERE u.id = ?
            """,
            (user_id,),
        )
        out = cur.fetchone()
    if not new_active:
        # Outside the above `with` block: that transaction must commit
        # first, since this opens its own connection and would otherwise
        # hit SQLite's write lock while the outer one is still open.
        sessions.revoke_all_sessions_for_user(user_id)
    return AdminUserOut(
        id=out["id"],
        email=out["email"],
        display_name=out["display_name"],
        role=out["role"] or "editor",
        is_active=bool(out["is_active"]),
        email_verified=bool(out["email_verified"]),
        created_at=out["created_at"],
        media_count=out["media_count"],
    )


@router.delete("/users/{user_id}")
def delete_user(user_id: str, current_user: CurrentUser = Depends(require_admin)) -> dict:
    if user_id == current_user.id:
        raise HTTPException(400, "You cannot delete your own account")
    with db_cursor() as cur:
        cur.execute("SELECT id, role FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "User not found")
        _assert_last_admin_safe(cur, user_id, row["role"])

        cur.execute("SELECT id, file_path, thumb_path FROM media WHERE user_id = ?", (user_id,))
        media_rows = cur.fetchall()
        for m in media_rows:
            cur.execute("DELETE FROM search_index WHERE media_id = ?", (m["id"],))
        cur.execute("DELETE FROM media WHERE user_id = ?", (user_id,))

    # Revoke (and SSE-notify) active sessions BEFORE deleting the user row,
    # since sessions.user_id cascades on delete -- after that the rows (and
    # any way to look them up to notify their SSE connections) are gone.
    sessions.revoke_all_sessions_for_user(user_id)

    with db_cursor() as cur:
        # otp_codes / mfa_backup_codes have ON DELETE CASCADE on user_id, so
        # deleting the user row cleans those up automatically; media has no
        # such cascade (users.id has other referrers too), hence the manual
        # delete above, mirroring media.py's delete_media file cleanup.
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))

    for m in media_rows:
        for p in (m["file_path"], m["thumb_path"]):
            if p and Path(p).exists():
                Path(p).unlink(missing_ok=True)
    return {"ok": True}


@router.get("/permissions", response_model=PermissionsResponse)
def list_permissions(_: CurrentUser = Depends(require_admin)) -> PermissionsResponse:
    with db_cursor() as cur:
        cur.execute("SELECT code, resource, action, description FROM permissions ORDER BY resource, action")
        rows = cur.fetchall()
    return PermissionsResponse(
        permissions=[
            PermissionOut(code=r["code"], resource=r["resource"], action=r["action"], description=r["description"])
            for r in rows
        ]
    )


@router.get("/roles", response_model=RolesResponse)
def list_roles(_: CurrentUser = Depends(require_admin)) -> RolesResponse:
    with db_cursor() as cur:
        cur.execute("SELECT id, name, slug, description, is_system FROM roles ORDER BY id")
        role_rows = cur.fetchall()
        roles_out = []
        for r in role_rows:
            cur.execute(
                """
                SELECT p.code FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = ?
                """,
                (r["id"],),
            )
            perms = [row["code"] for row in cur.fetchall()]
            cur.execute("SELECT COUNT(*) AS n FROM users WHERE role = ?", (r["slug"],))
            user_count = cur.fetchone()["n"]
            roles_out.append(
                RoleOut(
                    id=r["id"],
                    name=r["name"],
                    slug=r["slug"],
                    description=r["description"],
                    is_system=bool(r["is_system"]),
                    user_count=user_count,
                    permissions=perms,
                )
            )
    return RolesResponse(roles=roles_out)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role_permissions(
    role_id: int, req: UpdateRolePermissionsRequest, _: CurrentUser = Depends(require_admin)
) -> RoleOut:
    with db_cursor() as cur:
        cur.execute("SELECT id, name, slug, description, is_system FROM roles WHERE id = ?", (role_id,))
        role = cur.fetchone()
        if not role:
            raise HTTPException(404, "Role not found")

        cur.execute("SELECT id, code FROM permissions")
        all_perms = {r["code"]: r["id"] for r in cur.fetchall()}
        unknown = [c for c in req.permissions if c not in all_perms]
        if unknown:
            raise HTTPException(400, f"Unknown permission code(s): {', '.join(unknown)}")

        if role["slug"] == "admin":
            missing = [c for c in _ADMIN_SELF_LOCKOUT_GUARD if c not in req.permissions]
            if missing:
                raise HTTPException(
                    400,
                    "The admin role must keep user and role management permissions "
                    f"({', '.join(_ADMIN_SELF_LOCKOUT_GUARD)}), otherwise admins could lock "
                    "themselves out of the admin panel.",
                )

        cur.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        for code in req.permissions:
            cur.execute(
                "INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (role_id, all_perms[code]),
            )

        cur.execute("SELECT COUNT(*) AS n FROM users WHERE role = ?", (role["slug"],))
        user_count = cur.fetchone()["n"]

    return RoleOut(
        id=role["id"],
        name=role["name"],
        slug=role["slug"],
        description=role["description"],
        is_system=bool(role["is_system"]),
        user_count=user_count,
        permissions=req.permissions,
    )
