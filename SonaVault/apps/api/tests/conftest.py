"""Shared test fixtures: generates throwaway crypto secrets and points the app
at an isolated SQLite database + an in-memory fake Redis *before* any
sonavault module is imported, so the whole suite runs hermetically with no
external services."""

import base64
import os
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

_tmp_dir = tempfile.mkdtemp(prefix="sonavault-test-")
_key_path = os.path.join(_tmp_dir, "jwt_ed25519_private.pem")
_private_key = Ed25519PrivateKey.generate()
with open(_key_path, "wb") as f:
    f.write(
        _private_key.private_bytes(
            encoding=Encoding.PEM, format=PrivateFormat.PKCS8, encryption_algorithm=NoEncryption()
        )
    )

os.environ.setdefault("SV_JWT_ED25519_PRIVATE_KEY_PATH", _key_path)
os.environ.setdefault("SV_MASTER_KEK_B64", base64.b64encode(os.urandom(32)).decode())
os.environ.setdefault("SV_BLIND_INDEX_KEY_B64", base64.b64encode(os.urandom(32)).decode())
os.environ.setdefault(
    "SV_DATABASE_URL", f"sqlite+aiosqlite:///{os.path.join(_tmp_dir, 'sonavault_test.db')}"
)
os.environ.setdefault("SV_BLOB_ROOT", os.path.join(_tmp_dir, "blobs"))
os.environ.setdefault("SV_CACHE_ROOT", os.path.join(_tmp_dir, "cache"))

import pytest_asyncio  # noqa: E402
from fakeredis import aioredis as fake_aioredis  # noqa: E402

import sonavault.models  # noqa: E402,F401
from sonavault.core.security import rate_limit  # noqa: E402
from sonavault.db import Base, engine  # noqa: E402


@pytest_asyncio.fixture(autouse=True, scope="session")
async def _fake_redis_singleton():
    fake = fake_aioredis.FakeRedis(decode_responses=True)
    rate_limit._redis = fake
    yield fake
    await fake.flushall()


@pytest_asyncio.fixture(autouse=True, scope="session")
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
