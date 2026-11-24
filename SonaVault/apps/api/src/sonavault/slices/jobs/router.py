import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.pipeline.admission import STAGE_ORDER
from sonavault.core.security.rbac import CurrentUser, require_min_tier
from sonavault.db import get_db
from sonavault.models.pipeline import PipelineJob
from sonavault.slices.jobs.schemas import JobOut, StageRunOut
from sonavault.slices.jobs.service import (
    JobAlreadyCompleteError,
    JobNotFoundError,
    StageByName,
    get_job,
    list_jobs,
    resume_job,
)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

_can_view = require_min_tier("field_contributor")


def _to_job_out(job: PipelineJob, stage_by_name: StageByName) -> JobOut:
    stages = [
        StageRunOut(
            stage_name=name,
            status=stage_by_name[name].status if name in stage_by_name else "pending",
            attempt_count=stage_by_name[name].attempt_count if name in stage_by_name else 0,
            started_at=stage_by_name[name].started_at if name in stage_by_name else None,
            finished_at=stage_by_name[name].finished_at if name in stage_by_name else None,
            error_detail=stage_by_name[name].error_detail if name in stage_by_name else None,
        )
        for name in STAGE_ORDER
    ]
    return JobOut(
        job_id=str(job.job_id),
        asset_sha256=job.asset_sha256,
        pipeline_version=job.pipeline_version,
        status=job.status,
        current_stage=job.current_stage,
        created_at=job.created_at,
        finished_at=job.finished_at,
        stages=stages,
    )


@router.get("", response_model=list[JobOut])
async def get_jobs(
    asset_sha256: str | None = None,
    limit: int = 50,
    user: CurrentUser = Depends(_can_view),
    db: AsyncSession = Depends(get_db),
):
    jobs = await list_jobs(db, asset_sha256=asset_sha256, limit=limit)
    return [_to_job_out(job, stages) for job, stages in jobs]


@router.get("/{job_id}", response_model=JobOut)
async def get_single_job(
    job_id: uuid.UUID, user: CurrentUser = Depends(_can_view), db: AsyncSession = Depends(get_db)
):
    try:
        job, stages = await get_job(db, job_id=job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _to_job_out(job, stages)


@router.post("/{job_id}/resume", response_model=JobOut)
async def resume(
    job_id: uuid.UUID,
    run_inline: bool = False,
    user: CurrentUser = Depends(_can_view),
    db: AsyncSession = Depends(get_db),
):
    try:
        job, stages = await resume_job(db, job_id=job_id, run_inline=run_inline)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except JobAlreadyCompleteError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _to_job_out(job, stages)
