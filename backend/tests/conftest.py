"""Stubs partagés pour la suite de tests.

On charge ces stubs *avant* que pytest importe `app.*`, pour éviter
ImportError sur whisper/moviepy/sqlalchemy quand on teste les modules
algorithmiques (EDL, broll planner) en isolation.
"""
import os
import sys
import types

for _name in (
    "whisper", "moviepy", "moviepy.editor", "auto_editor", "scenedetect",
    "aiofiles", "fastapi", "celery", "redis", "passlib", "jose",
    "sqlalchemy", "sqlalchemy.ext.asyncio", "sqlalchemy.orm",
    "sqlalchemy.dialects", "sqlalchemy.dialects.postgresql",
):
    sys.modules.setdefault(_name, types.ModuleType(_name))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@x/x")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://x:x@x/x")
os.environ.setdefault("REDIS_URL", "redis://x/0")
os.environ.setdefault("SECRET_KEY", "a" * 40)
os.environ.setdefault("IMAGE_GENERATION_PROVIDER", "noop")
