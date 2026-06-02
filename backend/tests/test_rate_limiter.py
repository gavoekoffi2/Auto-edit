"""Tests du rate limiter — verifie le fail-closed en production."""
import pytest
from fastapi import HTTPException

from app.services import rate_limiter


class _BrokenRedis:
    async def get(self, *_): raise RuntimeError("redis down")
    async def ttl(self, *_): raise RuntimeError("redis down")
    def pipeline(self): raise RuntimeError("redis down")


async def _broken_get_redis():
    return _BrokenRedis()


@pytest.mark.asyncio
async def test_fail_open_in_dev(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_get_redis", _broken_get_redis)
    monkeypatch.setattr(rate_limiter.settings, "APP_ENV", "development", raising=False)
    # En dev: on log un warning et on laisse passer (pas d'exception)
    await rate_limiter.check_rate_limit("k", max_attempts=1, window_seconds=10)


@pytest.mark.asyncio
async def test_fail_closed_in_production(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_get_redis", _broken_get_redis)
    monkeypatch.setattr(rate_limiter.settings, "APP_ENV", "production", raising=False)
    with pytest.raises(HTTPException) as exc:
        await rate_limiter.check_rate_limit("k", max_attempts=1, window_seconds=10)
    assert exc.value.status_code == 503
