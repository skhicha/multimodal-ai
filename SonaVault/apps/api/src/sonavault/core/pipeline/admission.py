"""Admission control & idempotency for the 7-stage pipeline.

Pre-execution checkpoint check: a stage is skipped if a PipelineStageRun row
already exists with status SUCCEEDED for (asset_sha256, stage_name,
pipeline_version) — this is what makes resuming after a mid-stage worker
kill or a GPU 503 safe to simply re-run from the top: every already-completed
stage is a fast no-op, not re-executed work.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.models.pipeline import PipelineStageRun

PIPELINE_VERSION = "v1"
STAGE_ORDER = ("preprocess", "speech", "acoustic", "nlp", "index", "seal")


async def get_stage_run(
    session: AsyncSession,
    *,
    asset_sha256: str,
    stage_name: str,
    pipeline_version: str = PIPELINE_VERSION,
) -> PipelineStageRun | None:
    result = await session.execute(
        select(PipelineStageRun).where(
            PipelineStageRun.asset_sha256 == asset_sha256,
            PipelineStageRun.stage_name == stage_name,
            PipelineStageRun.pipeline_version == pipeline_version,
        )
    )
    return result.scalar_one_or_none()


async def is_stage_complete(
    session: AsyncSession,
    *,
    asset_sha256: str,
    stage_name: str,
    pipeline_version: str = PIPELINE_VERSION,
) -> bool:
    run = await get_stage_run(
        session, asset_sha256=asset_sha256, stage_name=stage_name, pipeline_version=pipeline_version
    )
    return run is not None and run.status == "succeeded"


async def start_stage(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    asset_sha256: str,
    stage_name: str,
    pipeline_version: str = PIPELINE_VERSION,
) -> PipelineStageRun:
    run = await get_stage_run(
        session, asset_sha256=asset_sha256, stage_name=stage_name, pipeline_version=pipeline_version
    )
    if run is None:
        run = PipelineStageRun(
            job_id=job_id,
            asset_sha256=asset_sha256,
            stage_name=stage_name,
            pipeline_version=pipeline_version,
            attempt_count=0,
        )
        session.add(run)
    run.status = "running"
    run.attempt_count = (run.attempt_count or 0) + 1
    run.started_at = datetime.now(UTC)
    run.error_detail = None
    await session.flush()
    return run


async def complete_stage(
    session: AsyncSession, *, run: PipelineStageRun, output_sha256: str | None = None
) -> None:
    run.status = "succeeded"
    run.output_sha256 = output_sha256
    run.finished_at = datetime.now(UTC)
    await session.flush()


async def fail_stage(session: AsyncSession, *, run: PipelineStageRun, error_detail: str) -> None:
    run.status = "failed"
    run.error_detail = error_detail
    run.finished_at = datetime.now(UTC)
    await session.flush()


def next_stage(current: str | None) -> str | None:
    if current is None:
        return STAGE_ORDER[0]
    try:
        idx = STAGE_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(STAGE_ORDER):
        return None
    return STAGE_ORDER[idx + 1]
