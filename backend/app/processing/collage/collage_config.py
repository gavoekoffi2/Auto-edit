"""Collage Premium B-roll — configuration centralisée.

Toutes les constantes du moteur « Collage Premium » vivent ici (même
convention que `app.autoedit_engine.config`): lecture d'``os.environ`` pour
rester utilisable depuis le moteur ET depuis Celery sans importer pydantic.

Rien ici n'est un secret: les clés API sont lues à l'appel, jamais stockées
dans une constante de module.
"""
from __future__ import annotations

import os

# --------------------------------------------------------------------------- #
# IDENTITÉ DU MOTEUR
# --------------------------------------------------------------------------- #
ENGINE_NAME = "collage_premium"
#: Type de mouvement exposé au reste du pipeline (nouveau, à côté de Ken Burns).
MOTION_KIND = "collage_assemble"
#: Version du verrou de style. À incrémenter dès que le prompt de style change:
#: elle entre dans la clé de cache, donc un changement invalide proprement les
#: anciens assets sans purge manuelle.
STYLE_LOCK_VERSION = "1"


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() not in {"0", "false", "no", ""}


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except ValueError:
        return default


# --------------------------------------------------------------------------- #
# ACTIVATION
# --------------------------------------------------------------------------- #
#: Le moteur est OPT-IN: tant qu'il est éteint, les pipelines V1/V2 se
#: comportent exactement comme avant (aucun appel, aucun coût, aucun risque).
ENABLED = _flag("COLLAGE_BROLL_ENABLED", "0")

#: Profil de direction artistique (voir `collage_profiles`):
#:   editorial   -> Collage Premium historique (images IA autorisées)
#:   ugc_product -> présentation de produit, zéro image payante
#:   ugc_motion  -> idem + scènes de motion design côté montage
PROFILE = os.getenv("COLLAGE_PROFILE", "editorial").strip().lower()

#: Part maximale des beats B-roll d'une vidéo qui peuvent partir en collage.
#: Garde-fou produit ET budget: le collage coûte plus cher qu'une image simple.
MAX_SHARE_OF_BROLL = _f("COLLAGE_MAX_SHARE", 0.5)
#: Plafond dur du nombre de scènes collage par vidéo (budget API).
MAX_SCENES = _i("COLLAGE_MAX_SCENES", 4)
#: En dessous de cette durée de vidéo, on ne tente pas de collage.
MIN_VIDEO_DURATION = _f("COLLAGE_MIN_VIDEO_DURATION", 20.0)

# --------------------------------------------------------------------------- #
# PLANIFICATION SÉMANTIQUE (CollageConceptPlanner)
# --------------------------------------------------------------------------- #
#: Modèle texte bon marché: on lui demande UNE analyse sémantique par lot de
#: segments (un seul appel HTTP pour toute la vidéo).
PLANNER_MODEL = os.getenv("COLLAGE_PLANNER_MODEL", "google/gemini-2.5-flash-lite")
PLANNER_ENABLED = _flag("COLLAGE_PLANNER_LLM", "1")
PLANNER_TIMEOUT_S = _i("COLLAGE_PLANNER_TIMEOUT", 60)
MIN_OBJECTS = 3
MAX_OBJECTS = 6

# --------------------------------------------------------------------------- #
# GÉNÉRATION D'IMAGE
# --------------------------------------------------------------------------- #
#: Nom du provider dans le registre (`collage_image_service.PROVIDERS`).
#: Vide => on retombe sur IMAGE_GENERATION_PROVIDER puis sur "noop".
IMAGE_PROVIDER = os.getenv("COLLAGE_IMAGE_PROVIDER", "").strip().lower()
IMAGE_MODEL = os.getenv("COLLAGE_IMAGE_MODEL", "").strip()
IMAGE_TIMEOUT_S = _i("COLLAGE_IMAGE_TIMEOUT", 180)
ASPECT_RATIO = os.getenv("COLLAGE_ASPECT_RATIO", "9:16")

#: Providers HTTP génériques pilotés par configuration (aucun fournisseur
#: n'est codé en dur dans la logique métier — voir collage_image_service).
GOOGLE_AI_STUDIO_BASE_URL = os.getenv(
    "GOOGLE_AI_STUDIO_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
)
GOOGLE_AI_STUDIO_MODEL = os.getenv(
    "GOOGLE_AI_STUDIO_IMAGE_MODEL", "gemini-2.5-flash-image"
)
MAXFUSION_BASE_URL = os.getenv("MAXFUSION_BASE_URL", "https://api.maxfusion.ai/v1")
MAXFUSION_IMAGE_MODEL = os.getenv("MAXFUSION_IMAGE_MODEL", "flux-1.1-pro")
MAXFUSION_VIDEO_MODEL = os.getenv("MAXFUSION_VIDEO_MODEL", "")

# --------------------------------------------------------------------------- #
# GÉNÉRATION VIDÉO (collage_assemble)
# --------------------------------------------------------------------------- #
#: "local" = compositing déterministe FFmpeg/PIL (défaut: gratuit, offline,
#: reproductible). Un nom de provider vidéo bascule sur l'image→vidéo IA.
VIDEO_PROVIDER = os.getenv("COLLAGE_VIDEO_PROVIDER", "local").strip().lower()
VIDEO_TIMEOUT_S = _i("COLLAGE_VIDEO_TIMEOUT", 300)

CLIP_DURATION = _f("COLLAGE_CLIP_DURATION", 4.2)
CLIP_DURATION_MIN = _f("COLLAGE_CLIP_DURATION_MIN", 3.0)
CLIP_DURATION_MAX = _f("COLLAGE_CLIP_DURATION_MAX", 6.0)
#: Le fond vide tient ce ratio du clip avant que le premier élément tombe.
EMPTY_HOLD_RATIO = _f("COLLAGE_EMPTY_HOLD", 0.10)
#: Part du clip pendant laquelle les éléments s'assemblent (le reste = tenue).
ASSEMBLY_RATIO = _f("COLLAGE_ASSEMBLY_RATIO", 0.66)
#: Durée d'entrée d'UN élément (stop-motion: court et net, pas un fondu mou).
ELEMENT_ENTRANCE_DUR = _f("COLLAGE_ELEMENT_ENTRANCE", 0.34)
#: Nombre de paliers de la quantification stop-motion (0 = mouvement continu).
STOP_MOTION_STEPS = _i("COLLAGE_STOP_MOTION_STEPS", 3)
#: Léger « souffle » de caméra sur toute la scène (bien moins que Ken Burns).
BREATH_AMOUNT = _f("COLLAGE_BREATH", 0.035)
KEYLINE_WIDTH = _i("COLLAGE_KEYLINE_WIDTH", 7)
KEYLINE_COLOR = (247, 241, 227, 255)     # crème
PAPER_GRAIN_STRENGTH = _f("COLLAGE_GRAIN", 11.0)
SHADOW_OFFSET = _i("COLLAGE_SHADOW_OFFSET", 14)
SHADOW_ALPHA = _i("COLLAGE_SHADOW_ALPHA", 70)

# --------------------------------------------------------------------------- #
# CONTRÔLE QUALITÉ
# --------------------------------------------------------------------------- #
QUALITY_ENABLED = _flag("COLLAGE_QUALITY_ENABLED", "1")
#: Score global minimal (0-100) pour qu'un asset soit jugé utilisable.
QUALITY_MIN_SCORE = _f("COLLAGE_QUALITY_MIN_SCORE", 62.0)
#: Nombre TOTAL de tentatives de génération d'image par scène (1 = pas de retry).
QUALITY_MAX_ATTEMPTS = _i("COLLAGE_QUALITY_MAX_ATTEMPTS", 2)
#: Seuils des détecteurs heuristiques (voir collage_quality_service).
QUALITY_TEXT_MAX_GLYPHS = _i("COLLAGE_QUALITY_TEXT_MAX_GLYPHS", 26)
QUALITY_WATERMARK_MAX_SCORE = _f("COLLAGE_QUALITY_WATERMARK_MAX", 0.62)
QUALITY_MIN_SEPARATION = _f("COLLAGE_QUALITY_MIN_SEPARATION", 0.40)
QUALITY_MIN_COHERENCE = _f("COLLAGE_QUALITY_MIN_COHERENCE", 0.55)

# --------------------------------------------------------------------------- #
# PERFORMANCE / COÛT
# --------------------------------------------------------------------------- #
#: Parallélisme des appels réseau (I/O bound) et du rendu (CPU bound).
IO_WORKERS = _i("COLLAGE_IO_WORKERS", 4)
RENDER_WORKERS = _i("COLLAGE_RENDER_WORKERS", 2)
#: Cache disque partagé entre jobs: un même concept/prompt n'est jamais payé
#: deux fois (clé = hash du contenu + version du style).
CACHE_ENABLED = _flag("COLLAGE_CACHE_ENABLED", "1")
CACHE_DIR = os.getenv(
    "COLLAGE_CACHE_DIR", os.path.join(os.getenv("UPLOAD_DIR", "./uploads"), ".collage_cache")
)
CACHE_TTL_DAYS = _f("COLLAGE_CACHE_TTL_DAYS", 30.0)
CACHE_MAX_ENTRIES = _i("COLLAGE_CACHE_MAX_ENTRIES", 4000)

# --------------------------------------------------------------------------- #
# PALETTES DE SECOURS
# Le planner IA choisit les couleurs; sans lui (mode heuristique) on tourne sur
# ces familles « papier coloré » éditoriales, seedées par le texte.
# --------------------------------------------------------------------------- #
FALLBACK_PALETTES: list[dict] = [
    {"background": "#E8452C", "papers": ["#F7F1E3", "#1D1D1B", "#F2B705"]},
    {"background": "#1B4D3E", "papers": ["#F7F1E3", "#E8452C", "#EFD9A0"]},
    {"background": "#F2B705", "papers": ["#1D1D1B", "#F7F1E3", "#2E5EAA"]},
    {"background": "#2E5EAA", "papers": ["#F7F1E3", "#F2B705", "#1D1D1B"]},
    {"background": "#D94F70", "papers": ["#F7F1E3", "#1B4D3E", "#EFD9A0"]},
    {"background": "#1D1D1B", "papers": ["#F7F1E3", "#E8452C", "#F2B705"]},
]

#: SFX du moteur, choisis dans le vocabulaire EXISTANT (`config.SFX_NAMES`) —
#: on n'ajoute aucun asset son: papier déchiré + claquements stop-motion.
SFX_POOL = ["paper_rip", "snap", "pop", "paper_rip", "click", "impact"]


# --------------------------------------------------------------------------- #
def refresh() -> None:
    """Relit la configuration depuis l'environnement.

    Les constantes sont figées à l'import (comme dans `autoedit_engine.config`).
    Or le worker Celery propage les réglages produit vers ``os.environ`` juste
    avant un rendu: si le module avait été importé plus tôt dans le process, il
    servirait des valeurs périmées. Les points d'entrée du moteur appellent donc
    `refresh()` — c'est explicite, sans coût, et testable en monkeypatchant
    l'environnement.
    """
    globals().update({
        "ENABLED": _flag("COLLAGE_BROLL_ENABLED", "0"),
        "PROFILE": os.getenv("COLLAGE_PROFILE", "editorial").strip().lower(),
        "MAX_SHARE_OF_BROLL": _f("COLLAGE_MAX_SHARE", 0.5),
        "MAX_SCENES": _i("COLLAGE_MAX_SCENES", 4),
        "MIN_VIDEO_DURATION": _f("COLLAGE_MIN_VIDEO_DURATION", 20.0),
        "PLANNER_MODEL": os.getenv("COLLAGE_PLANNER_MODEL", "google/gemini-2.5-flash-lite"),
        "PLANNER_ENABLED": _flag("COLLAGE_PLANNER_LLM", "1"),
        "IMAGE_PROVIDER": os.getenv("COLLAGE_IMAGE_PROVIDER", "").strip().lower(),
        "IMAGE_MODEL": os.getenv("COLLAGE_IMAGE_MODEL", "").strip(),
        "VIDEO_PROVIDER": os.getenv("COLLAGE_VIDEO_PROVIDER", "local").strip().lower(),
        "CACHE_ENABLED": _flag("COLLAGE_CACHE_ENABLED", "1"),
        "CACHE_DIR": os.getenv(
            "COLLAGE_CACHE_DIR",
            os.path.join(os.getenv("UPLOAD_DIR", "./uploads"), ".collage_cache")),
        "QUALITY_ENABLED": _flag("COLLAGE_QUALITY_ENABLED", "1"),
        "QUALITY_MIN_SCORE": _f("COLLAGE_QUALITY_MIN_SCORE", 62.0),
        "QUALITY_MAX_ATTEMPTS": _i("COLLAGE_QUALITY_MAX_ATTEMPTS", 2),
        "IO_WORKERS": _i("COLLAGE_IO_WORKERS", 4),
        "RENDER_WORKERS": _i("COLLAGE_RENDER_WORKERS", 2),
    })
