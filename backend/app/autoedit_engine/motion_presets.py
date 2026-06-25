"""
Motion-design presets — varied looks so two videos never feel identical.

The credit-saver edit leans heavily on motion design (it does not depend on AI
B-roll), so the look must change from one video to the next. Each preset is a
named *family* with its own palette, shape density and animation flavour:

    clean_fintech     cards, thin lines, badges — blue / green / white
    neon_social       glow, streaks, highlights — violet / cyan
    african_premium   orange / gold / deep green, subtle, never folkloric
    minimal_creator   mostly zooms / flashes / captions, very few shapes
    kinetic_education  arrows, circles, underlines, explanatory labels

A *stable seed* (hash of videoId | jobId | transcriptText) picks the preset, so
a given job is reproducible while different jobs vary. Colours reuse the engine
palette tuple shape ``(bg_top, bg_bottom, accent_rgba, gold_rgba)`` so the
existing motion renderer can consume them unchanged.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Tuple

RGB = Tuple[int, int, int]
RGBA = Tuple[int, int, int, int]


@dataclass(frozen=True)
class MotionDesignPreset:
    name: str
    bg_top: RGB
    bg_bottom: RGB
    accent: RGBA          # primary ink (arrows / doodles)
    gold: RGBA            # secondary ink (highlights / counters)
    shape_density: float  # 0..1 — how many decorative shapes/cards appear
    style: str            # free-form flavour tag for renderers/tests

    def palette(self) -> Tuple[RGB, RGB, RGBA, RGBA]:
        """The engine palette tuple consumed by motion_design.select_palette."""
        return (self.bg_top, self.bg_bottom, self.accent, self.gold)


# Order matters: index 0 is the safe signature look, used as the default.
PRESETS: List[MotionDesignPreset] = [
    MotionDesignPreset(
        name="clean_fintech",
        bg_top=(11, 16, 30), bg_bottom=(18, 28, 52),
        accent=(90, 160, 255, 255), gold=(80, 230, 170, 255),
        shape_density=0.7, style="cards_lines_badges",
    ),
    MotionDesignPreset(
        name="neon_social",
        bg_top=(18, 12, 32), bg_bottom=(36, 14, 54),
        accent=(170, 110, 255, 255), gold=(90, 230, 255, 255),
        shape_density=0.85, style="glow_streaks_highlights",
    ),
    MotionDesignPreset(
        name="african_premium",
        bg_top=(20, 16, 10), bg_bottom=(34, 22, 12),
        accent=(255, 168, 56, 255), gold=(70, 200, 130, 255),
        shape_density=0.6, style="gold_orange_deepgreen",
    ),
    MotionDesignPreset(
        name="minimal_creator",
        bg_top=(12, 14, 20), bg_bottom=(20, 22, 30),
        accent=(0, 220, 255, 255), gold=(255, 255, 255, 255),
        shape_density=0.25, style="zooms_flashes_captions",
    ),
    MotionDesignPreset(
        name="kinetic_education",
        bg_top=(14, 18, 28), bg_bottom=(22, 30, 48),
        accent=(255, 199, 64, 255), gold=(90, 170, 255, 255),
        shape_density=0.9, style="arrows_circles_underlines",
    ),
]

PRESETS_BY_NAME: Dict[str, MotionDesignPreset] = {p.name: p for p in PRESETS}
DEFAULT_PRESET = PRESETS[0].name


def style_seed(*parts: object) -> int:
    """Stable 32-bit seed from the first non-empty of *parts*.

    Usage mirrors the spec: ``style_seed(video_id, job_id, transcript_text)``.
    A given identifier always yields the same seed (reproducible job), while
    different identifiers spread across the preset families.
    """
    key = next((str(p) for p in parts if p), "autoedit")
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest, 16) & 0xFFFFFFFF


def choose_preset(*parts: object) -> MotionDesignPreset:
    """Deterministically pick a preset family from a stable seed of *parts*."""
    seed = style_seed(*parts)
    return PRESETS[seed % len(PRESETS)]


def preset_for(name: str | None) -> MotionDesignPreset:
    """Look up a preset by name, falling back to the default family."""
    if name and name in PRESETS_BY_NAME:
        return PRESETS_BY_NAME[name]
    return PRESETS_BY_NAME[DEFAULT_PRESET]


def palette_for_preset(name: str | None) -> Tuple[RGB, RGB, RGBA, RGBA]:
    return preset_for(name).palette()
