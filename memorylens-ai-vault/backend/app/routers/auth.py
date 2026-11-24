import asyncio
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, EmailStr, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth import (
    CurrentUser,
    create_access_token,
    create_mfa_token,
    create_oauth_state_token,
    create_otp_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_refresh_session_id,
    get_refresh_user_id,
    get_user_by_id,
    hash_password,
    verify_password,
)
from app.db import db_cursor
from app.services import mailer, mfa, oauth_google, otp, sessions

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days, matches auth.REFRESH_TOKEN_DAYS

PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")

OTP_LOGIN_EXPIRE_MINUTES = 10
RESET_EXPIRE_MINUTES = 15
RESEND_COOLDOWN_SECONDS = 30
# otp_token -> last resend time, process-local. Good enough for a capstone;
# a real deployment would key this in a shared store alongside the DB.
_last_resend: dict[str, datetime] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expires_at(minutes: int) -> str:
    return (_now() + timedelta(minutes=minutes)).isoformat()


def _issue_otp_code(user_id: str, purpose: str, minutes: int) -> str:
    code = otp.generate_otp_code()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO otp_codes (user_id, code_hash, purpose, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, otp.hash_code(code), purpose, _expires_at(minutes)),
        )
    return code


def _invalidate_codes(user_id: str, purpose: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE otp_codes SET used = 1 WHERE user_id = ? AND purpose = ? AND used = 0",
            (user_id, purpose),
        )


def _verify_and_consume_code(user_id: str, purpose: str, code: str) -> bool:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, code_hash, expires_at FROM otp_codes
            WHERE user_id = ? AND purpose = ? AND used = 0
            ORDER BY id DESC
            """,
            (user_id, purpose),
        )
        rows = cur.fetchall()
        for row in rows:
            if row["expires_at"] < _now().isoformat():
                continue
            if otp.verify_code(code, row["code_hash"]):
                cur.execute("UPDATE otp_codes SET used = 1 WHERE id = ?", (row["id"],))
                return True
    return False


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not PASSWORD_RE.match(v):
            raise ValueError("Password must be at least 8 characters and include a letter and a number")
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Display name is required")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str = "editor"
    email_verified: bool = False
    otp_enabled: bool = False
    mfa_enabled: bool = False


def _user_out(row_or_user) -> "UserOut":
    """Builds UserOut from either a sqlite3.Row (has dict-style access to
    all selected columns) or an app.auth.CurrentUser -- every call site
    below was duplicating these six fields, which is exactly how the
    earlier mfa_enabled field would've been forgotten on one of them."""
    get = row_or_user.__getitem__ if hasattr(row_or_user, "keys") else None
    if get:
        return UserOut(
            id=row_or_user["id"],
            email=row_or_user["email"],
            display_name=row_or_user["display_name"],
            role=row_or_user["role"] or "editor",
            email_verified=bool(row_or_user["email_verified"]),
            otp_enabled=bool(row_or_user["otp_enabled"]),
            mfa_enabled=bool(row_or_user["mfa_enabled"]),
        )
    u = row_or_user
    return UserOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        role=u.role,
        email_verified=u.email_verified,
        otp_enabled=u.otp_enabled,
        mfa_enabled=u.mfa_enabled,
    )


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class OtpRequiredResponse(BaseModel):
    otp_required: bool = True
    otp_token: str


class OtpVerifyRequest(BaseModel):
    otp_token: str
    code: str


class OtpResendRequest(BaseModel):
    otp_token: str


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_code: str  # data: URI PNG, drop straight into an <img src>


class MfaEnableRequest(BaseModel):
    code: str


class MfaEnableResponse(BaseModel):
    backup_codes: list[str]


class MfaDisableRequest(BaseModel):
    password: str


class VerifyEmailRequest(BaseModel):
    code: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not PASSWORD_RE.match(v):
            raise ValueError("Password must be at least 8 characters and include a letter and a number")
        return v


class UpdateMeRequest(BaseModel):
    otp_enabled: bool


class GoogleStatusResponse(BaseModel):
    configured: bool


class MyPermissionsResponse(BaseModel):
    role: str
    permissions: list[str]


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=REFRESH_COOKIE_MAX_AGE,
        path="/",
    )


@router.post("/register", response_model=AuthResponse)
@limiter.limit("5/minute")
def register(req: RegisterRequest, request: Request, response: Response) -> AuthResponse:
    with db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = ?", (req.email,))
        if cur.fetchone():
            raise HTTPException(400, "An account with this email already exists")
        user_id = uuid.uuid4().hex
        cur.execute("SELECT COUNT(*) AS n FROM users")
        is_first_user = cur.fetchone()["n"] == 0
        role = "admin" if is_first_user else "editor"
        cur.execute(
            "INSERT INTO users (id, email, password_hash, display_name, role) VALUES (?, ?, ?, ?, ?)",
            (user_id, req.email, hash_password(req.password), req.display_name, role),
        )

    code = _issue_otp_code(user_id, "verify_email", RESET_EXPIRE_MINUTES * 2)
    mailer.send_email(
        req.email,
        "Verify your MemoryLens AI email",
        f"Your verification code is {code}. It expires in {RESET_EXPIRE_MINUTES * 2} minutes.",
    )

    session_id = sessions.create_session(user_id, sessions.label_from_user_agent(request.headers.get("user-agent")))
    access = create_access_token(user_id, session_id)
    refresh = create_refresh_token(user_id, session_id)
    _set_refresh_cookie(response, refresh)
    return AuthResponse(
        access_token=access,
        user=UserOut(
            id=user_id, email=req.email, display_name=req.display_name, role=role, email_verified=False, otp_enabled=False
        ),
    )


@router.post("/login", response_model=None)
@limiter.limit("5/minute")
def login(req: LoginRequest, request: Request, response: Response):
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, email, password_hash, display_name, otp_enabled, mfa_enabled, is_active, role, email_verified "
            "FROM users WHERE email = ?",
            (req.email,),
        )
        row = cur.fetchone()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    if not row["is_active"]:
        raise HTTPException(403, "Your account has been deactivated. Contact an administrator.")

    # MFA (authenticator app) takes priority over the simpler email-OTP
    # step when both are enabled -- it's the stronger factor, and stacking
    # both on one login would be unusual UX for a capstone demo.
    if row["mfa_enabled"]:
        return MfaRequiredResponse(mfa_token=create_mfa_token(row["id"]))

    if row["otp_enabled"]:
        code = _issue_otp_code(row["id"], "login", OTP_LOGIN_EXPIRE_MINUTES)
        mailer.send_email(
            row["email"],
            "Your MemoryLens AI login code",
            f"Your one-time code is {code}. It expires in {OTP_LOGIN_EXPIRE_MINUTES} minutes.",
        )
        otp_token = create_otp_token(row["id"])
        return OtpRequiredResponse(otp_token=otp_token)

    session_id = sessions.create_session(row["id"], sessions.label_from_user_agent(request.headers.get("user-agent")))
    access = create_access_token(row["id"], session_id)
    refresh = create_refresh_token(row["id"], session_id)
    _set_refresh_cookie(response, refresh)
    return AuthResponse(access_token=access, user=_user_out(row))


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    response: Response,
    user_id: str = Depends(get_refresh_user_id),
    session_id: Optional[str] = Depends(get_refresh_session_id),
) -> AuthResponse:
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User not found")
    # Rotates the refresh token's VALUE on every use (while keeping the
    # same underlying session row/id, so "active sessions" stays stable
    # per device) -- limits how useful a leaked/replayed old refresh token
    # is, since the next legitimate refresh already moved past it.
    access = create_access_token(user.id, session_id)
    new_refresh = create_refresh_token(user.id, session_id)
    _set_refresh_cookie(response, new_refresh)
    return AuthResponse(access_token=access, user=_user_out(user))


@router.post("/logout")
def logout(response: Response, session_id: Optional[str] = Depends(get_refresh_session_id)) -> dict:
    if session_id:
        sessions.revoke_session(session_id)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    return {"ok": True}


class SessionOut(BaseModel):
    id: str
    device_label: Optional[str] = None
    created_at: str
    is_current: bool


@router.get("/sessions", response_model=list[SessionOut])
def list_my_sessions(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[SessionOut]:
    rows = sessions.list_sessions(current_user.id)
    return [
        SessionOut(
            id=row["id"],
            device_label=row["device_label"],
            created_at=row["created_at"],
            is_current=row["id"] == current_user.session_id,
        )
        for row in rows
        if row["revoked_at"] is None
    ]


@router.post("/sessions/logout-others")
def logout_other_devices(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    revoked = sessions.revoke_all_sessions_for_user(current_user.id, except_session_id=current_user.session_id)
    return {"ok": True, "revoked_count": len(revoked)}


@router.post("/sse-ticket")
def issue_sse_ticket(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    """
    Mints a short-lived (~20s), single-use ticket for /api/auth/events.
    Called with a normal Authorization header, like any other endpoint --
    only the resulting ticket, never the real access token, goes into the
    SSE connection's URL (EventSource can't set custom headers, so the
    session has to be identified some other way than Authorization; a
    long-lived bearer token sitting in a URL would otherwise end up in
    browser history and server/proxy access logs for as long as it's
    valid, which this ticket avoids by being useless after one use or 20s).
    """
    return {"ticket": sessions.issue_sse_ticket(current_user.session_id)}


@router.get("/events")
async def auth_events(ticket: str) -> StreamingResponse:
    """
    Server-Sent Events stream for cross-device logout: one open connection
    per logged-in browser tab, keyed by this login's session id. The tab
    first exchanges its real access token for a one-time ticket via
    POST /sse-ticket (normal Authorization header), then opens this
    connection with that ticket -- see issue_sse_ticket() above for why.
    When this session is revoked -- by logging out on another tab/device,
    by "log out all other devices", or by an admin deactivating/deleting
    the account -- a "logout" event is pushed here immediately; see
    app/services/sessions.py.
    """
    session_id = sessions.consume_sse_ticket(ticket)
    if not session_id:
        raise HTTPException(401, "Invalid or expired connection ticket")
    if not sessions.is_session_valid(session_id):
        raise HTTPException(401, "This session has been logged out")

    async def event_stream() -> AsyncIterator[str]:
        queue = sessions.subscribe(session_id)
        try:
            yield "event: ping\ndata: connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"event: {event}\ndata: {event}\n\n"
                    if event == "logout":
                        break
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: keepalive\n\n"
        finally:
            sessions.unsubscribe(session_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser = Depends(get_current_user)) -> UserOut:
    return _user_out(current_user)


@router.get("/my-permissions", response_model=MyPermissionsResponse)
def my_permissions(current_user: CurrentUser = Depends(get_current_user)) -> MyPermissionsResponse:
    """
    Self-lookup sibling of admin.list_permissions: any authenticated user
    (not just admins) can ask what their OWN role currently grants, per the
    role_permissions table. The frontend uses this to proactively hide/
    disable controls the user's role doesn't have access to, instead of
    only finding out via a 403 after clicking.
    """
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT p.code FROM role_permissions rp
            JOIN roles r ON r.id = rp.role_id
            JOIN permissions p ON p.id = rp.permission_id
            WHERE r.slug = ?
            ORDER BY p.code
            """,
            (current_user.role,),
        )
        codes = [row["code"] for row in cur.fetchall()]
    return MyPermissionsResponse(role=current_user.role, permissions=codes)


@router.patch("/me", response_model=UserOut)
def update_me(req: UpdateMeRequest, current_user: CurrentUser = Depends(get_current_user)) -> UserOut:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE users SET otp_enabled = ? WHERE id = ?",
            (1 if req.otp_enabled else 0, current_user.id),
        )
    current_user.otp_enabled = req.otp_enabled
    return _user_out(current_user)


@router.post("/otp/verify", response_model=AuthResponse)
@limiter.limit("10/minute")
def otp_verify(req: OtpVerifyRequest, request: Request, response: Response) -> AuthResponse:
    user_id = decode_token(req.otp_token, "otp")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User not found")
    if not _verify_and_consume_code(user_id, "login", req.code):
        raise HTTPException(401, "Invalid or expired code")

    session_id = sessions.create_session(user.id, sessions.label_from_user_agent(request.headers.get("user-agent")))
    access = create_access_token(user.id, session_id)
    refresh = create_refresh_token(user.id, session_id)
    _set_refresh_cookie(response, refresh)
    return AuthResponse(
        access_token=access,
        user=_user_out(user),
    )


@router.post("/otp/resend")
@limiter.limit("10/minute")
def otp_resend(req: OtpResendRequest, request: Request) -> dict:
    user_id = decode_token(req.otp_token, "otp")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User not found")

    last = _last_resend.get(req.otp_token)
    if last and (_now() - last).total_seconds() < RESEND_COOLDOWN_SECONDS:
        raise HTTPException(429, "Please wait before requesting another code")
    _last_resend[req.otp_token] = _now()

    _invalidate_codes(user_id, "login")
    code = _issue_otp_code(user_id, "login", OTP_LOGIN_EXPIRE_MINUTES)
    mailer.send_email(
        user.email,
        "Your MemoryLens AI login code",
        f"Your one-time code is {code}. It expires in {OTP_LOGIN_EXPIRE_MINUTES} minutes.",
    )
    return {"ok": True}


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(current_user: CurrentUser = Depends(get_current_user)) -> MfaSetupResponse:
    # Generates a fresh secret every call (re-running setup before
    # confirming just replaces the pending secret -- nothing is "enabled"
    # until /mfa/enable verifies a real code against it).
    secret = mfa.generate_secret()
    with db_cursor() as cur:
        cur.execute("UPDATE users SET totp_secret = ? WHERE id = ?", (secret, current_user.id))
    uri = mfa.provisioning_uri(secret, current_user.email)
    return MfaSetupResponse(secret=secret, otpauth_uri=uri, qr_code=mfa.qr_code_data_uri(uri))


@router.post("/mfa/enable", response_model=MfaEnableResponse)
def mfa_enable(req: MfaEnableRequest, current_user: CurrentUser = Depends(get_current_user)) -> MfaEnableResponse:
    with db_cursor() as cur:
        cur.execute("SELECT totp_secret FROM users WHERE id = ?", (current_user.id,))
        row = cur.fetchone()
    if not row or not row["totp_secret"]:
        raise HTTPException(400, "Call /mfa/setup first to get a code to scan")
    if not mfa.verify_totp(row["totp_secret"], req.code):
        raise HTTPException(401, "Invalid code")

    backup_codes = mfa.generate_backup_codes()
    with db_cursor() as cur:
        cur.execute("UPDATE users SET mfa_enabled = 1 WHERE id = ?", (current_user.id,))
        cur.execute("DELETE FROM mfa_backup_codes WHERE user_id = ?", (current_user.id,))
        cur.executemany(
            "INSERT INTO mfa_backup_codes (user_id, code_hash) VALUES (?, ?)",
            [(current_user.id, mfa.hash_backup_code(c)) for c in backup_codes],
        )
    return MfaEnableResponse(backup_codes=backup_codes)


@router.post("/mfa/disable")
def mfa_disable(req: MfaDisableRequest, current_user: CurrentUser = Depends(get_current_user)) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = ?", (current_user.id,))
        row = cur.fetchone()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(401, "Incorrect password")
    with db_cursor() as cur:
        cur.execute(
            "UPDATE users SET mfa_enabled = 0, totp_secret = NULL WHERE id = ?",
            (current_user.id,),
        )
        cur.execute("DELETE FROM mfa_backup_codes WHERE user_id = ?", (current_user.id,))
    return {"ok": True}


@router.post("/mfa/verify", response_model=AuthResponse)
@limiter.limit("10/minute")
def mfa_verify(req: MfaVerifyRequest, request: Request, response: Response) -> AuthResponse:
    user_id = decode_token(req.mfa_token, "mfa")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User not found")

    with db_cursor() as cur:
        cur.execute("SELECT totp_secret FROM users WHERE id = ?", (user_id,))
        secret_row = cur.fetchone()
    secret = secret_row["totp_secret"] if secret_row else None

    ok = bool(secret) and mfa.verify_totp(secret, req.code)
    if not ok:
        # Fall back to a one-time backup code if the TOTP code didn't match.
        with db_cursor() as cur:
            cur.execute(
                "SELECT id, code_hash FROM mfa_backup_codes WHERE user_id = ? AND used = 0",
                (user_id,),
            )
            for backup_row in cur.fetchall():
                if mfa.verify_backup_code(req.code, backup_row["code_hash"]):
                    cur.execute("UPDATE mfa_backup_codes SET used = 1 WHERE id = ?", (backup_row["id"],))
                    ok = True
                    break
    if not ok:
        raise HTTPException(401, "Invalid code")

    session_id = sessions.create_session(user.id, sessions.label_from_user_agent(request.headers.get("user-agent")))
    access = create_access_token(user.id, session_id)
    refresh = create_refresh_token(user.id, session_id)
    _set_refresh_cookie(response, refresh)
    return AuthResponse(access_token=access, user=_user_out(user))


@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, current_user: CurrentUser = Depends(get_current_user)) -> dict:
    if not _verify_and_consume_code(current_user.id, "verify_email", req.code):
        raise HTTPException(401, "Invalid or expired code")
    with db_cursor() as cur:
        cur.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (current_user.id,))
    return {"ok": True}


@router.post("/resend-verification")
@limiter.limit("5/minute")
def resend_verification(request: Request, current_user: CurrentUser = Depends(get_current_user)) -> dict:
    _invalidate_codes(current_user.id, "verify_email")
    code = _issue_otp_code(current_user.id, "verify_email", RESET_EXPIRE_MINUTES * 2)
    mailer.send_email(
        current_user.email,
        "Verify your MemoryLens AI email",
        f"Your verification code is {code}. It expires in {RESET_EXPIRE_MINUTES * 2} minutes.",
    )
    return {"ok": True}


@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(req: ForgotPasswordRequest, request: Request) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT id, email FROM users WHERE email = ?", (req.email,))
        row = cur.fetchone()
    if row:
        code = _issue_otp_code(row["id"], "password_reset", RESET_EXPIRE_MINUTES)
        mailer.send_email(
            row["email"],
            "Reset your MemoryLens AI password",
            f"Your password reset code is {code}. It expires in {RESET_EXPIRE_MINUTES} minutes.",
        )
    return {"ok": True}


@router.post("/reset-password")
@limiter.limit("5/minute")
def reset_password(req: ResetPasswordRequest, request: Request) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = ?", (req.email,))
        row = cur.fetchone()
    if not row or not _verify_and_consume_code(row["id"], "password_reset", req.code):
        raise HTTPException(401, "Invalid or expired code")
    with db_cursor() as cur:
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(req.new_password), row["id"]),
        )
    # Refresh/access tokens are stateless JWTs with no server-side revocation
    # list in this codebase, so existing sessions can't be invalidated here;
    # they simply expire on their normal schedule (see app/auth.py).
    return {"ok": True}


@router.get("/google/status", response_model=GoogleStatusResponse)
def google_status() -> GoogleStatusResponse:
    return GoogleStatusResponse(configured=oauth_google.is_configured())


@router.get("/google/login")
def google_login():
    if not oauth_google.is_configured():
        # Honest, non-broken fallback: no Google Cloud credentials set up in
        # this environment. Send the user back to Login with a flag it can
        # show a clear message for, rather than erroring the redirect.
        return RedirectResponse(f"{FRONTEND_URL}/login?google_error=not_configured")
    state = create_oauth_state_token()
    return RedirectResponse(oauth_google.build_auth_url(state))


@router.get("/google/callback")
def google_callback(
    request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None
):
    if error or not code or not state:
        return RedirectResponse(f"{FRONTEND_URL}/login?google_error=denied")

    try:
        decode_token(state, "oauth_state")
    except HTTPException:
        return RedirectResponse(f"{FRONTEND_URL}/login?google_error=invalid_state")

    try:
        google_access_token = oauth_google.exchange_code(code)
        info = oauth_google.fetch_userinfo(google_access_token)
    except Exception:  # noqa: BLE001 - any Google-side failure degrades to an honest error, never a 500
        return RedirectResponse(f"{FRONTEND_URL}/login?google_error=google_failed")

    email = info.get("email")
    if not email:
        return RedirectResponse(f"{FRONTEND_URL}/login?google_error=no_email")
    google_sub = info.get("sub")
    display_name = info.get("name") or email.split("@")[0]

    with db_cursor() as cur:
        cur.execute("SELECT id, is_active FROM users WHERE google_sub = ? OR email = ?", (google_sub, email))
        row = cur.fetchone()
        if row:
            user_id = row["id"]
            if not row["is_active"]:
                return RedirectResponse(f"{FRONTEND_URL}/login?google_error=deactivated")
            # Links a pre-existing password account to this Google identity
            # the first time it's used, and confirms the email since Google
            # already verified it on its end.
            cur.execute(
                "UPDATE users SET google_sub = ?, email_verified = 1 WHERE id = ?",
                (google_sub, user_id),
            )
        else:
            user_id = uuid.uuid4().hex
            cur.execute("SELECT COUNT(*) AS n FROM users")
            is_first_user = cur.fetchone()["n"] == 0
            role = "admin" if is_first_user else "editor"
            # No password is ever set by the user for a Google-only account;
            # password_hash is NOT NULL, so a random, never-typeable value
            # fills it -- a plain password login is simply impossible for
            # this account unless its owner later sets one via "forgot
            # password", which still works normally.
            cur.execute(
                "INSERT INTO users (id, email, password_hash, display_name, role, google_sub, email_verified) "
                "VALUES (?, ?, ?, ?, ?, ?, 1)",
                (user_id, email, hash_password(uuid.uuid4().hex), display_name, role, google_sub),
            )

    session_id = sessions.create_session(user_id, sessions.label_from_user_agent(request.headers.get("user-agent")))
    access = create_access_token(user_id, session_id)
    refresh = create_refresh_token(user_id, session_id)
    redirect = RedirectResponse(f"{FRONTEND_URL}/oauth/callback?token={access}")
    _set_refresh_cookie(redirect, refresh)
    return redirect
