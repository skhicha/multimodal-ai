"""
OTP code generation and hashing helpers, reusing the same passlib bcrypt
context as password hashing in app.auth (one bcrypt context for the app).
"""
from __future__ import annotations

import secrets

from app.auth import pwd_context


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str) -> str:
    return pwd_context.hash(code)


def verify_code(code: str, hash_: str) -> bool:
    return pwd_context.verify(code, hash_)
