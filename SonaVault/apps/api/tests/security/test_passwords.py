import pytest

from sonavault.core.security.passwords import (
    WeakPasswordError,
    hash_password,
    verify_password,
)


def test_hash_and_verify_roundtrip():
    pw = "correct horse battery staple"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed)
    assert not verify_password("wrong password", hashed)


def test_rejects_short_password():
    with pytest.raises(WeakPasswordError):
        hash_password("short1")
