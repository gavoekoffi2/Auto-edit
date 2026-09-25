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
                detail=f"Trop de tentatives. Réessaie dans {max(1, int(ttl or 60) // 60)} min.",
            )

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
                detail="Service momentanément indisponible. Réessaie dans un instant.",
            )
        # dev/staging: don't block iteration
        logger.warning("[dev] Rate limiter error (allowing request): %s", e)


def _rate_limit_unavailable(e: Exception) -> None:
    if settings.is_production:
        logger.error("Rate limiter unavailable in production — failing closed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service momentanément indisponible. Réessaie dans un instant.",
        )
    logger.warning("[dev] Rate limiter error (allowing request): %s", e)


async def ensure_not_limited(key: str, max_attempts: int) -> None:
    """Lève 429 si *key* a déjà atteint *max_attempts* — SANS compter la requête.

    À combiner avec :func:`record_failure` pour ne pénaliser que les ÉCHECS
    (ex. login): derrière un NAT d'opérateur mobile (CGNAT, très courant en
    Afrique), des centaines d'utilisateurs légitimes partagent une IP et ne
    doivent pas se bloquer mutuellement en se connectant normalement.
    """
    try:
        r = await _get_redis()
        current = await r.get(f"rate_limit:{key}")
        if current is not None and int(current) >= max_attempts:
            ttl = await r.ttl(f"rate_limit:{key}")
            minutes = max(1, int(ttl or 60) // 60 + (1 if (ttl or 0) % 60 else 0))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Trop de tentatives. Réessaie dans {minutes} min.",
            )
    except HTTPException:
        raise
    except Exception as e:
        _rate_limit_unavailable(e)


async def record_failure(key: str, window_seconds: int) -> None:
    """Compte un échec pour *key* (fenêtre glissante simple)."""
    try:
        r = await _get_redis()
        pipe = r.pipeline()
        pipe.incr(f"rate_limit:{key}")
        pipe.expire(f"rate_limit:{key}", window_seconds)
        await pipe.execute()
    except Exception as e:  # l'échec d'écriture ne doit pas masquer la vraie réponse
        logger.warning("Rate limiter: could not record failure for %s: %s", key, e)


async def reset_counter(key: str) -> None:
    try:
        r = await _get_redis()
        await r.delete(f"rate_limit:{key}")
    except Exception:
        pass
