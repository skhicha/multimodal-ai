import uuid

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy import select

from sonavault.adapters.sidecars import vllm_client
from sonavault.adapters.storage import blob_nvme
from sonavault.config import get_settings
from sonavault.core.pipeline import stages
from sonavault.models.acoustics import TranscriptSegment
from sonavault.models.assets import Asset
from sonavault.models.pipeline import PipelineJob, PipelineStageRun
from sonavault.slices.telemetry import gb10_collector

pytestmark = pytest.mark.asyncio


async def _create_test_audio_asset(
    session, audio_bytes: bytes = b"dummy-riff-wave-data"
) -> tuple[str, uuid.UUID]:
    sha256 = blob_nvme.put(audio_bytes)
    asset = Asset(
        sha256=sha256,
        asset_type="audio",
        mime_type="audio/wav",
        size_bytes=len(audio_bytes),
        station_code="CI01",
        sanctuary_id="channel-islands",
    )
    job = PipelineJob(asset_sha256=sha256, status="running")
    session.add(asset)
    session.add(job)
    await session.flush()
    return sha256, job.job_id


@respx.mock
async def test_speech_sidecar_timeout_marks_stage_failed(db_session):
    settings = get_settings()
    respx.post(f"{settings.speech_sidecar_url}/v1/transcribe").mock(
        side_effect=httpx.TimeoutException("Read timed out from speech-audio-gpu sidecar")
    )

    sha256, job_id = await _create_test_audio_asset(db_session)

    with pytest.raises(httpx.TimeoutException):
        await stages.run_speech_stage(db_session, job_id=job_id, asset_sha256=sha256)

    # Verify stage run was recorded as failed with error detail
    result = await db_session.execute(
        select(PipelineStageRun).where(
            PipelineStageRun.asset_sha256 == sha256,
            PipelineStageRun.stage_name == "speech",
        )
    )
    stage_run = result.scalar_one_or_none()
    assert stage_run is not None
    assert stage_run.status == "failed"
    assert "timed out" in stage_run.error_detail


@respx.mock
async def test_nlp_sidecar_503_service_unavailable(db_session):
    settings = get_settings()
    respx.post(f"{settings.nlp_sidecar_url}/v1/ner/gliner").mock(
        return_value=Response(503, text="Service Unavailable: GPU memory saturation")
    )

    sha256, job_id = await _create_test_audio_asset(db_session)

    # Seed a transcript segment to trigger NLP stage
    segment = TranscriptSegment(
        asset_sha256=sha256,
        seg_index=0,
        start_sec=0.0,
        end_sec=3.0,
        speaker_label="SPEAKER_00",
        source_lang="en",
        text_redacted="Observer reports vessel spotted near MPA boundary",
        model_version="v1",
    )
    db_session.add(segment)
    await db_session.flush()

    with pytest.raises(httpx.HTTPStatusError):
        await stages.run_nlp_stage(db_session, job_id=job_id, asset_sha256=sha256)

    result = await db_session.execute(
        select(PipelineStageRun).where(
            PipelineStageRun.asset_sha256 == sha256,
            PipelineStageRun.stage_name == "nlp",
        )
    )
    stage_run = result.scalar_one_or_none()
    assert stage_run is not None
    assert stage_run.status == "failed"
    assert "503" in stage_run.error_detail or "Service Unavailable" in stage_run.error_detail


@respx.mock
async def test_vllm_client_handles_network_failure():
    settings = get_settings()
    respx.post(f"{settings.vllm_base_url}/v1/chat/completions").mock(
        return_value=Response(502, text="Bad Gateway: vLLM engine initializing")
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        generator = vllm_client.stream_chat_completion(
            messages=[{"role": "user", "content": "Generate briefing"}]
        )
        await anext(generator)

    assert exc_info.value.response.status_code == 502


@respx.mock
async def test_telemetry_resilience_when_all_sidecars_unreachable():
    settings = get_settings()
    respx.get(f"{settings.speech_sidecar_url}/healthz").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    respx.get(f"{settings.nlp_sidecar_url}/healthz").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    respx.get(f"{settings.vllm_base_url}/health").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    respx.get(f"{settings.vllm_base_url}/metrics").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    respx.get(f"{settings.qdrant_url}/healthz").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    summary = await gb10_collector.get_health_summary()
    assert summary.status == "critical"
    assert summary.sidecars_total >= 3
    for sidecar in summary.details:
        assert sidecar.healthy is False

    telemetry = await gb10_collector.collect_full_telemetry()
    assert telemetry.unified_memory.total_bytes > 0


@respx.mock
async def test_sidecar_transient_failure_and_recovery(db_session):
    settings = get_settings()
    sha256, job_id = await _create_test_audio_asset(db_session)

    # Call 1 fails with 503
    route = respx.post(f"{settings.speech_sidecar_url}/v1/transcribe")
    route.side_effect = [
        Response(503, text="Temporarily Unavailable"),
        Response(
            200,
            json={
                "segments": [
                    {
                        "start_sec": 0.0,
                        "end_sec": 2.5,
                        "text": "Recovered audio transcript",
                        "language": "en",
                    }
                ],
                "detected_language": "en",
            },
        ),
    ]
    respx.post(f"{settings.speech_sidecar_url}/v1/diarize").mock(
        return_value=Response(200, json={"turns": []})
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/events/ast").mock(
        return_value=Response(200, json={"events": []})
    )

    # First attempt fails
    with pytest.raises(httpx.HTTPStatusError):
        await stages.run_speech_stage(db_session, job_id=job_id, asset_sha256=sha256)

    # Reset failed stage to re-attempt
    stage_run = (
        await db_session.execute(
            select(PipelineStageRun).where(
                PipelineStageRun.asset_sha256 == sha256,
                PipelineStageRun.stage_name == "speech",
            )
        )
    ).scalar_one()
    stage_run.status = "pending"
    await db_session.commit()

    # Second attempt succeeds
    await stages.run_speech_stage(db_session, job_id=job_id, asset_sha256=sha256)

    stage_run_after = (
        await db_session.execute(
            select(PipelineStageRun).where(
                PipelineStageRun.asset_sha256 == sha256,
                PipelineStageRun.stage_name == "speech",
            )
        )
    ).scalar_one()
    assert stage_run_after.status == "succeeded"
