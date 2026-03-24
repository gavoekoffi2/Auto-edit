"""Async Redis-based rate limiter."""
import logging
from fastapi import HTTPException, status
from redis.asyncio import from_url as redis_from_url

from app.config import settings

logger = logging.getLogger(__name__)

# Reusable async Redis connection
_redis_client = None


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

        current = await r.get(redis_key)
        if current is not None and int(current) >= max_attempts:
            ttl = await r.ttl(redis_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {ttl} seconds.",
            )

        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds)
        await pipe.execute()

    except HTTPException:
        raise
    except Exception as e:
        # If Redis is down, allow the request (fail open)
        logger.warning(f"Rate limiter error (allowing request): {e}")
