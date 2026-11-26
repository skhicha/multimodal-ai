"""FIDO2/WebAuthn Passkeys (py_webauthn) — primary phishing-resistant MFA.

Challenges are stored in Redis with a 120s TTL, strictly bound to RP_ID and
ORIGIN. Supports hardware security keys, Touch/Face ID, Windows Hello, and
platform passkeys. Works both as a 2FA second factor and as 1-click
passwordless sign-in (user_verification="required").
"""

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticationCredential,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from sonavault.config import get_settings
from sonavault.core.security.rate_limit import get_redis

CHALLENGE_TTL_SECONDS = 120


async def store_challenge(*, key: str, challenge: bytes) -> None:
    r = get_redis()
    await r.set(f"sv:webauthn:challenge:{key}", challenge.hex(), ex=CHALLENGE_TTL_SECONDS)


async def pop_challenge(*, key: str) -> bytes | None:
    r = get_redis()
    redis_key = f"sv:webauthn:challenge:{key}"
    value = await r.get(redis_key)
    if value is None:
        return None
    await r.delete(redis_key)
    return bytes.fromhex(value if isinstance(value, str) else value.decode())


def registration_options(*, user_id: str, email: str, existing_credential_ids: list[bytes]):
    settings = get_settings()
    return generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_id.encode("utf-8"),
        user_name=email,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=cid) for cid in existing_credential_ids
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )


def verify_registration(*, credential: RegistrationCredential, expected_challenge: bytes):
    settings = get_settings()
    return verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=settings.public_origin,
        expected_rp_id=settings.webauthn_rp_id,
    )


def authentication_options(*, allowed_credential_ids: list[bytes]):
    settings = get_settings()
    return generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=[PublicKeyCredentialDescriptor(id=cid) for cid in allowed_credential_ids],
    )


def verify_authentication(
    *,
    credential: AuthenticationCredential,
    expected_challenge: bytes,
    credential_public_key: bytes,
    credential_current_sign_count: int,
):
    settings = get_settings()
    result = verify_authentication_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=settings.public_origin,
        expected_rp_id=settings.webauthn_rp_id,
        credential_public_key=credential_public_key,
        credential_current_sign_count=credential_current_sign_count,
    )
    if result.new_sign_count <= credential_current_sign_count:
        # Monotonic counter did not advance: possible cloned authenticator.
        raise ValueError("WebAuthn sign_count did not increase; rejecting as cloned credential.")
    return result
