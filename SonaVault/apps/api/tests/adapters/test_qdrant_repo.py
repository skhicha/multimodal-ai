"""Integration test against a real Qdrant instance (SV_QDRANT_URL).
Skipped automatically if Qdrant is unreachable."""

import random

import pytest

from sonavault.adapters.vector import qdrant_repo

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _skip_if_qdrant_unreachable():
    try:
        client = qdrant_repo.get_client()
        await client.get_collections()
    except Exception:
        pytest.skip("Qdrant not reachable at SV_QDRANT_URL")


def _random_dense(size: int) -> list[float]:
    vec = [random.random() for _ in range(size)]
    norm = sum(v * v for v in vec) ** 0.5
    return [v / norm for v in vec]


async def test_ensure_collections_is_idempotent():
    await qdrant_repo.ensure_collections()
    await qdrant_repo.ensure_collections()  # must not raise on second call
    client = qdrant_repo.get_client()
    for name in qdrant_repo.COLLECTIONS:
        assert await client.collection_exists(name)


async def test_deterministic_point_id_is_stable_and_unique():
    id1 = qdrant_repo.deterministic_point_id(
        asset_sha256="a" * 64, segment_index=0, model_version="v1"
    )
    id2 = qdrant_repo.deterministic_point_id(
        asset_sha256="a" * 64, segment_index=0, model_version="v1"
    )
    id3 = qdrant_repo.deterministic_point_id(
        asset_sha256="a" * 64, segment_index=1, model_version="v1"
    )
    assert id1 == id2
    assert id1 != id3


async def test_upsert_and_hybrid_search_with_rbac_filter():
    await qdrant_repo.ensure_collections()

    sha256 = "b" * 64
    point = qdrant_repo.UpsertPoint(
        point_id=qdrant_repo.deterministic_point_id(
            asset_sha256=sha256, segment_index=0, model_version="test"
        ),
        dense_vector=_random_dense(1024),
        sparse_indices=[1, 5, 9],
        sparse_values=[0.8, 0.5, 0.2],
        payload={
            "asset_sha256": sha256,
            "sanctuary_id": "OC02",
            "rbac_tier": 1,
            "text": "humpback call",
        },
    )
    await qdrant_repo.upsert("transcript_segments", [point])

    results = await qdrant_repo.hybrid_search(
        "transcript_segments",
        dense_vector=point.dense_vector,
        sparse_indices=point.sparse_indices,
        sparse_values=point.sparse_values,
        limit=5,
        max_tier=3,
        sanctuary_scopes=["OC02"],
    )
    assert len(results) >= 1
    assert results[0].payload["asset_sha256"] == sha256


async def test_hybrid_search_excludes_out_of_scope_sanctuary():
    await qdrant_repo.ensure_collections()

    sha256 = "c" * 64
    point = qdrant_repo.UpsertPoint(
        point_id=qdrant_repo.deterministic_point_id(
            asset_sha256=sha256, segment_index=0, model_version="test"
        ),
        dense_vector=_random_dense(1024),
        sparse_indices=[2, 4],
        sparse_values=[0.6, 0.3],
        payload={"asset_sha256": sha256, "sanctuary_id": "RESTRICTED_ZONE", "rbac_tier": 1},
    )
    await qdrant_repo.upsert("transcript_segments", [point])

    results = await qdrant_repo.hybrid_search(
        "transcript_segments",
        dense_vector=point.dense_vector,
        sparse_indices=point.sparse_indices,
        sparse_values=point.sparse_values,
        limit=50,
        max_tier=3,
        sanctuary_scopes=["OC02"],  # does not include RESTRICTED_ZONE
    )
    returned_ids = {r.id for r in results}
    assert point.point_id not in returned_ids
