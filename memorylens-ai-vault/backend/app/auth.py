"""
JWT auth helpers: password hashing, token issuance/verification, and the
get_current_user FastAPI dependency used by every protected router.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, Query
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.db import db_cursor
from app.services import sessions

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    # No hardcoded fallback: a shared default secret across machines/
    # checkouts would let a JWT signed on one machine be accepted as valid
    # on another even against a completely different (e.g. freshly wiped)
    # database, since token *signature* validity and the DB-identity check
    # in get_current_user are two independent things. Fail loudly instead.
    raise RuntimeError(
        "JWT_SECRET environment variable is not set. Refusing to start with an "
        "insecure default signing secret -- set JWT_SECRET in backend/.env "
        "(generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\")."
    )
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 60
REFRESH_TOKEN_DAYS = 7
OTP_TOKEN_MINUTES = 5
OAUTH_STATE_MINUTES = 10

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_token(
    user_id: str, token_type: str, expires_delta: timedelta, session_id: Optional[str] = None
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: str, session_id: Optional[str] = None) -> str:
    return _create_token(user_id, "access", timedelta(minutes=ACCESS_TOKEN_MINUTES), session_id)


def create_refresh_token(user_id: str, session_id: Optional[str] = None) -> str:
    return _create_token(user_id, "refresh", timedelta(days=REFRESH_TOKEN_DAYS), session_id)


def create_otp_token(user_id: str) -> str:
    return _create_token(user_id, "otp", timedelta(minutes=OTP_TOKEN_MINUTES))


def create_mfa_token(user_id: str) -> str:
    # Same shape as create_otp_token but a distinct "mfa" type so it can
    # only ever be used against /api/auth/mfa/verify, never the email-OTP
    # verify endpoint, even though both are short-lived pending-login tokens.
    return _create_token(user_id, "mfa", timedelta(minutes=OTP_TOKEN_MINUTES))


def create_oauth_state_token() -> str:
    # CSRF protection for the Google OAuth redirect: a self-contained,
    # short-lived signed token used as the `state` param instead of a
    # server-side session store (this codebase has none) -- its signature
    # and expiry are all that's checked on the callback, no payload needed.
    return _create_token("google-oauth", "oauth_state", timedelta(minutes=OAUTH_STATE_MINUTES))


def decode_token_payload(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")
    if payload.get("type") != expected_type:
        raise HTTPException(401, "Invalid token type")
    if not payload.get("sub"):
        raise HTTPException(401, "Invalid token")
    return payload


def decode_token(token: str, expected_type: str) -> str:
    return decode_token_payload(token, expected_type)["sub"]


class CurrentUser:
    def __init__(
        self,
        id: str,
        email: str,
        display_name: str,
        role: str = "editor",
        email_verified: bool = False,
        otp_enabled: bool = False,
        mfa_enabled: bool = False,
        is_active: bool = True,
    ):
        self.id = id
        self.email = email
        self.display_name = display_name
        self.role = role
        self.email_verified = email_verified
        self.otp_enabled = otp_enabled
        self.mfa_enabled = mfa_enabled
        self.is_active = is_active
        self.session_id: Optional[str] = None


def get_user_by_id(user_id: str) -> Optional[CurrentUser]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, email, display_name, role, email_verified, otp_enabled, mfa_enabled, is_active "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return CurrentUser(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        role=row["role"] or "editor",
        email_verified=bool(row["email_verified"]),
        otp_enabled=bool(row["otp_enabled"]),
        mfa_enabled=bool(row["mfa_enabled"]),
        is_active=bool(row["is_active"]),
    )


def get_current_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> CurrentUser:
    # Plain <img>/<video> tags can't send an Authorization header, so media
    # byte-serving routes (thumbnail/keyframe/file) accept the same access
    # token as a `?token=` query param. Every other route only ever gets a
    # header, since the frontend's fetch wrapper always sets it.
    if authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization.split(" ", 1)[1].strip()
    elif token:
        raw_token = token
    else:
        raise HTTPException(401, "Missing or invalid access token")
    payload = decode_token_payload(raw_token, "access")
    user_id = payload["sub"]
    session_id = payload.get("sid")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User not found")
    if not user.is_active:
        # A still-valid access/refresh JWT is otherwise stateless and would
        # keep working right up to its natural expiry even after an admin
        # deactivates the account -- so every protected request re-checks
        # is_active against the DB rather than trusting the token alone.
        raise HTTPException(403, "Your account has been deactivated. Contact an administrator.")
    if not sessions.is_session_valid(session_id):
        # Logged out (or revoked by an admin) from this device specifically,
        # on another request/connection -- see app/services/sessions.py.
        raise HTTPException(401, "This session has been logged out")
    user.session_id = session_id
    return user


def get_refresh_user_id(refresh_token: Optional[str] = Cookie(None)) -> str:
    if not refresh_token:
        raise HTTPException(401, "Missing refresh token")
    payload = decode_token_payload(refresh_token, "refresh")
    user_id = payload["sub"]
    user = get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User not found")
    if not sessions.is_session_valid(payload.get("sid")):
        raise HTTPException(401, "This session has been logged out")
    return user_id


def get_refresh_session_id(refresh_token: Optional[str] = Cookie(None)) -> Optional[str]:
    """Same decode as get_refresh_user_id but returns the embedded session
    id instead, for routes (logout, refresh rotation) that need to revoke
    or rotate the specific session rather than just identify the user."""
    if not refresh_token:
        return None
    try:
        payload = decode_token_payload(refresh_token, "refresh")
    except HTTPException:
        return None
    return payload.get("sid")


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user


def has_permission(role: str, code: str) -> bool:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM role_permissions rp
            JOIN roles r ON r.id = rp.role_id
            JOIN permissions p ON p.id = rp.permission_id
            WHERE r.slug = ? AND p.code = ?
            """,
            (role, code),
        )
        return cur.fetchone() is not None


def require_permission(code: str):
    """
    FastAPI dependency factory: raises a clean 403 unless the current
    user's role currently grants `code` per the role_permissions table.
    This is the finer-grained, DB-editable sibling of require_role(); new
    code should prefer this where per-role toggling is useful, while
    existing require_role()-guarded routes keep working unchanged.
    """

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_permission(current_user.role, code):
            raise HTTPException(403, f"This action requires the '{code}' permission.")
        return current_user

    return _check


def require_role(*roles: str):
    """
    FastAPI dependency factory: raises a clean 403 unless current_user.role
    is one of `roles`. Use e.g. Depends(require_role("admin", "editor")) to
    block viewers from write endpoints while still allowing admins/editors.
    """

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                403,
                f"This action requires one of the following roles: {', '.join(roles)}. "
                f"Your role is '{current_user.role}'.",
            )
        return current_user

    return _check
