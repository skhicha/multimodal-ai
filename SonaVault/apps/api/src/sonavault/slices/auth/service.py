import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.config import get_settings
from sonavault.core.security.jwt import (
    mfa_challenge_token,
    mint_access_token,
    mint_refresh_token,
)
from sonavault.core.security.passwords import (
    WeakPasswordError,
    dummy_verify,
    hash_password,
    verify_password,
)
from sonavault.core.security.rate_limit import (
    clear_lockout,
    get_redis,
    is_locked_out,
    record_failed_attempt,
)
from sonavault.models.auth import User, UserSession


class AuthError(Exception):
    pass


class AccountLockedError(AuthError):
    pass


class RefreshReuseError(AuthError):
    """Raised when a refresh token presents a jti that no longer matches the
    session's current refresh_jti — i.e. it was already rotated away. This
    indicates token theft; the entire session family is revoked."""


async def register_user(session: AsyncSession, *, email: str, password: str) -> User:
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        # Do not leak existence; caller returns a generic success message either way.
        raise AuthError("duplicate")
    try:
        pw_hash = hash_password(password)
    except WeakPasswordError as exc:
        raise AuthError(str(exc)) from exc
    user = User(email=email, password_hash=pw_hash, role="viewer", sanctuary_scopes=[])
    session.add(user)
    await session.flush()
    return user


async def authenticate(
    session: AsyncSession, *, email: str, password: str
) -> tuple[User | None, str | None, bool]:
    """Returns (user, mfa_ticket, mfa_setup_required). user is None on failed
    credentials. mfa_ticket is set when password is correct but an already-
    enrolled MFA factor must still complete. mfa_setup_required is True when
    the user's role tier mandates MFA but none is enrolled yet — login still
    succeeds (a user who can never log in could never reach the enrollment
    endpoints), but the frontend must force them straight to MFA setup and
    every step-up-gated/sensitive endpoint remains unavailable until they do."""
    lockout_key = f"login:{email.lower()}"
    if await is_locked_out(lockout_key):
        raise AccountLockedError()

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or user.password_hash is None:
        dummy_verify()
        await record_failed_attempt(lockout_key)
        return None, None, False

    if not verify_password(password, user.password_hash):
        await record_failed_attempt(lockout_key)
        return None, None, False

    await clear_lockout(lockout_key)

    if user.mfa_enabled:
        methods = ["webauthn", "totp", "recovery_code"]
        ticket = mfa_challenge_token(sub=str(user.id), methods=methods)
        return user, ticket, False

    settings = get_settings()
    mfa_setup_required = (
        settings.enforce_mfa_tier_min <= _tier(user.role) or settings.enforce_mfa_all
    )
    return user, None, mfa_setup_required


def _tier(role: str) -> int:
    from sonavault.core.security.rbac import ROLE_TIERS

    return ROLE_TIERS.get(role, 0)


async def create_session(
    session: AsyncSession,
    *,
    user: User,
    ip_addr: str | None,
    user_agent: str | None,
    amr: list[str],
) -> UserSession:
    settings = get_settings()
    row = UserSession(
        user_id=user.id,
        ip_addr=ip_addr,
        user_agent=user_agent,
        amr=amr,
        mfa_verified_at=datetime.now(UTC) if "totp" in amr or "webauthn" in amr else None,
        expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days),
    )
    session.add(row)
    await session.flush()
    return row


def issue_access_token(*, user: User, sess: UserSession) -> str:
    mfa_verified_at = sess.mfa_verified_at.timestamp() if sess.mfa_verified_at else None
    return mint_access_token(
        sub=str(user.id),
        sid=str(sess.id),
        role=user.role,
        sanctuary_scopes=user.sanctuary_scopes,
        amr=sess.amr,
        mfa_verified_at=mfa_verified_at,
    )


def issue_refresh_token(*, user: User, sess: UserSession) -> str:
    return mint_refresh_token(
        sub=str(user.id),
        sid=str(sess.id),
        family_id=str(sess.family_id),
        jti=str(sess.refresh_jti),
    )


async def rotate_refresh_token(session: AsyncSession, *, payload: dict) -> tuple[User, UserSession]:
    """Validates a presented refresh token against the session store and
    rotates it. Raises RefreshReuseError (after revoking the whole family) if
    the jti does not match the session's current refresh_jti, and AuthError
    for any other invalid/expired/revoked session."""
    sid = uuid.UUID(payload["sid"])
    sess = await session.get(UserSession, sid)
    if sess is None or sess.revoked_at is not None:
        raise AuthError("session_not_found_or_revoked")
    if sess.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise AuthError("session_expired")

    if str(sess.refresh_jti) != payload["jti"]:
        await session.execute(
            update(UserSession)
            .where(UserSession.family_id == sess.family_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await session.commit()
        raise RefreshReuseError()

    user = await session.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise AuthError("user_inactive")

    sess.refresh_jti = uuid.uuid4()
    await session.flush()
    return user, sess


async def revoke_session(session: AsyncSession, *, sid: uuid.UUID, user_id: uuid.UUID) -> bool:
    sess = await session.get(UserSession, sid)
    if sess is None or sess.user_id != user_id:
        return False
    sess.revoked_at = datetime.now(UTC)
    await session.flush()
    return True


async def revoke_all_sessions(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def list_active_sessions(session: AsyncSession, *, user_id: uuid.UUID) -> list[UserSession]:
    result = await session.execute(
        select(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .order_by(UserSession.expires_at.desc())
    )
    sessions = result.scalars().all()
    now = datetime.now(UTC)
    return [s for s in sessions if s.expires_at.replace(tzinfo=UTC) >= now]


async def send_email_otp(email: str) -> tuple[str, bool]:
    """Generates a 6-digit cryptographic verification code and dispatches it
    via SMTP if configured, or stores in redis/cache with dev fallback."""
    import logging
    import secrets
    import smtplib
    from email.mime.text import MIMEText

    logger = logging.getLogger("sonavault.auth.email")
    code = f"{secrets.randbelow(900000) + 100000}"

    r = get_redis()
    await r.setex(f"sv:email_otp:{email.lower()}", 600, code)

    settings = get_settings()
    sent_via_smtp = False

    if settings.smtp_host:
        try:
            msg = MIMEText(
                f"Your SonaVault Sovereign Access Code is: {code}\n\n"
                f"Valid for 10 minutes on station {settings.public_origin}."
            )
            msg["Subject"] = f"SonaVault Security Access Code: {code}"
            msg["From"] = settings.smtp_from
            msg["To"] = email

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                if settings.smtp_tls:
                    server.starttls()
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
            sent_via_smtp = True
            logger.info("Dispatched verification email to %s via SMTP", email)
        except Exception as exc:
            logger.warning("SMTP dispatch failed (%s); falling back to in-memory logger", exc)

    logger.info("SonaVault Email Code for %s: [%s]", email, code)
    return code, sent_via_smtp


async def verify_email_otp(session: AsyncSession, *, email: str, code: str) -> User:
    """Verifies a 6-digit OTP for email login, provisioning the account if new."""
    r = get_redis()
    stored = await r.get(f"sv:email_otp:{email.lower()}")
    if not stored or str(stored).strip() != code.strip():
        raise AuthError("Invalid or expired verification code")

    await r.delete(f"sv:email_otp:{email.lower()}")

    result = await session.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=email.lower(),
            password_hash=None,
            role="acoustic_analyst",
            sanctuary_scopes=["OC02", "CI01", "MB01", "FK01", "HI01"],
            mfa_enabled=False,
            is_active=True,
        )
        session.add(user)
        await session.flush()

    return user


async def authenticate_or_provision_sso_user(
    session: AsyncSession, *, email: str, provider: str, display_name: str | None = None
) -> User:
    """Authenticates or provisions a sovereign user authenticated via OAuth2/OIDC SSO."""
    result = await session.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=email.lower(),
            password_hash=None,
            role="acoustic_analyst",
            sanctuary_scopes=["OC02", "CI01", "MB01", "FK01", "HI01"],
            mfa_enabled=False,
            is_active=True,
        )
        session.add(user)
        await session.flush()

    return user
