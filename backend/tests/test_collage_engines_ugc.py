"""Les TROIS moteurs de collage papier.

Contrat produit vérifié ici:

  1. `collage_premium`     éditorial, images IA autorisées (comportement d'avant);
  2. `collage_ugc_product` présentation de produit, ZÉRO appel d'image payant,
                           zéro motion design — le collage papier illustre seul;
  3. `collage_ugc_motion`  identique, plus les scènes de motion design.

La garantie qui compte le plus pour le coût: aucun des deux moteurs UGC ne doit
pouvoir déclencher une génération d'image, même si une clé API est présente
dans l'environnement.
"""
from __future__ import annotations

import os

import pytest

from app.api.v1.modes import MODE_DEFINITIONS
from app.config import VALID_MODES
from app.processing.collage import collage_config as ccfg
from app.processing.collage import collage_profiles, collage_shapes
from app.processing.collage.collage_concept_planner import CollageConceptPlanner
from app.processing.collage.collage_pipeline import run_collage_for_ideas
from app.processing.pipeline_v2 import V2_MODE_PRESETS, _export_collage_env

UGC_MODES = ("collage_ugc_product", "collage_ugc_motion")
ALL_COLLAGE_MODES = ("collage_premium",) + UGC_MODES


# --------------------------------------------------------------------------- #
# 1. Catalogue: les trois moteurs existent et sont sélectionnables
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("mode", ALL_COLLAGE_MODES)
def test_engine_is_selectable_end_to_end(mode):
    assert mode in VALID_MODES                      # accepté par l'API
    assert mode in V2_MODE_PRESETS                  # connu du pipeline
    listed = [m for m in MODE_DEFINITIONS if m["id"] == mode]
    assert listed, f"{mode} absent du catalogue exposé au frontend"
    assert listed[0]["defaults"]["collage_broll"] is True


def test_the_three_engines_have_distinct_profiles():
    profiles = {m: V2_MODE_PRESETS[m]["collage_profile"] for m in ALL_COLLAGE_MODES}
    assert len(set(profiles.values())) == 3, profiles
    assert set(profiles.values()) <= set(collage_profiles.PROFILES)


def test_premium_engine_behaviour_is_unchanged():
    """Le moteur d'origine ne doit pas avoir bougé en ajoutant les deux autres."""
    preset = V2_MODE_PRESETS["collage_premium"]
    assert preset["visual_mode"] == "auto_fallback"   # images IA quand possible
    assert preset["motion_design"] is True
    assert collage_profiles.get(preset["collage_profile"]).allow_ai_images is True


# --------------------------------------------------------------------------- #
# 2. Le verrou de coût des moteurs UGC
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("mode", UGC_MODES)
def test_ugc_engines_never_allow_paid_images(mode):
    preset = V2_MODE_PRESETS[mode]
    # Deux verrous indépendants, volontairement redondants:
    #   - le mode visuel coupe tous les appels payants du moteur de montage;
    #   - le profil de collage refuse l'image même si on l'appelait directement.
    assert preset["visual_mode"] == "credit_saver"
    assert collage_profiles.get(preset["collage_profile"]).allow_ai_images is False


@pytest.mark.parametrize("mode", UGC_MODES)
def test_ugc_engine_uses_the_noop_image_provider_even_with_an_api_key(
        mode, tmp_path, monkeypatch):
    """Le test qui protège la facture: clé API présente, zéro appel émis."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-should-not-be-used")
    _export_collage_env(V2_MODE_PRESETS[mode])
    ccfg.refresh()

    ideas = [{"id": "cg_000", "source_start": 0.0, "source_end": 4.0,
              "excerpt": "le prix est vraiment imbattable pour cette qualité"}]
    result = run_collage_for_ideas(
        ideas, str(tmp_path), allow_paid_images=True,   # même en l'autorisant…
        allow_planner_llm=False, profile=ccfg.PROFILE,
    )
    # …le profil impose le fournisseur « noop »: aucune requête réseau d'image.
    assert result.stats["provider"] == "noop"
    assert result.stats["images"] == 0
    assert result.stats["profile"] == V2_MODE_PRESETS[mode]["collage_profile"]


def test_motion_design_is_the_only_difference_between_the_two_ugc_engines():
    product = dict(V2_MODE_PRESETS["collage_ugc_product"])
    motion = dict(V2_MODE_PRESETS["collage_ugc_motion"])
    assert product.pop("motion_design") is False
    assert motion.pop("motion_design") is True
    product.pop("collage_profile")
    motion.pop("collage_profile")
    assert product == motion


# --------------------------------------------------------------------------- #
# 3. Direction artistique: le collage parle bien du PRODUIT
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    ("la livraison est arrivée en 48h à domicile", "delivery"),
    ("le prix est imbattable, moins cher qu'ailleurs", "price"),
    ("des milliers d'avis clients le recommandent", "proof"),
    ("regardez le résultat après une semaine", "result"),
    ("la formule est naturelle, sans paraben", "ingredients"),
    ("tu commandes depuis le lien en bio", "order"),
    ("il reste très peu de stock, ça part vite", "urgency"),
])
def test_product_intent_detection(text, expected):
    assert collage_profiles.UGC_PRODUCT.intent_for(text) == expected


@pytest.mark.parametrize("text", [
    # Pièges du français: sans ancrage sur les limites de mot, ces phrases
    # partaient sur l'intention « prix » (franc/coute) ou « avis » (ravis).
    "franchement je vais te montrer le résultat après une semaine",
    "écoute bien, la différence est visible dès le premier jour",
    "je suis ravis du résultat obtenu en une semaine",
])
def test_short_words_do_not_trigger_the_wrong_intent(text):
    assert collage_profiles.UGC_PRODUCT.intent_for(text) == "result"


def test_ugc_planner_produces_concrete_product_objects():
    """Sans LLM, l'heuristique doit déjà donner des objets illustrables."""
    planner = CollageConceptPlanner(use_llm=False,
                                    profile=collage_profiles.UGC_PRODUCT)
    concepts = planner.plan([
        {"id": "a", "source_start": 0.0, "source_end": 4.0,
         "text": "la livraison arrive en 48h et le colis est nickel"},
        {"id": "b", "source_start": 5.0, "source_end": 9.0,
         "text": "des milliers d'avis clients recommandent ce produit"},
    ])
    assert len(concepts) == 2
    for concept in concepts:
        assert len(concept.objects) >= ccfg.MIN_OBJECTS
        # Chaque objet doit se traduire en une découpe RECONNAISSABLE — un
        # objet qui ne mappe sur rien retomberait sur une forme arbitraire.
        for obj in concept.objects:
            assert collage_shapes.resolve_pictogram(obj.name) in collage_shapes.PICTOGRAMS


def test_ugc_and_editorial_do_not_share_planner_cache_entries():
    """La même phrase ne doit pas resservir un concept de l'autre direction."""
    text = {"id": "x", "source_start": 0.0, "source_end": 4.0,
            "text": "la confiance se construit une brique à la fois"}
    editorial = CollageConceptPlanner(use_llm=False,
                                      profile=collage_profiles.EDITORIAL)
    ugc = CollageConceptPlanner(use_llm=False, profile=collage_profiles.UGC_PRODUCT)
    assert editorial._prepare(text, 0)["cache_key"] != ugc._prepare(text, 0)["cache_key"]


# --------------------------------------------------------------------------- #
# 4. Le collage porte TOUTE l'illustration quand il n'y a pas d'image IA
# --------------------------------------------------------------------------- #
def test_ugc_profile_takes_every_illustratable_beat():
    """Un beat laissé au B-roll photo resterait NON illustré (pas d'image IA)."""
    from app.autoedit_engine.pipeline import _split_collage_ideas

    os.environ["COLLAGE_BROLL_ENABLED"] = "1"
    _export_collage_env(V2_MODE_PRESETS["collage_ugc_product"])
    ccfg.refresh()

    ideas = [{"id": f"i{i}", "excerpt": f"phrase produit numéro {i}",
              "source_start": i * 5.0, "source_end": i * 5.0 + 4.0}
             for i in range(5)]
    collage, photo = _split_collage_ideas(ideas)
    assert len(collage) == 5
    assert photo == []


def test_editorial_profile_still_shares_beats_with_photo_broll():
    os.environ["COLLAGE_BROLL_ENABLED"] = "1"
    _export_collage_env(V2_MODE_PRESETS["collage_premium"])
    ccfg.refresh()
    assert ccfg.MAX_SHARE_OF_BROLL < 1.0


# --------------------------------------------------------------------------- #
# 5. Bibliothèque de pictogrammes
# --------------------------------------------------------------------------- #
def test_every_library_object_maps_to_a_real_pictogram():
    for library in (collage_profiles.UGC_LIBRARY, ):
        for _, (_, objects, _) in library.items():
            for name in objects:
                assert name in collage_shapes.PICTOGRAMS, name


def test_pictogram_resolution_is_stable_and_language_agnostic():
    assert collage_shapes.resolve_pictogram("colis") == "box"
    assert collage_shapes.resolve_pictogram("parcel") == "box"
    assert collage_shapes.resolve_pictogram("étiquette de prix") == "tag"
    assert collage_shapes.resolve_pictogram("camion de livraison") == "truck"
    # Un mot inconnu retombe sur une forme STABLE (pas de scène qui change
    # d'aspect d'un rendu à l'autre) et jamais toujours la même.
    a = collage_shapes.resolve_pictogram("zorglub")
    assert a == collage_shapes.resolve_pictogram("zorglub")
    assert a in collage_shapes.PICTOGRAMS


def test_cutout_is_transparent_outside_the_torn_paper():
    import numpy as np

    piece = collage_shapes.render_cutout(
        "bottle", 200, 200, paper_color=(247, 241, 227, 255),
        ink_color=(29, 29, 27, 255), accent_color=(242, 183, 5, 255), seed=7)
    alpha = np.asarray(piece.split()[3])
    assert alpha[0, 0] == 0                 # coin extérieur: papier découpé
    assert alpha[100, 100] == 255           # centre: pleine matière
