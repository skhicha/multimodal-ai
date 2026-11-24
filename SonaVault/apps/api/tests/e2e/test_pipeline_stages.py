import uuid

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy import select

from sonavault.adapters.storage import blob_nvme
from sonavault.config import get_settings
from sonavault.core.pipeline import stages
from sonavault.core.pipeline.admission import is_stage_complete
from sonavault.core.provenance.ledger import verify_chain
from sonavault.db import SessionLocal
from sonavault.models.acoustics import AcousticEvent, TranscriptSegment
from sonavault.models.assets import Asset
from sonavault.models.pipeline import PipelineJob

pytestmark = pytest.mark.asyncio


async def _make_asset_and_job(session, *, audio_bytes: bytes) -> tuple[str, uuid.UUID]:
    sha256 = blob_nvme.put(audio_bytes)
    session.add(
        Asset(sha256=sha256, asset_type="audio", mime_type="audio/wav", size_bytes=len(audio_bytes))
    )
    job = PipelineJob(asset_sha256=sha256)
    session.add(job)
    await session.flush()
    return sha256, job.job_id


@respx.mock
async def test_speech_stage_persists_segments_with_speaker_overlap_match():
    settings = get_settings()
    respx.post(f"{settings.speech_sidecar_url}/v1/transcribe").mock(
        return_value=Response(
            200,
            json={
                "segments": [
                    {"start_sec": 0.0, "end_sec": 2.0, "text": "First segment", "language": "en"},
                    {"start_sec": 2.0, "end_sec": 4.0, "text": "Second segment", "language": "en"},
                ],
                "detected_language": "en",
            },
        )
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/diarize").mock(
        return_value=Response(
            200,
            json={
                "turns": [
                    {"start_sec": 0.0, "end_sec": 2.0, "speaker_label": "SPEAKER_00"},
                    {"start_sec": 2.0, "end_sec": 4.0, "speaker_label": "SPEAKER_01"},
                ]
            },
        )
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/events/ast").mock(
        return_value=Response(
            200,
            json={
                "events": [
                    {
                        "window_start_sec": 0.0,
                        "window_end_sec": 10.24,
                        "labels": {"Whale vocalization": 0.9, "Engine noise": 0.1},
                    }
                ]
            },
        )
    )

    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session, audio_bytes=b"speech-stage-test-audio")
        await session.commit()

        await stages.run_speech_stage(session, job_id=job_id, asset_sha256=sha256)
        await session.commit()

        result = await session.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.asset_sha256 == sha256)
            .order_by(TranscriptSegment.seg_index)
        )
        segments = result.scalars().all()
        assert len(segments) == 2
        assert segments[0].speaker_label == "SPEAKER_00"
        assert segments[1].speaker_label == "SPEAKER_01"
        assert segments[0].text_redacted == "First segment"

        result2 = await session.execute(
            select(AcousticEvent).where(AcousticEvent.asset_sha256 == sha256)
        )
        events = result2.scalars().all()
        assert events[0].audioset_label == "Whale vocalization"
        assert events[0].confidence == 0.9

        assert await is_stage_complete(session, asset_sha256=sha256, stage_name="speech")


@respx.mock
async def test_speech_stage_admission_control_skips_rerun():
    """A second call after success must not re-hit the sidecar at all."""
    settings = get_settings()
    route = respx.post(f"{settings.speech_sidecar_url}/v1/transcribe").mock(
        return_value=Response(200, json={"segments": [], "detected_language": "en"})
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/diarize").mock(
        return_value=Response(200, json={"turns": []})
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/events/ast").mock(
        return_value=Response(200, json={"events": []})
    )

    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session, audio_bytes=b"admission-skip-test")
        await session.commit()

        await stages.run_speech_stage(session, job_id=job_id, asset_sha256=sha256)
        await session.commit()
        assert route.call_count == 1

        await stages.run_speech_stage(session, job_id=job_id, asset_sha256=sha256)
        await session.commit()
        assert route.call_count == 1  # unchanged: admission control skipped it


@respx.mock
async def test_speech_stage_marks_failed_on_sidecar_error():
    settings = get_settings()
    respx.post(f"{settings.speech_sidecar_url}/v1/transcribe").mock(return_value=Response(503))

    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session, audio_bytes=b"failure-test-audio")
        await session.commit()

        with pytest.raises(httpx.HTTPStatusError):
            await stages.run_speech_stage(session, job_id=job_id, asset_sha256=sha256)
        await session.commit()

        assert not await is_stage_complete(session, asset_sha256=sha256, stage_name="speech")


@respx.mock
async def test_nlp_stage_redacts_pii_without_corrupting_surrounding_text():
    settings = get_settings()
    respx.post(f"{settings.nlp_sidecar_url}/v1/ner/gliner").mock(
        return_value=Response(
            200,
            json={
                "entities": [
                    {
                        "text": "555-1234",
                        "label": "phone_number",
                        "start": 21,
                        "end": 29,
                        "score": 0.9,
                    }
                ]
            },
        )
    )

    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session, audio_bytes=b"nlp-stage-test-audio")
        session.add(
            TranscriptSegment(
                asset_sha256=sha256,
                seg_index=0,
                start_sec=0.0,
                end_sec=1.0,
                text_redacted="Call the observer at 555-1234 now",
                model_version="v1",
            )
        )
        await session.commit()

        await stages.run_nlp_stage(session, job_id=job_id, asset_sha256=sha256)
        await session.commit()

        result = await session.execute(
            select(TranscriptSegment).where(TranscriptSegment.asset_sha256 == sha256)
        )
        seg = result.scalar_one()
        assert seg.text_redacted == "Call the observer at [REDACTED] now"


@respx.mock
async def test_nlp_stage_redacts_multiple_entities_in_correct_order():
    """Redaction must process entities back-to-front so earlier offsets
    aren't invalidated by shrinking/growing the string from a later edit."""
    settings = get_settings()
    text = "Alice called Bob about the sighting"
    respx.post(f"{settings.nlp_sidecar_url}/v1/ner/gliner").mock(
        return_value=Response(
            200,
            json={
                "entities": [
                    {"text": "Alice", "label": "person_name", "start": 0, "end": 5, "score": 0.95},
                    {"text": "Bob", "label": "person_name", "start": 13, "end": 16, "score": 0.95},
                ]
            },
        )
    )

    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session, audio_bytes=b"multi-entity-test-audio")
        session.add(
            TranscriptSegment(
                asset_sha256=sha256,
                seg_index=0,
                start_sec=0.0,
                end_sec=1.0,
                text_redacted=text,
                model_version="v1",
            )
        )
        await session.commit()

        await stages.run_nlp_stage(session, job_id=job_id, asset_sha256=sha256)
        await session.commit()

        result = await session.execute(
            select(TranscriptSegment).where(TranscriptSegment.asset_sha256 == sha256)
        )
        seg = result.scalar_one()
        assert seg.text_redacted == "[REDACTED] called [REDACTED] about the sighting"


async def test_seal_stage_appends_provenance_event_and_is_idempotent():
    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session, audio_bytes=b"seal-stage-test-audio")
        await session.commit()

        await stages.run_seal_stage(session, job_id=job_id, asset_sha256=sha256)
        await stages.run_seal_stage(session, job_id=job_id, asset_sha256=sha256)  # no-op on resume
        await session.commit()

        valid, broken_at = await verify_chain(session, sha256)
        assert valid
        assert broken_at is None


@respx.mock
async def test_acoustic_stage_stores_clap_embedding():
    settings = get_settings()
    respx.post(f"{settings.speech_sidecar_url}/v1/events/ast").mock(
        return_value=Response(
            200,
            json={
                "events": [
                    {
                        "window_start_sec": 0.0,
                        "window_end_sec": 10.24,
                        "labels": {"Humpback whale": 0.85},
                    }
                ]
            },
        )
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/embed/clap-audio").mock(
        return_value=Response(200, json={"embedding": [0.05] * 512})
    )

    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session, audio_bytes=b"acoustic-clap-audio")
        await session.commit()

        await stages.run_acoustic_stage(session, job_id=job_id, asset_sha256=sha256)
        await session.commit()

        assert await is_stage_complete(session, asset_sha256=sha256, stage_name="acoustic")
        asset = await session.get(Asset, sha256)
        assert asset.extra_metadata is not None
        assert len(asset.extra_metadata["clap_embedding"]) == 512


@respx.mock
async def test_orchestrator_executes_all_stages(monkeypatch):
    from sonavault.adapters.vector import qdrant_repo
    from sonavault.core.pipeline.orchestrator import execute_pipeline

    async def _mock_ensure():
        pass

    async def _mock_upsert(coll, pts):
        pass

    monkeypatch.setattr(qdrant_repo, "ensure_collections", _mock_ensure)
    monkeypatch.setattr(qdrant_repo, "upsert", _mock_upsert)

    settings = get_settings()
    respx.post(f"{settings.speech_sidecar_url}/v1/transcribe").mock(
        return_value=Response(
            200,
            json={
                "segments": [
                    {
                        "start_sec": 0.0,
                        "end_sec": 2.0,
                        "text": "Ship spotted at station OC02",
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
            json={"turns": [{"start_sec": 0.0, "end_sec": 2.0, "speaker_label": "SPEAKER_00"}]},
        )
    )
    respx.post(f"{settings.speech_sidecar_url}/v1/events/ast").mock(
        return_value=Response(
            200,
            json={
                "events": [
                    {
                        "window_start_sec": 0.0,
                        "window_end_sec": 10.24,
                        "labels": {"Speech": 0.9},
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
                    {"dense": [0.01] * 1024, "sparse": {"indices": [1], "values": [0.5]}}
                ]
            },
        )
    )

    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(
            session, audio_bytes=b"orchestrator-full-flow-audio"
        )
        await session.commit()

        job = await execute_pipeline(session, job_id=job_id, asset_sha256=sha256)
        assert job.status == "succeeded"
        assert job.current_stage == "seal"
