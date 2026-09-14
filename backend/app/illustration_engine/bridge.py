"""Bridge between the illustration engine and the existing montage pipeline.

The montage's step 4 used to be `content.derive_motion_scenes()` +
`motion_design.render_all()`. This module is the drop-in replacement: same
inputs, same output shape, so `plan_overlays`, `composite` and `mix_sfx` keep
working untouched.

Keeping the contract identical is what makes the switch reversible: set
`ILLUSTRATION_ENGINE_ENABLED=false` and the legacy engine takes over again,
with no redeploy.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import config
from .director import IllustrationDirector

# Montage visual modes that forbid any paid image call.
_NO_PAID_MODES = ("credit_saver",)


def is_active(do_motion: bool = True) -> bool:
    """Should the new engine own the illustration step for this render?"""
    return bool(do_motion and config.ENABLED)


def aspect_for(width: int, height: int) -> str:
    """Pick the aspect preset matching the montage's canvas."""
    if height <= 0:
        return config.DEFAULT_ASPECT
    ratio = width / float(height)
    if ratio >= 1.2:
        return "16:9"
    if ratio <= 0.85:
        return "9:16"
    return "1:1"


def run(vu_data: dict, outdir: str, *,
        style: str = None, intensity: str = None, ai_mode: str = None,
        aspect: str = None, width: int = 0, height: int = 0, fps: int = None,
        workdir: str = "", visual_mode: str = "auto_fallback",
        disable_paid_images: bool = False, preview: bool = False,
        edl_ranges: Sequence[dict] = ()) -> Tuple[List[dict], Dict[str, Any]]:
    """Run the engine and return (legacy_motion_clips, report).

    `legacy_motion_clips` is exactly the shape the old
    `motion_design.render_all()` returned, including `source_start`,
    `duration`, `mov` and `events`, so it can be written straight to
    `_motion_clips.json`.
    """
    allow_paid = bool(
        os.environ.get("OPENROUTER_API_KEY")
        and visual_mode not in _NO_PAID_MODES
        and not disable_paid_images)

    director = IllustrationDirector(
        style=style or os.environ.get("ILLUSTRATION_STYLE", "professional"),
        intensity=intensity, ai_mode=ai_mode,
        aspect=aspect or (aspect_for(width, height) if width and height else None),
        width=width, height=height, fps=fps, workdir=workdir,
        preview=preview, allow_paid_images=allow_paid)

    result = director.run(vu_data, outdir, edl_ranges=edl_ranges)
    clips = result.legacy_clips
    report = dict(result.report)
    report["engine"] = "illustration_engine"
    return clips, report


def spans(clips: Sequence[dict]) -> List[Tuple[float, float]]:
    """Source spans the B-roll and keyword popups must stay away from.

    Mirrors `content.motion_scene_spans()` so callers can swap engines without
    a second code path.
    """
    out: List[Tuple[float, float]] = []
    for clip in clips:
        try:
            start = float(clip["source_start"])
            duration = float(clip.get("duration") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue
        out.append((start, start + duration))
    return out


def plan_only(vu_data: dict, *, style: str = None, intensity: str = None,
              ai_mode: str = None, aspect: str = None) -> Dict[str, Any]:
    """Storyboard without rendering — powers the API preview and the UI panel."""
    director = IllustrationDirector(style=style or "professional",
                                    intensity=intensity, ai_mode=ai_mode,
                                    aspect=aspect)
    board = director.storyboard(vu_data)
    return {
        "style": board.style,
        "intensity": board.intensity,
        "ai_mode": board.ai_mode,
        "provider": board.provider,
        "coverage": round(board.coverage, 4),
        "type_histogram": board.type_histogram(),
        "notes": list(board.notes),
        "plan": board.plan_summary(),
        "storyboard": board.to_dict(),
    }

# --------------------------------------------------------------------------- #
# read-only payloads for the API
# --------------------------------------------------------------------------- #
# Kept here, next to plan_only, so the HTTP layer stays a thin shell and this
# logic is importable and testable without a database or an auth chain — the
# same separation `api/v1/modes.py` uses for the mode catalogue.
def capabilities() -> Dict[str, Any]:
    """What this deployment can actually do.

    Exposed so a client can read the catalogue from the engine itself instead
    of hardcoding a copy that drifts the first time a style is added. It also
    reports whether the optional hand-drawing engine is installed on this host,
    which no client can know on its own.
    """
    from .schemas.visual import VISUAL_TYPES
    from .styles import STYLES, UI_STYLES

    try:
        from .renderers import animator_available
        hand_drawing = animator_available()
    except Exception:  # noqa: BLE001 - reporting capabilities must not fail
        hand_drawing = False

    return {
        "enabled": bool(config.ENABLED),
        "styles": sorted(STYLES),
        "ui_styles": dict(UI_STYLES),
        "intensities": sorted(config.INTENSITY),
        "ai_modes": list(config.VALID_AI_MODES),
        "ai_mode_default": config.AI_MODE,
        "aspects": sorted(config.ASPECTS),
        "visual_types": list(VISUAL_TYPES),
        # The hand-drawing engine is an optional dependency: say so plainly
        # instead of letting the UI promise what this host cannot deliver.
        "whiteboard_animator": hand_drawing,
        "score_bands": {
            "none": [0.0, config.SCORE_NONE],
            "optional": [config.SCORE_NONE, config.SCORE_OPTIONAL],
            "recommended": [config.SCORE_OPTIONAL, config.SCORE_RECOMMENDED],
            "strongly_recommended": [config.SCORE_RECOMMENDED, 1.0],
        },
    }


def analyze_passage(text: str) -> Dict[str, Any]:
    """How the engine reads one passage: discourse figure and extracted matter.

    Purely local and side-effect free — this is the offline mode.
    """
    from .analyzer import ConceptDetector, SemanticAnalyzer, band
    from .analyzer.visual_opportunity_detector import VisualOpportunityDetector

    unit = SemanticAnalyzer().analyze_text(text or "", 0.0, 6.0)
    concepts = ConceptDetector()
    detector = VisualOpportunityDetector(60.0, concepts)
    score = detector.score(unit)
    return {
        "pattern": unit.pattern,
        "confidence": round(unit.confidence, 3),
        "items": list(unit.items),
        "numbers": [list(n) for n in unit.numbers],
        "sides": list(unit.sides),
        "concepts": concepts.concepts(text or "", limit=5),
        "domains": concepts.domains(text or ""),
        "suggested_title": concepts.headline(text or "", 4),
        "visual_score": round(score, 3),
        "band": band(score),
        "reason": detector.reason(unit, score),
    }
