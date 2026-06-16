"""Async Redis-based rate limiter.

Politique d'erreur:
  - En **production**: fail-closed. Si Redis tombe, on retourne 503. Sinon
    n'importe quel attaquant peut brute-force login/signup en mettant
    Redis hors-ligne.
  - En **dev/staging**: fail-open avec warning, pour ne pas bloquer le dev.
"""
import logging
from fastapi import HTTPException, status
from redis.asyncio import from_url as redis_from_url
from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)


# Reusable async Redis connection
_redis_client: Redis | None = None


async def _get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_from_url(settings.REDIS_URL)
    return _redis_client


async def check_rate_limit(
    key: str, max_attempts: int = 5, window_seconds: int = 900
) -> None:
    """Check rate limit for a given key. Raises 429 if exceeded.

    En production, raise 503 si Redis est indisponible (fail-closed).
    En dev, on log un warning et on laisse passer.
    """
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

        # Atomic INCR + conditional EXPIRE via Lua: the TTL is set only on the
        # first attempt (when INCR returns 1). Without this, each failed login
        # would reset the 15-minute window, letting an attacker keep it open
        # indefinitely with a slow-drip attack.
        _lua_incr_set_ttl = (
            "local v = redis.call('INCR', KEYS[1]) "
            "if v == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end "
            "return v"
        )
        await r.eval(_lua_incr_set_ttl, 1, redis_key, window_seconds)

    except HTTPException:
        raise
    except Exception as e:
        if settings.is_production:
            logger.error(
                "Rate limiter unavailable in production — failing closed: %s", e
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter temporarily unavailable. Please retry in a moment.",
            )
        # dev/staging: don't block iteration
        logger.warning("[dev] Rate limiter error (allowing request): %s", e)
