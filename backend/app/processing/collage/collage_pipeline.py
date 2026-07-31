"""ÉTAPE 1 — `CollagePipeline`: l'orchestrateur du moteur Collage Premium.

    beats (transcript)
        ↓  CollageConceptPlanner      analyse sémantique → concept JSON
        ↓  CollagePromptBuilder       concept → prompts verrouillés
        ↓  CollageImageService        prompts → image (parallèle, caché)
        ↓  CollageQualityService      score → relance automatique si besoin
        ↓  CollageVideoService        image + concept → clip `collage_assemble`
        ↓  CollageQualityService      cohérence image finale ↔ vidéo
        → clips prêts pour la timeline

Zéro validation humaine: là où le workflow de référence s'arrête à trois portes
d'approbation, on remplace chaque porte par un contrat vérifiable par la
machine (schéma JSON validé, score qualité, relance ciblée).

Le pipeline ne lève JAMAIS: à la moindre difficulté il rend moins de scènes (ou
zéro) et documente pourquoi dans `CollageRunResult.skipped_reason`. Le montage
appelant continue exactement comme avant.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional, Sequence

from . import collage_config as ccfg
from . import collage_profiles
from .collage_concept_planner import CollageConceptPlanner, beats_from_ideas
from .collage_profiles import CollageProfile
from .collage_image_service import CollageImageService
from .collage_prompt_builder import CollagePromptBuilder
from .collage_quality_service import CollageQualityService
from .collage_types import (
    CollageAsset,
    CollageConcept,
    CollagePrompts,
    CollageRunResult,
)
from .collage_video_service import CollageVideoService

logger = logging.getLogger(__name__)


class CollagePipeline:
    """Moteur `collage_premium` — de la phrase au clip animé, sans intervention."""

    def __init__(self,
                 planner: Optional[CollageConceptPlanner] = None,
                 prompt_builder: Optional[CollagePromptBuilder] = None,
                 image_service: Optional[CollageImageService] = None,
                 video_service: Optional[CollageVideoService] = None,
                 quality_service: Optional[CollageQualityService] = None,
                 max_scenes: Optional[int] = None,
                 profile: Optional[CollageProfile] = None):
        self.profile = profile or collage_profiles.get(ccfg.PROFILE)
        self.planner = planner or CollageConceptPlanner(profile=self.profile)
        self.prompts = prompt_builder or CollagePromptBuilder()
        self.images = image_service or CollageImageService()
        self.videos = video_service or CollageVideoService()
        self.quality = quality_service or CollageQualityService()
        self.max_scenes = int(max_scenes or ccfg.MAX_SCENES)

    # ------------------------------------------------------------------ #
    def run(self, beats: Sequence[dict], workdir: str,
            *, render: bool = True) -> CollageRunResult:
        """Exécute le moteur pour *beats* et écrit les assets sous *workdir*."""
        result = CollageRunResult()
        started = time.time()
        beats = list(beats or [])[: max(0, self.max_scenes)]
        if not beats:
            result.skipped_reason = "no_beats"
            return result

        image_dir = os.path.join(workdir, "collage")
        clip_dir = os.path.join(workdir, "collage_clips")

        # --- 1. Analyse sémantique (un appel LLM pour toute la vidéo) ------
        concepts = self.planner.plan(beats)
        if not concepts:
            result.skipped_reason = "no_concepts"
            return result
        result.concepts = concepts

        # --- 2-4. Prompts → images → contrôle qualité → relance ciblée -----
        assets = self._generate_with_quality(concepts, image_dir)
        result.assets = assets
        usable = {a.concept_id: a for a in assets if a.image_path}

        # --- 5. Animation `collage_assemble` -------------------------------
        if render:
            by_id = {c.id: c for c in concepts}
            items = []
            for concept in concepts:
                asset = usable.get(concept.id)
                # Sans image exploitable, le rendu local produit quand même la
                # scène (collage procédural) — la vidéo n'est jamais perdue.
                items.append((concept,
                              asset.image_path if asset else None,
                              self.prompts.build(concept)))
            clips = self.videos.animate_many(items, clip_dir)

            # --- 6. Cohérence image finale ↔ vidéo -------------------------
            for clip in clips:
                asset = usable.get(clip.concept_id)
                clip.quality = self.quality.review_clip(
                    clip.clip_path,
                    asset.image_path if asset else None,
                    asset.quality if asset else None,
                )
            result.clips = [c for c in clips if c.concept_id in by_id]

        result.stats = {
            "profile": self.profile.id,
            "beats": len(beats),
            "concepts": len(concepts),
            "concepts_llm": sum(1 for c in concepts if c.planner == "llm"),
            "images": len(usable),
            "images_from_cache": sum(1 for a in assets if a.from_cache),
            "images_retried": sum(1 for a in assets if a.attempts > 1),
            "clips": len(result.clips),
            "provider": self.images.provider.name,
            "renderer": self.videos.renderer.name,
            "elapsed_s": round(time.time() - started, 2),
        }
        logger.info("[collage_pipeline] %s", result.stats)
        return result

    # ------------------------------------------------------------------ #
    def _generate_with_quality(self, concepts: Sequence[CollageConcept],
                               image_dir: str) -> list[CollageAsset]:
        """Génère les images et relance CIBLÉE celles qui ratent le contrôle.

        Le retry n'est jamais une relance à l'identique: les défauts détectés
        repartent dans le prompt en consignes explicites (`retry_hints`), sinon
        le modèle reproduit la même erreur et on paie deux fois pour rien.
        """
        pending: list[tuple[CollageConcept, CollagePrompts]] = [
            (c, self.prompts.build(c)) for c in concepts
        ]
        best: dict[str, CollageAsset] = {}
        tries: dict[str, int] = {}
        max_attempts = max(1, ccfg.QUALITY_MAX_ATTEMPTS)

        for attempt in range(1, max_attempts + 1):
            if not pending:
                break
            assets = self.images.generate_many(pending, image_dir, attempt=attempt)
            by_id = {c.id: c for c, _ in pending}
            retry: list[tuple[CollageConcept, CollagePrompts]] = []

            for asset in assets:
                concept = by_id[asset.concept_id]
                tries[asset.concept_id] = attempt
                asset.quality = self.quality.review_image(asset.image_path, concept)
                previous = best.get(asset.concept_id)
                # On garde toujours le MEILLEUR essai, même si aucun n'est parfait:
                # un visuel imparfait vaut mieux qu'un trou dans le montage.
                if previous is None or asset.quality.score > (
                        previous.quality.score if previous.quality else -1):
                    best[asset.concept_id] = asset

                if asset.quality.usable or attempt >= max_attempts:
                    continue
                hints = self.quality.retry_hints(asset.quality)
                retry.append((concept, self.prompts.build(concept, quality_hints=hints)))
                logger.info("[collage_pipeline] %s: relance (score=%d, défauts=%s)",
                            concept.id, asset.quality.score,
                            ",".join(asset.quality.issues) or "-")
            pending = retry

        # `attempts` = nombre TOTAL d'essais payés pour cette scène (pas l'index
        # de l'essai retenu): c'est ce chiffre qui doit remonter au rapport de
        # job pour suivre le coût réel des relances.
        for concept_id, asset in best.items():
            asset.attempts = tries.get(concept_id, asset.attempts)
        return [best[c.id] for c in concepts if c.id in best]


# --------------------------------------------------------------------------- #
def run_collage_for_ideas(ideas: Sequence[dict], workdir: str,
                          *, max_scenes: Optional[int] = None,
                          allow_paid_images: bool = True,
                          allow_planner_llm: Optional[bool] = None,
                          profile: Optional[str] = None,
                          pipeline: Optional[CollagePipeline] = None) -> CollageRunResult:
    """Adaptateur pour le moteur Auto Edit.

    Prend les « ideas » déjà découpées par `content.derive_broll_ideas` (donc
    aucune re-détection de beats, aucune duplication de logique) et renvoie des
    clips prêts pour `plan_overlays`.

    Deux leviers de coût, VOLONTAIREMENT séparés:

    *allow_paid_images* = False force le provider `noop`: chaque objet du
    concept est alors découpé en vectoriel (`collage_shapes`). C'est le mode
    permanent des moteurs UGC — aucun appel d'image, jamais.

    *allow_planner_llm* pilote l'analyse TEXTE (un seul appel par vidéo, sur un
    modèle bon marché). C'est elle qui fait que le collage parle du produit dont
    la personne parle: on la garde par défaut même sans images. Passer False
    rend le moteur strictement hors-ligne (repli sur la bibliothèque du profil).
    """
    if pipeline is None:
        resolved = collage_profiles.get(profile or ccfg.PROFILE)
        image_service = None
        if not (allow_paid_images and resolved.allow_ai_images):
            from .collage_image_service import (
                CollageImageService,
                NoopCollageImageProvider,
            )
            image_service = CollageImageService(provider=NoopCollageImageProvider())
        planner = CollageConceptPlanner(use_llm=allow_planner_llm, profile=resolved)
        pipeline = CollagePipeline(image_service=image_service, planner=planner,
                                   max_scenes=max_scenes or resolved.max_scenes,
                                   profile=resolved)
    return pipeline.run(beats_from_ideas(ideas), workdir)
