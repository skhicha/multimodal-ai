import uuid
from urllib.parse import urlparse

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from sonavault.adapters.vector import qdrant_repo
from sonavault.config import get_settings
from sonavault.db import SessionLocal
from sonavault.main import create_app
from sonavault.models.auth import User

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _skip_if_qdrant_unreachable():
    try:
        client = qdrant_repo.get_client()
        await client.get_collections()
    except Exception:
        pytest.skip("Qdrant not reachable at SV_QDRANT_URL")
    await qdrant_repo.ensure_collections()


def _random_dense(size: int) -> list[float]:
    import random

    vec = [random.random() for _ in range(size)]
    norm = sum(v * v for v in vec) ** 0.5
    return [v / norm for v in vec]


@pytest.fixture
async def viewer_client():
    # A unique sanctuary code per test invocation avoids false "leaked
    # candidate" signals from stale points left in the long-lived Qdrant
    # dev container by earlier test runs that happened to also use "OC02".
    sanctuary_code = f"TESTSANC-{uuid.uuid4().hex[:8]}"

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"search-viewer-{uuid.uuid4().hex[:8]}@sanctuary.org"
        await c.post(
            "/api/v1/auth/register", json={"email": email, "password": "CorrectHorseBattery9"}
        )
        login = (
            await c.post(
                "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
            )
        ).json()
        c.headers["Authorization"] = f"Bearer {login['access_token']}"

        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            user.sanctuary_scopes = [sanctuary_code]
            await session.commit()

        login2 = (
            await c.post(
                "/api/v1/auth/login", json={"email": email, "password": "CorrectHorseBattery9"}
            )
        ).json()
        c.headers["Authorization"] = f"Bearer {login2['access_token']}"
        c.sanctuary_code = sanctuary_code
        yield c


def _passthrough_qdrant_route(settings):
    qdrant_url = urlparse(settings.qdrant_url)
    respx.route(host=qdrant_url.hostname, port=qdrant_url.port).pass_through()


@respx.mock
async def test_hybrid_search_reranks_and_scopes_by_sanctuary(viewer_client: AsyncClient):
    settings = get_settings()
    _passthrough_qdrant_route(settings)

    in_scope_sha = uuid.uuid4().hex + uuid.uuid4().hex
    out_of_scope_sha = uuid.uuid4().hex + uuid.uuid4().hex

    dense_a, dense_b = _random_dense(1024), _random_dense(1024)
    await qdrant_repo.upsert(
        "transcript_segments",
        [
            qdrant_repo.UpsertPoint(
                point_id=qdrant_repo.deterministic_point_id(
                    asset_sha256=in_scope_sha, segment_index=0, model_version="test-search"
                ),
                dense_vector=dense_a,
                sparse_indices=[1, 2],
                sparse_values=[0.5, 0.4],
                payload={
                    "asset_sha256": in_scope_sha,
                    "sanctuary_id": viewer_client.sanctuary_code,
                    "rbac_tier": 1,
                    "text": "humpback whale call recorded near station",
                },
            ),
            qdrant_repo.UpsertPoint(
                point_id=qdrant_repo.deterministic_point_id(
                    asset_sha256=out_of_scope_sha, segment_index=0, model_version="test-search"
                ),
                dense_vector=dense_b,
                sparse_indices=[1, 2],
                sparse_values=[0.5, 0.4],
                payload={
                    "asset_sha256": out_of_scope_sha,
                    "sanctuary_id": "RESTRICTED_ZONE",
                    "rbac_tier": 1,
                    "text": "vessel noise in a zone this user cannot access",
                },
            ),
        ],
    )

    respx.post(f"{settings.nlp_sidecar_url}/v1/embed/bge-m3").mock(
        return_value=Response(
            200,
            json={
                "embeddings": [
                    {"dense": dense_a, "sparse": {"indices": [1, 2], "values": [0.5, 0.4]}}
                ]
            },
        )
    )
    respx.post(f"{settings.nlp_sidecar_url}/v1/rerank").mock(
        return_value=Response(200, json={"results": [{"index": 0, "score": 0.93}]})
    )

    resp = await viewer_client.post(
        "/api/v1/search/hybrid", json={"query": "whale call", "collection": "transcript_segments"}
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert all(r["asset_sha256"] != out_of_scope_sha for r in results)
    assert any(r["asset_sha256"] == in_scope_sha for r in results)
    matched = next(r for r in results if r["asset_sha256"] == in_scope_sha)
    assert matched["rerank_score"] == 0.93


@respx.mock
async def test_hybrid_search_rejects_unknown_collection(viewer_client: AsyncClient):
    resp = await viewer_client.post(
        "/api/v1/search/hybrid", json={"query": "x", "collection": "not_a_real_collection"}
    )
    assert resp.status_code == 422


@respx.mock
async def test_acoustic_text_search_uses_clap_embedding(viewer_client: AsyncClient):
    settings = get_settings()
    _passthrough_qdrant_route(settings)

    acoustic_sha = uuid.uuid4().hex + uuid.uuid4().hex
    dense = _random_dense(512)
    await qdrant_repo.upsert(
        "acoustic_events",
        [
            qdrant_repo.UpsertPoint(
                point_id=qdrant_repo.deterministic_point_id(
                    asset_sha256=acoustic_sha, segment_index=0, model_version="test-clap"
                ),
                dense_vector=dense,
                sparse_indices=[0],
                sparse_values=[1.0],
                payload={
                    "asset_sha256": acoustic_sha,
                    "sanctuary_id": viewer_client.sanctuary_code,
                    "rbac_tier": 1,
                },
            )
        ],
    )

    respx.post(f"{settings.speech_sidecar_url}/v1/embed/clap-text").mock(
        return_value=Response(200, json={"embedding": dense})
    )

    resp = await viewer_client.post(
        "/api/v1/search/acoustic-text", json={"query": "ship engine rumble"}
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["asset_sha256"] == acoustic_sha for r in results)
