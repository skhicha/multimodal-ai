"""Redis sliding-window rate limiting & progressive-delay account lockout.

- Per-account: 5 failed login/MFA attempts per 15-minute window, with
  progressive delays (1s, 2s, 4s, 8s, 16s) before temporary lockout.
- Per-IP: 20 req/min on /api/v1/auth/*, 120 req/min general API.
Returns HTTP 429 with Retry-After when exceeded.
"""

import time

import redis.asyncio as redis

from sonavault.config import get_settings

LOCKOUT_WINDOW_SECONDS = 15 * 60
MAX_ATTEMPTS = 5
PROGRESSIVE_DELAYS = [1, 2, 4, 8, 16]

AUTH_PATH_LIMIT_PER_MIN = 20
GENERAL_PATH_LIMIT_PER_MIN = 120

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def record_failed_attempt(key: str) -> tuple[int, float]:
    """Returns (attempt_count_in_window, required_delay_seconds)."""
    r = get_redis()
    redis_key = f"sv:lockout:{key}"
    pipe = r.pipeline()
    pipe.incr(redis_key)
    pipe.expire(redis_key, LOCKOUT_WINDOW_SECONDS)
    count, _ = await pipe.execute()
    count = int(count)
    delay_index = min(count, len(PROGRESSIVE_DELAYS)) - 1
    delay = PROGRESSIVE_DELAYS[max(delay_index, 0)]
    return count, delay


async def is_locked_out(key: str) -> bool:
    r = get_redis()
    count = await r.get(f"sv:lockout:{key}")
    return count is not None and int(count) >= MAX_ATTEMPTS


async def clear_lockout(key: str) -> None:
    r = get_redis()
    await r.delete(f"sv:lockout:{key}")


async def sliding_window_allow(*, bucket: str, limit_per_min: int) -> tuple[bool, int]:
    """Fixed 60s window counter. Returns (allowed, retry_after_seconds)."""
    r = get_redis()
    now_minute = int(time.time() // 60)
    redis_key = f"sv:ratelimit:{bucket}:{now_minute}"
    count = await r.incr(redis_key)
    if count == 1:
        await r.expire(redis_key, 60)
    if count > limit_per_min:
        ttl = await r.ttl(redis_key)
        return False, max(ttl, 1)
    return True, 0
