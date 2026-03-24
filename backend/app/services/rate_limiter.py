"""Simple Redis-based rate limiter."""
import logging
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


async def check_rate_limit(
    key: str, max_attempts: int = 5, window_seconds: int = 900
) -> None:
    """Check rate limit for a given key. Raises 429 if exceeded."""
    try:
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL)
        redis_key = f"rate_limit:{key}"

        current = r.get(redis_key)
        if current is not None and int(current) >= max_attempts:
            ttl = r.ttl(redis_key)
            r.close()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {ttl} seconds.",
            )

        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds)
        pipe.execute()
        r.close()

    except HTTPException:
        raise
    except Exception as e:
        # If Redis is down, allow the request (fail open)
        logger.warning(f"Rate limiter error (allowing request): {e}")
