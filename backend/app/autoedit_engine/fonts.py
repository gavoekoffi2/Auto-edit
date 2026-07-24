"""
Font resolution for PIL overlays / B-roll / keyword popups.

Looks for Google Fonts in ``~/.fonts`` and the system font tree, falling back
to the always-present DejaVuSans-Bold so rendering never hard-fails.
"""
from __future__ import annotations

import glob
import os
from functools import lru_cache
from typing import Any, Optional

from PIL import ImageFont

from . import config

_SEARCH_DIRS = [
    # Polices OFL embarquées dans le repo — toujours présentes, build
    # reproductible sans téléchargement réseau.
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts"),
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
    "poppins": ["Poppins-SemiBold", "Poppins-Bold", "Poppins"],
    "caveat": ["Caveat-Bold", "Caveat"],
    # Serif éditorial élégant (style affiche / board de présentation).
    "playfair": ["PlayfairDisplay-Variable", "PlayfairDisplay"],
    "playfair italic": ["PlayfairDisplay-Italic-Variable", "PlayfairDisplay-Italic"],
    "dejavusans": ["DejaVuSans-Bold"],
}

# Familles variables dont l'axe de graisse doit être forcé (sinon PIL rend
# l'axe par défaut, souvent trop fin pour de la vidéo).
_VARIATION_WEIGHTS = {
    "montserrat": ("ExtraBold", "Bold"),
    "playfair": ("SemiBold", "Medium"),
    "playfair italic": ("SemiBold", "Medium"),
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
def load_font(family: str, size: int) -> Any:
    """Load *family* at *size*, falling back to DejaVuSans-Bold."""
    path = _find_font_file(family)
    if path is None:
        path = config.FONT_FALLBACK
    try:
        font = ImageFont.truetype(path, size)
        # Variable fonts default to their lightest axis in Pillow inside the
        # production image. That made overlay/popup text look like hollow black
        # outlines on video. Force a strong weight for PIL-rendered graphics.
        key = next((k for k in _VARIATION_WEIGHTS if k in family.lower()), None)
        if key and hasattr(font, "set_variation_by_name"):
            for weight in _VARIATION_WEIGHTS[key]:
                try:
                    font.set_variation_by_name(weight)
                    break
                except Exception:
                    continue
        return font
    except OSError:
        fallback = config.FONT_FALLBACK if os.path.exists(config.FONT_FALLBACK) else _find_font_file("dejavusans")
        if fallback:
            try:
                return ImageFont.truetype(fallback, size)
            except OSError:
                pass
        return ImageFont.load_default()
