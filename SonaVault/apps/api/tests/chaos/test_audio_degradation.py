import uuid

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy import select

from sonavault.adapters.storage import blob_nvme
from sonavault.config import get_settings
from sonavault.core.pipeline import stages
from sonavault.models.assets import Asset
from sonavault.models.pipeline import PipelineJob, PipelineStageRun

pytestmark = pytest.mark.asyncio


async def _make_asset_with_bytes(
    session, data: bytes, mime: str = "audio/wav"
) -> tuple[str, uuid.UUID]:
    sha256 = blob_nvme.put(data)
    asset = Asset(
        sha256=sha256,
        asset_type="audio",
        mime_type=mime,
        size_bytes=len(data),
        station_code="CI01",
        sanctuary_id="channel-islands",
    )
    job = PipelineJob(asset_sha256=sha256, status="pending")
    session.add(asset)
    session.add(job)
    await session.commit()
    return sha256, job.job_id


async def test_zeroed_audio_buffer_handled_safely(db_session):
    # Pure zeroed PCM buffer (silence)
    zero_bytes = b"\x00" * 64000
    sha256, job_id = await _make_asset_with_bytes(db_session, zero_bytes)

    # Preprocessing stage must complete without division by zero
    await stages.run_preprocess_stage(db_session, job_id=job_id, asset_sha256=sha256)

    run = (
        await db_session.execute(
            select(PipelineStageRun).where(
                PipelineStageRun.asset_sha256 == sha256,
                PipelineStageRun.stage_name == "preprocess",
            )
        )
    ).scalar_one()
    assert run.status == "succeeded"


@respx.mock
async def test_clipped_audio_with_dc_offset(db_session):
    settings = get_settings()
    # High-amplitude square wave clipping at +/- 32767 with large DC offset
    clipped_bytes = (b"\xff\x7f" * 1000) + (b"\x00\x80" * 1000)
    sha256, job_id = await _make_asset_with_bytes(db_session, clipped_bytes)

    respx.post(f"{settings.speech_sidecar_url}/v1/transcribe").mock(
        return_value=Response(
            200,
            json={"segments": [], "detected_language": "en"},
        )
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/diarize").mock(
        return_value=Response(200, json={"turns": []})
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/events/ast").mock(
        return_value=Response(200, json={"events": []})
    )

    await stages.run_speech_stage(db_session, job_id=job_id, asset_sha256=sha256)

    run = (
        await db_session.execute(
            select(PipelineStageRun).where(
                PipelineStageRun.asset_sha256 == sha256,
                PipelineStageRun.stage_name == "speech",
            )
        )
    ).scalar_one()
    assert run.status == "succeeded"


@respx.mock
async def test_corrupted_non_wav_buffer_rejected_by_sidecar(db_session):
    settings = get_settings()
    corrupt_bytes = b"CORRUPTED_NON_AUDIO_HEADER_PAYLOAD_XX" * 50
    sha256, job_id = await _make_asset_with_bytes(db_session, corrupt_bytes)

    respx.post(f"{settings.speech_sidecar_url}/v1/transcribe").mock(
        return_value=Response(
            422,
            text="Unprocessable Audio: Corrupt RIFF header or invalid format",
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await stages.run_speech_stage(db_session, job_id=job_id, asset_sha256=sha256)

    run = (
        await db_session.execute(
            select(PipelineStageRun).where(
                PipelineStageRun.asset_sha256 == sha256,
                PipelineStageRun.stage_name == "speech",
            )
        )
    ).scalar_one()
    assert run.status == "failed"
    assert "422" in run.error_detail or "Unprocessable" in run.error_detail
