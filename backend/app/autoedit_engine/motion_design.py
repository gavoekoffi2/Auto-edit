"""
STEP 6bis — MOTION DESIGN ILLUSTRÉ (PIL -> ProRes 4444 RGBA).

Full-frame animated scenes that DRAW what the speaker is explaining — not just
text.  Each scene takes over the frame for ~4.5-5.5 s while the voice keeps
talking, exactly like a pro explainer insert:

  * dark premium stage (gradient + drifting dot grid + vignette)
  * the ILLUSTRATION of the spoken idea:
      - AI flat-design image when available (``scene["image"]``), presented in
        a glowing rounded panel with pop-in, float and slow Ken Burns;
      - otherwise a PROCEDURAL line-art drawing (icon library below) that is
        drawn on screen stroke by stroke, whiteboard style;
  * hand-drawn animated doodles: curved arrows that draw themselves toward the
    illustration, a sketch circle around the headline, sparkles popping;
  * the headline keyword + kicker chip, numbered step pills (kind="steps") or
    an animated counter (kind="number");
  * entrance light-sweep + flash, exit fade — the SFX cues (riser, whoosh,
    pops on each element) are planned from the ``events`` this module exports.

Usage:
    python -m app.autoedit_engine.motion_design scenes.json --outdir motion_clips
    python -m app.autoedit_engine.motion_design --from-vu transcripts/v_vu.json --outdir motion_clips
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# Pillow-version-robust LANCZOS (Resampling moved in 9.1; constants vary by version).
try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    _RESAMPLE = Image.LANCZOS  # noqa: PIL legacy fallback

from . import config
from . import content
from . import silhouettes
from .fonts import load_font
from .render_utils import ProResPipe, alpha_fade, clamp, ease_in_out, ease_out_back, ease_out_cube

W, H = config.WIDTH, config.HEIGHT
ACCENT = config.MOTION_ACCENT
GOLD = config.MOTION_GOLD
INK = config.MOTION_INK
# Stage background (mutable: varied per video by select_palette()).
BG_TOP = config.MOTION_BG_TOP
BG_BOTTOM = config.MOTION_BG_BOTTOM


def select_palette(seed_text: str, preset: Optional[str] = None) -> str:
    """Pick a per-video colour palette (accent/gold/background).

    When *preset* names a motion-design family it is used directly (the
    credit-saver edit drives this so the look varies per video in a
    reproducible way). Otherwise a stable seed of the spoken content chooses a
    family, so two different videos never share the same look — even when every
    scene falls back to the procedural drawings. Returns the chosen family name.
    """
    global ACCENT, GOLD, BG_TOP, BG_BOTTOM, INK
    try:
        from . import motion_presets
        chosen = (motion_presets.preset_for(preset) if preset
                  else motion_presets.choose_preset(seed_text))
        BG_TOP, BG_BOTTOM, ACCENT, GOLD = chosen.palette()
        # Encre du texte: sombre sur les familles à fond clair (sketch_notes),
        # blanche partout ailleurs — sinon les titres seraient illisibles.
        INK = getattr(chosen, "ink", config.MOTION_INK)
        return chosen.name
    except Exception:
        # Fallback to the legacy palette table if presets are unavailable.
        palettes = getattr(config, "MOTION_PALETTES", None)
        if not palettes:
            return "default"
        import hashlib
        h = int(hashlib.md5((seed_text or "x").encode("utf-8")).hexdigest(), 16)
        bg_top, bg_bot, accent, gold = palettes[h % len(palettes)]
        BG_TOP, BG_BOTTOM = bg_top, bg_bot
        ACCENT, GOLD = accent, gold
        return "legacy"
STROKE_W = 14                      # doodle ink width (px)

# --------------------------------------------------------------------------- #
# scene LAYOUTS — distinct compositions, not just recoloured copies of the
# same template. A preset (motion_presets.py) only changes the colour/shape
# density; a layout changes WHERE things sit and HOW the background moves, so
# two scenes genuinely look like a different piece of design:
#
#   stage_center     signature look — centered panel, chip kicker, dot grid
#   split_panel      illustration as a wide letterboxed strip, single
#                     diagonal connector arrow, vertical drifting lines
#   badge_top        big illustration low on the frame, kicker+headline fused
#                     into a full-width ribbon banner across the top, rays
#   fullbleed_frame  illustration bleeds edge-to-edge, headline lives in a
#                     lower-third caption bar instead of floating mid-screen
#   corner_stack     small illustration tucked top-right, big vertical
#                     stacked kicker+headline chip pinned to the left edge,
#                     drifting diagonal corner wedges in the background
#   ticker_strip     illustration centered high, headline rides a bold
#                     horizontal marquee/ticker bar near the bottom, faint
#                     scrolling dash lines
#   frame_card       illustration sits inside a bracketed "card" with corner
#                     ticks (polaroid feel), headline centered just under the
#                     card, thin scanline shimmer in the background
#   diagonal_split   the frame is cut by a diagonal: illustration on one
#                     side, headline running along the cut on the other,
#                     a single bright diagonal seam sweeping slowly
#   circle_spot      the illustration is masked in a big CIRCLE (spotlight)
#                     with an accent orbit ring, headline below — breaks the
#                     "square panel" monotony entirely
#   polaroid_tilt    instant-photo look: white-framed tilted polaroid card,
#                     headline hand-written under the photo, drifting
#                     confetti in the background
#   arch_gate        the illustration lives in an ARCH (rounded-top portal),
#                     headline + sketch circle under the gate, faint rays
#
# Eleven structurally different compositions — and three different image
# MASKS (rounded panel / circle / arch / polaroid) — mean a video with
# several motion-design beats genuinely ALTERNATES between designs instead
# of settling on one template for its whole length; across videos the
# sequence is reshuffled (seeded by the spoken content) so two edits rarely
# walk through the layouts in the same order either.
# --------------------------------------------------------------------------- #
LAYOUTS = [
    "stage_center", "split_panel", "badge_top", "fullbleed_frame",
    "corner_stack", "ticker_strip", "frame_card", "diagonal_split",
    "circle_spot", "polaroid_tilt", "arch_gate",
]

# --------------------------------------------------------------------------- #
# BOARD layouts — famille à part (style "board_pitch").
#
# Répliquent le langage visuel d'un board de présentation motion-design: un
# panneau vert sapin texturé qui NE BOUGE PAS (titre serif en haut à droite,
# label serif à gauche, pile de flyers) + une grande CARTE-SCÈNE claire au
# format 9:16 qui joue le contenu. D'un beat à l'autre le panneau reste
# identique et seule la carte change — c'est ce qui donne la sensation d'une
# vraie présentation plutôt que d'une suite de vignettes sans lien.
#
#   board_stage   illustration plein cadre dans la carte + mot-clé en bas
#   board_quote   pas d'image: la phrase prononcée en serif italique, le
#                  mot-clé en gras barré/souligné dessous (grille de "+")
#   board_number  gros chiffre serif + label au-dessus + unité en gras
#   board_split   illustration en haut de la carte, mot-clé sur bandeau bas
# --------------------------------------------------------------------------- #
#   board_overflow  objet géant coupé par les bords, en diagonale opposée,
#                    mot-clé centré par-dessus
#   board_sandwich  serif en haut + illustration contenue au centre + serif en
#                    bas (le « sandwich typographique » de la référence)
#   board_collage   mini-étiquettes sombres qui pop en cascade autour de
#                    l'illustration, question serif au centre
#   board_annotated illustration zoomée + étiquettes d'annotation en relief
#   board_showcase  « packshot »: visuel incliné encadré de blanc + code-barres
BOARD_LAYOUTS = [
    "board_stage", "board_quote", "board_split", "board_number",
    "board_overflow", "board_sandwich", "board_collage", "board_annotated",
    "board_showcase",
]

# Les compositions qui reçoivent les coins « vague » noirs (décor animé). Elles
# alternent avec les cartes nues pour que le décor lui-même ne devienne pas une
# signature figée.
BOARD_WAVE_LAYOUTS = {"board_sandwich", "board_collage", "board_showcase"}

# Compositions qui accueillent bien une SILHOUETTE plein pied: elles montrent
# l'illustration entière. Les autres la recadrent (haut ou bas de carte) ou la
# déforment, ce qui couperait le personnage en deux.
BOARD_SILHOUETTE_LAYOUTS = ["board_stage", "board_sandwich", "board_annotated",
                            "board_showcase"]
# Idem côté compositions génériques: seules celles au masque rectangulaire
# gardent le personnage entier (le cercle/l'arche lui couperaient tête et pieds).
GENERIC_SILHOUETTE_LAYOUTS = {"stage_center", "fullbleed_frame", "frame_card",
                              "split_panel", "ticker_strip"}

# Géométrie du board (px, cadre 1080x1920). La carte est elle-même un 9:16 et
# s'arrête au-dessus de la bande des sous-titres (ZONE_SUBS_Y) pour ne jamais
# passer dessous.
BOARD_CARD = (400, 330, 1020, 1432)      # x0, y0, x1, y1  (620 x 1102)
BOARD_TITLE_Y = 250                      # titre serif, aligné à droite
BOARD_LABEL_Y = 500                      # label serif, aligné à gauche
BOARD_MARGIN = 58
BOARD_DEFAULT_TITLE = "L'essentiel"
BOARD_DEFAULT_LABEL = "Le point"

# The illustration MASK each layout uses (default: rounded panel). This is
# what kills the "toujours un carré avec l'image dedans" repetition.
LAYOUT_ILLU_SHAPES = {
    "circle_spot": "circle",
    "polaroid_tilt": "polaroid",
    "arch_gate": "arch",
}


def _layout_sequence(seed_text: str, n: int) -> List[str]:
    """A per-video shuffled rotation through every layout, never repeating
    the same one twice in a row, so a single video alternates between many
    designs instead of looping a short cycle.
    """
    import random
    rng = random.Random(seed_text or "x")
    seq: List[str] = []
    last: Optional[str] = None
    while len(seq) < n:
        pool = list(LAYOUTS)
        rng.shuffle(pool)
        if last is not None and pool[0] == last and len(pool) > 1:
            pool[0], pool[1] = pool[1], pool[0]
        seq.extend(pool)
        last = seq[-1]
    return seq[:n]


def _board_layout_sequence(seed_text: str, n: int) -> List[str]:
    """Rotation des compositions de CARTE pour le style board.

    Le panneau ne change pas — seule la carte change — donc on alterne les
    compositions sans jamais répéter la même deux fois de suite, en partant
    d'un point différent selon la vidéo.
    """
    import hashlib
    if n <= 0:
        return []
    offset = int(hashlib.md5((seed_text or "board").encode("utf-8")).hexdigest(), 16)
    k = len(BOARD_LAYOUTS)
    return [BOARD_LAYOUTS[(offset + i) % k] for i in range(n)]

# Scene animation timeline (seconds from scene start).  These are the moments
# plan_overlays converts into per-element SFX cues.
T_ILLU = 0.12        # illustration pop / draw-on starts
T_KICKER = 0.05
T_HEADLINE = 0.42
T_UNDERLINE = 0.75
T_CIRCLE = 0.85
T_ARROWS = 0.95
T_ELEMENTS = 1.05    # first step pill / counter start
STEP_STAGGER = 0.50
EXIT_FADE = 0.22


# --------------------------------------------------------------------------- #
# procedural icon library — every stroke is a polyline in normalized [0,1]²
# coordinates; the renderer reveals them progressively (draw-on / whiteboard).
# --------------------------------------------------------------------------- #
Stroke = List[Tuple[float, float]]


def _arc(cx: float, cy: float, r: float, a0: float, a1: float, n: int = 28,
         ry: Optional[float] = None) -> Stroke:
    ry = r if ry is None else ry
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
             cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def _icon_money() -> List[Stroke]:
    rect = [(0.08, 0.28), (0.92, 0.28), (0.92, 0.72), (0.08, 0.72), (0.08, 0.28)]
    return [rect, _arc(0.5, 0.5, 0.13, 0, 2 * math.pi),
            [(0.18, 0.44), (0.18, 0.56)], [(0.82, 0.44), (0.82, 0.56)]]


def _icon_growth() -> List[Stroke]:
    return [[(0.10, 0.12), (0.10, 0.88), (0.92, 0.88)],
            [(0.16, 0.74), (0.36, 0.56), (0.52, 0.64), (0.86, 0.24)],
            [(0.70, 0.24), (0.86, 0.24), (0.86, 0.40)]]


def _icon_phone() -> List[Stroke]:
    rect = [(0.30, 0.06), (0.70, 0.06), (0.70, 0.94), (0.30, 0.94), (0.30, 0.06)]
    return [rect, [(0.42, 0.14), (0.58, 0.14)], _arc(0.5, 0.84, 0.035, 0, 2 * math.pi)]


def _icon_people() -> List[Stroke]:
    return [_arc(0.36, 0.30, 0.13, 0, 2 * math.pi),
            _arc(0.36, 0.80, 0.24, math.pi, 2 * math.pi),
            _arc(0.72, 0.36, 0.10, 0, 2 * math.pi),
            _arc(0.72, 0.76, 0.18, math.pi, 2 * math.pi)]


def _icon_cart() -> List[Stroke]:
    return [[(0.06, 0.18), (0.20, 0.18), (0.32, 0.62), (0.82, 0.62), (0.92, 0.30), (0.28, 0.30)],
            _arc(0.40, 0.78, 0.06, 0, 2 * math.pi), _arc(0.74, 0.78, 0.06, 0, 2 * math.pi)]


def _icon_idea() -> List[Stroke]:
    return [_arc(0.5, 0.40, 0.22, -0.25 * math.pi, 1.25 * math.pi),
            [(0.40, 0.62), (0.40, 0.74), (0.60, 0.74), (0.60, 0.62)],
            [(0.43, 0.82), (0.57, 0.82)],
            [(0.5, 0.06), (0.5, 0.13)], [(0.18, 0.18), (0.26, 0.24)],
            [(0.82, 0.18), (0.74, 0.24)], [(0.10, 0.44), (0.19, 0.44)],
            [(0.90, 0.44), (0.81, 0.44)]]


def _icon_target() -> List[Stroke]:
    return [_arc(0.5, 0.55, 0.34, 0, 2 * math.pi), _arc(0.5, 0.55, 0.18, 0, 2 * math.pi),
            [(0.86, 0.10), (0.56, 0.50)],
            [(0.74, 0.10), (0.86, 0.10), (0.86, 0.22)]]


def _icon_gear() -> List[Stroke]:
    strokes = [_arc(0.5, 0.5, 0.26, 0, 2 * math.pi), _arc(0.5, 0.5, 0.10, 0, 2 * math.pi)]
    for k in range(8):
        a = k * math.pi / 4
        strokes.append([(0.5 + 0.28 * math.cos(a), 0.5 + 0.28 * math.sin(a)),
                        (0.5 + 0.40 * math.cos(a), 0.5 + 0.40 * math.sin(a))])
    return strokes


def _icon_book() -> List[Stroke]:
    return [[(0.5, 0.22), (0.5, 0.82)],
            [(0.5, 0.22), (0.30, 0.14), (0.08, 0.18), (0.08, 0.78), (0.30, 0.74), (0.5, 0.82)],
            [(0.5, 0.22), (0.70, 0.14), (0.92, 0.18), (0.92, 0.78), (0.70, 0.74), (0.5, 0.82)],
            [(0.18, 0.34), (0.40, 0.28)], [(0.60, 0.28), (0.82, 0.34)]]


def _icon_megaphone() -> List[Stroke]:
    return [[(0.10, 0.40), (0.10, 0.62), (0.30, 0.62), (0.66, 0.84), (0.66, 0.18), (0.30, 0.40), (0.10, 0.40)],
            [(0.30, 0.62), (0.34, 0.86), (0.46, 0.86)],
            _arc(0.74, 0.51, 0.10, -0.4 * math.pi, 0.4 * math.pi),
            _arc(0.74, 0.51, 0.20, -0.4 * math.pi, 0.4 * math.pi)]


def _icon_shield() -> List[Stroke]:
    return [[(0.5, 0.06), (0.88, 0.20), (0.88, 0.52), (0.5, 0.94), (0.12, 0.52), (0.12, 0.20), (0.5, 0.06)],
            [(0.32, 0.46), (0.46, 0.62), (0.72, 0.30)]]


def _icon_clock() -> List[Stroke]:
    return [_arc(0.5, 0.5, 0.38, 0, 2 * math.pi),
            [(0.5, 0.26), (0.5, 0.5), (0.70, 0.62)]]


def _icon_rocket() -> List[Stroke]:
    return [[(0.5, 0.04), (0.68, 0.30), (0.68, 0.62), (0.32, 0.62), (0.32, 0.30), (0.5, 0.04)],
            _arc(0.5, 0.34, 0.08, 0, 2 * math.pi),
            [(0.32, 0.48), (0.14, 0.70), (0.32, 0.66)],
            [(0.68, 0.48), (0.86, 0.70), (0.68, 0.66)],
            [(0.44, 0.66), (0.40, 0.84)], [(0.5, 0.66), (0.5, 0.92)], [(0.56, 0.66), (0.60, 0.84)]]


def _icon_map() -> List[Stroke]:
    drop = _arc(0.5, 0.42, 0.26, math.pi * 0.13, math.pi * 0.87)
    drop = [(0.5, 0.92)] + drop[::-1] + [(0.5, 0.92)]
    return [drop, _arc(0.5, 0.40, 0.10, 0, 2 * math.pi)]


def _icon_chart() -> List[Stroke]:
    return [[(0.10, 0.10), (0.10, 0.90), (0.92, 0.90)],
            [(0.22, 0.78), (0.22, 0.56)], [(0.42, 0.78), (0.42, 0.40)],
            [(0.62, 0.78), (0.62, 0.62)], [(0.82, 0.78), (0.82, 0.24)]]


def _icon_star() -> List[Stroke]:
    pts = []
    for k in range(11):
        a = -math.pi / 2 + k * math.pi / 5
        r = 0.42 if k % 2 == 0 else 0.18
        pts.append((0.5 + r * math.cos(a), 0.5 + r * math.sin(a)))
    return [pts]


def _icon_heart() -> List[Stroke]:
    left = _arc(0.32, 0.36, 0.20, math.pi, 2.6 * math.pi)
    right = _arc(0.68, 0.36, 0.20, -0.6 * math.pi, math.pi)
    return [left + [(0.5, 0.86)] + right[::-1]]


def _icon_globe() -> List[Stroke]:
    return [_arc(0.5, 0.5, 0.40, 0, 2 * math.pi),
            _arc(0.5, 0.5, 0.40, 0, 2 * math.pi, ry=0.40 * 0.4),
            [(0.5, 0.10), (0.5, 0.90)], [(0.10, 0.5), (0.90, 0.5)]]


def _icon_chat() -> List[Stroke]:
    bubble = [(0.10, 0.16), (0.90, 0.16), (0.90, 0.66), (0.40, 0.66),
              (0.26, 0.84), (0.30, 0.66), (0.10, 0.66), (0.10, 0.16)]
    return [bubble, [(0.26, 0.36), (0.74, 0.36)], [(0.26, 0.50), (0.60, 0.50)]]


def _icon_lock() -> List[Stroke]:
    body = [(0.22, 0.46), (0.78, 0.46), (0.78, 0.90), (0.22, 0.90), (0.22, 0.46)]
    shackle = _arc(0.5, 0.40, 0.22, math.pi, 2 * math.pi)
    return [body, shackle, _arc(0.5, 0.66, 0.06, 0, 2 * math.pi)]


def _icon_handshake() -> List[Stroke]:
    return [[(0.06, 0.42), (0.30, 0.42), (0.46, 0.56), (0.54, 0.50)],
            [(0.94, 0.42), (0.70, 0.42), (0.54, 0.56), (0.46, 0.50)],
            [(0.30, 0.42), (0.30, 0.26)], [(0.70, 0.42), (0.70, 0.26)]]


def _icon_calendar() -> List[Stroke]:
    rect = [(0.10, 0.20), (0.90, 0.20), (0.90, 0.90), (0.10, 0.90), (0.10, 0.20)]
    return [rect, [(0.10, 0.38), (0.90, 0.38)],
            [(0.28, 0.08), (0.28, 0.28)], [(0.72, 0.08), (0.72, 0.28)],
            [(0.28, 0.58), (0.40, 0.58)], [(0.52, 0.58), (0.64, 0.58)],
            [(0.28, 0.74), (0.40, 0.74)], [(0.52, 0.74), (0.64, 0.74)]]


def _icon_transfer() -> List[Stroke]:
    """Two phones + arrows: money transfer / remittance."""
    left_phone = [(0.10, 0.24), (0.34, 0.24), (0.34, 0.78), (0.10, 0.78), (0.10, 0.24)]
    right_phone = [(0.66, 0.24), (0.90, 0.24), (0.90, 0.78), (0.66, 0.78), (0.66, 0.24)]
    arrow1 = [(0.36, 0.38), (0.56, 0.38), (0.50, 0.31), (0.56, 0.38), (0.50, 0.45)]
    arrow2 = [(0.64, 0.64), (0.44, 0.64), (0.50, 0.57), (0.44, 0.64), (0.50, 0.71)]
    return [left_phone, right_phone, arrow1, arrow2, _arc(0.22, 0.52, 0.055, 0, 2 * math.pi), _arc(0.78, 0.52, 0.055, 0, 2 * math.pi)]


def _icon_crypto() -> List[Stroke]:
    coin = _arc(0.50, 0.50, 0.34, 0, 2 * math.pi)
    b = [(0.43, 0.26), (0.43, 0.74), (0.58, 0.74), (0.66, 0.66), (0.58, 0.58),
         (0.43, 0.58), (0.60, 0.58), (0.68, 0.50), (0.60, 0.42), (0.43, 0.42)]
    return [coin, b, [(0.38, 0.20), (0.38, 0.30)], [(0.58, 0.20), (0.58, 0.30)],
            [(0.38, 0.70), (0.38, 0.82)], [(0.58, 0.70), (0.58, 0.82)]]


def _icon_bank() -> List[Stroke]:
    roof = [(0.10, 0.36), (0.50, 0.12), (0.90, 0.36), (0.10, 0.36)]
    base = [(0.12, 0.82), (0.88, 0.82)]
    cols = []
    for x in (0.24, 0.40, 0.56, 0.72):
        cols.append([(x, 0.42), (x, 0.78)])
    return [roof, base, [(0.16, 0.88), (0.84, 0.88)]] + cols


def _icon_card() -> List[Stroke]:
    card = [(0.10, 0.28), (0.90, 0.28), (0.90, 0.74), (0.10, 0.74), (0.10, 0.28)]
    return [card, [(0.10, 0.42), (0.90, 0.42)], [(0.22, 0.58), (0.44, 0.58)], [(0.68, 0.58), (0.82, 0.58)]]


def _icon_check() -> List[Stroke]:
    return [_arc(0.50, 0.50, 0.40, 0, 2 * math.pi), [(0.28, 0.52), (0.44, 0.68), (0.74, 0.34)]]


def _icon_warning() -> List[Stroke]:
    tri = [(0.50, 0.12), (0.90, 0.84), (0.10, 0.84), (0.50, 0.12)]
    return [tri, [(0.50, 0.34), (0.50, 0.62)], _arc(0.50, 0.73, 0.035, 0, 2 * math.pi)]


ICONS: Dict[str, List[Stroke]] = {
    "money": _icon_money(), "growth": _icon_growth(), "phone": _icon_phone(),
    "people": _icon_people(), "cart": _icon_cart(), "idea": _icon_idea(),
    "target": _icon_target(), "gear": _icon_gear(), "book": _icon_book(),
    "megaphone": _icon_megaphone(), "shield": _icon_shield(),
    "clock": _icon_clock(), "rocket": _icon_rocket(), "map": _icon_map(),
    "chart": _icon_chart(), "star": _icon_star(), "heart": _icon_heart(),
    "globe": _icon_globe(), "chat": _icon_chat(), "lock": _icon_lock(),
    "handshake": _icon_handshake(), "calendar": _icon_calendar(),
    "transfer": _icon_transfer(), "crypto": _icon_crypto(), "bank": _icon_bank(),
    "card": _icon_card(), "check": _icon_check(), "warning": _icon_warning(),
}


# --------------------------------------------------------------------------- #
# draw-on stroke helpers
# --------------------------------------------------------------------------- #
def _seg_len(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _strokes_total_len(strokes: Sequence[Stroke]) -> float:
    return sum(_seg_len(a, b) for s in strokes for a, b in zip(s, s[1:])) or 1e-6


def _partial_strokes(strokes: Sequence[Stroke], frac: float) -> List[Stroke]:
    """Reveal the strokes progressively along their cumulative length."""
    frac = clamp(frac)
    if frac >= 0.999:
        return list(strokes)
    budget = _strokes_total_len(strokes) * frac
    out: List[Stroke] = []
    for stroke in strokes:
        if budget <= 0:
            break
        partial: Stroke = [stroke[0]]
        for a, b in zip(stroke, stroke[1:]):
            d = _seg_len(a, b)
            if d <= budget:
                partial.append(b)
                budget -= d
            else:
                t = budget / d if d > 0 else 0.0
                partial.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
                budget = 0
                break
        if len(partial) > 1:
            out.append(partial)
    return out


def _draw_strokes(draw: ImageDraw.ImageDraw, strokes: Sequence[Stroke],
                  box: Tuple[float, float, float, float], color, width: int = STROKE_W):
    """Draw normalized strokes inside *box* with round caps/joints."""
    x0, y0, x1, y1 = box
    sw, sh = x1 - x0, y1 - y0
    r = width / 2
    for stroke in strokes:
        pts = [(x0 + px * sw, y0 + py * sh) for px, py in stroke]
        if len(pts) < 2:
            continue
        draw.line(pts, fill=color, width=width, joint="curve")
        for cap in (pts[0], pts[-1]):
            draw.ellipse((cap[0] - r, cap[1] - r, cap[0] + r, cap[1] + r), fill=color)


def _bezier(p0, p1, p2, n: int = 36) -> Stroke:
    pts: Stroke = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts


def _arrow_strokes(p0, p1, p2, head: float = 34.0) -> List[Stroke]:
    """A curved hand-drawn arrow (quadratic bezier) + its arrowhead."""
    body = _bezier(p0, p1, p2)
    (ax, ay), (bx, by) = body[-2], body[-1]
    ang = math.atan2(by - ay, bx - ax)
    head_l = [(bx - head * math.cos(ang - 0.5), by - head * math.sin(ang - 0.5)), (bx, by)]
    head_r = [(bx - head * math.cos(ang + 0.5), by - head * math.sin(ang + 0.5)), (bx, by)]
    return [body, head_l, head_r]


def _sketch_ellipse(cx: float, cy: float, rx: float, ry: float,
                    turns: float = 1.12, n: int = 64, wobble: float = 5.0) -> Stroke:
    """A hand-sketched ellipse (slight radius wobble, > 1 full turn)."""
    pts: Stroke = []
    total = 2 * math.pi * turns
    for i in range(n + 1):
        a = -0.5 * math.pi + total * i / n
        wob = wobble * math.sin(a * 3.1 + 0.7)
        pts.append((cx + (rx + wob) * math.cos(a), cy + (ry + wob * 0.6) * math.sin(a)))
    return pts


# --------------------------------------------------------------------------- #
# stage (background) + small ui helpers
# --------------------------------------------------------------------------- #
def _stage_base() -> Image.Image:
    """Opaque gradient stage + vignette, computed once per scene.

    The vignette is alpha_composite'd (NOT pasted) so the stage stays fully
    opaque — the scene is a real takeover, nothing may bleed through from the
    video underneath.
    """
    grad = Image.new("RGB", (1, H))
    top, bot = BG_TOP, BG_BOTTOM
    px = grad.load()
    for y in range(H):
        t = y / (H - 1)
        px[0, y] = tuple(int(top[c] + (bot[c] - top[c]) * t) for c in range(3))
    base = grad.resize((W, H)).convert("RGBA")

    vig = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(vig)
    dv.ellipse((-W * 0.35, -H * 0.20, W * 1.35, H * 1.20), fill=255)
    shade_a = vig.filter(ImageFilter.GaussianBlur(160)).point(lambda v: (255 - v) * 110 // 255)
    zero = Image.new("L", (W, H), 0)
    shade = Image.merge("RGBA", (zero, zero, zero, shade_a))
    return Image.alpha_composite(base, shade)


def _dots_layer(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 10.0 * math.sin(t * 0.6)
    for gy in range(120, H - 60, 96):
        for gx in range(60, W, 96):
            x = gx + drift * (1 if (gy // 96) % 2 == 0 else -1)
            d.ellipse((x - 2, gy - 2, x + 2, gy + 2), fill=(255, 255, 255, 16))
    return layer


def _lines_layer(t: float) -> Image.Image:
    """split_panel motif: slow vertical drifting hairlines."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 18.0 * math.sin(t * 0.35)
    for gx in range(40, W, 84):
        x = gx + drift
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 10), width=2)
    return layer


def _rays_layer(t: float) -> Image.Image:
    """badge_top motif: faint rays radiating from the top-center banner."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W // 2, 140
    spin = t * 0.15
    for k in range(14):
        a = spin + k * (2 * math.pi / 14)
        x2, y2 = cx + math.cos(a) * 1400, cy + math.sin(a) * 1400
        d.line([(cx, cy), (x2, y2)], fill=(255, 255, 255, 9), width=3)
    return layer


def _grain_layer(t: float) -> Image.Image:
    """fullbleed_frame motif: sparse drifting dust specks over the bleed image."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 14.0 * math.sin(t * 0.5)
    for gy in range(80, H, 140):
        for gx in range(40, W, 140):
            x = gx + drift * (1 if (gy // 140) % 2 == 0 else -1)
            y = gy + drift * 0.4
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 255, 12))
    return layer


def _wedges_layer(t: float) -> Image.Image:
    """corner_stack motif: drifting diagonal wedges from the top-left corner."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 12.0 * math.sin(t * 0.45)
    for k in range(6):
        off = k * 220 + drift
        d.line([(-200 + off, -200), (1400 + off, 1000)], fill=(255, 255, 255, 11), width=14)
    return layer


def _ticker_layer(t: float) -> Image.Image:
    """ticker_strip motif: faint horizontal dashes scrolling sideways."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    scroll = (t * 140) % 120
    for gy in range(160, H, 220):
        for gx in range(-120, W + 120, 120):
            x = gx - scroll
            d.line([(x, gy), (x + 60, gy)], fill=(255, 255, 255, 12), width=4)
    return layer


def _scanlines_layer(t: float) -> Image.Image:
    """frame_card motif: thin shimmering scanlines drifting downward."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    shift = (t * 60) % 48
    for y in range(int(-48 + shift), H, 48):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 7), width=2)
    return layer


def _diagonal_seam_layer(t: float) -> Image.Image:
    """diagonal_split motif: a single bright seam sweeping slowly across."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 30.0 * math.sin(t * 0.3)
    cx = W * 0.42 + drift
    d.line([(cx - H * 0.5, 0), (cx + H * 0.5, H)], fill=(255, 255, 255, 26), width=6)
    return layer


def _orbits_layer(t: float) -> Image.Image:
    """circle_spot motif: slow rotating dashed orbit rings around the frame."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W // 2, 640
    spin = t * 0.25
    for radius in (430, 560, 700):
        n_dash = max(10, radius // 34)
        for k in range(n_dash):
            a0 = spin + k * (2 * math.pi / n_dash)
            a1 = a0 + (math.pi / n_dash) * 0.9
            pts = [(cx + radius * math.cos(a), cy + radius * math.sin(a))
                   for a in (a0, (a0 + a1) / 2, a1)]
            d.line(pts, fill=(255, 255, 255, 14), width=3)
    return layer


def _confetti_layer(t: float) -> Image.Image:
    """polaroid_tilt motif: small tilted paper squares drifting downward."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    fall = (t * 26) % 260
    for gy in range(-130, H, 260):
        for gx in range(50, W, 190):
            y = gy + fall
            wob = 14.0 * math.sin(t * 0.7 + gx * 0.05)
            x = gx + wob
            s = 9 + (gx // 190 + gy // 260) % 3 * 4
            ang = 0.6 * math.sin(t * 0.5 + gx)
            ca, sa = math.cos(ang), math.sin(ang)
            pts = [(x + ca * dx - sa * dy, y + sa * dx + ca * dy)
                   for dx, dy in ((-s, -s), (s, -s), (s, s), (-s, s))]
            d.polygon(pts, outline=(255, 255, 255, 16))
    return layer


def _bg_motif(layout: str, t: float) -> Image.Image:
    if layout == "split_panel":
        return _lines_layer(t)
    if layout == "badge_top":
        return _rays_layer(t)
    if layout == "fullbleed_frame":
        return _grain_layer(t)
    if layout == "corner_stack":
        return _wedges_layer(t)
    if layout == "ticker_strip":
        return _ticker_layer(t)
    if layout == "frame_card":
        return _scanlines_layer(t)
    if layout == "diagonal_split":
        return _diagonal_seam_layer(t)
    if layout == "circle_spot":
        return _orbits_layer(t)
    if layout == "polaroid_tilt":
        return _confetti_layer(t)
    if layout == "arch_gate":
        return _rays_layer(t)
    return _dots_layer(t)


def _light_sweep(progress: float) -> Image.Image:
    """Diagonal white sweep crossing the frame (entrance transition)."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pos = (progress * 1.6 - 0.3) * (W + H)
    band = 180
    for off in range(-band, band, 8):
        a = int(120 * math.exp(-((off / 110.0) ** 2)))
        if a <= 2:
            continue
        d.line([(pos + off - H, H), (pos + off, 0)], fill=(255, 255, 255, a), width=8)
    return layer


def _fit_font(family: str, size: int, text: str, max_w: int, min_size: int = 30):
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    s = size
    while s > min_size:
        font = load_font(family, s)
        l, t, r, b = probe.textbbox((0, 0), text, font=font, stroke_width=3)
        if r - l <= max_w:
            return font
        s -= 4
    return load_font(family, min_size)


def _apply_alpha(img: Image.Image, factor: float) -> Image.Image:
    if factor >= 0.999:
        return img
    r, g, b, a = img.split()
    a = a.point(lambda v: int(v * factor))
    return Image.merge("RGBA", (r, g, b, a))


def _rounded_image(img: Image.Image, radius: int = 44) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width, img.height), radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def _fmt_value(value: float, raw: str) -> str:
    suffix = "%" if "%" in (raw or "") else ""
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value)):,}".replace(",", " ") + suffix
    return f"{value:,.1f}".replace(",", " ") + suffix


# --------------------------------------------------------------------------- #
# scene rendering
# --------------------------------------------------------------------------- #
def _illu_box(kind: str, layout: str = "stage_center") -> Tuple[int, int, int, int]:
    """Bounds of the illustration zone — varies by *layout* (see LAYOUTS),
    not just by *kind* (steps/number scenes always keep extra room for text).
    """
    if kind == "steps":
        return (210, 330, W - 210, 950)
    if kind == "number":
        return (170, 330, W - 170, 1000)
    if layout == "split_panel":
        return (70, 470, W - 70, 1240)        # wide letterboxed strip, lower
    if layout == "badge_top":
        return (130, 600, W - 130, 1430)      # big panel, room for top ribbon
    if layout == "fullbleed_frame":
        return (0, 210, W, 1540)              # edge-to-edge bleed
    if layout == "corner_stack":
        return (430, 300, W - 60, 1080)       # tucked top-right, room left for the stack
    if layout == "ticker_strip":
        return (140, 260, W - 140, 1280)      # centered high, room low for the ticker bar
    if layout == "frame_card":
        return (160, 300, W - 160, 1220)      # bracketed card, room below for headline
    if layout == "diagonal_split":
        return (340, 360, W - 60, 1300)       # right-of-seam, headline runs along the cut
    if layout == "circle_spot":
        return (225, 330, W - 225, 330 + (W - 450))   # perfect circle, high
    if layout == "polaroid_tilt":
        return (190, 330, W - 190, 1140)      # instant-photo card, room below
    if layout == "arch_gate":
        return (240, 290, W - 240, 1190)      # tall arch portal
    return (120, 330, W - 120, 1130)          # stage_center (signature look)


def _pop(t: float, start: float, dur: float = 0.45) -> float:
    return ease_out_back(clamp((t - start) / dur))


def _linear(t: float, start: float, dur: float) -> float:
    return clamp((t - start) / dur)


def _draw_kicker(draw: ImageDraw.ImageDraw, target: Image.Image, text: str, t: float):
    p = _pop(t, T_KICKER, 0.35)
    if p <= 0:
        return
    font = load_font("Montserrat", 40)
    l, tt, r, b = draw.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - tt
    pad_x, pad_y = 36, 16
    cw, ch = int((tw + 2 * pad_x) * (0.6 + 0.4 * p)), int((th + 2 * pad_y) * (0.6 + 0.4 * p))
    x0, y0 = (W - cw) // 2, 196 - ch // 2 + 40
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=ch // 2,
                         fill=(12, 14, 22, 215), outline=GOLD, width=4)
    if p > 0.55:
        f2 = load_font("Montserrat", int(40 * min(1.0, p)))
        dl.text((W // 2, y0 + ch // 2), text, font=f2, fill=GOLD, anchor="mm")
    target.alpha_composite(layer)


def _draw_headline(draw: ImageDraw.ImageDraw, headline: str, t: float, y: int):
    p = _pop(t, T_HEADLINE, 0.4)
    if p <= 0:
        return
    font = _fit_font("Anton", 132, headline, 940, min_size=64)
    # pop via font size approximation: draw at full size, fade quickly
    a = int(255 * clamp(p * 1.6))
    draw.text((W // 2, y), headline, font=font, anchor="mm",
              fill=(255, 255, 255, a), stroke_width=6, stroke_fill=(0, 0, 0, min(a, 230)))
    # underline draw-on
    up = ease_out_cube(_linear(t, T_UNDERLINE, 0.35))
    if up > 0:
        l, tt, r, b = draw.textbbox((W // 2, y), headline, font=font, anchor="mm")
        width = (r - l) * 0.92 * up
        draw.line([(W // 2 - width / 2, b + 26), (W // 2 + width / 2, b + 26)],
                  fill=GOLD, width=10)


def _draw_headline_circle(draw: ImageDraw.ImageDraw, headline: str, t: float, y: int):
    p = _linear(t, T_CIRCLE, 0.45)
    if p <= 0 or len(headline) > 14:
        return
    font = _fit_font("Anton", 132, headline, 940, min_size=64)
    l, tt, r, b = draw.textbbox((W // 2, y), headline, font=font, anchor="mm")
    rx, ry = (r - l) / 2 + 70, (b - tt) / 2 + 44
    sketch = _sketch_ellipse(W // 2, y, rx, ry)
    _draw_strokes(draw, _partial_strokes([sketch], ease_in_out(p)),
                  (0, 0, 1, 1), ACCENT, width=8)


def _draw_arrows(draw: ImageDraw.ImageDraw, t: float, box: Tuple[int, int, int, int]):
    x0, y0, x1, y1 = box
    cy = (y0 + y1) // 2
    left = _arrow_strokes((70, y1 + 130), (40, cy + 120), (x0 + 30, cy + 60))
    right = _arrow_strokes((W - 70, y0 - 90), (W - 30, y0 + 60), (x1 - 26, y0 + 130))
    pl = ease_in_out(_linear(t, T_ARROWS, 0.5))
    pr = ease_in_out(_linear(t, T_ARROWS + 0.20, 0.5))
    if pl > 0:
        _draw_strokes(draw, _partial_strokes(left, pl), (0, 0, 1, 1), ACCENT, width=11)
    if pr > 0:
        _draw_strokes(draw, _partial_strokes(right, pr), (0, 0, 1, 1), GOLD, width=11)


def _draw_arrow_diagonal(draw: ImageDraw.ImageDraw, t: float, box: Tuple[int, int, int, int]):
    """split_panel layout: a single bold diagonal connector, headline -> panel."""
    x0, y0, x1, y1 = box
    arrow = _arrow_strokes((W - 140, 300), (W // 2 + 40, 360), (x1 - 40, y0 + 70))
    p = ease_in_out(_linear(t, T_ARROWS, 0.55))
    if p > 0:
        _draw_strokes(draw, _partial_strokes(arrow, p), (0, 0, 1, 1), GOLD, width=13)


def _draw_ribbon_banner(draw: ImageDraw.ImageDraw, target: Image.Image,
                        kicker: str, headline: str, t: float):
    """badge_top layout: kicker + headline fused into a full-width top ribbon."""
    p = _pop(t, T_KICKER, 0.4)
    if p <= 0:
        return
    h = int(300 * (0.5 + 0.5 * p))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rectangle((0, 0, W, h), fill=(10, 10, 14, 230))
    dl.line([(0, h), (W, h)], fill=GOLD, width=6)
    if p > 0.4:
        fk = load_font("Montserrat", 38)
        dl.text((W // 2, max(40, h - 200)), kicker, font=fk, fill=GOLD, anchor="mm")
    if p > 0.6:
        fh = _fit_font("Anton", 108, headline, 980, min_size=56)
        a = int(255 * clamp((p - 0.6) / 0.4))
        dl.text((W // 2, max(120, h - 100)), headline, font=fh, anchor="mm",
                fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))
    target.alpha_composite(layer)


def _draw_caption_bar(draw: ImageDraw.ImageDraw, target: Image.Image,
                      kicker: str, headline: str, t: float):
    """fullbleed_frame layout: headline lives in a lower-third caption bar."""
    p = _pop(t, T_HEADLINE, 0.4)
    if p <= 0:
        return
    y0 = H - int(360 * (0.5 + 0.5 * p))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rectangle((0, y0, W, H), fill=(8, 8, 12, 215))
    dl.line([(0, y0), (W, y0)], fill=ACCENT, width=6)
    fk = load_font("Montserrat", 36)
    dl.text((90, y0 + 60), kicker.upper(), font=fk, fill=GOLD, anchor="lm")
    fh = _fit_font("Anton", 104, headline, W - 180, min_size=54)
    a = int(255 * clamp(p * 1.6))
    dl.text((90, y0 + 170), headline, font=fh, anchor="lm",
            fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))
    target.alpha_composite(layer)


def _draw_corner_stack(draw: ImageDraw.ImageDraw, target: Image.Image,
                       kicker: str, headline: str, t: float):
    """corner_stack layout: kicker + headline stacked vertically, pinned left."""
    p = _pop(t, T_KICKER, 0.4)
    if p <= 0:
        return
    w = int(360 * (0.5 + 0.5 * p))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rounded_rectangle((40, 280, 40 + w, 1080), radius=36,
                         fill=(10, 10, 14, 225), outline=GOLD, width=4)
    if p > 0.35:
        fk = load_font("Montserrat", 36)
        dl.text((40 + w // 2, 360), kicker.upper(), font=fk, fill=GOLD, anchor="mm")
    if p > 0.55:
        fh = _fit_font("Anton", 92, headline, w - 70, min_size=46)
        a = int(255 * clamp((p - 0.55) / 0.45))
        # wrap onto a few lines so a long headline fits the narrow stack
        words = headline.split()
        lines: List[str] = []
        cur = ""
        for word in words:
            probe = (cur + " " + word).strip()
            if draw.textbbox((0, 0), probe, font=fh)[2] <= w - 70 or not cur:
                cur = probe
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        ly = 520
        for line in lines[:4]:
            dl.text((40 + w // 2, ly), line, font=fh, anchor="mm",
                    fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))
            ly += 130
    target.alpha_composite(layer)


def _draw_ticker_bar(draw: ImageDraw.ImageDraw, target: Image.Image,
                     kicker: str, headline: str, t: float):
    """ticker_strip layout: headline rides a bold marquee bar near the bottom."""
    p = _pop(t, T_HEADLINE, 0.4)
    if p <= 0:
        return
    h = int(220 * (0.5 + 0.5 * p))
    y0 = 1370
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rectangle((0, y0, W, y0 + h), fill=GOLD)
    fh = _fit_font("Anton", 96, headline, W - 140, min_size=48)
    a = int(255 * clamp(p * 1.6))
    dl.text((W // 2, y0 + h // 2 + 10), headline, font=fh, anchor="mm",
            fill=(10, 10, 14, a))
    fk = load_font("Montserrat", 34)
    dl.text((W // 2, y0 - 36), kicker.upper(), font=fk, fill=ACCENT, anchor="mm")
    target.alpha_composite(layer)


def _draw_card_caption(draw: ImageDraw.ImageDraw, target: Image.Image,
                       kicker: str, headline: str, t: float,
                       box: Tuple[int, int, int, int]):
    """frame_card layout: bracketed corner ticks around the card + caption below."""
    x0, y0, x1, y1 = box
    p = _pop(t, T_ILLU, 0.4)
    if p > 0:
        tick = 56
        col = GOLD
        for cx, cy, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            draw.line([(cx, cy), (cx + dx * tick, cy)], fill=col, width=8)
            draw.line([(cx, cy), (cx, cy + dy * tick)], fill=col, width=8)
    hp = _pop(t, T_HEADLINE, 0.4)
    if hp <= 0:
        return
    fk = load_font("Montserrat", 36)
    draw.text((W // 2, y1 + 70), kicker.upper(), font=fk, fill=GOLD, anchor="mm")
    fh = _fit_font("Anton", 110, headline, W - 200, min_size=56)
    a = int(255 * clamp(hp * 1.6))
    draw.text((W // 2, y1 + 180), headline, font=fh, anchor="mm",
              fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))


def _draw_diagonal_caption(draw: ImageDraw.ImageDraw, target: Image.Image,
                           kicker: str, headline: str, t: float):
    """diagonal_split layout: headline runs vertically down the left seam."""
    p = _pop(t, T_HEADLINE, 0.4)
    if p <= 0:
        return
    fk = load_font("Montserrat", 36)
    draw.text((150, 420), kicker.upper(), font=fk, fill=GOLD, anchor="lm")
    fh = _fit_font("Anton", 100, headline, 360, min_size=48)
    a = int(255 * clamp(p * 1.6))
    words = headline.split()
    lines: List[str] = []
    cur = ""
    for word in words:
        probe = (cur + " " + word).strip()
        if draw.textbbox((0, 0), probe, font=fh)[2] <= 360 or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    ly = 540
    for line in lines[:4]:
        draw.text((150, ly), line, font=fh, anchor="lm",
                  fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))
        ly += 130


def _draw_polaroid_caption(draw: ImageDraw.ImageDraw, target: Image.Image,
                           headline: str, t: float,
                           box: Tuple[int, int, int, int]):
    """polaroid_tilt layout: marker-style caption under the instant photo.

    The kicker chip is drawn separately at the top of the frame; the rotated
    card overflows the box a little, so the caption stays clear of its white
    bottom margin.
    """
    p = _pop(t, T_HEADLINE, 0.4)
    if p <= 0:
        return
    y = min(H - 500, box[3] + 210)
    fh = _fit_font("Caveat", 128, headline, W - 220, min_size=64)
    a = int(255 * clamp(p * 1.6))
    draw.text((W // 2, y), headline, font=fh, anchor="mm",
              fill=(255, 255, 255, a), stroke_width=3, stroke_fill=(0, 0, 0, min(a, 210)))
    up = ease_out_cube(_linear(t, T_UNDERLINE, 0.35))
    if up > 0:
        l, tt, r, b = draw.textbbox((W // 2, y), headline, font=fh, anchor="mm")
        width = (r - l) * 0.85 * up
        draw.line([(W // 2 - width / 2, b + 18), (W // 2 + width / 2, b + 18)],
                  fill=ACCENT, width=8)


def _draw_sparkles(draw: ImageDraw.ImageDraw, t: float, box: Tuple[int, int, int, int]):
    x0, y0, x1, y1 = box
    spots = [(x0 + 30, y0 - 40, 1.30), (x1 - 40, y1 - 20, 1.55), (x0 + 80, y1 + 40, 1.80)]
    for cx, cy, t0 in spots:
        p = _pop(t, t0, 0.3)
        if p <= 0:
            continue
        s = 16 + 14 * p
        a = int(235 * clamp(2.2 - abs(p * 2 - 1)))
        col = (255, 255, 255, max(0, min(255, a)))
        draw.line([(cx - s, cy), (cx + s, cy)], fill=col, width=7)
        draw.line([(cx, cy - s), (cx, cy + s)], fill=col, width=7)


def _wrap_words(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int = 3) -> List[str]:
    words = (text or "").split()
    lines: List[str] = []
    cur = ""
    for word in words:
        probe = (cur + " " + word).strip()
        if draw.textbbox((0, 0), probe, font=font)[2] <= max_w or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = word
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip("…") + "…"
    return lines


def _draw_spoken_line(draw: ImageDraw.ImageDraw, target: Image.Image,
                      scene: dict, t: float, layout: str):
    """Large readable line that mirrors the spoken idea under each drawing.

    This fixes the old 'tiny generic keyword' problem: a viewer sees the exact
    phrase the illustration is meant to explain, not only a one-word headline.
    """
    text = (scene.get("spoken_line") or scene.get("excerpt") or "").strip()
    if not text:
        return
    p = _pop(t, T_HEADLINE + 0.18, 0.42)
    if p <= 0:
        return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    font = load_font("Montserrat", 46)
    max_w = W - 180
    lines = _wrap_words(dl, text, font, max_w, max_lines=3)
    if not lines:
        return
    line_h = 58
    pad_x, pad_y = 34, 24
    box_h = len(lines) * line_h + pad_y * 2
    # Keep the spoken line high enough for TikTok safe-zone captions, but below
    # the main illustration/headline. Full-bleed and ticker layouts reserve more
    # space near the bottom, so the readable line floats slightly above them.
    y0 = 1500 if layout not in {"ticker_strip", "fullbleed_frame"} else 1180
    y0 = min(y0, H - box_h - 180)
    x0, x1 = 80, W - 80
    dl.rounded_rectangle((x0, y0, x1, y0 + box_h), radius=34,
                         fill=(8, 10, 18, int(218 * clamp(p))),
                         outline=(255, 255, 255, int(40 * clamp(p))), width=2)
    accent_w = int((x1 - x0 - 50) * ease_out_cube(clamp((t - T_UNDERLINE) / 0.55)))
    if accent_w > 0:
        dl.line([(x0 + 25, y0 + 10), (x0 + 25 + accent_w, y0 + 10)], fill=GOLD, width=5)
    a = int(255 * clamp(p * 1.3))
    y = y0 + pad_y + line_h / 2
    for line in lines:
        dl.text((W // 2, y), line, font=font, anchor="mm",
                fill=(255, 255, 255, a), stroke_width=2, stroke_fill=(0, 0, 0, min(a, 190)))
        y += line_h
    target.alpha_composite(layer)


def _arch_mask(bw: int, bh: int) -> Image.Image:
    """Rounded-top "portal" mask: half-circle top + straight sides/bottom."""
    mask = Image.new("L", (bw, bh), 0)
    dm = ImageDraw.Draw(mask)
    dm.ellipse((0, 0, bw, min(bw, bh)), fill=255)
    if bh > bw // 2:
        dm.rectangle((0, bw // 2, bw, bh), fill=255)
    return mask


def _paste_illustration(canvas: Image.Image, illu: Image.Image, t: float, dur: float,
                        box: Tuple[int, int, int, int], shape: str = "rounded"):
    """AI illustration with pop + float + Ken Burns, masked per-layout:
    rounded panel (signature), full circle, arch portal, or tilted polaroid.
    """
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    p = _pop(t, T_ILLU, 0.5)
    if p <= 0:
        return
    kb = 1.0 + 0.06 * ease_in_out(clamp(t / dur))
    scale = (0.55 + 0.45 * min(p, 1.06)) * kb
    # cover-fit the source into the panel
    ratio = max(bw / illu.width, bh / illu.height)
    iw, ih = int(illu.width * ratio * scale), int(illu.height * ratio * scale)
    img = illu.resize((max(1, iw), max(1, ih)), _RESAMPLE)
    left, top = (img.width - bw) // 2, (img.height - bh) // 2
    img = img.crop((left, top, left + bw, top + bh))

    float_y = int(8 * math.sin(2 * math.pi * 0.4 * t))
    px, py = x0, y0 + float_y

    if shape == "circle":
        mask = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, bw, bh), fill=255)
        cut = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        cut.paste(img, (0, 0), mask)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dg = ImageDraw.Draw(glow)
        for grow, alpha in ((26, 28), (14, 55)):
            dg.ellipse((px - grow, py - grow, px + bw + grow, py + bh + grow),
                       outline=(ACCENT[0], ACCENT[1], ACCENT[2], alpha), width=grow)
        canvas.alpha_composite(glow)
        canvas.alpha_composite(cut, (px, py))
        d = ImageDraw.Draw(canvas)
        d.ellipse((px, py, px + bw, py + bh), outline=ACCENT, width=6)
        return

    if shape == "arch":
        mask = _arch_mask(bw, bh)
        cut = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        cut.paste(img, (0, 0), mask)
        canvas.alpha_composite(cut, (px, py))
        d = ImageDraw.Draw(canvas)
        d.arc((px, py, px + bw, py + bw), 180, 360, fill=ACCENT, width=6)
        d.line([(px, py + bw // 2), (px, py + bh)], fill=ACCENT, width=6)
        d.line([(px + bw, py + bw // 2), (px + bw, py + bh)], fill=ACCENT, width=6)
        d.line([(px, py + bh), (px + bw, py + bh)], fill=GOLD, width=8)
        return

    if shape == "polaroid":
        border, bottom = 26, 130
        card = Image.new("RGBA", (bw + 2 * border, bh + border + bottom),
                         (250, 248, 242, 255))
        card.paste(img, (border, border))
        # settle from a stronger tilt to the resting angle as it pops in
        angle = -3.2 - 6.0 * (1.0 - min(1.0, p))
        card = card.rotate(angle, expand=True, resample=Image.BICUBIC)
        cw, ch = card.size
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2 + float_y
        # soft drop shadow under the tilted card
        sh_a = card.split()[3].point(lambda v: int(v * 0.45))
        zero = Image.new("L", (cw, ch), 0)
        shadow = Image.merge("RGBA", (zero, zero, zero, sh_a)).filter(
            ImageFilter.GaussianBlur(12))
        canvas.alpha_composite(shadow, (cx - cw // 2 + 14, cy - ch // 2 + 20))
        canvas.alpha_composite(card, (cx - cw // 2, cy - ch // 2))
        return

    img = _rounded_image(img)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    for grow, alpha in ((26, 28), (14, 55)):
        dg.rounded_rectangle((px - grow, py - grow, px + bw + grow, py + bh + grow),
                             radius=44 + grow, outline=(ACCENT[0], ACCENT[1], ACCENT[2], alpha),
                             width=grow)
    canvas.alpha_composite(glow)
    canvas.alpha_composite(img, (px, py))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((px, py, px + bw, py + bh), radius=44, outline=ACCENT, width=5)


def _draw_icon_drawing(target: Image.Image, icon: str, t: float, dur: float,
                       box: Tuple[int, int, int, int], shape: str = "rounded"):
    """Procedural fallback: the line-art icon draws itself, whiteboard style.

    The backing panel follows the layout's illustration mask (rounded panel,
    circle, arch, or white polaroid card) so the fallback keeps the same
    composition variety as the AI-illustrated scenes.
    """
    strokes = ICONS.get(icon, ICONS[content.DEFAULT_ICON])
    p = ease_in_out(_linear(t, T_ILLU, 1.1))
    if p <= 0:
        return
    x0, y0, x1, y1 = box
    side = min(x1 - x0, y1 - y0) - 120
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2 + int(8 * math.sin(2 * math.pi * 0.4 * t))
    d = ImageDraw.Draw(target)
    top, bot = cy - (y1 - y0) // 2, cy + (y1 - y0) // 2
    ink, accent = INK, ACCENT
    if shape == "circle":
        d.ellipse((x0, top, x1, bot), fill=(16, 20, 34, 235),
                  outline=(255, 255, 255, 36), width=3)
    elif shape == "arch":
        bw = x1 - x0
        d.pieslice((x0, top, x1, top + bw), 180, 360, fill=(16, 20, 34, 235))
        d.rectangle((x0, top + bw // 2, x1, bot), fill=(16, 20, 34, 235))
    elif shape == "polaroid":
        # white instant-photo card -> draw the sketch in dark ink for contrast
        d.rounded_rectangle((x0, top, x1, bot), radius=14,
                            fill=(250, 248, 242, 245), outline=(210, 205, 195, 255), width=2)
        ink = (30, 30, 34, 255)
    else:
        d.rounded_rectangle((x0, top, x1, bot), radius=44,
                            fill=(16, 20, 34, 235), outline=(255, 255, 255, 36), width=3)
    ibox = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
    _draw_strokes(d, _partial_strokes(strokes, p), ibox, ink, width=STROKE_W)
    # accent re-draw: a second colored pass chases the first ink pass
    p2 = ease_in_out(_linear(t, T_ILLU + 0.35, 1.1))
    if p2 > 0:
        _draw_strokes(d, _partial_strokes(strokes, p2 * 0.999), ibox, accent, width=6)


def _draw_steps(draw: ImageDraw.ImageDraw, steps: List[str], t: float) -> List[float]:
    """Numbered step pills, staggered pop + connector arrows. Returns event times."""
    events: List[float] = []
    n = min(4, len(steps))
    top = 1000
    row_h = 92
    gap = 18
    for i in range(n):
        t0 = T_ELEMENTS + i * STEP_STAGGER
        events.append(t0)
        p = _pop(t, t0, 0.4)
        if p <= 0:
            continue
        slide = int((1 - ease_out_cube(clamp(p))) * 160)
        y0 = top + i * (row_h + gap)
        x0 = 120 - slide if i % 2 == 0 else 120 + slide
        x1 = x0 + W - 240
        draw.rounded_rectangle((x0, y0, x1, y0 + row_h), radius=row_h // 2,
                               fill=(16, 20, 34, 225), outline=ACCENT, width=3)
        badge_r = 30
        bx, by = x0 + 52, y0 + row_h // 2
        draw.ellipse((bx - badge_r, by - badge_r, bx + badge_r, by + badge_r), fill=GOLD)
        f_n = load_font("Anton", 40)
        draw.text((bx, by - 2), str(i + 1), font=f_n, fill=(20, 16, 6, 255), anchor="mm")
        f_s = _fit_font("Montserrat", 42, steps[i], x1 - x0 - 160)
        draw.text((bx + 56, by), steps[i], font=f_s, fill=(255, 255, 255, 255), anchor="lm")
    return events


def _draw_counter(draw: ImageDraw.ImageDraw, value: float, raw: str, t: float) -> List[float]:
    t0 = T_ELEMENTS
    p = ease_out_cube(_linear(t, t0, 1.3))
    if p <= 0:
        return [t0]
    shown = _fmt_value(value * p, raw)
    font = _fit_font("Anton", 200, _fmt_value(value, raw), 880, min_size=90)
    draw.text((W // 2, 1110), shown, font=font, fill=GOLD, anchor="mm",
              stroke_width=8, stroke_fill=(0, 0, 0, 235))
    return [t0]


# --------------------------------------------------------------------------- #
# BOARD rendering — panneau fixe + carte-scène animée
# --------------------------------------------------------------------------- #
def _board_grain(seed: int = 7) -> Image.Image:
    """Deterministic fine grain, so the green board reads as textured felt."""
    import numpy as np
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 46, size=(H // 4, W // 4), dtype="uint8")
    layer = Image.fromarray(small, "L").resize((W, H), Image.BILINEAR)
    zero = Image.new("L", (W, H), 0)
    return Image.merge("RGBA", (zero, zero, zero, layer))


def _board_base() -> Image.Image:
    """Opaque dark-green board: vertical gradient + centre glow + vignette."""
    grad = Image.new("RGB", (1, H))
    px = grad.load()
    for y in range(H):
        f = y / (H - 1)
        px[0, y] = tuple(int(BG_TOP[c] + (BG_BOTTOM[c] - BG_TOP[c]) * f) for c in range(3))
    base = grad.resize((W, H)).convert("RGBA")

    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((-W * 0.15, -H * 0.12, W * 1.15, H * 0.72), fill=64)
    glow = glow.filter(ImageFilter.GaussianBlur(210))
    white = Image.new("L", (W, H), 255)
    base = Image.alpha_composite(base, Image.merge("RGBA", (white, white, white, glow)))

    base = Image.alpha_composite(base, _board_grain())

    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.30, -H * 0.16, W * 1.30, H * 1.16), fill=255)
    shade = vig.filter(ImageFilter.GaussianBlur(170)).point(lambda v: (255 - v) * 165 // 255)
    zero = Image.new("L", (W, H), 0)
    return Image.alpha_composite(base, Image.merge("RGBA", (zero, zero, zero, shade)))


# Couleur de détourage: un liseré de la teinte de la carte posé derrière le
# texte sombre, pour qu'il reste net même au-dessus de la grille de repères.
_CARD_KNOCK = (250, 250, 248, 255)


def _card_plate(bw: int, bh: int) -> Image.Image:
    """The light stage card: soft vertical gradient, brighter in the middle."""
    grad = Image.new("RGB", (1, bh))
    px = grad.load()
    for y in range(bh):
        f = abs(y / (bh - 1) - 0.42) * 2.0
        v = int(253 - 30 * min(1.0, f) ** 1.4)
        px[0, y] = (v, v, max(0, v - 2))
    return grad.resize((bw, bh)).convert("RGBA")


def _plus_grid(draw: ImageDraw.ImageDraw, bw: int, y_from: int, y_to: int,
               alpha: int = 46):
    """The faint '+' registration grid.

    In the reference it only fills the EMPTY middle band of the card — never
    behind the text — so the typography stays perfectly clean.
    """
    col = (122, 130, 134, alpha)
    step, arm = 82, 9
    for y in range(y_from, y_to, step):
        for x in range(56, bw - 40, step):
            draw.line([(x - arm, y), (x + arm, y)], fill=col, width=3)
            draw.line([(x, y - arm), (x, y + arm)], fill=col, width=3)


def _corner_waves(layer: Image.Image, bw: int, bh: int, p: float, flip: bool = False):
    """Les coins « vague » noirs de la référence: deux masses organiques en
    diagonale opposée, qui se déploient depuis les angles de la carte."""
    if p <= 0:
        return
    d = ImageDraw.Draw(layer)
    reach = int(min(bw, bh) * 0.30 * min(1.0, p))
    corners = ((0, 0, 1, 1), (bw, bh, -1, -1)) if not flip else ((bw, 0, -1, 1), (0, bh, 1, -1))
    for cx, cy, sx, sy in corners:
        pts = [(cx, cy)]
        for i in range(25):                     # bord courbe (bezier quadratique)
            u = i / 24
            x = (1 - u) ** 2 * (cx + sx * reach) + 2 * (1 - u) * u * (cx + sx * reach * 0.45) \
                + u ** 2 * cx
            y = (1 - u) ** 2 * cy + 2 * (1 - u) * u * (cy + sy * reach * 0.52) \
                + u ** 2 * (cy + sy * reach)
            pts.append((x, y))
        d.polygon(pts, fill=(14, 14, 16, 255))


def _barcode(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, seed: str):
    """Bande code-barres — le détail « packshot produit » de la référence."""
    import random
    rng = random.Random(seed)
    cx = x
    while cx < x + w - 4:
        bar = rng.choice((3, 3, 5, 8))
        if rng.random() < 0.62:
            draw.rectangle((cx, y, cx + bar, y + h), fill=(18, 18, 20, 255))
        cx += bar + rng.choice((3, 4, 6))


def _floating_chips(draw: ImageDraw.ImageDraw, labels: List[str], bw: int, bh: int,
                    t: float, y0: int = 150):
    """Mini-étiquettes sombres qui pop en cascade (réf.: « C'est trop cher »,
    « Je vais réfléchir » flottant autour de l'illustration)."""
    import random
    for i, label in enumerate(labels[:3]):
        p = _pop(t, 0.55 + i * 0.28, 0.36)
        if p <= 0:
            continue
        rng = random.Random(label)
        f = load_font("Montserrat", 34)
        l, tt, r, b = draw.textbbox((0, 0), label, font=f)
        cw, ch = (r - l) + 46, (b - tt) + 28
        cx = int(bw * (0.28 + 0.44 * ((i * 0.5) % 1.0))) + rng.randint(-30, 30)
        cy = y0 + i * 96 + rng.randint(-14, 14)
        s = min(1.0, p)
        cw, ch = int(cw * s), int(ch * s)
        draw.rounded_rectangle((cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2),
                               radius=ch // 2, fill=(18, 18, 20, 235))
        if s > 0.7:
            draw.text((cx, cy), label, font=f, anchor="mm", fill=(244, 242, 236, 255))


def _annotation_tags(draw: ImageDraw.ImageDraw, labels: List[str], bw: int, bh: int,
                     t: float):
    """Étiquettes d'annotation façon 3D qui se posent sur l'illustration
    (réf.: « PREMIER CONTACT », « OBJECTIONS » en relief orange)."""
    for i, label in enumerate(labels[:3]):
        p = _pop(t, 0.6 + i * 0.30, 0.38)
        if p <= 0:
            continue
        f = load_font("Anton", 38)
        text = label.upper()
        l, tt, r, b = draw.textbbox((0, 0), text, font=f)
        cw, ch = (r - l) + 40, (b - tt) + 24
        # étalées en escalier sur l'illustration, jamais empilées au centre
        cx = int(bw * (0.56 - i * 0.13))
        cy = int(bh * (0.24 + i * 0.22))
        off = int((1.0 - min(1.0, p)) * 60)
        x0, y0 = cx - cw // 2 + off, cy - ch // 2
        draw.rectangle((x0 + 6, y0 + 7, x0 + cw + 6, y0 + ch + 7), fill=(24, 24, 26, 210))
        draw.rectangle((x0, y0, x0 + cw, y0 + ch), fill=(18, 18, 20, 245))
        if p > 0.6:
            draw.text((x0 + cw // 2, y0 + ch // 2), text, font=f, anchor="mm",
                      fill=(ACCENT[0], ACCENT[1], ACCENT[2], 255))


def _flyer_stack(canvas: Image.Image, t: float):
    """The little pile of product flyers pinned under the left-hand label."""
    p = _pop(t, T_KICKER + 0.10, 0.45)
    if p <= 0:
        return
    fw, fh = 322, 400
    cx, cy = BOARD_MARGIN + fw // 2, 812
    for k, (dx, dy, ang, shade) in enumerate(
            ((24, 18, 3.4, 212), (11, 9, -1.8, 231), (0, 0, 1.2, 250))):
        card = Image.new("RGBA", (fw, fh), (shade, shade, shade - 4, 255))
        d = ImageDraw.Draw(card)
        d.rectangle((0, 0, fw - 1, fh - 1), outline=(194, 196, 192, 255), width=2)
        if k == 2:                       # only the top flyer carries artwork
            # bandeau titre "produit" — deux lignes serrées façon couverture
            d.rectangle((22, 26, 40, 96), fill=GOLD)
            f1 = load_font("Anton", 40)
            d.text((54, 30), "LA MÉTHODE", font=f1, fill=(28, 120, 76, 255))
            d.text((54, 66), "COMPLÈTE", font=f1, fill=(22, 24, 23, 255))
            # bloc "capture" sombre + lignes de texte
            d.rounded_rectangle((22, 120, fw - 22, fh - 74), radius=10,
                                fill=(48, 56, 52, 255))
            for i in range(7):
                y = 146 + i * 26
                d.line([(42, y), (fw - 46 - (i % 3) * 30, y)],
                       fill=(158, 168, 162, 255), width=6)
            d.rectangle((22, fh - 60, fw - 22, fh - 26), fill=(28, 120, 76, 255))
        rot = card.rotate(ang, expand=True, resample=Image.BICUBIC)
        scale = 0.82 + 0.18 * min(1.0, p)
        rw, rh = max(1, int(rot.width * scale)), max(1, int(rot.height * scale))
        rot = rot.resize((rw, rh), _RESAMPLE)
        sh_a = rot.split()[3].point(lambda v: int(v * 0.40))
        zero = Image.new("L", (rw, rh), 0)
        canvas.alpha_composite(
            Image.merge("RGBA", (zero, zero, zero, sh_a)).filter(ImageFilter.GaussianBlur(9)),
            (cx - rw // 2 + dx + 8, cy - rh // 2 + dy + 12))
        canvas.alpha_composite(rot, (cx - rw // 2 + dx, cy - rh // 2 + dy))


def _board_furniture(canvas: Image.Image, title: str, label: str, t: float):
    """The parts of the board that never move: serif title, label, flyers."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    pt = ease_out_cube(_linear(t, 0.0, 0.45))
    if pt > 0:
        ft = _fit_font("Playfair", 74, title, W - BOARD_MARGIN - 340, min_size=40)
        d.text((W - BOARD_MARGIN, BOARD_TITLE_Y), title, font=ft, anchor="rm",
               fill=(INK[0], INK[1], INK[2], int(255 * pt)))

    pl = ease_out_cube(_linear(t, 0.14, 0.45))
    if pl > 0:
        fl = _fit_font("Playfair", 92, label, BOARD_CARD[0] - BOARD_MARGIN - 30, min_size=48)
        d.text((BOARD_MARGIN, BOARD_LABEL_Y), label, font=fl, anchor="lm",
               fill=(INK[0], INK[1], INK[2], int(255 * pl)))
    canvas.alpha_composite(layer)
    _flyer_stack(canvas, t)


def _board_content_offset(t: float, dur: float, bw: int) -> Tuple[int, float]:
    """Lateral slide of the card content: in from the right, out to the left.

    Reproduces the reference's signature move — the current subject walks out
    of the frame while the next element arrives, the card itself never moves.
    """
    enter = ease_out_cube(clamp((t - 0.10) / 0.48))
    off = (1.0 - enter) * bw * 0.52
    fade = enter
    out = clamp((t - (dur - 0.42)) / 0.42)
    if out > 0:
        off -= out * out * bw * 0.75
        fade = min(fade, 1.0 - out * out)
    return int(off), clamp(fade)


def _board_card_content(scene: dict, illu: Optional[Image.Image], layout: str,
                        t: float, dur: float, bw: int, bh: int) -> Image.Image:
    """Everything that plays INSIDE the stage card (card-local coordinates)."""
    card = _card_plate(bw, bh)
    d = ImageDraw.Draw(card)
    # La grille ne sert qu'à meubler le vide d'une carte typographique; les
    # cartes qui portent une image n'en ont pas besoin.
    if layout == "board_quote" or illu is None:
        _plus_grid(d, bw, int(bh * 0.44), int(bh * 0.72))

    off, fade = _board_content_offset(t, dur, bw)
    headline = (scene.get("headline") or "").strip()
    phrase = (scene.get("spoken_line") or scene.get("excerpt") or "").strip()

    body = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    db = ImageDraw.Draw(body)

    if layout == "board_number" and scene.get("value") is not None:
        kicker = (scene.get("kicker") or "").strip()
        if kicker:
            fs = _fit_font("Playfair Italic", 68, kicker, bw - 100, min_size=34)
            db.text((bw // 2, 168), kicker, font=fs, anchor="mm", fill=(34, 38, 36, 255))
        shown = _fmt_value(float(scene["value"]) * ease_out_cube(_linear(t, 0.25, 1.15)),
                           scene.get("raw", ""))
        fn = _fit_font("Playfair", 360, shown, bw - 90, min_size=140)
        db.text((bw // 2, bh // 2 - 20), shown, font=fn, anchor="mm", fill=(18, 20, 19, 255))
        if headline:
            fh = _fit_font("Anton", 96, headline.upper(), bw - 90, min_size=42)
            db.text((bw // 2, bh - 190), headline.upper(), font=fh, anchor="mm",
                    fill=(24, 26, 25, 255))

    elif layout == "board_quote" or illu is None:
        # Beat purement typographique (réf.: « Plus jamais », « Tu veux
        # arrêter de … »): jamais d'image, la phrase porte la carte.
        if phrase:
            fq = _fit_font("Playfair Italic", 88, phrase, bw - 100, min_size=40)
            lines = _wrap_words(db, phrase, fq, bw - 100, max_lines=3)
            y = 240                                     # zone haute, au-dessus de la grille
            for line in lines:
                db.text((bw // 2, y), line, font=fq, anchor="mm", fill=(30, 34, 32, 255),
                        stroke_width=6, stroke_fill=_CARD_KNOCK)
                y += 104
        if headline:
            fh = _fit_font("Anton", 104, headline.upper(), bw - 90, min_size=46)
            hy = bh - 210                               # zone basse, sous la grille
            db.text((bw // 2, hy), headline.upper(), font=fh, anchor="mm",
                    fill=(20, 22, 21, 255), stroke_width=6, stroke_fill=_CARD_KNOCK)
            up = ease_out_cube(_linear(t, 0.85, 0.42))
            if up > 0:                                  # trait marqueur animé
                l, tt, r, b = db.textbbox((bw // 2, hy), headline.upper(), font=fh, anchor="mm")
                db.line([(l - 8, b + 20), (l - 8 + (r - l + 16) * up, b + 20)],
                        fill=GOLD[:3] + (255,), width=12)

    elif layout == "board_split":
        top_h = int(bh * 0.58)
        ratio = max(bw / illu.width, top_h / illu.height)
        img = illu.resize((max(1, int(illu.width * ratio)), max(1, int(illu.height * ratio))),
                          _RESAMPLE)
        left, top = (img.width - bw) // 2, (img.height - top_h) // 2
        body.alpha_composite(img.crop((left, top, left + bw, top + top_h)), (0, 0))
        db.line([(0, top_h), (bw, top_h)], fill=GOLD[:3] + (255,), width=7)
        if headline:
            fh = _fit_font("Anton", 100, headline.upper(), bw - 90, min_size=44)
            db.text((bw // 2, top_h + 118), headline.upper(),
                    font=fh, anchor="mm", fill=(20, 22, 21, 255))
        if phrase:
            fp = _fit_font("Playfair Italic", 54, phrase, bw - 110, min_size=30)
            lines = _wrap_words(db, phrase, fp, bw - 110, max_lines=3)
            y = top_h + 230
            for line in lines:
                db.text((bw // 2, y), line, font=fp, anchor="mm", fill=(62, 66, 64, 255))
                y += 64

    elif layout == "board_overflow":
        # Objet surdimensionné coupé par les bords, en diagonale opposée.
        big = int(bw * 0.56)
        thumb = _rounded_image(illu.resize((big, big), _RESAMPLE), 40)
        grow = 0.84 + 0.16 * ease_out_cube(_linear(t, 0.15, 0.6))
        # deux exemplaires en diagonale opposée, volontairement coupés par les
        # bords de la carte (le masque arrondi fait la découpe)
        for (ax, ay), sc in (((-0.16, 0.02), 1.0), ((0.60, 0.70), 1.12)):
            s = max(1, int(big * sc * grow))
            body.alpha_composite(thumb.resize((s, s), _RESAMPLE),
                                 (int(bw * ax), int(bh * ay)))
        db = ImageDraw.Draw(body)
        if headline:
            fh = _fit_font("Anton", 112, headline.upper(), bw - 110, min_size=48)
            db.text((bw // 2, bh // 2), headline.upper(), font=fh, anchor="mm",
                    fill=(20, 22, 21, 255), stroke_width=9, stroke_fill=_CARD_KNOCK)

    elif layout == "board_sandwich":
        # Serif en haut, visuel contenu au centre, serif en bas.
        head, tail = (phrase, "") if not headline else (phrase, headline)
        iw = int(bw * 0.66)
        thumb = _rounded_image(illu.resize((iw, iw), _RESAMPLE), 30)
        body.alpha_composite(thumb, ((bw - iw) // 2, (bh - iw) // 2 - 10))
        db = ImageDraw.Draw(body)
        # Texte rentré (bw-230) pour ne jamais mordre sur les coins « vague ».
        if head:
            ft = _fit_font("Playfair Italic", 68, head, bw - 230, min_size=34)
            lines = _wrap_words(db, head, ft, bw - 230, max_lines=2)
            y = 210
            for line in lines:
                db.text((bw // 2, y), line, font=ft, anchor="mm", fill=(28, 32, 30, 255))
                y += 78
        if tail:
            fb = _fit_font("Playfair Italic", 62, tail, bw - 230, min_size=32)
            db.text((bw // 2, bh - 205), tail, font=fb, anchor="mm", fill=(28, 32, 30, 255))

    elif layout == "board_collage":
        # Mini-étiquettes en cascade + illustration basse + question serif.
        ih = int(bh * 0.42)
        ratio = max(bw / illu.width, ih / illu.height)
        img = illu.resize((max(1, int(illu.width * ratio)), max(1, int(illu.height * ratio))),
                          _RESAMPLE)
        left, top = (img.width - bw) // 2, (img.height - ih) // 2
        body.alpha_composite(img.crop((left, top, left + bw, top + ih)), (0, bh - ih))
        db = ImageDraw.Draw(body)
        chips = [w for w in (phrase or "").split(",") if len(w.strip()) > 3][:3]
        if not chips and phrase:
            words = phrase.split()
            chips = [" ".join(words[i:i + 3]) for i in range(0, min(9, len(words)), 3)]
        _floating_chips(db, [c.strip()[:26] for c in chips], bw, bh, t, y0=252)
        if headline:
            fq = _fit_font("Playfair Italic", 76, headline, bw - 200, min_size=36)
            db.text((bw // 2, bh - ih - 96), headline, font=fq, anchor="mm",
                    fill=(26, 30, 28, 255), stroke_width=7, stroke_fill=_CARD_KNOCK)

    elif layout == "board_annotated":
        # Illustration zoomée + étiquettes d'annotation qui se posent dessus.
        zoom = 1.18 + 0.06 * ease_in_out(clamp(t / dur))
        ratio = max(bw / illu.width, bh / illu.height) * zoom
        img = illu.resize((max(1, int(illu.width * ratio)), max(1, int(illu.height * ratio))),
                          _RESAMPLE)
        left, top = (img.width - bw) // 2, (img.height - bh) // 2
        body.alpha_composite(img.crop((left, top, left + bw, top + bh)), (0, 0))
        db = ImageDraw.Draw(body)
        # Seuls des mots porteurs deviennent des étiquettes: un « c'est » ou un
        # « dans » collé sur l'illustration ne raconte rien au spectateur.
        tags = [w for w in (phrase or "").replace(",", " ").split()
                if len(w) >= 6 and w.lower().strip("'’.,;:!?") not in config.STOPWORDS][:2]
        if headline:
            tags = [headline] + tags
        _annotation_tags(db, tags, bw, bh, t)

    elif layout == "board_showcase":
        # Packshot: visuel incliné bordé de blanc + code-barres.
        iw = int(bw * 0.70)
        thumb = illu.resize((iw, iw), _RESAMPLE)
        border = 22
        cardimg = Image.new("RGBA", (iw + 2 * border, iw + 2 * border + 58),
                            (252, 251, 247, 255))
        cardimg.paste(thumb, (border, border))
        cd = ImageDraw.Draw(cardimg)
        if headline:
            fl = _fit_font("Anton", 44, headline.upper(), iw - 20, min_size=22)
            cd.text(((iw + 2 * border) // 2, iw + border + 28), headline.upper(),
                    font=fl, anchor="mm", fill=(22, 118, 74, 255))
        tilt = -4.0 + 2.5 * (1.0 - ease_out_cube(_linear(t, 0.15, 0.55)))
        rot = cardimg.rotate(tilt, expand=True, resample=Image.BICUBIC)
        sh_a = rot.split()[3].point(lambda v: int(v * 0.42))
        zero = Image.new("L", rot.size, 0)
        body.alpha_composite(
            Image.merge("RGBA", (zero, zero, zero, sh_a)).filter(ImageFilter.GaussianBlur(11)),
            ((bw - rot.width) // 2 + 12, int(bh * 0.20) + 16))
        body.alpha_composite(rot, ((bw - rot.width) // 2, int(bh * 0.20)))
        db = ImageDraw.Draw(body)
        bp = ease_out_cube(_linear(t, 0.75, 0.4))
        if bp > 0:
            _barcode(db, int(bw * 0.28), bh - 150, int(bw * 0.44 * bp), 62,
                     headline or "code")

    else:                                               # board_stage
        kb = 1.0 + 0.05 * ease_in_out(clamp(t / dur))
        ratio = max(bw / illu.width, bh / illu.height) * kb
        img = illu.resize((max(1, int(illu.width * ratio)), max(1, int(illu.height * ratio))),
                          _RESAMPLE)
        left, top = (img.width - bw) // 2, (img.height - bh) // 2
        body.alpha_composite(img.crop((left, top, left + bw, top + bh)), (0, 0))
        band = Image.new("L", (1, bh))
        bp = band.load()
        for y in range(bh):
            f = max(0.0, (y / bh - 0.50) / 0.50)
            bp[0, y] = int(232 * f ** 1.4)
        zero = Image.new("L", (bw, bh), 0)
        body.alpha_composite(Image.merge("RGBA", (zero, zero, zero, band.resize((bw, bh)))))
        db = ImageDraw.Draw(body)
        # La carte plein cadre ne porte QUE le mot-clé: la phrase prononcée
        # reste lisible dans les sous-titres, inutile de la doubler ici.
        if headline:
            fh = _fit_font("Anton", 112, headline.upper(), bw - 80, min_size=48)
            db.text((bw // 2, bh - 150), headline.upper(), font=fh, anchor="mm",
                    fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 205))
            up = ease_out_cube(_linear(t, 0.80, 0.40))
            if up > 0:
                l, tt, r, b = db.textbbox((bw // 2, bh - 150), headline.upper(),
                                          font=fh, anchor="mm")
                db.line([(l, b + 26), (l + (r - l) * up, b + 26)],
                        fill=GOLD[:3] + (255,), width=10)

    card.alpha_composite(_apply_alpha(body, fade), (off, 0))
    # Décor: les coins « vague » se déploient PAR-DESSUS le contenu, comme dans
    # la référence — mais seulement sur certaines compositions, pour que le
    # décor ne devienne pas lui-même une signature figée.
    if layout in BOARD_WAVE_LAYOUTS:
        waves = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        _corner_waves(waves, bw, bh, ease_out_cube(_linear(t, 0.05, 0.5)),
                      flip=(layout == "board_collage"))
        card.alpha_composite(waves)
    return card


def _compose_board_frame(scene: dict, illu: Optional[Image.Image], stage: Image.Image,
                         t: float, dur: float, layout: str) -> Image.Image:
    """Full board frame: fixed green panel + animated stage card."""
    canvas = stage.copy()
    _board_furniture(canvas,
                     scene.get("board_title") or BOARD_DEFAULT_TITLE,
                     scene.get("board_label") or BOARD_DEFAULT_LABEL, t)

    x0, y0, x1, y1 = BOARD_CARD
    bw, bh = x1 - x0, y1 - y0
    p = ease_out_cube(_linear(t, T_ILLU, 0.42))
    if p <= 0:
        return canvas
    scale = 0.94 + 0.06 * p
    cw, ch = max(1, int(bw * scale)), max(1, int(bh * scale))
    px, py = x0 + (bw - cw) // 2, y0 + (bh - ch) // 2

    content = _board_card_content(scene, illu, layout, t, dur, bw, bh)
    if (cw, ch) != (bw, bh):
        content = content.resize((cw, ch), _RESAMPLE)
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=38, fill=255)
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    card.paste(content, (0, 0), mask)

    sh = Image.merge("RGBA", (Image.new("L", (cw, ch), 0), Image.new("L", (cw, ch), 0),
                              Image.new("L", (cw, ch), 0),
                              mask.point(lambda v: int(v * 0.46))))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)), (px + 10, py + 20))
    canvas.alpha_composite(_apply_alpha(card, p), (px, py))
    return canvas


# --------------------------------------------------------------------------- #
# scene entrance / exit transitions (variants cycled per scene)
# --------------------------------------------------------------------------- #
ENTRANCE_DUR = 0.5
EXIT_MOTION_DUR = 0.38


def _iris(canvas: Image.Image, p: float, closing: bool = False) -> Image.Image:
    """Circular reveal (or close) of the whole scene, with an accent ring."""
    p = clamp(p)
    radius = (1.0 - p if closing else p) * math.hypot(W, H) * 0.62
    mask = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(mask)
    cx, cy = W // 2, H // 2 - 140
    dm.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
    r, g, b, a = canvas.split()
    out = Image.merge("RGBA", (r, g, b, ImageChops.multiply(a, mask)))
    if 0.02 < p < 0.98 and radius > 4:
        do = ImageDraw.Draw(out)
        do.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                   outline=ACCENT, width=10)
    return out


def _translate(canvas: Image.Image, dx: int, dy: int) -> Image.Image:
    if dx == 0 and dy == 0:
        return canvas
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(canvas, (dx, dy))
    return out


def _scale_center(canvas: Image.Image, s: float) -> Image.Image:
    if abs(s - 1.0) < 1e-3:
        return canvas
    nw, nh = max(1, int(W * s)), max(1, int(H * s))
    img = canvas.resize((nw, nh), _RESAMPLE)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(img, ((W - nw) // 2, (H - nh) // 2))
    return out


def _apply_scene_transitions(canvas: Image.Image, scene: dict,
                             t: float, dur: float) -> Image.Image:
    variant_in = scene.get("variant_in", "sweep")
    variant_out = scene.get("variant_out", "scale_fade")

    ep = clamp(t / ENTRANCE_DUR)
    if ep < 1.0:
        if variant_in == "iris":
            canvas = _iris(canvas, ease_out_cube(ep))
            flash = Image.new("RGBA", (W, H), (255, 255, 255, int((1 - ep) * 70)))
            canvas.alpha_composite(flash)
        elif variant_in == "slide_up":
            off = int((1.0 - ease_out_back(ep)) * H)
            canvas = _translate(canvas, 0, off)
        else:  # "sweep" — signature diagonal light sweep + flash
            canvas.alpha_composite(_light_sweep(ep))
            flash = Image.new("RGBA", (W, H), (255, 255, 255, int((1 - ep) * 130)))
            canvas.alpha_composite(flash)

    xq = 1.0 - clamp((dur - t) / EXIT_MOTION_DUR)
    if xq > 0:
        x2 = xq * xq
        if variant_out == "slide_down":
            canvas = _translate(canvas, 0, int(x2 * H))
        elif variant_out == "iris_close":
            canvas = _iris(canvas, x2, closing=True)
        else:  # "scale_fade"
            canvas = _scale_center(canvas, 1.0 - 0.10 * x2)
    return canvas


def _compose_frame(scene: dict, illu: Optional[Image.Image], stage: Image.Image,
                   t: float, dur: float) -> Image.Image:
    kind = scene.get("kind", "idea")
    # The BOARD family owns the whole frame (fixed panel + stage card), so it
    # bypasses the generic composition tree entirely — including for steps and
    # number beats, which the card renders in its own style.
    raw_layout = scene.get("layout", "stage_center")
    if raw_layout in BOARD_LAYOUTS:
        return _apply_alpha(
            _apply_scene_transitions(
                _compose_board_frame(scene, illu, stage, t, dur, raw_layout), scene, t, dur),
            alpha_fade(t, dur, fin=0.18, fout=EXIT_FADE))

    # The distinct layouts (see LAYOUTS) only apply to plain "idea" beats —
    # steps/number scenes keep their own bespoke composition (pills/counter)
    # so those stay legible regardless of the layout rotation.
    layout = raw_layout if kind == "idea" else "stage_center"

    canvas = stage.copy()
    canvas.alpha_composite(_bg_motif(layout, t))

    box = _illu_box(kind, layout)
    shape = LAYOUT_ILLU_SHAPES.get(layout, "rounded") if kind == "idea" else "rounded"
    if illu is not None:
        _paste_illustration(canvas, illu, t, dur, box, shape=shape)

    # All ink (panels, doodles, text) goes on its own layer composited once:
    # ImageDraw REPLACES pixels (alpha included), so drawing semi-transparent
    # fills straight on the canvas would punch see-through holes in the scene.
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg)

    if illu is None:
        _draw_icon_drawing(fg, scene.get("icon", content.DEFAULT_ICON), t, dur, box,
                           shape=shape)
        draw = ImageDraw.Draw(fg)

    kicker = scene.get("kicker", "À RETENIR")
    headline_y = 1245 if kind != "steps" else 0
    if kind == "steps":
        _draw_kicker(draw, fg, kicker, t)
        draw = ImageDraw.Draw(fg)
        _draw_steps(draw, scene.get("steps", []), t)
    else:
        if kind == "number" and scene.get("value") is not None:
            _draw_kicker(draw, fg, kicker, t)
            draw = ImageDraw.Draw(fg)
            _draw_counter(draw, float(scene["value"]), scene.get("raw", ""), t)
            headline_y = 1290
            _draw_headline(draw, scene.get("headline", ""), t, headline_y)
            _draw_headline_circle(draw, scene.get("headline", ""), t, headline_y)
            _draw_arrows(draw, t, box)
        elif layout == "badge_top":
            _draw_ribbon_banner(draw, fg, kicker, scene.get("headline", ""), t)
            draw = ImageDraw.Draw(fg)
        elif layout == "fullbleed_frame":
            _draw_caption_bar(draw, fg, kicker, scene.get("headline", ""), t)
            draw = ImageDraw.Draw(fg)
        elif layout == "split_panel":
            _draw_kicker(draw, fg, kicker, t)
            draw = ImageDraw.Draw(fg)
            _draw_headline(draw, scene.get("headline", ""), t, 1340)
            _draw_arrow_diagonal(draw, t, box)
        elif layout == "corner_stack":
            _draw_corner_stack(draw, fg, kicker, scene.get("headline", ""), t)
            draw = ImageDraw.Draw(fg)
        elif layout == "ticker_strip":
            _draw_ticker_bar(draw, fg, kicker, scene.get("headline", ""), t)
            draw = ImageDraw.Draw(fg)
        elif layout == "frame_card":
            _draw_card_caption(draw, fg, kicker, scene.get("headline", ""), t, box)
        elif layout == "diagonal_split":
            _draw_diagonal_caption(draw, fg, kicker, scene.get("headline", ""), t)
        elif layout == "circle_spot":
            _draw_kicker(draw, fg, kicker, t)
            draw = ImageDraw.Draw(fg)
            hy = min(H - 470, box[3] + 170)
            _draw_headline(draw, scene.get("headline", ""), t, hy)
            _draw_arrows(draw, t, box)
        elif layout == "polaroid_tilt":
            _draw_kicker(draw, fg, kicker, t)
            draw = ImageDraw.Draw(fg)
            _draw_polaroid_caption(draw, fg, scene.get("headline", ""), t, box)
        elif layout == "arch_gate":
            _draw_kicker(draw, fg, kicker, t)
            draw = ImageDraw.Draw(fg)
            hy = min(H - 470, box[3] + 175)
            _draw_headline(draw, scene.get("headline", ""), t, hy)
        else:  # stage_center — signature look
            _draw_kicker(draw, fg, kicker, t)
            draw = ImageDraw.Draw(fg)
            _draw_headline(draw, scene.get("headline", ""), t, headline_y)
            _draw_headline_circle(draw, scene.get("headline", ""), t, headline_y)
            _draw_arrows(draw, t, box)

    _draw_sparkles(draw, t, box)
    canvas.alpha_composite(fg)

    # Readable semantic caption that mirrors the actual spoken phrase. It is
    # drawn after the template headline so it stays large/clear across layouts.
    _draw_spoken_line(draw, canvas, scene, t, layout)

    canvas = _apply_scene_transitions(canvas, scene, t, dur)
    return _apply_alpha(canvas, alpha_fade(t, dur, fin=0.18, fout=EXIT_FADE))


def scene_events(scene: dict) -> dict:
    """Element timings (relative to scene start) used for SFX planning."""
    dur = float(scene.get("duration", config.MOTION_SCENE_DUR))
    elements = [T_HEADLINE, T_ARROWS]
    kind = scene.get("kind", "idea")
    if kind == "steps":
        n = min(4, len(scene.get("steps", []))) or 2
        elements = [T_ELEMENTS + i * STEP_STAGGER for i in range(n)]
    elif kind == "number":
        elements = [T_HEADLINE, T_ELEMENTS]
    elements = sorted(et for et in elements if et < dur - EXIT_FADE - 0.2)
    return {
        "entrance": 0.0,
        "elements": [round(et, 3) for et in elements],
        "exit": round(dur - EXIT_FADE, 3),
    }


def _silhouette_size(scene: dict) -> Optional[Tuple[int, int]]:
    """Taille de la plaque silhouette pour cette scène, ou None si sa
    composition la recadrerait mal (voir *_SILHOUETTE_LAYOUTS)."""
    layout = scene.get("layout") or "stage_center"
    if layout in BOARD_LAYOUTS:
        if layout not in BOARD_SILHOUETTE_LAYOUTS:
            return None
        x0, y0, x1, y1 = BOARD_CARD
    else:
        if layout not in GENERIC_SILHOUETTE_LAYOUTS:
            return None
        x0, y0, x1, y1 = _illu_box(scene.get("kind", "idea"), layout)
    return (max(1, x1 - x0), max(1, y1 - y0))


def _silhouette_plate(scene: dict) -> Optional[Image.Image]:
    """Illustration de repli VECTORIELLE: une silhouette « papercut lumineux »
    posée sur une plaque claire, aux couleurs de la palette du style.

    Elle remplace le dessin au trait quand la composition s'y prête — c'est
    gratuit (aucun crédit image) et strictement reproductible.
    """
    size = _silhouette_size(scene)
    if size is None:
        return None
    pose = scene.get("silhouette") or silhouettes.pose_for_icon(scene.get("icon"))
    custom = silhouettes.load_custom_svg(pose, *size)
    if custom is not None:
        plate = Image.new("RGBA", size, silhouettes.PLATE)
        plate.alpha_composite(custom)
        return plate
    # Col CHAUD + liseré FROID, comme sur la référence: ACCENT porte la teinte
    # chaude de la palette, GOLD la seconde teinte (froide sur le board).
    return silhouettes.render_plate(pose, size[0], size[1],
                                    body=(13, 13, 16, 255), accent=ACCENT, rim=GOLD)


def render_scene(scene: dict, out_path: str, fps: int = config.FPS) -> dict:
    """Render one motion-design scene to ProRes 4444; returns the enriched spec."""
    dur = float(scene.get("duration", config.MOTION_SCENE_DUR))
    illu: Optional[Image.Image] = None
    silhouette_used: Optional[str] = None
    image_path = scene.get("image")
    if image_path and os.path.exists(image_path):
        try:
            illu = Image.open(image_path).convert("RGBA")
        except OSError as exc:
            print(f"[motion_design] WARN cannot read {image_path}: {exc} "
                  f"-> procedural drawing", file=sys.stderr)
    # Une silhouette n'est PAS une image IA: le rapport du job doit continuer à
    # ne compter que les illustrations réellement payées.
    ai_illustrated = illu is not None
    if illu is None and scene.get("silhouette") is not False:
        illu = _silhouette_plate(scene)
        if illu is not None:
            silhouette_used = (scene.get("silhouette")
                               or silhouettes.pose_for_icon(scene.get("icon")))

    stage = (_board_base() if scene.get("layout") in BOARD_LAYOUTS
             else _stage_base())
    n_frames = max(1, int(round(dur * fps)))
    with ProResPipe(out_path, fps=fps) as pipe:
        for fi in range(n_frames):
            pipe.write(_compose_frame(scene, illu, stage, fi / fps, dur))

    events = scene_events(scene)
    if illu is None:
        events["draw"] = T_ILLU       # the drawing draws itself -> pencil SFX
    return {**scene, "mov": out_path, "duration": round(dur, 3),
            "illustrated": ai_illustrated, "silhouette": silhouette_used,
            "events": events}


def render_all(scenes: List[dict], outdir: str, *, preset: Optional[str] = None,
               seed_text: Optional[str] = None) -> List[dict]:
    os.makedirs(outdir, exist_ok=True)
    # Per-video colour palette (variety across videos). A stable seed (job/video
    # id or the transcript) keeps a given job reproducible; *preset* forces a
    # named motion-design family.
    seed = seed_text or "|".join(
        s.get("headline", "") + s.get("excerpt", "") for s in scenes)
    family = select_palette(seed, preset=preset)
    # Le style "board_pitch" possède sa PROPRE famille de compositions: le
    # panneau vert reste identique d'un beat à l'autre et seule la carte change
    # (cf. BOARD_LAYOUTS), exactement comme un board de présentation.
    layouts = (_board_layout_sequence(seed, len(scenes)) if family == "board_pitch"
               else _layout_sequence(seed, len(scenes)))
    out: List[dict] = []
    for i, scene in enumerate(scenes):
        # Cycle the entrance/exit transition variants so two consecutive
        # takeovers never use the same move (belles transitions variées), AND
        # rotate the scene LAYOUT itself (composition, not just colour) so the
        # motion-design beats of a single video alternate between many
        # designs instead of repeating one template — the rotation is
        # reshuffled per video so different edits don't even share the same
        # layout order.
        layout = layouts[i]
        # Sans image IA, la scène sera illustrée par une SILHOUETTE vectorielle:
        # on l'oriente alors vers une composition qui montre le personnage en
        # entier (board_quote reste volontairement un beat purement typographique).
        if (layout in BOARD_LAYOUTS and layout != "board_quote"
                and layout not in BOARD_SILHOUETTE_LAYOUTS
                and not scene.get("image")):
            layout = BOARD_SILHOUETTE_LAYOUTS[i % len(BOARD_SILHOUETTE_LAYOUTS)]
        scene = {
            **scene,
            "variant_in": config.MOTION_ENTRANCES[i % len(config.MOTION_ENTRANCES)],
            "variant_out": config.MOTION_EXITS[i % len(config.MOTION_EXITS)],
            "layout": layout,
        }
        path = os.path.join(outdir, f"{scene['id']}.mov")
        try:
            rendered = render_scene(scene, path)
        except Exception as exc:  # noqa: BLE001 - one bad scene must not kill the montage
            print(f"[motion_design] WARN scene {scene.get('id')} failed: {exc}",
                  file=sys.stderr)
            continue
        out.append(rendered)
        if rendered["illustrated"]:
            src = "AI illustration"
        elif rendered.get("silhouette"):
            src = f"silhouette '{rendered['silhouette']}'"
        else:
            src = f"drawing '{scene.get('icon')}'"
        print(f"[motion_design] {scene['id']} {scene.get('kind', 'idea'):7s} "
              f"({rendered['duration']:.1f}s, {src}) -> {path}")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Render illustrated motion-design scenes -> ProRes 4444 .mov")
    ap.add_argument("scenes", nargs="?", help="JSON list of scene specs")
    ap.add_argument("--from-vu", help="derive scenes from a transcript _vu.json")
    ap.add_argument("--outdir", default="motion_clips")
    ap.add_argument("--dump-scenes", help="write derived scenes to this path and exit")
    args = ap.parse_args(argv)

    if args.from_vu:
        vu = json.load(open(args.from_vu, encoding="utf-8"))
        scenes = content.derive_motion_scenes(vu)
    elif args.scenes:
        scenes = json.load(open(args.scenes, encoding="utf-8"))
    else:
        ap.error("provide scenes.json or --from-vu")

    if args.dump_scenes:
        json.dump(scenes, open(args.dump_scenes, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"[motion_design] {len(scenes)} scenes -> {args.dump_scenes}")
        return 0

    rendered = render_all(scenes, args.outdir)
    json.dump(rendered, open(os.path.join(args.outdir, "_motion_clips.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
