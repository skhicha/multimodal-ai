"""PyJWT EdDSA (Ed25519) access tokens + opaque rotating refresh tokens.

Access token: 15 min TTL, claims {sub, sid, role, sanctuary_scopes, amr,
mfa_verified_at, jti, exp}. Held strictly in frontend memory (never
localStorage/sessionStorage) to eliminate XSS token theft.

Refresh token: 7-day TTL, HttpOnly/Secure/SameSite=Strict cookie. Rotation with
reuse detection is enforced at the session-repository layer (user_sessions +
Redis mirror): every refresh invalidates the old jti and mints a new one in the
same family_id; presenting an already-used jti revokes the whole family.
"""

import time
import uuid
from pathlib import Path
from typing import Any

import jwt

from sonavault.config import get_settings

ALGORITHM = "EdDSA"


def _private_key() -> str:
    settings = get_settings()
    path = Path(settings.jwt_ed25519_private_key_path)
    if not path.exists():
        raise RuntimeError(f"JWT Ed25519 private key not found at {path}. Run `make keys` first.")
    return path.read_text()


def _public_key() -> Any:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key = load_pem_private_key(_private_key().encode(), password=None)
    return key.public_key()


def mint_access_token(
    *,
    sub: str,
    sid: str,
    role: str,
    sanctuary_scopes: list[str],
    amr: list[str],
    mfa_verified_at: float | None,
) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": sub,
        "sid": sid,
        "role": role,
        "sanctuary_scopes": sanctuary_scopes,
        "amr": amr,
        "mfa_verified_at": mfa_verified_at,
        "iat": now,
        "exp": now + settings.jwt_access_ttl_min * 60,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _private_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _public_key(), algorithms=[ALGORITHM])


def mfa_challenge_token(*, sub: str, methods: list[str]) -> str:
    """Short-lived (5 min) ticket issued between password verification and
    MFA completion. Never grants an authenticated session."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "scope": "mfa-challenge",
        "methods": methods,
        "iat": now,
        "exp": now + 5 * 60,
    }
    return jwt.encode(payload, _private_key(), algorithm=ALGORITHM)


def decode_mfa_challenge_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, _public_key(), algorithms=[ALGORITHM])
    if payload.get("scope") != "mfa-challenge":
        raise jwt.InvalidTokenError("not an mfa-challenge token")
    return payload


def mint_refresh_token(*, sub: str, sid: str, family_id: str, jti: str) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": sub,
        "sid": sid,
        "family_id": family_id,
        "jti": jti,
        "scope": "refresh",
        "iat": now,
        "exp": now + settings.jwt_refresh_ttl_days * 24 * 3600,
    }
    return jwt.encode(payload, _private_key(), algorithm=ALGORITHM)


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, _public_key(), algorithms=[ALGORITHM])
    if payload.get("scope") != "refresh":
        raise jwt.InvalidTokenError("not a refresh token")
    return payload


def mint_stream_token(*, sub: str, station_code: str, ttl_seconds: int = 300) -> str:
    """Short-lived, station-scoped token MediaMTX's HTTP auth hook validates
    before allowing a client to read or publish a hydrophone stream path."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "scope": "stream",
        "station_code": station_code,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(payload, _private_key(), algorithm=ALGORITHM)


def decode_stream_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, _public_key(), algorithms=[ALGORITHM])
    if payload.get("scope") != "stream":
        raise jwt.InvalidTokenError("not a stream token")
    return payload
