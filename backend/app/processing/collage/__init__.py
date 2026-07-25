"""Moteur **Collage Premium B-roll** (code interne: ``collage_assemble``).

Nouveau type de B-roll de CutForge: comprendre le SENS d'une phrase, en tirer
une métaphore visuelle, générer les pièces du collage puis les assembler à
l'écran — entièrement automatiquement.

Chaîne complète (voir `docs/COLLAGE_PREMIUM_BROLL.md`):

    transcript → concept (JSON) → prompts verrouillés → image → contrôle
    qualité → animation `collage_assemble` → timeline → rendu final

Les imports lourds (PIL/NumPy/moteur) restent dans les sous-modules: importer
`app.processing.collage` ne coûte rien tant qu'on ne demande pas un service.
"""
from app.processing.collage import collage_config as config  # noqa: F401
from app.processing.collage.collage_types import (  # noqa: F401
    BrollType,
    CollageAsset,
    CollageClip,
    CollageConcept,
    CollageObject,
    CollagePrompts,
    CollageRunResult,
    Emotion,
    QualityReport,
)

__all__ = [
    "config",
    "BrollType",
    "CollageAsset",
    "CollageClip",
    "CollageConcept",
    "CollageObject",
    "CollagePrompts",
    "CollageRunResult",
    "Emotion",
    "QualityReport",
    "CollagePipeline",
    "run_collage_for_ideas",
]


def __getattr__(name: str):
    """Chargement paresseux du pipeline (évite d'importer PIL/NumPy pour rien)."""
    if name in {"CollagePipeline", "run_collage_for_ideas"}:
        from app.processing.collage import collage_pipeline
        return getattr(collage_pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
