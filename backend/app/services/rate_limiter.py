"""Async Redis-based rate limiter with atomic increment."""
import logging
from fastapi import HTTPException, status
from redis.asyncio import from_url as redis_from_url

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client = None

# Atomic Lua script: increment and set TTL only on first key creation.
# Returns [current_count, ttl].
_LUA_INCR = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


async def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_from_url(settings.REDIS_URL)
    return _redis_client


async def check_rate_limit(
    key: str, max_attempts: int = 5, window_seconds: int = 900
) -> None:
    """Check rate limit for a given key. Raises 429 if exceeded."""
    try:
        r = await _get_redis()
        redis_key = f"rate_limit:{key}"

        count, ttl = await r.eval(_LUA_INCR, 1, redis_key, window_seconds)

        if int(count) > max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {max(1, int(ttl))} seconds.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Rate limiter error (allowing request): %s", e)
