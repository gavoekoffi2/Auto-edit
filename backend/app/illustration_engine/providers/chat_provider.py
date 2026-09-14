"""Shared plumbing for OpenAI-compatible chat endpoints.

FreeLLMAPI and the configurable cloud provider speak the same protocol, so the
request building, the strict JSON contract and the timeout handling live once.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

from ..analyzer.semantic_analyzer import SemanticUnit
from ..schemas.visual import PATTERNS, VISUAL_TYPES
from .base import SemanticProvider

SYSTEM_PROMPT = (
    "Tu es le directeur d'illustration d'un montage vidéo. On te donne les "
    "unités de discours numérotées d'une vidéo face caméra. Pour CHAQUE unité "
    "qui mérite vraiment une illustration explicative, tu renvoies un objet. "
    "N'illustre PAS les salutations, les appels à l'abonnement, les transitions "
    "vides ni les propos sans structure. Réponds UNIQUEMENT par un tableau JSON, "
    "sans texte autour."
)

SCHEMA_HINT = (
    '[{"index": <entier de l\'unité>, '
    '"pattern": "<%s>", '
    '"visual_type": "<%s>", '
    '"visual_score": <0.0 à 1.0>, '
    '"title": "<titre court, 4 mots max, MAJUSCULES>", '
    '"items": ["<label court>", "..."], '
    '"concept": "<ce que la scène doit expliquer>"}]'
) % ("|".join(PATTERNS), "|".join(VISUAL_TYPES))

_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
MAX_UNITS = 40


class ChatSemanticProvider(SemanticProvider):
    """Calls an OpenAI-compatible /chat/completions endpoint."""

    name = "chat"
    network = True

    def __init__(self, base_url: str = "", model: str = "",
                 api_key: str = "", timeout: float = 20.0):
        self.base_url = (base_url or "").rstrip("/")
        self.model = model or ""
        self.api_key = api_key or ""
        self.timeout = float(timeout)

    def available(self) -> bool:
        return bool(self.base_url and self.model)

    # ------------------------------------------------------------------ #
    def _payload(self, units: Sequence[SemanticUnit]) -> Dict[str, Any]:
        lines = []
        for index, unit in enumerate(units[:MAX_UNITS]):
            text = " ".join((unit.text or "").split())[:320]
            lines.append(f"{index}. [{unit.start:.1f}s-{unit.end:.1f}s] {text}")
        user = (
            f"Schéma de réponse:\n{SCHEMA_HINT}\n\n"
            f"Unités de discours:\n" + "\n".join(lines)
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 2000,
        }

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _refine(self, units: Sequence[SemanticUnit]) -> List[dict]:
        import requests   # local import: the engine must import without it

        response = requests.post(
            f"{self.base_url}/chat/completions", headers=self._headers(),
            json=self._payload(units), timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return self.parse(content)

    # ------------------------------------------------------------------ #
    @staticmethod
    def parse(content: str) -> List[dict]:
        """Pull the JSON array out of a model reply. Tolerant, then strict.

        Models wrap JSON in prose or fences often enough that refusing the
        whole response over a stray sentence would make the mode useless.
        """
        if not content:
            return []
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            match = _JSON_ARRAY.search(text)
            if not match:
                return []
            try:
                parsed = json.loads(match.group(0))
            except (ValueError, TypeError):
                return []
        if isinstance(parsed, dict):
            parsed = parsed.get("scenes") or parsed.get("results") or []
        return parsed if isinstance(parsed, list) else []
