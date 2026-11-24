"""Content-addressed NVMe blob store: /data/blobs/<ab>/<cd>/<sha256>.

Two-level sharding by the first 4 hex chars keeps any single directory from
accumulating too many entries. Writes are atomic (temp file + os.replace) so
a crash mid-write never leaves a corrupt blob visible under its final name.
"""

import hashlib
import os
from pathlib import Path

from sonavault.config import get_settings


def _shard_path(sha256: str) -> Path:
    settings = get_settings()
    return settings.blob_path / sha256[0:2] / sha256[2:4] / sha256


def put(data: bytes) -> str:
    sha256 = hashlib.sha256(data).hexdigest()
    path = _shard_path(sha256)
    if path.exists():
        return sha256  # content-addressed: identical bytes already stored

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".tmp.{os.getpid()}")
    with open(tmp_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)
    return sha256


def get(sha256: str) -> bytes:
    path = _shard_path(sha256)
    return path.read_bytes()


def exists(sha256: str) -> bool:
    return _shard_path(sha256).exists()


def path_for(sha256: str) -> str:
    return str(_shard_path(sha256))


def verify_fixity(sha256: str) -> bool:
    """Re-hashes the stored blob and confirms it matches its own filename —
    the core PREMIS fixity-audit primitive."""
    if not exists(sha256):
        return False
    actual = hashlib.sha256(get(sha256)).hexdigest()
    return actual == sha256
