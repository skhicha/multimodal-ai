from datetime import datetime

from pydantic import BaseModel


class StageRunOut(BaseModel):
    stage_name: str
    status: str
    attempt_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error_detail: str | None


class JobOut(BaseModel):
    job_id: str
    asset_sha256: str
    pipeline_version: str
    status: str
    current_stage: str | None
    created_at: datetime
    finished_at: datetime | None
    stages: list[StageRunOut] = []
