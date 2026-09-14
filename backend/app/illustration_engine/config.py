"""Every knob of the illustration engine, in one place.

Environment variables win over defaults so an operator can retune a VPS
without a redeploy.
"""
from __future__ import annotations

import os
from typing import Dict, Tuple


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _b(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------------- #
# master switches
# --------------------------------------------------------------------------- #
ENABLED = _b("ILLUSTRATION_ENGINE_ENABLED", True)

# offline | free | cloud — offline never touches the network.
AI_MODE = (os.getenv("ILLUSTRATION_AI_MODE", "offline") or "offline").strip().lower()
VALID_AI_MODES = ("offline", "free", "cloud")
if AI_MODE not in VALID_AI_MODES:
    AI_MODE = "offline"

# FreeLLMAPI is opt-in AND needs an explicit base URL: the MIT licence of the
# proxy says nothing about the terms of the providers behind it, so the
# operator must knowingly point at one. See docs/THIRD_PARTY_LICENSES.md.
FREELLM_BASE_URL = os.getenv("FREELLM_BASE_URL", "").strip()
FREELLM_MODEL = os.getenv("FREELLM_MODEL", "").strip()
FREELLM_TIMEOUT = _f("FREELLM_TIMEOUT", 20.0)

CLOUD_BASE_URL = os.getenv("ILLUSTRATION_CLOUD_BASE_URL", "").strip()
CLOUD_API_KEY_ENV = os.getenv("ILLUSTRATION_CLOUD_API_KEY_ENV", "OPENROUTER_API_KEY")
CLOUD_MODEL = os.getenv("ILLUSTRATION_CLOUD_MODEL", "").strip()
CLOUD_TIMEOUT = _f("ILLUSTRATION_CLOUD_TIMEOUT", 30.0)

# --------------------------------------------------------------------------- #
# canvas
# --------------------------------------------------------------------------- #
# The product priority is YouTube 16:9; the existing CutForge pipeline is
# vertical, so both are first-class and the director takes the size from the
# pipeline instead of hardcoding one.
ASPECTS: Dict[str, Tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}
DEFAULT_ASPECT = os.getenv("ILLUSTRATION_ASPECT", "16:9")
FPS = _i("ILLUSTRATION_FPS", 30)

# Preview renders trade resolution for speed on a VPS.
PREVIEW_SCALE = _f("ILLUSTRATION_PREVIEW_SCALE", 0.5)
PREVIEW_FPS = _i("ILLUSTRATION_PREVIEW_FPS", 15)

# --------------------------------------------------------------------------- #
# visual score thresholds — the mission's four bands
# --------------------------------------------------------------------------- #
SCORE_NONE = 0.40         # below: never illustrate
SCORE_OPTIONAL = 0.60     # 0.40-0.59: only if the budget allows
SCORE_RECOMMENDED = 0.80  # 0.60-0.79: recommended; 0.80+: strongly recommended

# Intensity presets pick the acceptance threshold and the density budget.
# `min_gap` is the seconds of uninterrupted talking head required between two
# illustrations. It belongs to the intensity profile: a user who asks for
# "high" is asking for a denser edit, and a fixed global gap would silently
# ignore that.
INTENSITY: Dict[str, Dict[str, float]] = {
    "low":    {"threshold": SCORE_RECOMMENDED, "per_minute": 0.6,
               "max_coverage": 0.10, "min_gap": 16.0},
    "medium": {"threshold": SCORE_OPTIONAL + 0.05, "per_minute": 1.2,
               "max_coverage": 0.18, "min_gap": 9.0},
    "high":   {"threshold": SCORE_NONE + 0.05, "per_minute": 2.0,
               "max_coverage": 0.28, "min_gap": 5.0},
}
DEFAULT_INTENSITY = os.getenv("ILLUSTRATION_INTENSITY", "medium")

# --------------------------------------------------------------------------- #
# pacing constraints — "the talking head stays the backbone"
# --------------------------------------------------------------------------- #
MIN_SCENE_DUR = _f("ILLUSTRATION_MIN_DUR", 3.0)
MAX_SCENE_DUR = _f("ILLUSTRATION_MAX_DUR", 7.0)
MIN_GAP = _f("ILLUSTRATION_MIN_GAP", 9.0)      # seconds of face between scenes
MIN_START = _f("ILLUSTRATION_MIN_START", 3.0)   # never take over the opening
TAIL_GUARD = _f("ILLUSTRATION_TAIL_GUARD", 2.0)  # nor the very last seconds
MAX_SCENES = _i("ILLUSTRATION_MAX_SCENES", 40)
LEAD = _f("ILLUSTRATION_LEAD", 0.15)            # start just before the beat
# No visual type may exceed this share of the storyboard — forces diversity.
MAX_TYPE_SHARE = _f("ILLUSTRATION_MAX_TYPE_SHARE", 0.45)
# Two scenes whose concepts overlap by more than this are considered repeats.
REPEAT_SIMILARITY = _f("ILLUSTRATION_REPEAT_SIMILARITY", 0.6)

# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
# Optional heavy dependency. When absent the whiteboard renderer uses its own
# native reveal engine (PIL + numpy only).
USE_WHITEBOARD_ANIMATOR = _b("ILLUSTRATION_USE_WHITEBOARD_ANIMATOR", True)
WHITEBOARD_QUALITY = os.getenv("ILLUSTRATION_WHITEBOARD_QUALITY", "medium")
# Cap the CPU cost of the third-party animator on a small VPS.
WHITEBOARD_MAX_DUR = _f("ILLUSTRATION_WHITEBOARD_MAX_DUR", 9.0)

PRORES_PROFILE = os.getenv("ILLUSTRATION_PRORES_PROFILE", "4444")
PRORES_PIX_FMT = os.getenv("ILLUSTRATION_PRORES_PIX_FMT", "yuva444p10le")

# Parallel scene rendering. 0 means "decide from cpu_count".
RENDER_WORKERS = _i("ILLUSTRATION_RENDER_WORKERS", 0)

# --------------------------------------------------------------------------- #
# audio
# --------------------------------------------------------------------------- #
SFX_ENABLED = _b("ILLUSTRATION_SFX_ENABLED", True)
SFX_GAIN = _f("ILLUSTRATION_SFX_GAIN", 0.55)
MUSIC_DUCK_DB = _f("ILLUSTRATION_MUSIC_DUCK_DB", -9.0)
SFX_DUCK_DB = _f("ILLUSTRATION_SFX_DUCK_DB", -4.0)
DUCK_ATTACK = _f("ILLUSTRATION_DUCK_ATTACK", 0.12)
DUCK_RELEASE = _f("ILLUSTRATION_DUCK_RELEASE", 0.35)

# --------------------------------------------------------------------------- #
# cache
# --------------------------------------------------------------------------- #
CACHE_ENABLED = _b("ILLUSTRATION_CACHE_ENABLED", True)
CACHE_DIR = os.getenv("ILLUSTRATION_CACHE_DIR", "")


def aspect_size(aspect: str | None = None) -> Tuple[int, int]:
    """(width, height) for an aspect name, defaulting to the configured one."""
    return ASPECTS.get(aspect or DEFAULT_ASPECT, ASPECTS["16:9"])


def intensity_profile(name: str | None = None) -> Dict[str, float]:
    return dict(INTENSITY.get(name or DEFAULT_INTENSITY, INTENSITY["medium"]))
