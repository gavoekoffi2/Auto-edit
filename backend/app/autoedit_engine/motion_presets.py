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
    ink: RGBA = (255, 255, 255, 255)  # text ink — dark for light backgrounds
    #: Comment la scène est ILLUSTRÉE quand aucune image IA n'est disponible.
    #:   "render3d"    -> scène 3D procédurale animée (`motion_3d`) — défaut
    #:   "silhouette"  -> plaque silhouette vectorielle
    #:   "line"        -> dessin au trait qui se trace (look carnet)
    #: Le repli au trait était la cause du « motion design qui ne fonctionne
    #: pas »: sur un montage réel, quatre traits blancs ne racontent rien.
    illustration: str = "render3d"
    #: Style du moteur 3D (`motion_3d.STYLES`). None = déduit de la famille.
    style_3d: str | None = None

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
        style_3d="chrome_metal",
    ),
    MotionDesignPreset(
        name="neon_social",
        bg_top=(18, 12, 32), bg_bottom=(36, 14, 54),
        accent=(170, 110, 255, 255), gold=(90, 230, 255, 255),
        shape_density=0.85, style="glow_streaks_highlights",
        style_3d="glass_neon",
    ),
    MotionDesignPreset(
        name="african_premium",
        bg_top=(20, 16, 10), bg_bottom=(34, 22, 12),
        accent=(255, 168, 56, 255), gold=(70, 200, 130, 255),
        shape_density=0.6, style="gold_orange_deepgreen",
        style_3d="clay_studio",
    ),
    MotionDesignPreset(
        name="minimal_creator",
        bg_top=(12, 14, 20), bg_bottom=(20, 22, 30),
        accent=(0, 220, 255, 255), gold=(255, 255, 255, 255),
        shape_density=0.25, style="zooms_flashes_captions",
        style_3d="glass_neon",
    ),
    MotionDesignPreset(
        name="kinetic_education",
        bg_top=(14, 18, 28), bg_bottom=(22, 30, 48),
        accent=(255, 199, 64, 255), gold=(90, 170, 255, 255),
        shape_density=0.9, style="arrows_circles_underlines",
        style_3d="iso_blocks",
    ),
    MotionDesignPreset(
        name="sunset_vibes",
        bg_top=(30, 12, 26), bg_bottom=(52, 20, 24),
        accent=(255, 120, 90, 255), gold=(255, 205, 110, 255),
        shape_density=0.65, style="warm_coral_amber",
        style_3d="clay_studio",
    ),
    MotionDesignPreset(
        name="electric_lime",
        bg_top=(12, 16, 14), bg_bottom=(20, 30, 20),
        accent=(190, 255, 80, 255), gold=(140, 130, 255, 255),
        shape_density=0.8, style="lime_violet_energy",
        style_3d="glass_neon",
    ),
    # ------------------------------------------------------------------ #
    # Familles 3D NATIVES — pensées pour le moteur `motion_3d`: c'est l'objet
    # en volume qui porte la scène, le décor 2D se met en retrait (densité de
    # formes basse) pour ne pas concurrencer le rendu.
    # ------------------------------------------------------------------ #
    MotionDesignPreset(
        name="clay_3d",
        bg_top=(30, 26, 44), bg_bottom=(18, 15, 28),
        accent=(255, 138, 112, 255), gold=(255, 206, 122, 255),
        shape_density=0.35, style="clay_render_soft_shadow",
        style_3d="clay_studio",
    ),
    MotionDesignPreset(
        name="glass_3d",
        bg_top=(10, 14, 34), bg_bottom=(5, 7, 20),
        accent=(96, 208, 255, 255), gold=(180, 130, 255, 255),
        shape_density=0.30, style="glass_neon_rimlight",
        style_3d="glass_neon",
    ),
    MotionDesignPreset(
        name="chrome_3d",
        bg_top=(20, 22, 30), bg_bottom=(8, 9, 14),
        accent=(168, 198, 255, 255), gold=(226, 200, 140, 255),
        shape_density=0.28, style="chrome_specular_premium",
        style_3d="chrome_metal",
    ),
    MotionDesignPreset(
        name="iso_3d",
        bg_top=(22, 28, 46), bg_bottom=(12, 16, 28),
        accent=(255, 186, 72, 255), gold=(96, 214, 200, 255),
        shape_density=0.40, style="isometric_blocks_bold",
        style_3d="iso_blocks",
    ),
    MotionDesignPreset(
        name="paper_3d",
        bg_top=(244, 238, 226), bg_bottom=(228, 219, 202),
        accent=(224, 84, 62, 255), gold=(46, 132, 118, 255),
        shape_density=0.34, style="paper_craft_relief",
        ink=(28, 26, 24, 255), style_3d="paper_relief",
    ),
    # Réf. vidéo 1 (Captions AI) — collage éditorial: papier bleu froissé,
    # barres noires, blanc cassé. Sert le style "pill_editorial".
    MotionDesignPreset(
        name="editorial_paper",
        bg_top=(38, 84, 200), bg_bottom=(24, 58, 156),
        accent=(245, 242, 234, 255), gold=(255, 224, 130, 255),
        shape_density=0.55, style="paper_collage_bars",
        style_3d="paper_relief",
    ),
    # Réf. vidéo 3 (Captions AI) — carnet crème, encre noire au pinceau,
    # écriture manuscrite. Sert le style "handwritten_note".
    MotionDesignPreset(
        name="sketch_notes",
        bg_top=(247, 243, 233), bg_bottom=(240, 234, 220),
        accent=(24, 24, 24, 255), gold=(43, 98, 226, 255),
        shape_density=0.5, style="brush_bars_handwriting",
        ink=(20, 20, 20, 255),
        # Le trait manuscrit EST l'identité de cette famille: elle garde le
        # dessin qui se trace, c'est la seule qui n'est pas rendue en 3D.
        illustration="line",
    ),
    # Réf. vidéo « board de présentation » (motion design 3D publicitaire) —
    # panneau vert sapin texturé, titres serif éditoriaux, pile de flyers et
    # grande carte-scène claire au centre. Sert le style "board_pitch".
    MotionDesignPreset(
        name="board_pitch",
        bg_top=(56, 88, 77), bg_bottom=(38, 66, 58),
        accent=(232, 196, 110, 255), gold=(116, 202, 150, 255),
        shape_density=0.4, style="green_board_serif_cards",
        ink=(245, 243, 236, 255),
        style_3d="clay_studio",
    ),
]

PRESETS_BY_NAME: Dict[str, MotionDesignPreset] = {p.name: p for p in PRESETS}
DEFAULT_PRESET = PRESETS[0].name

# Familles réservées aux styles de montage qui les demandent explicitement.
# Elles ne participent PAS à la rotation aléatoire par seed: leur fond clair /
# encre sombre casserait le look des templates classiques.
STYLE_ONLY_PRESETS = {"editorial_paper", "sketch_notes", "board_pitch"}
_ROTATION: List[MotionDesignPreset] = [
    p for p in PRESETS if p.name not in STYLE_ONLY_PRESETS
]


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
    """Deterministically pick a preset family from a stable seed of *parts*.

    Only rotation-safe families are eligible; the light-background families
    (STYLE_ONLY_PRESETS) must be requested explicitly via ``preset_for``.
    """
    seed = style_seed(*parts)
    return _ROTATION[seed % len(_ROTATION)]


def preset_for(name: str | None) -> MotionDesignPreset:
    """Look up a preset by name, falling back to the default family."""
    if name and name in PRESETS_BY_NAME:
        return PRESETS_BY_NAME[name]
    return PRESETS_BY_NAME[DEFAULT_PRESET]


def palette_for_preset(name: str | None) -> Tuple[RGB, RGB, RGBA, RGBA]:
    return preset_for(name).palette()


#: Familles dont la scène est rendue par le moteur 3D procédural.
RENDER3D_PRESETS: List[str] = [p.name for p in PRESETS if p.illustration == "render3d"]


def illustration_mode(name: str | None) -> str:
    """« render3d » | « silhouette » | « line » pour la famille *name*."""
    return preset_for(name).illustration


def style_3d_for(name: str | None) -> str | None:
    """Style du moteur 3D à utiliser pour la famille *name* (None si aucun)."""
    preset = preset_for(name)
    if preset.illustration != "render3d":
        return None
    if preset.style_3d:
        return preset.style_3d
    from . import motion_3d
    return motion_3d.style_for_family(preset.name) or motion_3d.DEFAULT_STYLE
