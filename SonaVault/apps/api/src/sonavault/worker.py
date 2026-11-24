"""RQ worker entrypoint. Reuses the api image (0 GB delta).

Usage: python -m sonavault.worker <queue-name> [<queue-name> ...]
Dedicated queues: ingest-cpu, gpu-speech, gpu-nlp, fixity-audit.
gpu-speech/gpu-nlp run with concurrency 1 per the GPU unified-memory budget.
"""

import asyncio
import sys
import uuid

from redis import Redis
from rq import Worker

from sonavault.config import get_settings


def process_pipeline_job(job_id_str: str, asset_sha256: str) -> None:
    """RQ synchronous job entrypoint that executes the async pipeline orchestrator."""
    from sonavault.core.pipeline.orchestrator import execute_pipeline
    from sonavault.db import SessionLocal

    async def _run():
        async with SessionLocal() as session:
            await execute_pipeline(session, job_id=uuid.UUID(job_id_str), asset_sha256=asset_sha256)

    asyncio.run(_run())


def main() -> None:
    settings = get_settings()
    queues = sys.argv[1:] or ["ingest-cpu"]
    connection = Redis.from_url(settings.redis_url)
    worker = Worker(queues, connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
