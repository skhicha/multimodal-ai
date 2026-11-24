import uuid

import pytest

from sonavault.core.pipeline import admission
from sonavault.db import SessionLocal
from sonavault.models.assets import Asset
from sonavault.models.pipeline import PipelineJob


async def _make_asset_and_job(session) -> tuple[str, uuid.UUID]:
    sha256 = uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars, unique per test
    session.add(Asset(sha256=sha256, asset_type="audio", mime_type="audio/wav", size_bytes=100))
    job = PipelineJob(asset_sha256=sha256)
    session.add(job)
    await session.flush()
    return sha256, job.job_id


@pytest.mark.asyncio
async def test_stage_not_complete_before_running():
    async with SessionLocal() as session:
        sha256, _ = await _make_asset_and_job(session)
        assert not await admission.is_stage_complete(
            session, asset_sha256=sha256, stage_name="preprocess"
        )


@pytest.mark.asyncio
async def test_start_complete_marks_stage_succeeded():
    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session)
        run = await admission.start_stage(
            session, job_id=job_id, asset_sha256=sha256, stage_name="preprocess"
        )
        assert run.status == "running"
        assert run.attempt_count == 1

        await admission.complete_stage(session, run=run, output_sha256=sha256)
        await session.commit()

        assert await admission.is_stage_complete(
            session, asset_sha256=sha256, stage_name="preprocess"
        )


@pytest.mark.asyncio
async def test_admission_control_skips_already_succeeded_stage():
    """Simulates a pipeline resume after a worker kill: re-running a
    succeeded stage must be detected as already-done, not re-executed."""
    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session)
        run = await admission.start_stage(
            session, job_id=job_id, asset_sha256=sha256, stage_name="speech"
        )
        await admission.complete_stage(session, run=run)
        await session.commit()

        # Resume logic checks admission before doing any GPU work:
        already_done = await admission.is_stage_complete(
            session, asset_sha256=sha256, stage_name="speech"
        )
        assert already_done is True


@pytest.mark.asyncio
async def test_failed_stage_can_be_retried_and_increments_attempt_count():
    async with SessionLocal() as session:
        sha256, job_id = await _make_asset_and_job(session)
        run1 = await admission.start_stage(
            session, job_id=job_id, asset_sha256=sha256, stage_name="nlp"
        )
        await admission.fail_stage(session, run=run1, error_detail="GPU 503")
        await session.commit()

        assert not await admission.is_stage_complete(session, asset_sha256=sha256, stage_name="nlp")

        run2 = await admission.start_stage(
            session, job_id=job_id, asset_sha256=sha256, stage_name="nlp"
        )
        assert run2.attempt_count == 2
        assert run2.error_detail is None  # cleared on restart
        assert run2.id == run1.id  # same row, not a duplicate (unique constraint)


def test_next_stage_ordering():
    assert admission.next_stage(None) == "preprocess"
    assert admission.next_stage("preprocess") == "speech"
    assert admission.next_stage("speech") == "acoustic"
    assert admission.next_stage("acoustic") == "nlp"
    assert admission.next_stage("nlp") == "index"
    assert admission.next_stage("index") == "seal"
    assert admission.next_stage("seal") is None
