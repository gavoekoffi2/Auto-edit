"""
Font resolution for PIL overlays / B-roll / keyword popups.

Looks for Google Fonts in ``~/.fonts`` and the system font tree, falling back
to the always-present DejaVuSans-Bold so rendering never hard-fails.
"""
from __future__ import annotations

import glob
import os
from functools import lru_cache
from typing import Optional

from PIL import ImageFont

from . import config

_SEARCH_DIRS = [
    os.path.expanduser("~/.fonts"),
    "/usr/share/fonts",
    "/usr/local/share/fonts",
]

# Preferred filename fragments per family (case-insensitive substring match).
_FAMILY_HINTS = {
    "montserrat": ["Montserrat-Bold", "Montserrat"],
    "anton": ["Anton-Regular", "Anton"],
    "bangers": ["Bangers-Regular", "Bangers"],
    "bebas neue": ["BebasNeue-Regular", "BebasNeue"],
    "bebas": ["BebasNeue-Regular", "BebasNeue"],
    "inter": ["Inter-Bold", "Inter"],
    "dejavusans": ["DejaVuSans-Bold"],
}


@lru_cache(maxsize=128)
def _find_font_file(family: str) -> Optional[str]:
    hints = _FAMILY_HINTS.get(family.lower(), [family])
    for hint in hints:
        for base in _SEARCH_DIRS:
            if not os.path.isdir(base):
                continue
            matches = glob.glob(os.path.join(base, "**", f"*{hint}*.ttf"), recursive=True)
            matches += glob.glob(os.path.join(base, "**", f"*{hint}*.otf"), recursive=True)
            if matches:
                return sorted(matches)[0]
    return None


@lru_cache(maxsize=256)
def load_font(family: str, size: int) -> ImageFont.FreeTypeFont:
    """Load *family* at *size*, falling back to DejaVuSans-Bold."""
    path = _find_font_file(family)
    if path is None:
        path = config.FONT_FALLBACK
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype(config.FONT_FALLBACK, size)
