"""Styles visuels et sonores du moteur YouTube long.

Chaque style est un « contrat » complet : typo, couleurs des sous-titres,
cartes chapitre, popups mots-clés, force des zooms et palette d'effets
sonores. Le style ``auto`` choisit un style de façon stable à partir d'une
graine propre à la vidéo : deux vidéos successives d'une même chaîne n'ont
donc pas le même look (pas de motif répété qui trahirait l'automatisation).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional


@dataclass(frozen=True)
class LongformStyle:
    id: str
    name: str
    # --- sous-titres -------------------------------------------------------
    caption_font: str
    caption_size: int
    caption_uppercase: bool
    caption_primary: str          # couleur des mots (hex RRGGBB)
    caption_highlight: str        # mot en cours (karaoké)
    caption_outline: str
    caption_outline_px: float
    caption_box: bool             # pavé semi-opaque derrière la ligne
    caption_box_color: str
    caption_margin_v: int         # distance au bas de l'image (px, 1080p)
    words_per_line: int
    # --- cartes chapitre / popups -----------------------------------------
    title_font: str
    card_bg: str
    card_fg: str
    card_accent: str
    popup_bg: str
    popup_fg: str
    # --- dynamique image ---------------------------------------------------
    punch_zoom: float             # zoom « serré » alterné à chaque coupe
    emphasis_zoom: float          # zoom fort sur les phrases d'emphase
    grade: str                    # filtre ffmpeg d'étalonnage ('' = aucun)
    # --- son ---------------------------------------------------------------
    sfx_chapter: List[str] = field(default_factory=list)
    sfx_popup: List[str] = field(default_factory=list)
    sfx_zoom: List[str] = field(default_factory=list)
    sfx_caption_click: str = "click"
    caption_click_db: float = -30.0   # 'off' si None
    sfx_db: float = -14.0             # gain des SFX de visuel
    music_db: float = -30.0           # niveau du lit musical (avant ducking)


# Étalonnages volontairement limités au filtre `eq` (travaille directement en
# YUV) : `colorbalance`/`curves` passent par du RGB flottant et rendaient le
# décodage ~12x plus lent — rédhibitoire sur une heure de vidéo.
_GRADE_WARM = "eq=contrast=1.06:brightness=-0.01:saturation=1.05:gamma_r=1.03:gamma_b=0.97"
_GRADE_DOC = "eq=contrast=1.11:brightness=-0.02:saturation=0.86:gamma=0.97"
_GRADE_COOL = "eq=contrast=1.05:saturation=0.98:gamma_b=1.03:gamma_r=0.99"


STYLES: Dict[str, LongformStyle] = {
    "studio_clean": LongformStyle(
        id="studio_clean", name="Studio épuré",
        caption_font="Poppins", caption_size=58, caption_uppercase=False,
        caption_primary="FFFFFF", caption_highlight="FFD60A",
        caption_outline="000000", caption_outline_px=0.0,
        caption_box=True, caption_box_color="101014",
        caption_margin_v=70, words_per_line=6,
        title_font="Poppins",
        card_bg="F6F4EF", card_fg="15151A", card_accent="FFB800",
        popup_bg="FFD60A", popup_fg="15151A",
        punch_zoom=1.10, emphasis_zoom=1.22, grade=_GRADE_WARM,
        sfx_chapter=["swoosh_up", "transition", "whoosh"],
        sfx_popup=["pop", "ding", "bubble"],
        sfx_zoom=["whoosh"],
        caption_click_db=-32.0, sfx_db=-15.0, music_db=-30.0,
    ),
    "energie_createur": LongformStyle(
        id="energie_createur", name="Énergie créateur",
        caption_font="Anton", caption_size=76, caption_uppercase=True,
        caption_primary="FFFFFF", caption_highlight="3DFF8B",
        caption_outline="000000", caption_outline_px=5.0,
        caption_box=False, caption_box_color="000000",
        caption_margin_v=90, words_per_line=4,
        title_font="Anton",
        card_bg="111111", card_fg="FFFFFF", card_accent="3DFF8B",
        popup_bg="3DFF8B", popup_fg="0B0B0B",
        punch_zoom=1.15, emphasis_zoom=1.30, grade=_GRADE_WARM,
        sfx_chapter=["impact", "cinematic_hit", "bass_hit"],
        sfx_popup=["snap", "pop", "digi_blip"],
        sfx_zoom=["swoosh_up", "whoosh"],
        caption_click_db=-28.0, sfx_db=-13.0, music_db=-28.0,
    ),
    "documentaire": LongformStyle(
        id="documentaire", name="Documentaire",
        caption_font="Montserrat", caption_size=52, caption_uppercase=False,
        caption_primary="F2F2F2", caption_highlight="F2F2F2",
        caption_outline="000000", caption_outline_px=2.5,
        caption_box=False, caption_box_color="000000",
        caption_margin_v=64, words_per_line=7,
        title_font="Playfair Display",
        card_bg="0E0E0E", card_fg="F4EFE6", card_accent="C9A227",
        popup_bg="F4EFE6", popup_fg="0E0E0E",
        punch_zoom=1.06, emphasis_zoom=1.14, grade=_GRADE_DOC,
        sfx_chapter=["cinematic_hit", "transition", "reverse_swell"],
        sfx_popup=["chime", "click"],
        sfx_zoom=[],
        caption_click_db=-36.0, sfx_db=-17.0, music_db=-32.0,
    ),
    "tech_minimal": LongformStyle(
        id="tech_minimal", name="Tech minimal",
        caption_font="Montserrat", caption_size=56, caption_uppercase=False,
        caption_primary="FFFFFF", caption_highlight="38E1FF",
        caption_outline="000000", caption_outline_px=0.0,
        caption_box=True, caption_box_color="0A1224",
        caption_margin_v=72, words_per_line=6,
        title_font="Bebas Neue",
        card_bg="0A1224", card_fg="FFFFFF", card_accent="38E1FF",
        popup_bg="0A1224", popup_fg="38E1FF",
        punch_zoom=1.12, emphasis_zoom=1.24, grade=_GRADE_COOL,
        sfx_chapter=["glitch", "swoosh_down", "data_tick"],
        sfx_popup=["digi_blip", "data_tick", "click"],
        sfx_zoom=["swoosh_up"],
        caption_click_db=-31.0, sfx_db=-15.0, music_db=-30.0,
    ),
}

AUTO_POOL = ("studio_clean", "energie_createur", "documentaire", "tech_minimal")

#: Style par défaut de chaque mode produit (surchargeable par l'option
#: ``longform_style`` du job).
MODE_STYLE = {
    "youtube_long": "auto",
    "youtube_long_sobre": "documentaire",
    "youtube_long_energie": "energie_createur",
}


def seed_for(path: str, extra: str = "") -> int:
    """Graine stable par vidéo (nom + taille), indépendante du serveur."""
    import os
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    h = hashlib.sha1(f"{os.path.basename(path)}|{size}|{extra}".encode()).hexdigest()
    return int(h[:8], 16)


def resolve_style(style_id: Optional[str], seed: int = 0) -> LongformStyle:
    """``auto`` / inconnu -> un style du pool choisi par la graine."""
    sid = (style_id or "auto").strip().lower()
    if sid in STYLES:
        return STYLES[sid]
    return STYLES[AUTO_POOL[seed % len(AUTO_POOL)]]


def with_overrides(style: LongformStyle, **kw) -> LongformStyle:
    kw = {k: v for k, v in kw.items() if v is not None}
    return replace(style, **kw) if kw else style


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    """'RRGGBB' -> '&HAABBGGRR' (alpha 0 = opaque, 255 = transparent)."""
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()
