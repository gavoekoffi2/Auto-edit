"""Détection des moments viraux d'une vidéo longue (fonctionnalité « Clips »).

Un modèle LLM (Gemini via OpenRouter, le même routage que le reste du moteur)
relit le transcript horodaté et propose les extraits les plus « clippables »:
hook fort, idée autonome, émotion, chiffres, punchline. Chaque extrait devient
ensuite un short monté par le moteur Auto Edit.

Repli heuristique intégral sans clé API: fenêtres alignées sur les phrases,
scorées par les key moments locaux (hooks/chiffres/mots émotionnels) — la
fonctionnalité marche donc toujours, l'IA la rend simplement meilleure.
"""
from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

import requests

from app.autoedit_engine import config as engine_config

logger = logging.getLogger(__name__)

MIN_CLIP_S = 15.0
MAX_CLIP_S = 90.0
DEFAULT_CLIP_TARGET_S = 45.0
MAX_CLIPS = 10

_MODEL = os.getenv("ENGINE_VIRAL_MOMENTS_MODEL", engine_config.PROMPT_REFINER_MODEL)
_TIMEOUT = 120

_PROMPT = (
    "Tu es un expert des formats courts (TikTok/Reels/Shorts). Voici le "
    "transcript horodaté (secondes) d'une vidéo longue. Choisis les {n} "
    "meilleurs extraits à transformer en shorts viraux.\n"
    "Critères: un extrait doit être AUTONOME (compréhensible seul), commencer "
    "sur un hook fort, contenir une idée/punchline/émotion/chiffre marquant, "
    "et durer entre {min_len:.0f} et {max_len:.0f} secondes.\n"
    "Réponds UNIQUEMENT avec un tableau JSON d'objets "
    '{{"start": <sec>, "end": <sec>, "title": "<titre court accrocheur>", '
    '"hook": "<première phrase de l\'extrait>", "reason": "<pourquoi viral>", '
    '"score": <0-100>}}. Les temps doivent tomber DANS le transcript.\n\n'
    "Transcript:\n{transcript}"
)


def _transcript_lines(vu: dict) -> str:
    lines: List[str] = []
    for seg in vu.get("segments", []):
        text = (seg.get("text") or "").strip()
        if text:
            lines.append(f"[{float(seg['start']):.1f} - {float(seg['end']):.1f}] {text}")
    return "\n".join(lines)


def _duration(vu: dict) -> float:
    return float(vu.get("duration") or 0.0) or max(
        (float(s["end"]) for s in vu.get("segments", [])), default=0.0)


def _snap_to_segments(start: float, end: float, vu: dict) -> tuple[float, float]:
    """Étend l'extrait aux frontières de phrases pour ne pas couper un mot."""
    segs = vu.get("segments", [])
    snap_start, snap_end = start, end
    for seg in segs:
        s, e = float(seg["start"]), float(seg["end"])
        if s <= start <= e:
            snap_start = s
        if s <= end <= e:
            snap_end = e
    return snap_start, snap_end


def _validate(raw: object, vu: dict, max_clips: int,
              min_len: float, max_len: float) -> List[dict]:
    if not isinstance(raw, list):
        return []
    total = _duration(vu)
    moments: List[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            start = max(0.0, float(item["start"]))
            end = min(total, float(item["end"]))
        except (KeyError, TypeError, ValueError):
            continue
        start, end = _snap_to_segments(start, end, vu)
        if end - start < min_len:
            continue
        if end - start > max_len:
            end = start + max_len
        try:
            score = max(0, min(100, int(float(item.get("score", 50)))))
        except (TypeError, ValueError):
            score = 50
        moments.append({
            "start": round(start, 2), "end": round(end, 2),
            "title": str(item.get("title") or "Extrait")[:120],
            "hook": str(item.get("hook") or "")[:200],
            "reason": str(item.get("reason") or "")[:300],
            "score": score,
        })
    # Dé-chevauchement: on garde les mieux scorés.
    moments.sort(key=lambda m: -m["score"])
    kept: List[dict] = []
    for m in moments:
        if all(m["end"] <= k["start"] or m["start"] >= k["end"] for k in kept):
            kept.append(m)
        if len(kept) >= max_clips:
            break
    kept.sort(key=lambda m: m["start"])
    return kept


def llm_moments(vu: dict, *, max_clips: int, min_len: float, max_len: float,
                api_key: Optional[str] = None) -> List[dict]:
    """LLM pass; [] on any failure (caller falls back to heuristics)."""
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    transcript = _transcript_lines(vu)
    if not api_key or not transcript:
        return []
    prompt = _PROMPT.format(n=max_clips, min_len=min_len, max_len=max_len,
                            transcript=transcript)
    try:
        resp = requests.post(
            engine_config.OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": _MODEL,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"viral moments HTTP {resp.status_code}")
        text = resp.json()["choices"][0]["message"]["content"] or ""
        lo, hi = text.find("["), text.rfind("]")
        if lo < 0 or hi <= lo:
            raise RuntimeError("no JSON array in answer")
        return _validate(json.loads(text[lo:hi + 1]), vu, max_clips, min_len, max_len)
    except Exception as exc:  # noqa: BLE001 - fall back to heuristics
        logger.warning("[viral_moments] LLM pass failed: %s", exc)
        return []


def heuristic_moments(vu: dict, *, max_clips: int, min_len: float,
                      max_len: float) -> List[dict]:
    """Fenêtres alignées sur les phrases, scorées par les key moments locaux."""
    from app.autoedit_engine import key_moments

    total = _duration(vu)
    segs = [s for s in vu.get("segments", []) if (s.get("text") or "").strip()]
    if not segs or total <= 0:
        return []
    try:
        cues = key_moments.plan_key_moments(vu)
        cue_times = [float(c.start) for c in cues]
    except Exception:  # noqa: BLE001 - scoring is best-effort
        cue_times = []

    target = min(max_len, max(min_len, DEFAULT_CLIP_TARGET_S))
    candidates: List[dict] = []
    for seg in segs:
        start = float(seg["start"])
        end = start
        # Étend la fenêtre jusqu'à ~target en respectant les fins de phrases.
        for nxt in segs:
            if float(nxt["start"]) >= start and float(nxt["end"]) - start <= max_len:
                end = max(end, float(nxt["end"]))
            if end - start >= target:
                break
        if end - start < min_len:
            continue
        score = 10 + sum(1 for t in cue_times if start <= t <= end) * 12
        if start < total * 0.1:
            score += 8                     # le début contient souvent le hook
        first_text = (seg.get("text") or "").strip()
        candidates.append({
            "start": round(start, 2), "end": round(end, 2),
            "title": first_text[:60] or "Extrait",
            "hook": first_text[:200],
            "reason": "moments clés détectés localement",
            "score": min(100, score),
        })
    return _validate(candidates, vu, max_clips, min_len, max_len)


def detect_viral_moments(vu: dict, *, max_clips: int = 5,
                         min_len: float = MIN_CLIP_S,
                         max_len: float = MAX_CLIP_S,
                         api_key: Optional[str] = None) -> tuple[List[dict], str]:
    """Returns (moments, provider) where provider is 'llm' or 'heuristic'."""
    max_clips = max(1, min(MAX_CLIPS, int(max_clips)))
    min_len = max(8.0, float(min_len))
    max_len = min(180.0, max(min_len + 5.0, float(max_len)))
    moments = llm_moments(vu, max_clips=max_clips, min_len=min_len,
                          max_len=max_len, api_key=api_key)
    if moments:
        return moments, "llm"
    return (heuristic_moments(vu, max_clips=max_clips, min_len=min_len,
                              max_len=max_len), "heuristic")
