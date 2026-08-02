"""Collage Premium B-roll — contrats de données (dataclasses immuables-ish).

Même philosophie que `app.processing.types`: zéro dépendance externe, tout est
sérialisable en JSON via ``to_dict`` pour traverser Celery / le rapport de job.

Le contrat central est le `CollageConcept`: c'est le JSON structuré produit par
le `CollageConceptPlanner` (ÉTAPE 2) et consommé par TOUT le reste du moteur
(prompts, layout de l'animation, contrôle qualité).
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

from . import collage_config as ccfg


# --------------------------------------------------------------------------- #
# Types de B-roll connus du produit (ÉTAPE 7)
# --------------------------------------------------------------------------- #
class BrollType(str, Enum):
    """Familles de B-roll que le `BrollPlanner` peut choisir automatiquement."""

    STATIC_IMAGE = "static_image"      # image IA + Ken Burns (historique)
    STOCK_VIDEO = "stock_video"        # banque de rushes (branchable plus tard)
    AI_VIDEO = "ai_video"              # texte/image → vidéo générative
    MOTION_DESIGN = "motion_design"    # scènes illustrées du moteur Auto Edit
    COLLAGE_PREMIUM = "collage_premium"  # ← ce moteur (motion `collage_assemble`)

    @classmethod
    def parse(cls, raw: object, default: "BrollType" = None) -> "BrollType":
        default = default or cls.STATIC_IMAGE
        if isinstance(raw, cls):
            return raw
        try:
            return cls(str(raw).strip().lower())
        except ValueError:
            return default


class Emotion(str, Enum):
    """Émotions dominantes normalisées (pilote la palette et le rythme)."""

    URGENCY = "urgency"
    HOPE = "hope"
    WARNING = "warning"
    PRIDE = "pride"
    CURIOSITY = "curiosity"
    TRUST = "trust"
    FRUSTRATION = "frustration"
    NEUTRAL = "neutral"

    @classmethod
    def parse(cls, raw: object) -> "Emotion":
        value = str(raw or "").strip().lower()
        for member in cls:
            if member.value == value:
                return member
        # Synonymes courants renvoyés par un LLM (FR + EN).
        aliases = {
            "urgence": cls.URGENCY, "peur": cls.WARNING, "danger": cls.WARNING,
            "alerte": cls.WARNING, "espoir": cls.HOPE, "optimism": cls.HOPE,
            "optimisme": cls.HOPE, "fierté": cls.PRIDE, "fierte": cls.PRIDE,
            "confiance": cls.TRUST, "curiosité": cls.CURIOSITY,
            "curiosite": cls.CURIOSITY, "surprise": cls.CURIOSITY,
            "frustration": cls.FRUSTRATION, "colère": cls.FRUSTRATION,
            "joie": cls.PRIDE, "calme": cls.NEUTRAL,
        }
        return aliases.get(value, cls.NEUTRAL)


#: Entrées « stop-motion » d'un élément. Volontairement sèches et lisibles —
#: un collage papier ne fond pas, il est POSÉ sur le fond.
ENTRANCES = ("drop", "slide_left", "slide_right", "scale_pop", "rotate_in", "rise")


# --------------------------------------------------------------------------- #
# Layouts — le pont entre le prompt image et l'animation
#
# Le layout est décidé AVANT la génération: le prompt image demande au modèle
# de placer les objets dans ces zones, et le `CollageVideoService` réutilise
# EXACTEMENT les mêmes zones pour révéler l'image morceau par morceau. C'est ce
# qui rend l'assemblage local possible sans segmentation sémantique.
#
# Chaque cellule = (nom d'ancrage, cx, cy, rayon) en coordonnées normalisées.
# --------------------------------------------------------------------------- #
#: Plusieurs gabarits par nombre d'objets. Le premier de chaque liste est le
#: gabarit HISTORIQUE (rendu inchangé quand aucune graine n'est fournie); les
#: suivants existent pour la variété: avec un seul gabarit, toutes les scènes
#: d'une même vidéo — et de toutes les vidéos — avaient rigoureusement la même
#: composition, ce qui se voit immédiatement au montage.
LAYOUT_TEMPLATES: dict[int, list[list[tuple[str, float, float, float]]]] = {
    3: [
        [   # héros en haut, deux appuis en bas
            ("center_top", 0.50, 0.34, 0.30),
            ("bottom_left", 0.28, 0.70, 0.24),
            ("bottom_right", 0.73, 0.70, 0.24),
        ],
        [   # colonne décalée, lecture de haut en bas
            ("top_left", 0.32, 0.24, 0.25),
            ("mid_right", 0.70, 0.50, 0.27),
            ("bottom_left", 0.34, 0.76, 0.25),
        ],
        [   # héros bas, contexte en haut
            ("top_left", 0.29, 0.24, 0.22),
            ("top_right", 0.72, 0.26, 0.22),
            ("center_bottom", 0.50, 0.67, 0.31),
        ],
    ],
    4: [
        [
            ("center", 0.50, 0.45, 0.26),
            ("top_left", 0.26, 0.22, 0.20),
            ("top_right", 0.75, 0.24, 0.19),
            ("bottom_center", 0.50, 0.76, 0.24),
        ],
        [   # diagonale descendante
            ("top_left", 0.28, 0.20, 0.21),
            ("mid_right", 0.73, 0.42, 0.22),
            ("mid_left", 0.29, 0.62, 0.20),
            ("bottom_right", 0.72, 0.82, 0.19),
        ],
        [   # héros à gauche, trois satellites qui tournent autour
            #
            # C'était une grille 2×2 à cellules rigoureusement égales: quatre
            # pièces de même taille dans les quatre coins, un trou au centre,
            # et aucune dominante — la seule composition du jeu où l'œil ne
            # savait pas où se poser.
            ("center_left", 0.37, 0.42, 0.30),
            ("top_right", 0.75, 0.21, 0.19),
            ("mid_right", 0.74, 0.58, 0.18),
            ("bottom_center", 0.46, 0.79, 0.21),
        ],
    ],
    5: [
        [
            ("center", 0.50, 0.47, 0.25),
            ("top_left", 0.24, 0.20, 0.18),
            ("top_right", 0.76, 0.21, 0.18),
            ("bottom_left", 0.24, 0.76, 0.19),
            ("bottom_right", 0.76, 0.75, 0.19),
        ],
        [   # bandeau haut de trois, duo bas
            # Trois pièces sur une même ligne, c'est le gabarit le plus serré du
            # jeu: les rayons sont réduits pour que les feuilles (agrandies par
            # PIECE_SPREAD, plus l'ombre portée) ne se touchent pas.
            ("top_left", 0.19, 0.24, 0.145),
            ("center_top", 0.50, 0.19, 0.155),
            ("top_right", 0.81, 0.25, 0.145),
            ("bottom_left", 0.31, 0.61, 0.21),
            ("bottom_right", 0.70, 0.85, 0.20),
        ],
    ],
    6: [
        [
            ("center_top", 0.50, 0.26, 0.22),
            ("mid_left", 0.24, 0.45, 0.18),
            ("mid_right", 0.76, 0.45, 0.18),
            ("center_bottom", 0.50, 0.64, 0.21),
            ("bottom_left", 0.26, 0.82, 0.16),
            ("bottom_right", 0.74, 0.82, 0.16),
        ],
        [   # grille 2x3 régulière
            ("top_left", 0.28, 0.20, 0.18),
            ("top_right", 0.73, 0.20, 0.18),
            ("mid_left", 0.28, 0.50, 0.18),
            ("mid_right", 0.73, 0.50, 0.18),
            ("bottom_left", 0.28, 0.80, 0.18),
            ("bottom_right", 0.73, 0.80, 0.18),
        ],
    ],
}

#: Description humaine des ancrages, injectée telle quelle dans le prompt image.
ANCHOR_LABELS: dict[str, str] = {
    "center": "in the centre of the frame",
    "center_top": "in the upper-centre of the frame",
    "center_bottom": "in the lower-centre of the frame",
    "top_left": "in the upper-left area",
    "top_right": "in the upper-right area",
    "mid_left": "on the middle-left side",
    "mid_right": "on the middle-right side",
    "bottom_left": "in the lower-left area",
    "bottom_right": "in the lower-right area",
    "bottom_center": "in the lower-centre of the frame",
}


def layout_for(count: int, seed: object = None) -> list[tuple[str, float, float, float]]:
    """Gabarit de composition pour *count* objets (borné à 3..6).

    *seed* (l'identifiant du concept, en pratique) fait tourner les variantes:
    deux scènes voisines n'ont plus la même composition, tout en restant
    parfaitement reproductibles. Sans graine, on renvoie le gabarit historique
    — les appelants existants et les rendus déjà produits sont préservés.

    **Le premier objet reçoit toujours la plus grande cellule.** L'objet n°1
    est le SUJET (celui que la phrase nomme, cf. l'ancrage lexical): le laisser
    tomber sur une cellule d'appui donnait des scènes où la voiture dont on
    parle était deux fois plus petite que la coche décorative à côté. On ne
    réécrit pas la composition pour autant — les cellules gardent leurs places,
    seul l'ORDRE d'attribution change, si bien que chaque gabarit conserve son
    équilibre.
    """
    count = max(ccfg.MIN_OBJECTS, min(ccfg.MAX_OBJECTS, int(count or 0)))
    variants = LAYOUT_TEMPLATES[count]
    if seed is None:
        cells = variants[0]
    else:
        digest = hashlib.sha1(str(seed).encode("utf-8")).digest()[0]
        cells = variants[digest % len(variants)]
    return _hero_first(cells)


def _hero_first(cells: list[tuple[str, float, float, float]]
                ) -> list[tuple[str, float, float, float]]:
    """Remonte la cellule au plus grand rayon en tête, l'ordre du reste intact."""
    if len(cells) < 2:
        return list(cells)
    hero = max(range(len(cells)), key=lambda i: cells[i][3])
    if hero == 0:
        return list(cells)
    return [cells[hero]] + [c for i, c in enumerate(cells) if i != hero]


# --------------------------------------------------------------------------- #
# Concept
# --------------------------------------------------------------------------- #
@dataclass
class CollageObject:
    """Un élément découpé du collage (une « pièce » de papier)."""

    name: str                       # objet concret: "clé", "porte fermée"
    order: int                      # ordre d'apparition, 1..N
    anchor: str = "center"          # cellule de layout
    entrance: str = "drop"
    paper_color: str = "#F7F1E3"    # papier coloré derrière la découpe
    note: str = ""                  # rôle narratif, une poignée de mots

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict, fallback_order: int = 1) -> "CollageObject":
        name = str(raw.get("name") or raw.get("objet") or raw.get("object") or "").strip()
        try:
            order = int(raw.get("order") or raw.get("ordre") or fallback_order)
        except (TypeError, ValueError):
            order = fallback_order
        entrance = str(raw.get("entrance") or "drop").strip().lower()
        return cls(
            name=name[:60],
            order=max(1, order),
            anchor=str(raw.get("anchor") or "center").strip().lower(),
            entrance=entrance if entrance in ENTRANCES else "drop",
            paper_color=_normalize_hex(raw.get("paper_color") or raw.get("color"), "#F7F1E3"),
            note=str(raw.get("note") or raw.get("role") or "")[:80],
        )


@dataclass
class CollageConcept:
    """JSON structuré produit par le planner (ÉTAPE 2).

    C'est la « fiche de scène »: ce que la phrase VEUT DIRE, ce qu'elle fait
    ressentir, la métaphore visuelle choisie, les objets qui la racontent, les
    couleurs et l'ordre d'apparition.
    """

    id: str
    source_start: float
    source_end: float
    excerpt: str
    meaning: str = ""
    emotion: Emotion = Emotion.NEUTRAL
    metaphor: str = ""
    objects: list[CollageObject] = field(default_factory=list)
    background_color: str = "#E8452C"
    palette: list[str] = field(default_factory=list)
    label: str = ""
    planner: str = "heuristic"      # llm | heuristic
    confidence: float = 0.5

    # ---------------------------------------------------------------- #
    @property
    def duration(self) -> float:
        return max(0.0, self.source_end - self.source_start)

    @property
    def sequence(self) -> list[str]:
        """Ordre d'apparition des éléments (noms), déjà trié."""
        return [o.name for o in self.ordered_objects()]

    def ordered_objects(self) -> list[CollageObject]:
        return sorted(self.objects, key=lambda o: (o.order, o.name))

    def layout(self) -> list[tuple[str, float, float, float]]:
        """Gabarit de CETTE scène — source unique de vérité.

        Le prompt image demande au modèle de placer les objets dans ces zones et
        l'animation révèle exactement les mêmes: les deux DOIVENT lire le même
        gabarit, sinon la découpe ne tombe plus sur les objets.
        """
        return layout_for(len(self.ordered_objects()), self.id)

    def cache_key(self) -> str:
        """Empreinte stable du concept: sert de clé de cache image/vidéo."""
        parts = [
            ccfg.STYLE_LOCK_VERSION, self.metaphor, self.background_color,
            "|".join(f"{o.order}:{o.name}:{o.anchor}:{o.paper_color}"
                     for o in self.ordered_objects()),
        ]
        return hashlib.sha1("~".join(parts).encode("utf-8")).hexdigest()[:20]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_start": round(self.source_start, 3),
            "source_end": round(self.source_end, 3),
            "duration": round(self.duration, 3),
            "excerpt": self.excerpt,
            "meaning": self.meaning,
            "emotion": self.emotion.value,
            "metaphor": self.metaphor,
            "objects": [o.to_dict() for o in self.ordered_objects()],
            "sequence": self.sequence,
            "background_color": self.background_color,
            "palette": list(self.palette),
            "label": self.label,
            "planner": self.planner,
            "confidence": round(float(self.confidence), 3),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "CollageConcept":
        objects = [
            CollageObject.from_dict(o, i + 1)
            for i, o in enumerate(raw.get("objects") or [])
            if isinstance(o, dict)
        ]
        return cls(
            id=str(raw.get("id") or "cg_000"),
            source_start=float(raw.get("source_start") or 0.0),
            source_end=float(raw.get("source_end") or 0.0),
            excerpt=str(raw.get("excerpt") or ""),
            meaning=str(raw.get("meaning") or "")[:240],
            emotion=Emotion.parse(raw.get("emotion")),
            metaphor=str(raw.get("metaphor") or "")[:240],
            objects=objects,
            background_color=_normalize_hex(raw.get("background_color"), "#E8452C"),
            palette=[_normalize_hex(c, "#F7F1E3") for c in (raw.get("palette") or [])][:5],
            label=str(raw.get("label") or "")[:40],
            planner=str(raw.get("planner") or "heuristic"),
            confidence=float(raw.get("confidence") or 0.5),
        )


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
@dataclass
class CollagePrompts:
    """Sortie du `CollagePromptBuilder` (ÉTAPE 3)."""

    image_prompt: str
    video_prompt: str
    negative_prompt: str
    style_lock_version: str = ccfg.STYLE_LOCK_VERSION
    aspect_ratio: str = ccfg.ASPECT_RATIO

    def cache_key(self) -> str:
        blob = f"{self.style_lock_version}|{self.aspect_ratio}|{self.image_prompt}"
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:20]

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Qualité
# --------------------------------------------------------------------------- #
@dataclass
class QualityReport:
    """Score qualité d'un asset (ÉTAPE 6).

    Le contrat public minimal demandé par le produit est
    ``{"visual_clarity": .., "style_consistency": .., "usable": ..}``; les
    autres champs sont des détails de diagnostic (et pilotent le retry).
    """

    visual_clarity: int = 0
    style_consistency: int = 0
    metaphor_readability: int = 0
    element_separation: int = 0
    text_free: bool = True
    watermark_free: bool = True
    glyph_like_shapes: int = 0
    video_image_coherence: int = 0
    usable: bool = False
    score: int = 0
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Assets & clips
# --------------------------------------------------------------------------- #
@dataclass
class CollageAsset:
    """Image finale d'une scène + traçabilité de sa génération."""

    concept_id: str
    image_path: Optional[str] = None
    provider: str = "noop"
    model: str = ""
    attempts: int = 0
    from_cache: bool = False
    cost_estimate_usd: Optional[float] = None
    quality: Optional[QualityReport] = None
    failure_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "image_path": self.image_path,
            "provider": self.provider,
            "model": self.model,
            "attempts": self.attempts,
            "from_cache": self.from_cache,
            "cost_estimate_usd": self.cost_estimate_usd,
            "quality": self.quality.to_dict() if self.quality else None,
            "failure_reason": self.failure_reason,
        }


@dataclass
class CollageClip:
    """Clip animé prêt à être inséré dans la timeline du moteur."""

    concept_id: str
    clip_path: str
    duration: float
    source_start: float
    source_end: float
    label: str = ""
    motion: str = ccfg.MOTION_KIND
    renderer: str = "local"
    quality: Optional[QualityReport] = None

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "clip_path": self.clip_path,
            "duration": round(self.duration, 3),
            "source_start": round(self.source_start, 3),
            "source_end": round(self.source_end, 3),
            "label": self.label,
            "motion": self.motion,
            "renderer": self.renderer,
            "quality": self.quality.to_dict() if self.quality else None,
        }

    def to_engine_overlay(self) -> dict:
        """Vue attendue par `plan_overlays` du moteur Auto Edit.

        On parle EXACTEMENT le même dialecte que `broll_anim.render_all`
        (``id`` / ``mov`` / ``duration`` / ``source_start``) — c'est ce qui
        permet de brancher le collage sans toucher au placement timeline.
        """
        return {
            "id": self.concept_id,
            "mov": self.clip_path,
            "duration": round(self.duration, 3),
            "source_start": round(self.source_start, 3),
            "source_end": round(self.source_end, 3),
            "label": self.label,
            "kind": ccfg.MOTION_KIND,
        }


@dataclass
class CollageRunResult:
    """Résultat complet d'un passage du moteur (pour le rapport de job)."""

    concepts: list[CollageConcept] = field(default_factory=list)
    assets: list[CollageAsset] = field(default_factory=list)
    clips: list[CollageClip] = field(default_factory=list)
    skipped_reason: Optional[str] = None
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "engine": ccfg.ENGINE_NAME,
            "motion": ccfg.MOTION_KIND,
            "style_lock_version": ccfg.STYLE_LOCK_VERSION,
            "concepts": [c.to_dict() for c in self.concepts],
            "assets": [a.to_dict() for a in self.assets],
            "clips": [c.to_dict() for c in self.clips],
            "skipped_reason": self.skipped_reason,
            "stats": self.stats,
        }


# --------------------------------------------------------------------------- #
def _normalize_hex(raw: object, default: str) -> str:
    """Accepte '#RGB', 'RRGGBB', '#RRGGBB'; renvoie '#RRGGBB' majuscule."""
    value = str(raw or "").strip().lstrip("#")
    if len(value) == 3 and all(c in "0123456789abcdefABCDEF" for c in value):
        value = "".join(c * 2 for c in value)
    if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value):
        return "#" + value.upper()
    return default


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = _normalize_hex(value, "#000000").lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
