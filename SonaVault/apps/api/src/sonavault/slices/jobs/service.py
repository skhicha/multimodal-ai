import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.pipeline.admission import STAGE_ORDER
from sonavault.models.pipeline import PipelineJob, PipelineStageRun

StageByName = dict[str, PipelineStageRun]


class JobNotFoundError(Exception):
    pass


class JobAlreadyCompleteError(Exception):
    pass


async def _stage_runs_by_name(db: AsyncSession, *, job_id: uuid.UUID) -> StageByName:
    result = await db.execute(select(PipelineStageRun).where(PipelineStageRun.job_id == job_id))
    return {s.stage_name: s for s in result.scalars()}


async def list_jobs(
    db: AsyncSession, *, asset_sha256: str | None, limit: int
) -> list[tuple[PipelineJob, StageByName]]:
    query = select(PipelineJob).order_by(PipelineJob.created_at.desc()).limit(min(limit, 200))
    if asset_sha256:
        query = query.where(PipelineJob.asset_sha256 == asset_sha256)
    result = await db.execute(query)
    jobs = list(result.scalars())
    return [(job, await _stage_runs_by_name(db, job_id=job.job_id)) for job in jobs]


async def get_job(db: AsyncSession, *, job_id: uuid.UUID) -> tuple[PipelineJob, StageByName]:
    job = await db.get(PipelineJob, job_id)
    if job is None:
        raise JobNotFoundError(f"Job {job_id} not found")
    return job, await _stage_runs_by_name(db, job_id=job_id)


def _first_incomplete_stage(stage_by_name: StageByName) -> str | None:
    for name in STAGE_ORDER:
        run = stage_by_name.get(name)
        if run is None or run.status != "succeeded":
            return name
    return None


async def resume_job(
    db: AsyncSession, *, job_id: uuid.UUID, run_inline: bool = False
) -> tuple[PipelineJob, StageByName]:
    """Re-enqueues the job from its first non-succeeded stage. Admission
    control (core.pipeline.admission) guarantees already-succeeded stages are
    skipped as fast no-ops rather than re-executed."""
    job, stage_by_name = await get_job(db, job_id=job_id)
    if job.status == "succeeded":
        raise JobAlreadyCompleteError(f"Job {job_id} already completed")

    resume_from = _first_incomplete_stage(stage_by_name)
    if resume_from is None:
        job.status = "succeeded"
        await db.commit()
        return job, stage_by_name

    job.status = "pending"
    job.current_stage = resume_from
    await db.commit()

    if run_inline:
        from sonavault.core.pipeline.orchestrator import execute_pipeline

        await execute_pipeline(db, job_id=job.job_id, asset_sha256=job.asset_sha256)
        job, stage_by_name = await get_job(db, job_id=job_id)

    return job, stage_by_name
