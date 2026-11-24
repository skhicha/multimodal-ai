"""Qdrant v1.20 multi-collection hybrid RRF search.

Three collections, all dense+sparse, per the architecture blueprint:
  - transcript_segments: dense bge_dense(1024-d, Cosine) + sparse bge_sparse
  - document_chunks:     identical dense+sparse schema
  - acoustic_events:     dense clap_audio(512-d, Cosine) + sparse audioset_sparse

RBAC/sanctuary payload filters are mandatory and non-overridable: every query
injects `rbac_tier <= user.max_tier AND sanctuary_id IN user.sanctuary_scopes`
(unless the caller already has full-sanctuary access).
"""

import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient, models

from sonavault.config import get_settings

RRF_K = 60
RRF_WEIGHTS = [1.5, 1.0]  # [dense, sparse]
PREFETCH_LIMIT = 50

COLLECTIONS = {
    "transcript_segments": {"dense": "bge_dense", "dense_size": 1024, "sparse": "bge_sparse"},
    "document_chunks": {"dense": "bge_dense", "dense_size": 1024, "sparse": "bge_sparse"},
    "acoustic_events": {"dense": "clap_audio", "dense_size": 512, "sparse": "audioset_sparse"},
}

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncQdrantClient(url=settings.qdrant_url)
    return _client


def deterministic_point_id(*, asset_sha256: str, segment_index: int, model_version: str) -> str:
    """UUIDv5 so re-indexing the same (asset, segment, model) overwrites the
    same point instead of creating a duplicate — required for idempotent
    pipeline resume."""
    namespace = uuid.UUID("5f2f5c3a-9b1e-4a7a-9f0e-1c2d3e4f5a6b")
    name = f"{asset_sha256}:{segment_index}:{model_version}"
    return str(uuid.uuid5(namespace, name))


async def ensure_collections() -> None:
    client = get_client()
    for name, schema in COLLECTIONS.items():
        exists = await client.collection_exists(name)
        if exists:
            continue
        await client.create_collection(
            collection_name=name,
            vectors_config={
                schema["dense"]: models.VectorParams(
                    size=schema["dense_size"], distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={schema["sparse"]: models.SparseVectorParams()},
        )
        for field in ("asset_sha256", "sanctuary_id", "rbac_tier"):
            await client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )


@dataclass
class UpsertPoint:
    point_id: str
    dense_vector: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]
    payload: dict[str, Any]


async def upsert(collection: str, points: list[UpsertPoint]) -> None:
    schema = COLLECTIONS[collection]
    client = get_client()
    qdrant_points = [
        models.PointStruct(
            id=p.point_id,
            vector={
                schema["dense"]: p.dense_vector,
                schema["sparse"]: models.SparseVector(
                    indices=p.sparse_indices, values=p.sparse_values
                ),
            },
            payload=p.payload,
        )
        for p in points
    ]
    await client.upsert(collection_name=collection, points=qdrant_points, wait=True)


def rbac_filter(*, max_tier: int, sanctuary_scopes: list[str], full_access: bool) -> models.Filter:
    """Public helper so callers needing a raw query_points() call (e.g. the
    CLAP-only acoustic search) can build the same mandatory RBAC filter
    hybrid_search() applies internally."""
    conditions: list[models.Condition] = [
        models.FieldCondition(key="rbac_tier", range=models.Range(lte=max_tier))
    ]
    if not full_access:
        conditions.append(
            models.FieldCondition(key="sanctuary_id", match=models.MatchAny(any=sanctuary_scopes))
        )
    return models.Filter(must=conditions)


async def hybrid_search(
    collection: str,
    *,
    dense_vector: list[float],
    sparse_indices: list[int],
    sparse_values: list[float],
    limit: int,
    max_tier: int,
    sanctuary_scopes: list[str],
    full_access: bool = False,
) -> list[models.ScoredPoint]:
    """Qdrant Universal Query API: dense+sparse prefetch merged via weighted
    RRF (k=60, weights=[1.5 dense, 1.0 sparse])."""
    schema = COLLECTIONS[collection]
    client = get_client()
    query_filter = rbac_filter(
        max_tier=max_tier, sanctuary_scopes=sanctuary_scopes, full_access=full_access
    )

    result = await client.query_points(
        collection_name=collection,
        prefetch=[
            models.Prefetch(
                query=dense_vector,
                using=schema["dense"],
                limit=max(PREFETCH_LIMIT, limit),
                filter=query_filter,
            ),
            models.Prefetch(
                query=models.SparseVector(indices=sparse_indices, values=sparse_values),
                using=schema["sparse"],
                limit=max(PREFETCH_LIMIT, limit),
                filter=query_filter,
            ),
        ],
        query=models.RrfQuery(rrf=models.Rrf(k=RRF_K, weights=RRF_WEIGHTS)),
        limit=limit,
        query_filter=query_filter,
    )
    return result.points
