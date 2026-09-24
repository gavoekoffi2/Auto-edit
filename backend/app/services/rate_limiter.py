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


def _retry_label(ttl: int) -> str:
    if ttl is None or ttl <= 0:
        return "quelques instants"
    if ttl < 90:
        return f"{ttl} secondes"
    return f"{(ttl + 59) // 60} minutes"


async def check_rate_limit(
    key: str, max_attempts: int = 5, window_seconds: int = 900,
    increment: bool = True,
) -> None:
    """Check rate limit for a given key. Raises 429 if exceeded.

    ``increment=False`` vérifie seulement le plafond (le compteur est alors
    alimenté séparément par :func:`record_rate_limit_hit`, ex. échecs de
    connexion uniquement).

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
                detail=f"Trop de tentatives. Réessaie dans {_retry_label(ttl)}.",
            )

        if increment:
            pipe = r.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds)
            await pipe.execute()

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


async def record_rate_limit_hit(key: str, window_seconds: int = 900) -> None:
    """Incrémente le compteur *key* (best effort, n'échoue jamais)."""
    try:
        r = await _get_redis()
        redis_key = f"rate_limit:{key}"
        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds)
        await pipe.execute()
    except Exception as e:  # noqa: BLE001
        logger.warning("Rate limiter hit not recorded (%s): %s", key, e)


async def clear_rate_limit(key: str) -> None:
    """Remet le compteur *key* à zéro (ex. connexion réussie)."""
    try:
        r = await _get_redis()
        await r.delete(f"rate_limit:{key}")
    except Exception as e:  # noqa: BLE001
        logger.warning("Rate limiter reset failed (%s): %s", key, e)
