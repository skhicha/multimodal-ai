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
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    SessionOut,
)
from sonavault.slices.auth.service import (
    AccountLockedError,
    AuthError,
    RefreshReuseError,
    authenticate,
    create_session,
    issue_access_token,
    issue_refresh_token,
    list_active_sessions,
    register_user,
    revoke_all_sessions,
    revoke_session,
    rotate_refresh_token,
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
