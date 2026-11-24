"""
Real authenticator-app MFA: TOTP (RFC 6238) via pyotp, same standard used
by Google Authenticator / Authy / 1Password etc, plus one-time backup
codes for when the user doesn't have their phone. This is separate from
(and stronger than) the simpler email-OTP login step -- a user can enable
either, both, or neither.
"""
from __future__ import annotations

import base64
import io
import secrets

import pyotp
import qrcode

from app.auth import pwd_context

ISSUER = "MemoryLens AI"
BACKUP_CODE_COUNT = 8


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_code_data_uri(uri: str) -> str:
    """Renders the provisioning URI as a QR code and returns it as a
    base64 PNG data: URI the frontend can drop straight into an <img>."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_totp(secret: str, code: str) -> bool:
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:  # noqa: BLE001 - malformed code input, never crash on it
        return False


def generate_backup_codes() -> list[str]:
    # 8-character alphanumeric, easy to type back in once, hard to guess.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    return ["".join(secrets.choice(alphabet) for _ in range(8)) for _ in range(BACKUP_CODE_COUNT)]


def hash_backup_code(code: str) -> str:
    return pwd_context.hash(code.upper())


def verify_backup_code(code: str, code_hash: str) -> bool:
    return pwd_context.verify(code.upper(), code_hash)
