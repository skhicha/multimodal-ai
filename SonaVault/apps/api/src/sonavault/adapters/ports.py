"""Swappable repository & infrastructure ports (typing.Protocol).

Lets the core app depend on an interface rather than a concrete backend:
RelationalStorePort (Postgres / SQLite WAL fallback), BlobStorePort
(content-addressed NVMe / S3), JobQueuePort (Redis+RQ / in-process AsyncIO),
VectorIndexPort (Qdrant), ProjectionCachePort (Atomic JSON Write Cache).
"""

from typing import Protocol


class BlobStorePort(Protocol):
    def put(self, data: bytes) -> str:
        """Writes content-addressed data, returns its sha256 hex digest."""
        ...

    def get(self, sha256: str) -> bytes: ...

    def exists(self, sha256: str) -> bool: ...

    def path_for(self, sha256: str) -> str: ...


class JobQueuePort(Protocol):
    def enqueue(self, queue_name: str, func: str, *args, **kwargs) -> str:
        """Returns a job id."""
        ...


class ProjectionCachePort(Protocol):
    def write(self, *, asset_sha256: str, view: str, payload: dict) -> str:
        """Returns an ETag."""
        ...

    def read(self, *, asset_sha256: str, view: str) -> dict | None: ...
