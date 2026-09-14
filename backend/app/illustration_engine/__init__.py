"""CutForge illustration engine.

An AI illustration director: it reads the transcript of a talking-head video,
works out which moments a picture would actually help with, designs a scene
for each, animates it in sync with the voice, scores it, and hands the clips
back to the montage pipeline. The original footage stays the backbone.

Quick use:

    from app.illustration_engine import IllustrationDirector

    director = IllustrationDirector(style="professional", aspect="16:9")
    result = director.run(vu_transcript, "out/illustrations")
    result.legacy_clips        # drop-in for the montage overlay planner
"""
from __future__ import annotations

from . import config
from .director import IllustrationDirector, DirectorResult
from .schemas import (
    AnimationInstruction, Box, IllustrationScene, IllustrationTimeline,
    RenderedIllustration, SFXCue, Storyboard, VisualElement, VisualOpportunity,
    VISUAL_TYPES, PATTERNS,
)
from .styles import STYLES, UI_STYLES, get_style, style_names

__all__ = [
    "IllustrationDirector", "DirectorResult", "config",
    "AnimationInstruction", "Box", "IllustrationScene", "IllustrationTimeline",
    "RenderedIllustration", "SFXCue", "Storyboard", "VisualElement",
    "VisualOpportunity", "VISUAL_TYPES", "PATTERNS",
    "STYLES", "UI_STYLES", "get_style", "style_names",
]

__version__ = "1.0.0"


def is_enabled() -> bool:
    """Whether the new engine should run at all (ILLUSTRATION_ENGINE_ENABLED)."""
    return bool(config.ENABLED)
