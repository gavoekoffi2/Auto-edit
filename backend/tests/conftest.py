"""Stubs partages pour la suite de tests.

On charge ces stubs *avant* que pytest importe `app.*`, pour eviter
ImportError sur whisper/moviepy/scenedetect quand on teste les modules
algorithmiques (EDL, broll planner) en isolation.

On stubbe uniquement les modules absents — si un module est reellement
installe, on le laisse tel quel.
"""
import os
import sys
import types
import importlib


def _stub_if_missing(name: str) -> None:
    try:
        importlib.import_module(name)
    except Exception:
        sys.modules[name] = types.ModuleType(name)


for _name in (
    "whisper", "moviepy", "moviepy.editor", "auto_editor", "scenedetect",
    "aiofiles", "celery", "redis", "redis.asyncio",
    "passlib", "passlib.context", "jose",
):
    _stub_if_missing(_name)

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@x/x")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://x:x@x/x")
os.environ.setdefault("REDIS_URL", "redis://x/0")
os.environ.setdefault("SECRET_KEY", "a" * 40)
os.environ.setdefault("IMAGE_GENERATION_PROVIDER", "noop")
os.environ.setdefault("APP_ENV", "development")
