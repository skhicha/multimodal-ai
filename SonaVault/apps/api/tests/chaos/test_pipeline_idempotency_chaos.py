import uuid
from urllib.parse import urlparse

import pytest
import respx
from httpx import Response

from sonavault.adapters.storage import blob_nvme
from sonavault.adapters.vector import qdrant_repo
from sonavault.config import get_settings
from sonavault.core.pipeline import stages
from sonavault.core.pipeline.admission import is_stage_complete
from sonavault.core.provenance.ledger import verify_chain
from sonavault.models.assets import Asset
from sonavault.models.pipeline import PipelineJob, PipelineStageRun
from sonavault.slices.jobs.service import (
    JobAlreadyCompleteError,
    resume_job,
)


def _mock_sidecars(settings):
    respx.post(f"{settings.speech_sidecar_url}/v1/transcribe").mock(
        return_value=Response(
            200,
            json={
                "segments": [
                    {
                        "start_sec": 0.0,
                        "end_sec": 3.0,
                        "text": "Humpback whale vocalization",
                        "language": "en",
                    }
                ],
                "detected_language": "en",
            },
        )
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/diarize").mock(
        return_value=Response(
            200,
            json={"turns": [{"start_sec": 0.0, "end_sec": 3.0, "speaker_label": "SPEAKER_00"}]},
        )
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/events/ast").mock(
        return_value=Response(
            200,
            json={
                "events": [
                    {
                        "window_start_sec": 0.0,
                        "window_end_sec": 3.0,
                        "labels": {"Whale vocalization": 0.95},
                    }
                ]
            },
        )
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/embed/clap-audio").mock(
        return_value=Response(200, json={"embedding": [0.01] * 512})
    )
    respx.post(f"{settings.nlp_sidecar_url}/v1/ner/gliner").mock(
        return_value=Response(200, json={"entities": []})
    )
    respx.post(f"{settings.nlp_sidecar_url}/v1/embed/bge-m3").mock(
        return_value=Response(
            200,
            json={
                "embeddings": [
                    {
                        "dense": [0.02] * 1024,
                        "sparse": {"indices": [10, 20], "values": [0.5, 0.8]},
                    }
                ]
            },
        )
    )


async def _create_test_asset(
    session, data: bytes = b"test-audio-idempotency"
) -> tuple[str, uuid.UUID]:
    sha256 = blob_nvme.put(data)
    asset = Asset(
        sha256=sha256,
        asset_type="audio",
        mime_type="audio/wav",
        size_bytes=len(data),
        station_code="CI01",
        sanctuary_id="channel-islands",
    )
    job = PipelineJob(asset_sha256=sha256, status="pending")
    session.add(asset)
    session.add(job)
    await session.commit()
    return sha256, job.job_id


@pytest.mark.asyncio
@respx.mock
async def test_pipeline_interrupted_at_stage_resumes_idempotently(db_session):
    settings = get_settings()
    _mock_sidecars(settings)

    # Allow live Qdrant calls to pass through
    qdrant_url = urlparse(settings.qdrant_url)
    respx.route(host=qdrant_url.hostname).pass_through()

    sha256, job_id = await _create_test_asset(db_session)

    # 1. Complete preprocess and speech stages
    await stages.run_preprocess_stage(db_session, job_id=job_id, asset_sha256=sha256)
    await stages.run_speech_stage(db_session, job_id=job_id, asset_sha256=sha256)
    await db_session.commit()

    assert await is_stage_complete(db_session, asset_sha256=sha256, stage_name="preprocess")
    assert await is_stage_complete(db_session, asset_sha256=sha256, stage_name="speech")

    # 2. Simulate failure during acoustic stage
    job = await db_session.get(PipelineJob, job_id)
    job.status = "failed"
    job.current_stage = "acoustic"
    fail_run = PipelineStageRun(
        job_id=job_id,
        asset_sha256=sha256,
        stage_name="acoustic",
        status="failed",
        error_detail="Chaos injection: AST worker memory pressure simulated failure",
    )
    db_session.add(fail_run)
    await db_session.commit()

    # 3. Resume the job inline
    resumed_job, stages_out = await resume_job(db_session, job_id=job_id, run_inline=True)

    assert resumed_job.status == "succeeded"

    # Verify all stages are completed
    for stage_name in ("preprocess", "speech", "acoustic", "nlp", "index", "seal"):
        assert await is_stage_complete(db_session, asset_sha256=sha256, stage_name=stage_name)

    # Verify PREMIS cryptographic seal chain
    chain_valid, error = await verify_chain(db_session, object_sha256=sha256)
    assert chain_valid is True
    assert error is None

    # 4. Resuming an already succeeded job must raise JobAlreadyCompleteError
    with pytest.raises(JobAlreadyCompleteError):
        await resume_job(db_session, job_id=job_id)


def test_deterministic_qdrant_point_ids_prevent_duplicates():
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    id1 = qdrant_repo.deterministic_point_id(asset_sha256=sha, segment_index=0, model_version="v1")
    id2 = qdrant_repo.deterministic_point_id(asset_sha256=sha, segment_index=0, model_version="v1")
    id3 = qdrant_repo.deterministic_point_id(asset_sha256=sha, segment_index=1, model_version="v1")

    assert id1 == id2
    assert id1 != id3
    assert isinstance(id1, str)
    assert uuid.UUID(id1)  # must be a valid UUID for Qdrant point IDs
