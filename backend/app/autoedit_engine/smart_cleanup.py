"""
STEP 1bis — Nettoyage IA du transcript (Gemini via OpenRouter).

Les heuristiques locales de ``build_edl`` retirent déjà les silences, les
bégaiements, les reprises adjacentes et les phrases quasi identiques. Cette
passe OPTIONNELLE fait relire le transcript horodaté par un modèle léger
(Gemini flash-lite par défaut) pour attraper ce que les heuristiques ratent:

  * répétitions ÉLOIGNÉES ou reformulées (la personne redit la même idée),
  * hésitations longues ("euh… donc… en fait…") noyées dans une phrase,
  * faux départs / phrases abandonnées à mi-chemin,
  * passages incohérents qui cassent le rythme du montage.

Le modèle renvoie des intervalles SOURCE à retirer. On les applique en
FILTRANT les mots du ``_vu.json``: les zones vidées deviennent des silences
que ``build_edl`` coupe ensuite naturellement (mêmes pads, mêmes fades) — la
coupe reste donc propre et alignée sur les mots.

GARANTIES (best-effort, jamais bloquant):
  * le moindre échec (pas de clé, réseau, JSON invalide) => transcript inchangé;
  * jamais plus de ``LLM_CLEANUP_MAX_REMOVAL`` de la durée parlée retirée;
  * spans snappés aux frontières de mots, minimum 0.25 s.

Usage:
    python -m app.autoedit_engine.smart_cleanup transcripts/video_vu.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional, Tuple

import requests

from . import config

# Modèle volontairement économique — une relecture de texte, pas de génération.
LLM_CLEANUP_ENABLED = os.getenv("ENGINE_LLM_CLEANUP", "1") not in {"0", "false", "no"}
LLM_CLEANUP_MODEL = os.getenv("ENGINE_LLM_CLEANUP_MODEL", config.PROMPT_REFINER_MODEL)
LLM_CLEANUP_MAX_REMOVAL = float(os.getenv("ENGINE_LLM_CLEANUP_MAX_REMOVAL", "0.30"))
_MIN_SPAN = 0.25          # ignore les micro-spans (les pads les mangeraient)
_TIMEOUT = 90

_PROMPT = (
    "Tu es un monteur vidéo professionnel spécialisé dans les formats viraux "
    "verticaux. Voici le transcript horodaté (secondes) d'une prise de parole "
    "face caméra. Repère UNIQUEMENT les passages à COUPER au montage :\n"
    "- répétitions d'une même idée ou phrase (garde la MEILLEURE occurrence, "
    "en général la dernière),\n"
    "- hésitations longues, remplissage (« euh », « donc voilà », etc.),\n"
    "- faux départs et phrases abandonnées,\n"
    "- passages confus qui cassent le rythme.\n"
    "NE COUPE PAS le contenu utile, l'accroche du début ni l'appel à l'action "
    "final. En cas de doute, ne coupe pas.\n"
    "Réponds UNIQUEMENT avec un tableau JSON (éventuellement vide) d'objets "
    '{"start": <sec>, "end": <sec>, "reason": "repetition|hesitation|'
    'false_start|incoherent"}. Les temps doivent tomber DANS le transcript.\n\n'
    "Transcript:\n{transcript}"
)


def _transcript_lines(vu: dict) -> str:
    lines: List[str] = []
    for seg in vu.get("segments", []):
        text = (seg.get("text") or "").strip()
        if text:
            lines.append(f"[{float(seg['start']):.2f} - {float(seg['end']):.2f}] {text}")
    return "\n".join(lines)


def _spoken_duration(vu: dict) -> float:
    total = 0.0
    for seg in vu.get("segments", []):
        for w in seg.get("words", []):
            total += max(0.0, float(w["end"]) - float(w["start"]))
    return total


def _validate_spans(raw: object, vu: dict) -> List[dict]:
    """Sanitize model output: shape, bounds, minimum length, removal cap."""
    if not isinstance(raw, list):
        return []
    duration = float(vu.get("duration") or 0.0) or max(
        (float(s["end"]) for s in vu.get("segments", [])), default=0.0)
    budget = _spoken_duration(vu) * LLM_CLEANUP_MAX_REMOVAL
    spans: List[dict] = []
    used = 0.0
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item["start"])
            end = float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        start, end = max(0.0, start), min(duration, end)
        if end - start < _MIN_SPAN:
            continue
        if used + (end - start) > budget:
            continue                       # le budget protège le contenu utile
        used += end - start
        spans.append({
            "start": round(start, 3), "end": round(end, 3),
            "reason": str(item.get("reason") or "cleanup")[:40],
        })
    spans.sort(key=lambda s: s["start"])
    return spans


def llm_cleanup_spans(vu: dict, api_key: Optional[str] = None,
                      model: str = LLM_CLEANUP_MODEL) -> List[dict]:
    """Ask the LLM for source-time spans to remove. [] on any failure."""
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    transcript = _transcript_lines(vu)
    if not api_key or not transcript:
        return []
    try:
        resp = requests.post(
            config.OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": model,
                  "messages": [{"role": "user",
                                "content": _PROMPT.replace("{transcript}", transcript)}]},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"cleanup LLM HTTP {resp.status_code}")
        text = resp.json()["choices"][0]["message"]["content"] or ""
        start, end = text.find("["), text.rfind("]")
        if start < 0 or end <= start:
            raise RuntimeError("no JSON array in cleanup answer")
        return _validate_spans(json.loads(text[start:end + 1]), vu)
    except Exception as exc:  # noqa: BLE001 - never block the render
        print(f"[smart_cleanup] WARN LLM pass skipped: {exc}", file=sys.stderr)
        return []


def apply_spans(vu: dict, spans: List[dict]) -> Tuple[dict, float]:
    """Drop words whose midpoint falls inside a span; returns (vu, seconds cut)."""
    if not spans:
        return vu, 0.0
    removed = 0.0
    segments: List[dict] = []
    for seg in vu.get("segments", []):
        kept: List[dict] = []
        for w in seg.get("words", []):
            mid = (float(w["start"]) + float(w["end"])) / 2.0
            if any(s["start"] <= mid <= s["end"] for s in spans):
                removed += max(0.0, float(w["end"]) - float(w["start"]))
            else:
                kept.append(w)
        if kept:
            segments.append({
                **seg,
                "words": kept,
                "text": " ".join(w["word"].strip() for w in kept).strip(),
                "start": float(kept[0]["start"]),
                "end": float(kept[-1]["end"]),
            })
    cleaned = {**vu, "segments": segments}
    return cleaned, removed


def clean_vu(vu_path: str, out_path: str,
             api_key: Optional[str] = None) -> Tuple[str, dict]:
    """Full pass: LLM spans -> filtered vu written to *out_path*.

    Returns ``(effective_vu_path, report)``. On failure or when nothing is
    flagged, the ORIGINAL path is returned untouched.
    """
    report = {"llm_cleanup_spans": 0, "llm_cleanup_removed_s": 0.0,
              "llm_cleanup_model": LLM_CLEANUP_MODEL}
    try:
        vu = json.load(open(vu_path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[smart_cleanup] WARN cannot read vu: {exc}", file=sys.stderr)
        return vu_path, report
    spans = llm_cleanup_spans(vu, api_key=api_key)
    if not spans:
        return vu_path, report
    cleaned, removed = apply_spans(vu, spans)
    if removed <= 0.0 or not cleaned.get("segments"):
        return vu_path, report
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(cleaned, fh, ensure_ascii=False, indent=2)
    report.update({
        "llm_cleanup_spans": len(spans),
        "llm_cleanup_removed_s": round(removed, 2),
        "llm_cleanup_reasons": sorted({s["reason"] for s in spans}),
    })
    print(f"[smart_cleanup] {len(spans)} passage(s) retirés par l'IA "
          f"({removed:.1f}s de parole) -> {out_path}")
    return out_path, report


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="LLM transcript cleanup (repetitions/hesitations)")
    ap.add_argument("vu", help="transcripts/<stem>_vu.json")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args(argv)
    out = args.out or args.vu.replace("_vu.json", "_vu_clean.json")
    path, report = clean_vu(args.vu, out)
    print(json.dumps({"vu": path, **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
