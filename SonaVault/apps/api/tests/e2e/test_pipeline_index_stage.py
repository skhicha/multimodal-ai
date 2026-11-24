import uuid

import pytest
import respx
from httpx import Response

from sonavault.adapters.storage import blob_nvme
from sonavault.adapters.vector import qdrant_repo
from sonavault.config import get_settings
from sonavault.core.pipeline import stages
from sonavault.core.pipeline.admission import is_stage_complete
from sonavault.db import SessionLocal
from sonavault.models.acoustics import TranscriptSegment
from sonavault.models.assets import Asset
from sonavault.models.pipeline import PipelineJob

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _skip_if_qdrant_unreachable():
    try:
        client = qdrant_repo.get_client()
        await client.get_collections()
    except Exception:
        pytest.skip("Qdrant not reachable at SV_QDRANT_URL")


async def _make_asset_with_segments(session) -> tuple[str, uuid.UUID]:
    sha256 = blob_nvme.put(uuid.uuid4().bytes + b"index-stage-test-audio")
    session.add(Asset(sha256=sha256, asset_type="audio", mime_type="audio/wav", size_bytes=32))
    job = PipelineJob(asset_sha256=sha256)
    session.add(job)
    session.add(
        TranscriptSegment(
            asset_sha256=sha256,
            seg_index=0,
            start_sec=0.0,
            end_sec=2.0,
            text_redacted="humpback whale vocalization near station",
            model_version="v1",
        )
    )
    await session.flush()
    return sha256, job.job_id


@respx.mock
async def test_index_stage_upserts_deterministic_points():
    settings = get_settings()
    respx.post(f"{settings.nlp_sidecar_url}/v1/embed/bge-m3").mock(
        return_value=Response(
            200,
            json={
                "embeddings": [
                    {"dense": [0.01] * 1024, "sparse": {"indices": [1, 2], "values": [0.5, 0.3]}}
                ]
            },
        )
    )
    # Let real Qdrant traffic pass through to the live network; only the
    # nlp sidecar call above is actually mocked.
    from urllib.parse import urlparse

    qdrant_url = urlparse(settings.qdrant_url)
    respx.route(host=qdrant_url.hostname, port=qdrant_url.port).pass_through()

    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_with_segments(session)
        await session.commit()

        await stages.run_index_stage(session, job_id=job_id, asset_sha256=sha256)
        await session.commit()

        assert await is_stage_complete(session, asset_sha256=sha256, stage_name="index")

        expected_id = qdrant_repo.deterministic_point_id(
            asset_sha256=sha256, segment_index=0, model_version="v1"
        )
        client = qdrant_repo.get_client()
        points = await client.retrieve(collection_name="transcript_segments", ids=[expected_id])
        assert len(points) == 1
        assert points[0].payload["asset_sha256"] == sha256
