"""AES-256-GCM envelope encryption (KEK -> DEK) for PII columns.

Protects: observer_name_enc, informant_contact_enc, and other sensitive
SQLAlchemy columns. Each write generates a fresh 96-bit nonce and binds
additional authenticated data (AAD) so ciphertext cannot be swapped between
rows/columns/users.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from sonavault.config import get_settings

NONCE_BYTES = 12


def _kek() -> bytes:
    settings = get_settings()
    if not settings.master_kek_b64:
        raise RuntimeError("SV_MASTER_KEK_B64 is not configured.")
    return base64.b64decode(settings.master_kek_b64)


def encrypt_field(plaintext: str, *, aad: bytes) -> bytes:
    """Returns nonce || ciphertext, suitable for a single BYTEA column."""
    aesgcm = AESGCM(_kek())
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
    return nonce + ciphertext


def decrypt_field(blob: bytes, *, aad: bytes) -> str:
    aesgcm = AESGCM(_kek())
    nonce, ciphertext = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
    return aesgcm.decrypt(nonce, ciphertext, aad).decode("utf-8")


def field_aad(*parts: str) -> bytes:
    """Builds deterministic AAD from row identity, e.g. field_aad(user_id, 'totp')."""
    return "|".join(parts).encode("utf-8")
