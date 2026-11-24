from typing import Any

from pydantic import BaseModel


class MfaVerifyRequest(BaseModel):
    mfa_ticket: str
    method: str  # "totp" | "webauthn" | "recovery_code"
    code: str | None = None  # TOTP digits or recovery code
    webauthn_credential: dict[str, Any] | None = None


class TotpEnrollResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TotpConfirmRequest(BaseModel):
    code: str


class WebAuthnRegisterVerifyRequest(BaseModel):
    credential: dict[str, Any]
    device_name: str | None = None


class WebAuthnAuthOptionsRequest(BaseModel):
    mfa_ticket: str


class WebAuthnCredentialOut(BaseModel):
    id: str
    device_name: str | None
    transports: list[str]
    created_current: bool = False
