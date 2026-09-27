"""Lecture des réglages: variables d'environnement, puis app.config.settings (.env)."""
from __future__ import annotations

import os
from typing import Optional


def setting(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name)
    if v:
        return v
    try:
        from app.config import settings  # import tardif: le moteur reste utilisable seul
        v = getattr(settings, name, None)
        return str(v) if v not in (None, "") else default
    except Exception:
        return default
