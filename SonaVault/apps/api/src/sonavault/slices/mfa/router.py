"""MFA vertical slice: TOTP enrollment/verification, WebAuthn passkeys, and
recovery codes. See service.py for the domain logic; this module only
handles request parsing, dependency injection, and HTTP status mapping."""

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json

from sonavault.core.security.deps import require_auth
from sonavault.core.security.rbac import CurrentUser
from sonavault.db import get_db
from sonavault.slices.auth.router import set_refresh_cookie
from sonavault.slices.mfa import service
from sonavault.slices.mfa.schemas import (
    MfaVerifyRequest,
    TotpConfirmRequest,
    TotpEnrollResponse,
    WebAuthnAuthOptionsRequest,
    WebAuthnCredentialOut,
    WebAuthnRegisterVerifyRequest,
)

router = APIRouter(prefix="/api/v1/mfa", tags=["mfa"])

_NOT_FOUND_ERRORS = (service.UserNotFoundError, service.CredentialNotFoundError)
_BAD_REQUEST_ERRORS = (service.NoPendingEnrollmentError, service.ChallengeExpiredError)


def _raise_for_mfa_error(exc: service.MfaError) -> NoReturn:
    if isinstance(exc, _NOT_FOUND_ERRORS):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, _BAD_REQUEST_ERRORS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if isinstance(exc, service.InvalidWebAuthnResponseError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if isinstance(exc, service.LockedOutError):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@router.post("/totp/enroll", response_model=TotpEnrollResponse)
async def totp_enroll(
    user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    try:
        enrollment = await service.enroll_totp(db, user=user)
    except service.MfaError as exc:
        _raise_for_mfa_error(exc)
    return TotpEnrollResponse(
        secret=enrollment.secret, provisioning_uri=enrollment.provisioning_uri
    )


@router.post("/totp/confirm")
async def totp_confirm(
    body: TotpConfirmRequest,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        codes = await service.confirm_totp(db, user=user, code=body.code)
    except service.MfaError as exc:
        _raise_for_mfa_error(exc)
    return {"status": "enrolled", "recovery_codes": codes}


@router.post("/recovery-codes/regenerate")
async def regenerate_recovery_codes(
    user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    codes = await service.regenerate_recovery_codes(db, user=user)
    return {"status": "regenerated", "recovery_codes": codes}


# --- WebAuthn passkeys -------------------------------------------------------


@router.post("/webauthn/register/options")
async def webauthn_register_options(
    user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    try:
        options = await service.webauthn_registration_options(db, user=user)
    except service.MfaError as exc:
        _raise_for_mfa_error(exc)
    return {"options": options_to_json(options)}


@router.post("/webauthn/register/verify")
async def webauthn_register_verify(
    body: WebAuthnRegisterVerifyRequest,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        codes = await service.webauthn_register_verify(
            db, user=user, credential=body.credential, device_name=body.device_name
        )
    except service.MfaError as exc:
        _raise_for_mfa_error(exc)
    return {"status": "registered", "recovery_codes": codes}


@router.get("/webauthn/credentials", response_model=list[WebAuthnCredentialOut])
async def list_webauthn_credentials(
    user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    credentials = await service.list_webauthn_credentials(db, user=user)
    return [
        WebAuthnCredentialOut(
            id=bytes_to_base64url(c.credential_id),
            device_name=c.device_name,
            transports=c.transports,
        )
        for c in credentials
    ]


@router.delete("/webauthn/credentials/{credential_b64}")
async def delete_webauthn_credential(
    credential_b64: str,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        await service.delete_webauthn_credential(
            db, user=user, credential_id=base64url_to_bytes(credential_b64)
        )
    except service.MfaError as exc:
        _raise_for_mfa_error(exc)
    return {"status": "deleted"}


@router.post("/webauthn/auth/options")
async def webauthn_auth_options(
    body: WebAuthnAuthOptionsRequest, db: AsyncSession = Depends(get_db)
):
    try:
        options = await service.webauthn_auth_options(db, mfa_ticket=body.mfa_ticket)
    except service.MfaError as exc:
        _raise_for_mfa_error(exc)
    return {"options": options_to_json(options)}


# --- Login-time MFA verification --------------------------------------------


@router.post("/verify")
async def mfa_verify(
    body: MfaVerifyRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    try:
        result = await service.verify_mfa(
            db,
            mfa_ticket=body.mfa_ticket,
            method=body.method,
            code=body.code,
            webauthn_credential=body.webauthn_credential,
        )
    except service.MfaError as exc:
        _raise_for_mfa_error(exc)
    set_refresh_cookie(response, result.refresh_token)
    return {"status": "authenticated", "access_token": result.access_token}
