"""Production Redis/RQ adapter: 4 dedicated queues isolating CPU ingest work
from GPU-bound stages so one never starves another.

- ingest-cpu: Stage 0/1 (fixity, geo-QA, FFmpeg prep, Document AI)
- gpu-speech: Stage 2 (speech-audio-gpu) — capped at 1 concurrent job
- gpu-nlp:    Stage 3 (nlp-retrieval-gpu) — capped at 1 concurrent job
- fixity-audit: on-demand PREMIS fixity verification jobs
"""

from redis import Redis
from rq import Queue

from sonavault.config import get_settings

QUEUE_NAMES = ("ingest-cpu", "gpu-speech", "gpu-nlp", "fixity-audit")
GPU_QUEUES = ("gpu-speech", "gpu-nlp")

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url)
    return _redis


def get_queue(name: str) -> Queue:
    if name not in QUEUE_NAMES:
        raise ValueError(f"Unknown queue: {name}")
    return Queue(name, connection=get_redis())


def enqueue(queue_name: str, func, *args, **kwargs) -> str:
    queue = get_queue(queue_name)
    job = queue.enqueue(func, *args, **kwargs)
    return job.id


def queue_depth(name: str) -> int:
    return len(get_queue(name))
