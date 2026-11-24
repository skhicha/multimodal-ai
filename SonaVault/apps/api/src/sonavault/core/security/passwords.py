"""Argon2id password hashing & NIST SP 800-63B-4 policy checks.

Per blueprint: m=65536 KiB (64 MiB), t=3, p=2, 16-byte CSPRNG salts, PHC strings.
Minimum length 12 (no truncation), unicode allowed, no forced rotation/complexity
rules; reject passwords found in a local breached-password blocklist.
"""

from functools import lru_cache
from pathlib import Path

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from sonavault.config import get_settings

MIN_LENGTH = 12
MAX_LENGTH = 128

_BLOCKLIST_PATH = Path(__file__).parent / "data" / "breached_passwords_top100k.txt"


def _build_hasher() -> PasswordHash:
    settings = get_settings()
    return PasswordHash(
        [
            Argon2Hasher(
                memory_cost=settings.argon2_memory_kib,
                time_cost=settings.argon2_time_cost,
                parallelism=settings.argon2_parallelism,
            )
        ]
    )


@lru_cache
def _hasher() -> PasswordHash:
    return _build_hasher()


@lru_cache
def _blocklist() -> frozenset[str]:
    if not _BLOCKLIST_PATH.exists():
        return frozenset()
    return frozenset(
        line.strip() for line in _BLOCKLIST_PATH.read_text().splitlines() if line.strip()
    )


class WeakPasswordError(ValueError):
    pass


def validate_password_policy(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise WeakPasswordError(f"Password must be at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        raise WeakPasswordError(f"Password must be at most {MAX_LENGTH} characters.")
    if password.lower() in _blocklist():
        raise WeakPasswordError("Password appears in a known breached-password list.")


def hash_password(password: str) -> str:
    validate_password_policy(password)
    return _hasher().hash(password)


def verify_password(password: str, phc_hash: str) -> bool:
    return _hasher().verify(password, phc_hash)


def needs_rehash(phc_hash: str) -> bool:
    return _hasher().check_needs_rehash(phc_hash)


@lru_cache
def _dummy_hash() -> str:
    return _hasher().hash("dummy-password-for-constant-time-timing-safety")


def dummy_verify() -> None:
    """Run a fake verification to keep timing constant for unknown accounts
    (user-enumeration defense)."""
    try:
        _hasher().verify("not-the-real-password", _dummy_hash())
    except Exception:
        pass
