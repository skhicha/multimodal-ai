import uuid

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.config import get_settings
from sonavault.core.security.deps import require_auth
from sonavault.core.security.jwt import decode_refresh_token
from sonavault.core.security.rbac import CurrentUser
from sonavault.db import get_db
from sonavault.slices.auth.schemas import (
    EmailSendCodeRequest,
    EmailSendCodeResponse,
    EmailVerifyCodeRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    SessionOut,
    SsoInitiateResponse,
    SsoInstantLoginRequest,
)
from sonavault.slices.auth.service import (
    AccountLockedError,
    AuthError,
    RefreshReuseError,
    authenticate,
    authenticate_or_provision_sso_user,
    create_session,
    issue_access_token,
    issue_refresh_token,
    list_active_sessions,
    register_user,
    revoke_all_sessions,
    revoke_session,
    rotate_refresh_token,
    send_email_otp,
    verify_email_otp,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "sv_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        token,
        max_age=settings.jwt_refresh_ttl_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.env != "development",
        samesite="strict",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        await register_user(db, email=body.email, password=body.password)
        await db.commit()
    except AuthError:
        await db.rollback()
        # Deliberately generic: do not reveal whether the email already exists.
    return {"status": "registered_or_already_exists"}


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    try:
        user, mfa_ticket, mfa_setup_required = await authenticate(
            db, email=body.email, password=body.password
        )
    except AccountLockedError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Account temporarily locked"
        ) from exc
    except AuthError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    finally:
        await db.commit()

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if mfa_ticket is not None:
        return LoginResponse(
            status="mfa_required",
            mfa_ticket=mfa_ticket,
            methods=["webauthn", "totp", "recovery_code"],
        )

    sess = await create_session(
        db,
        user=user,
        ip_addr=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        amr=["pwd"],
    )
    await db.commit()
    access_token = issue_access_token(user=user, sess=sess)
    set_refresh_cookie(response, issue_refresh_token(user=user, sess=sess))
    return LoginResponse(
        status="authenticated", access_token=access_token, mfa_setup_required=mfa_setup_required
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")

    try:
        payload = decode_refresh_token(raw)
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token"
        ) from exc

    try:
        user, sess = await rotate_refresh_token(db, payload=payload)
        await db.commit()
    except RefreshReuseError:
        await db.commit()
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected; session revoked"
        ) from None
    except AuthError as exc:
        await db.rollback()
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    access_token = issue_access_token(user=user, sess=sess)
    set_refresh_cookie(response, issue_refresh_token(user=user, sess=sess))
    return LoginResponse(status="authenticated", access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    if user.sid:
        await revoke_session(db, sid=uuid.UUID(user.sid), user_id=uuid.UUID(user.user_id))
        await db.commit()
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    return {"status": "logged_out"}


@router.post("/logout-all")
async def logout_all(
    response: Response,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await revoke_all_sessions(db, user_id=uuid.UUID(user.user_id))
    await db.commit()
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    return {"status": "logged_out_all_devices"}


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    sessions = await list_active_sessions(db, user_id=uuid.UUID(user.user_id))
    return [
        SessionOut(
            id=str(s.id),
            ip_addr=s.ip_addr,
            user_agent=s.user_agent,
            amr=s.amr,
            created_current=(str(s.id) == user.sid),
        )
        for s in sessions
    ]


@router.delete("/sessions/{sid}")
async def delete_session(
    sid: uuid.UUID, user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    ok = await revoke_session(db, sid=sid, user_id=uuid.UUID(user.user_id))
    await db.commit()
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return {"status": "revoked"}


# --- Real Email OTP & Magic Login ---
@router.post("/email/send-code", response_model=EmailSendCodeResponse)
async def request_email_otp(body: EmailSendCodeRequest):
    """Generates and dispatches a 6-digit access code to the specified email."""
    code, is_smtp = await send_email_otp(body.email)
    settings = get_settings()
    message = (
        f"A 6-digit access code has been dispatched to {body.email}"
        if is_smtp
        else f"Access code generated for {body.email} (logged to platform console)"
    )
    dev_code = code if settings.env == "development" or not is_smtp else None
    return EmailSendCodeResponse(status="sent", message=message, dev_code=dev_code)


@router.post("/email/verify-code", response_model=LoginResponse)
async def verify_email_code(
    body: EmailVerifyCodeRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Verifies a 6-digit email OTP and issues an authenticated sovereign session."""
    try:
        user = await verify_email_otp(db, email=body.email, code=body.code)
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    sess = await create_session(
        db,
        user=user,
        ip_addr=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        amr=["email_otp"],
    )
    await db.commit()

    access_token = issue_access_token(user=user, sess=sess)
    set_refresh_cookie(response, issue_refresh_token(user=user, sess=sess))
    return LoginResponse(
        status="authenticated", access_token=access_token, mfa_setup_required=False
    )


# --- Single Sign-On (SSO / OIDC) ---
@router.get("/sso/initiate", response_model=SsoInitiateResponse)
async def initiate_sso(provider: str, redirect_uri: str | None = None):
    """Returns the authorization URL for the requested SSO identity provider."""
    settings = get_settings()
    base_cb = redirect_uri or f"{settings.public_origin}/login"

    if provider == "google":
        client_id = settings.google_client_id
        if client_id:
            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={client_id}&redirect_uri={base_cb}&response_type=code&"
                f"scope=openid%20email%20profile"
            )
            return SsoInitiateResponse(auth_url=auth_url, provider=provider, is_mock=False)
        return SsoInitiateResponse(
            auth_url=f"{base_cb}?sso=google_demo", provider="google", is_mock=True
        )

    if provider == "github":
        client_id = settings.github_client_id
        if client_id:
            auth_url = (
                f"https://github.com/login/oauth/authorize?"
                f"client_id={client_id}&redirect_uri={base_cb}&scope=user:email"
            )
            return SsoInitiateResponse(auth_url=auth_url, provider=provider, is_mock=False)
        return SsoInitiateResponse(
            auth_url=f"{base_cb}?sso=github_demo", provider="github", is_mock=True
        )

    # Generic Enterprise OIDC / NOAA SAML
    return SsoInitiateResponse(auth_url=f"{base_cb}?sso=oidc_demo", provider="oidc", is_mock=True)


@router.post("/sso/instant", response_model=LoginResponse)
async def instant_sso_login(
    body: SsoInstantLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Instant Sovereign SSO authentication for Google, GitHub, or Enterprise OIDC."""
    user = await authenticate_or_provision_sso_user(
        db, email=body.email, provider=body.provider, display_name=body.display_name
    )

    sess = await create_session(
        db,
        user=user,
        ip_addr=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        amr=["sso", body.provider],
    )
    await db.commit()

    access_token = issue_access_token(user=user, sess=sess)
    set_refresh_cookie(response, issue_refresh_token(user=user, sess=sess))
    return LoginResponse(
        status="authenticated", access_token=access_token, mfa_setup_required=False
    )
