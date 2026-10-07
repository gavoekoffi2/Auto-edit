"""Petit client texte OpenRouter (JSON) — best-effort, jamais bloquant."""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("LONGFORM_LLM_MODEL",
                          os.getenv("PROMPT_REFINER_MODEL", "google/gemini-2.5-flash-lite"))


def api_key() -> Optional[str]:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    try:
        from app.config import settings
        return getattr(settings, "OPENROUTER_API_KEY", "") or None
    except Exception:  # noqa: BLE001
        return None


def ask_json(prompt: str, *, model: str = DEFAULT_MODEL, timeout: int = 90) -> Optional[Any]:
    """Pose une question, extrait le premier objet/tableau JSON de la réponse."""
    key = api_key()
    if not key:
        return None
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "temperature": 0.2,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        text = resp.json()["choices"][0]["message"]["content"] or ""
        starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
        if not starts:
            raise RuntimeError("pas de JSON dans la réponse")
        s = min(starts)
        e = max(text.rfind("]"), text.rfind("}"))
        return json.loads(text[s:e + 1])
    except Exception as exc:  # noqa: BLE001 — jamais bloquer le rendu
        print(f"[longform.llm] WARN: {type(exc).__name__}: {str(exc)[:160]}", file=sys.stderr)
        return None
