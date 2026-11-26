"""MFA domain logic: TOTP enrollment/verification, WebAuthn passkeys, and
recovery codes.

TOTP/WebAuthn *enrollment* happens inside an authenticated session (the user
is already logged in via password, possibly without MFA yet). The mfa_ticket
(issued by POST /auth/login when mfa_enabled is already true) is only used by
the *verification* functions to complete a login that is still pending its
second factor.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt as pyjwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn.helpers import (
    parse_authentication_credential_json,
    parse_registration_credential_json,
)
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse

from sonavault.core.security import mfa_webauthn
from sonavault.core.security.jwt import decode_mfa_challenge_token
from sonavault.core.security.mfa_totp import decrypt_secret, encrypt_secret, generate_secret
from sonavault.core.security.mfa_totp import provisioning_uri as totp_provisioning_uri
from sonavault.core.security.mfa_totp import verify_code as verify_totp_code
from sonavault.core.security.rate_limit import is_locked_out, record_failed_attempt
from sonavault.core.security.rbac import CurrentUser
from sonavault.core.security.recovery_codes import generate_codes, hash_code
from sonavault.core.security.recovery_codes import verify_code as verify_recovery_code
from sonavault.models.auth import MfaRecoveryCode, User, UserMfaMethod, WebAuthnCredential
from sonavault.slices.auth.service import create_session, issue_access_token, issue_refresh_token


class MfaError(Exception):
    pass


class UserNotFoundError(MfaError):
    pass


class NoPendingEnrollmentError(MfaError):
    pass


class InvalidCodeError(MfaError):
    pass


class ChallengeExpiredError(MfaError):
    pass


class InvalidWebAuthnResponseError(MfaError):
    pass


class CredentialNotFoundError(MfaError):
    pass


class InvalidTicketError(MfaError):
    pass


class LockedOutError(MfaError):
    pass


class VerificationFailedError(MfaError):
    pass


async def _issue_recovery_codes(db: AsyncSession, *, user_id: uuid.UUID) -> list[str]:
    # Replace any still-unused codes from a prior enrollment/regeneration.
    result = await db.execute(
        select(MfaRecoveryCode).where(
            MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.used_at.is_(None)
        )
    )
    for row in result.scalars():
        await db.delete(row)
    codes = generate_codes()
    for code in codes:
        db.add(MfaRecoveryCode(user_id=user_id, code_hash=hash_code(code)))
    return codes


async def _has_recovery_codes(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


@dataclass
class TotpEnrollment:
    secret: str
    provisioning_uri: str


async def enroll_totp(db: AsyncSession, *, user: CurrentUser) -> TotpEnrollment:
    user_id = uuid.UUID(user.user_id)
    db_user = await db.get(User, user_id)
    if db_user is None:
        raise UserNotFoundError(f"User {user_id} not found")

    secret = generate_secret()
    db.add(
        UserMfaMethod(
            user_id=db_user.id,
            method_type="totp",
            secret_enc=encrypt_secret(secret, user_id=str(db_user.id)),
        )
    )
    await db.commit()
    return TotpEnrollment(
        secret=secret, provisioning_uri=totp_provisioning_uri(secret=secret, email=db_user.email)
    )


async def confirm_totp(db: AsyncSession, *, user: CurrentUser, code: str) -> list[str]:
    user_id = uuid.UUID(user.user_id)
    result = await db.execute(
        select(UserMfaMethod).where(
            UserMfaMethod.user_id == user_id,
            UserMfaMethod.method_type == "totp",
            UserMfaMethod.confirmed_at.is_(None),
        )
    )
    method = result.scalars().first()
    if method is None:
        raise NoPendingEnrollmentError("No pending TOTP enrollment")

    secret = decrypt_secret(method.secret_enc, user_id=str(user_id))
    ok, step = verify_totp_code(secret=secret, code=code, last_used_step=method.last_used_step)
    if not ok:
        raise InvalidCodeError("Invalid or replayed code")

    method.last_used_step = step
    method.confirmed_at = datetime.now(UTC)

    db_user = await db.get(User, user_id)
    if db_user is None:
        raise UserNotFoundError(f"User {user_id} not found")
    db_user.mfa_enabled = True

    codes = await _issue_recovery_codes(db, user_id=user_id)
    await db.commit()
    return codes


async def regenerate_recovery_codes(db: AsyncSession, *, user: CurrentUser) -> list[str]:
    codes = await _issue_recovery_codes(db, user_id=uuid.UUID(user.user_id))
    await db.commit()
    return codes


async def webauthn_registration_options(db: AsyncSession, *, user: CurrentUser):
    user_id = uuid.UUID(user.user_id)
    db_user = await db.get(User, user_id)
    if db_user is None:
        raise UserNotFoundError(f"User {user_id} not found")

    result = await db.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id)
    )
    existing_ids = [c.credential_id for c in result.scalars()]

    options = mfa_webauthn.registration_options(
        user_id=str(user_id), email=db_user.email, existing_credential_ids=existing_ids
    )
    await mfa_webauthn.store_challenge(key=f"reg:{user_id}", challenge=options.challenge)
    return options


async def webauthn_register_verify(
    db: AsyncSession, *, user: CurrentUser, credential: dict, device_name: str | None
) -> list[str] | None:
    """Returns freshly-issued recovery codes if this was the user's first MFA
    factor, else None."""
    user_id = uuid.UUID(user.user_id)
    challenge = await mfa_webauthn.pop_challenge(key=f"reg:{user_id}")
    if challenge is None:
        raise ChallengeExpiredError("Registration challenge expired")

    try:
        parsed = parse_registration_credential_json(json.dumps(credential))
        verification = mfa_webauthn.verify_registration(
            credential=parsed, expected_challenge=challenge
        )
    except InvalidRegistrationResponse as exc:
        raise InvalidWebAuthnResponseError(f"Invalid passkey registration: {exc}") from exc

    db.add(
        WebAuthnCredential(
            user_id=user_id,
            credential_id=verification.credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            transports=credential.get("response", {}).get("transports", []),
            device_name=device_name,
        )
    )
    db_user = await db.get(User, user_id)
    if db_user is None:
        raise UserNotFoundError(f"User {user_id} not found")
    db_user.mfa_enabled = True

    codes = None
    if not await _has_recovery_codes(db, user_id=user_id):
        codes = await _issue_recovery_codes(db, user_id=user_id)
    await db.commit()
    return codes


async def list_webauthn_credentials(
    db: AsyncSession, *, user: CurrentUser
) -> list[WebAuthnCredential]:
    result = await db.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == uuid.UUID(user.user_id))
    )
    return list(result.scalars())


async def delete_webauthn_credential(
    db: AsyncSession, *, user: CurrentUser, credential_id: bytes
) -> None:
    result = await db.execute(
        select(WebAuthnCredential).where(
            WebAuthnCredential.user_id == uuid.UUID(user.user_id),
            WebAuthnCredential.credential_id == credential_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise CredentialNotFoundError("Credential not found")
    await db.delete(row)
    await db.commit()


async def webauthn_auth_options(db: AsyncSession, *, mfa_ticket: str):
    try:
        payload = decode_mfa_challenge_token(mfa_ticket)
    except pyjwt.InvalidTokenError as exc:
        raise InvalidTicketError("Invalid or expired MFA ticket") from exc

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id)
    )
    credential_ids = [c.credential_id for c in result.scalars()]
    if not credential_ids:
        raise CredentialNotFoundError("No passkeys enrolled")

    options = mfa_webauthn.authentication_options(allowed_credential_ids=credential_ids)
    await mfa_webauthn.store_challenge(key=f"auth:{user_id}", challenge=options.challenge)
    return options


async def _verify_totp(db: AsyncSession, *, user_id: uuid.UUID, code: str | None) -> bool:
    if not code:
        return False
    result = await db.execute(
        select(UserMfaMethod).where(
            UserMfaMethod.user_id == user_id,
            UserMfaMethod.method_type == "totp",
            UserMfaMethod.confirmed_at.is_not(None),
        )
    )
    method = result.scalar_one_or_none()
    if method is None:
        return False
    secret = decrypt_secret(method.secret_enc, user_id=str(user_id))
    ok, step = verify_totp_code(secret=secret, code=code, last_used_step=method.last_used_step)
    if ok:
        method.last_used_step = step
    return ok


async def _verify_recovery_code(db: AsyncSession, *, user_id: uuid.UUID, code: str | None) -> bool:
    if not code:
        return False
    result = await db.execute(
        select(MfaRecoveryCode).where(
            MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.used_at.is_(None)
        )
    )
    for row in result.scalars():
        if verify_recovery_code(code, row.code_hash):
            row.used_at = datetime.now(UTC)
            return True
    return False


async def _verify_webauthn(
    db: AsyncSession, *, user_id: uuid.UUID, credential: dict | None
) -> bool:
    if credential is None:
        return False
    challenge = await mfa_webauthn.pop_challenge(key=f"auth:{user_id}")
    if challenge is None:
        return False
    result = await db.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id)
    )
    creds_by_id = {c.credential_id: c for c in result.scalars()}
    if not creds_by_id:
        return False
    try:
        parsed = parse_authentication_credential_json(json.dumps(credential))
        cred_row = creds_by_id.get(parsed.raw_id)
        if cred_row is None:
            return False
        verification = mfa_webauthn.verify_authentication(
            credential=parsed,
            expected_challenge=challenge,
            credential_public_key=cred_row.public_key,
            credential_current_sign_count=cred_row.sign_count,
        )
    except (InvalidAuthenticationResponse, ValueError):
        return False
    cred_row.sign_count = verification.new_sign_count
    cred_row.last_used_at = datetime.now(UTC)
    return True


@dataclass
class MfaVerifyResult:
    access_token: str
    refresh_token: str


async def verify_mfa(
    db: AsyncSession,
    *,
    mfa_ticket: str,
    method: str,
    code: str | None,
    webauthn_credential: dict | None,
) -> MfaVerifyResult:
    """Completes a login that returned status=mfa_required."""
    try:
        payload = decode_mfa_challenge_token(mfa_ticket)
    except pyjwt.InvalidTokenError as exc:
        raise InvalidTicketError("Invalid or expired MFA ticket") from exc

    user_id = uuid.UUID(payload["sub"])
    lockout_key = f"mfa:{user_id}"
    if await is_locked_out(lockout_key):
        raise LockedOutError("Too many failed MFA attempts")

    db_user = await db.get(User, user_id)
    if db_user is None:
        raise UserNotFoundError(f"User {user_id} not found")

    amr = ["pwd"]
    if method == "totp" and await _verify_totp(db, user_id=user_id, code=code):
        verified = True
        amr.append("totp")
    elif method == "recovery_code" and await _verify_recovery_code(db, user_id=user_id, code=code):
        verified = True
        amr.append("recovery_code")
    elif method == "webauthn" and await _verify_webauthn(
        db, user_id=user_id, credential=webauthn_credential
    ):
        verified = True
        amr.append("webauthn")
    else:
        verified = False

    if not verified:
        await record_failed_attempt(lockout_key)
        await db.commit()
        raise VerificationFailedError("MFA verification failed")

    sess = await create_session(db, user=db_user, ip_addr=None, user_agent=None, amr=amr)
    await db.commit()

    access_token = issue_access_token(user=db_user, sess=sess)
    refresh_token = issue_refresh_token(user=db_user, sess=sess)
    return MfaVerifyResult(access_token=access_token, refresh_token=refresh_token)
