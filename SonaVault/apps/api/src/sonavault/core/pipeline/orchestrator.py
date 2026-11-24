"""Pipeline orchestrator for executing SonaVault's 7-stage resumable ingestion pipeline.

Orchestrates sequential execution of stages per STAGE_ORDER:
  preprocess -> speech -> acoustic -> nlp -> index -> seal

Features:
- Checkpoint admission control: already succeeded stages are skipped as no-ops
- Resilient error handling: stage failure updates PipelineJob.status = 'failed'
- Auto-resume from failure point
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.core.pipeline import stages
from sonavault.core.pipeline.admission import STAGE_ORDER, is_stage_complete
from sonavault.models.pipeline import PipelineJob

logger = logging.getLogger("sonavault.pipeline")

STAGE_DISPATCH = {
    "preprocess": stages.run_preprocess_stage,
    "speech": stages.run_speech_stage,
    "acoustic": stages.run_acoustic_stage,
    "nlp": stages.run_nlp_stage,
    "index": stages.run_index_stage,
    "seal": stages.run_seal_stage,
}


async def execute_pipeline(
    session: AsyncSession, *, job_id: uuid.UUID, asset_sha256: str
) -> PipelineJob:
    """Executes the pipeline stages sequentially for a given job.
    Idempotent: resumes from the first incomplete stage.
    """
    job = await session.get(PipelineJob, job_id)
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    job.status = "running"
    await session.commit()

    for stage_name in STAGE_ORDER:
        if await is_stage_complete(session, asset_sha256=asset_sha256, stage_name=stage_name):
            logger.info("Stage %s already completed for %s, skipping", stage_name, asset_sha256)
            continue

        job.current_stage = stage_name
        await session.commit()

        executor = STAGE_DISPATCH.get(stage_name)
        if executor is None:
            raise RuntimeError(f"Unknown stage: {stage_name}")

        try:
            await executor(session, job_id=job_id, asset_sha256=asset_sha256)
            await session.commit()
        except Exception as exc:
            logger.error(
                "Pipeline stage %s failed for job %s: %s", stage_name, job_id, exc, exc_info=True
            )
            job.status = "failed"
            job.current_stage = stage_name
            await session.commit()
            raise

    job.status = "succeeded"
    job.finished_at = datetime.now(UTC)
    await session.commit()
    return job
