"""Jev (TypeSafe) — le « décideur » du moteur Shorts.

Jev n'écrit pas de texte: on lui donne un contexte (`state`) et des questions
typées, il renvoie des probabilités calibrées. Il coûte ~0,042 $ / million de
jetons d'entrée (sortie gratuite) et répond en ~0,2 s: on lui confie donc tous
les ARBITRAGES du montage, et on garde les LLM pour ce qui demande d'écrire
(ordre du récit, titres, contenu des cartes, corrections).

    noul    -> probabilité (0-1) qu'une affirmation soit vraie
    choice  -> une option parmi des critères + probabilités + confiance
    score   -> note sur une échelle de 2 à 10 niveaux

Accès, dans l'ordre:
    1. OpenRouter « Decisions API » (OPENROUTER_API_KEY, modèle JEV_MODEL)
    2. API TypeSafe directe (TYPESAFE_API_KEY)
Sans clé (ou JEV_ENABLED=0), `decide` renvoie {} et l'appelant se replie sur
le LLM ou sur ses règles: Jev n'est jamais bloquant.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from ..conf import setting

logger = logging.getLogger(__name__)

OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
MAX_QUESTIONS = 40          # questions par requête (traitées en parallèle par Jev)
MAX_STATE_CHARS = 60_000    # ~ 17k jetons: marge sous la fenêtre de 32k

_lock = threading.Lock()
USAGE: dict[str, Any] = {"calls": 0, "questions": 0, "input_tokens": 0, "cost": 0.0, "errors": 0}


def reset_usage() -> None:
    with _lock:
        USAGE.update(calls=0, questions=0, input_tokens=0, cost=0.0, errors=0)


# ----------------------------------------------------------------- questions
def noul(instructions: str, yes: str, no: str) -> dict[str, Any]:
    return {"type": "noul", "instructions": instructions, "criteria": {"true": yes, "false": no}}


def choice(instructions: str, criteria: dict[str, str]) -> dict[str, Any]:
    return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}


def score(instructions: str, levels: list[str]) -> dict[str, Any]:
    return {"type": "score", "instructions": instructions, "criteria": list(levels)[:10]}


# ----------------------------------------------------------------- transport
def endpoints() -> list[dict[str, str]]:
    if (setting("JEV_ENABLED", "1") or "1").strip().lower() in ("0", "false", "no", "off"):
        return []
    out = []
    key = setting("OPENROUTER_API_KEY")
    if key:
        out.append({"name": "openrouter", "url": OPENROUTER_DECISIONS_URL, "key": key,
                    "model": setting("JEV_MODEL", "typesafe/jev-1.13") or "typesafe/jev-1.13"})
    tkey = setting("TYPESAFE_API_KEY")
    if tkey:
        out.append({"name": "typesafe", "url": TYPESAFE_URL, "key": tkey,
                    "model": setting("JEV_TYPESAFE_MODEL", "jev-latest") or "jev-latest"})
    return out


def available() -> bool:
    return bool(endpoints())


def _post(ep: dict[str, str], state: Any, questions: dict[str, Any], timeout: float) -> dict[str, Any]:
    import httpx
    headers = {"Authorization": f"Bearer {ep['key']}", "Content-Type": "application/json"}
    if ep["name"] == "openrouter":
        headers.update({"HTTP-Referer": setting("OPENROUTER_HTTP_REFERER", "https://cutforge.app") or "https://cutforge.app",
                        "X-Title": "CutForge Shorts"})
    with httpx.Client(timeout=timeout) as cl:
        r = cl.post(ep["url"], headers=headers, json={"model": ep["model"], "state": state, "questions": questions})
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if not isinstance(data.get("answers"), dict):
        raise RuntimeError("réponse Jev sans « answers »")
    return data


def _clip_state(state: Any) -> Any:
    raw = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)
    if len(raw) <= MAX_STATE_CHARS:
        return state
    return raw[:MAX_STATE_CHARS] + " …"


def decide(state: Any, questions: dict[str, dict[str, Any]], timeout: float = 30.0) -> dict[str, dict[str, Any]]:
    """Pose toutes les questions (par lots) sur le même contexte.

    Renvoie {id_question: réponse Jev}. Les questions sans réponse (Jev absent,
    erreur réseau) sont simplement absentes: l'appelant décide du repli.
    """
    eps = endpoints()
    if not eps or not questions:
        return {}
    state = _clip_state(state)
    items = list(questions.items())
    answers: dict[str, dict[str, Any]] = {}
    for i in range(0, len(items), MAX_QUESTIONS):
        batch = dict(items[i:i + MAX_QUESTIONS])
        for ep in eps:
            try:
                data = _post(ep, state, batch, timeout)
                answers.update({k: v for k, v in data["answers"].items() if k in batch and isinstance(v, dict)})
                u = data.get("usage") or {}
                with _lock:
                    USAGE["calls"] += 1; USAGE["questions"] += len(batch)
                    USAGE["input_tokens"] += int(u.get("input_tokens") or 0)
                    USAGE["cost"] += float(u.get("cost") or 0.0)
                break
            except Exception as e:  # passerelle suivante, puis repli de l'appelant
                with _lock:
                    USAGE["errors"] += 1
                logger.warning("Jev via %s indisponible: %s", ep["name"], e)
    return answers


# ----------------------------------------------------------------- lecture des réponses
def p_true(ans: Optional[dict[str, Any]], default: Optional[float] = None) -> Optional[float]:
    if not ans:
        return default
    try:
        return float(ans.get("noul"))
    except (TypeError, ValueError):
        return default


def picked(ans: Optional[dict[str, Any]], min_conf: float = 0.0) -> Optional[str]:
    if not ans or ans.get("choice") is None:
        return None
    conf = ans.get("confidence")
    if conf is not None and float(conf) < min_conf:
        return None
    return str(ans["choice"])


def level(ans: Optional[dict[str, Any]], default: Optional[float] = None) -> Optional[float]:
    if not ans:
        return default
    try:
        return float(ans.get("score"))
    except (TypeError, ValueError):
        return default
