"""PyOTP RFC 6238 TOTP with encrypted-at-rest secrets and replay-window guard."""

import time

import pyotp

from sonavault.core.security.crypto import decrypt_field, encrypt_field, field_aad

VALID_WINDOW = 1  # +/- 30s clock skew


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(*, secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="SonaVault")


def encrypt_secret(secret: str, *, user_id: str) -> bytes:
    return encrypt_field(secret, aad=field_aad(user_id, "totp"))


def decrypt_secret(blob: bytes, *, user_id: str) -> str:
    return decrypt_field(blob, aad=field_aad(user_id, "totp"))


def verify_code(*, secret: str, code: str, last_used_step: int | None) -> tuple[bool, int | None]:
    """Returns (is_valid, new_last_used_step). Rejects replay of the same
    30-second step even if the code itself is numerically correct."""
    totp = pyotp.TOTP(secret)
    current_step = int(totp.timecode(time.time()))
    if last_used_step is not None and current_step <= last_used_step:
        return False, None
    if not totp.verify(code, valid_window=VALID_WINDOW):
        return False, None
    return True, current_step
