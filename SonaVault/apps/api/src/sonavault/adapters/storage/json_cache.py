"""Atomic JSON Write Cache: materializes heavy multi-table read views (diarized
transcripts+translations+GLiNER spans+AST timelines+Leaflet GeoJSON) to NVMe at
/data/cache/projections/{asset_sha256}/{view}.json so FastAPI can serve them
directly with ETag/304 without joining across Postgres on every request.

Write protocol: write to a temp sibling file, fsync, then atomic os.replace()
so readers never observe a partially written file.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sonavault.config import get_settings

PROJECTION_VERSION = 1


def _projection_path(*, asset_sha256: str, view: str) -> Path:
    settings = get_settings()
    return settings.cache_path / "projections" / asset_sha256 / f"{view}.json"


def write_projection(*, asset_sha256: str, view: str, payload: dict[str, Any]) -> str:
    """Writes the projection atomically and returns its ETag (content hash)."""
    path = _projection_path(asset_sha256=asset_sha256, view=view)
    path.parent.mkdir(parents=True, exist_ok=True)

    envelope = {
        "asset_sha256": asset_sha256,
        "embedding_projection_version": PROJECTION_VERSION,
        "data": payload,
    }
    body = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    etag = hashlib.sha256(body).hexdigest()
    envelope["etag"] = etag
    body = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")

    tmp_path = path.with_suffix(f".tmp.{os.getpid()}")
    with open(tmp_path, "wb") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)
    return etag


def read_projection(*, asset_sha256: str, view: str) -> dict[str, Any] | None:
    path = _projection_path(asset_sha256=asset_sha256, view=view)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def read_etag(*, asset_sha256: str, view: str) -> str | None:
    projection = read_projection(asset_sha256=asset_sha256, view=view)
    return projection["etag"] if projection else None
