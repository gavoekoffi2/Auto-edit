"""PRÉCISION D'ILLUSTRATION — ce qui est DIT doit être ce qui est DESSINÉ.

Le défaut corrigé ici était visible à l'œil nu sur les montages: quelqu'un
parle de sa voiture, la scène de collage montre un flacon et une feuille.
Trois causes, un test par cause:

  1. le vocabulaire de découpes ignorait le monde réel (pas de voiture, pas de
     maison, pas d'ordinateur);
  2. un mot inconnu retombait sur ``sha1(mot) % N`` — stable, donc faux à
     chaque rendu, donc visible;
  3. les objets venaient d'une CATÉGORIE devinée (prix, livraison…) et jamais
     des noms réellement prononcés.

Ces tests ne demandent ni réseau, ni ffmpeg, ni clé API.
"""
from __future__ import annotations

import pytest

from app.processing.collage import collage_config as ccfg
from app.processing.collage import collage_lexicon as lexicon
from app.processing.collage import collage_profiles, collage_shapes
from app.processing.collage.collage_concept_planner import CollageConceptPlanner
from app.processing.collage.collage_prompt_builder import CollagePromptBuilder


def _beat(text: str, bid: str = "cg_000") -> dict:
    return {"id": bid, "source_start": 0.0, "source_end": 4.0, "text": text}


def _plan_one(text: str, profile=collage_profiles.UGC_PRODUCT):
    """Un concept, sans LLM: c'est le chemin par défaut des moteurs UGC."""
    planner = CollageConceptPlanner(use_llm=False, profile=profile, cache=None)
    concepts = planner.plan([_beat(text)])
    assert concepts, "le planner doit toujours produire une scène"
    return concepts[0]


def _pictograms(concept) -> list[str]:
    return [collage_shapes.resolve_strict(obj.name)
            for obj in concept.ordered_objects()]


# --------------------------------------------------------------------------- #
# 1. Le vocabulaire couvre le monde dont les gens parlent
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("word,expected", [
    ("voiture", "car"), ("ma bagnole", "car"), ("le véhicule", "car"),
    ("maison", "house"), ("appartement", "house"),
    ("ordinateur", "laptop"), ("mon pc", "laptop"),
    ("la clé", "key"), ("un avion", "plane"), ("le café", "cup"),
    ("mes lunettes", "glasses"), ("le diplôme", "graduation"),
    ("la facture", "document"), ("un immeuble", "building"),
    ("le colis", "box"), ("étiquette de prix", "tag"),
    ("camion de livraison", "truck"),
])
def test_everyday_words_have_their_own_cutout(word, expected):
    assert lexicon.resolve(word) == expected
    assert collage_shapes.resolve_strict(word) == expected


def test_every_cutout_has_a_canonical_noun_and_vice_versa():
    """Le lexique et la bibliothèque de découpes ne doivent jamais diverger."""
    assert set(lexicon.NOUNS) == set(collage_shapes.PICTOGRAMS)
    assert {pictogram for pictogram, _ in lexicon.LEXICON} <= set(
        collage_shapes.PICTOGRAMS)


def test_every_library_object_is_actually_drawable():
    """Sans ça, un moteur sans crédit dessine des formes au hasard.

    Les bibliothèques de métaphores nomment les objets en anglais générique
    (« rising bar », « padlock »): chacun doit se résoudre en une découpe.
    """
    libraries = (collage_profiles.EDITORIAL_LIBRARY, collage_profiles.UGC_LIBRARY)
    unresolved = [
        name
        for library in libraries
        for _, objects, _ in library.values()
        for name in objects
        if collage_shapes.resolve_strict(name) is None
    ]
    unresolved += [name
                   for default in (collage_profiles.EDITORIAL_DEFAULT,
                                   collage_profiles.UGC_DEFAULT)
                   for name in default[1]
                   if collage_shapes.resolve_strict(name) is None]
    assert unresolved == []


# --------------------------------------------------------------------------- #
# 2. Un mot inconnu n'invente plus une illustration
# --------------------------------------------------------------------------- #
#: Paires volontairement jumelles: ce sont des OPPOSÉS sémantiques, et le fait
#: qu'elles se ressemblent (même disque, marque différente) est ce qui les rend
#: lisibles l'une par rapport à l'autre.
_INTENTIONAL_TWINS = {frozenset({"check", "cross"})}


def test_no_two_cutouts_look_alike():
    """Deux idées différentes ne doivent jamais donner la même image.

    C'est la version généralisée du bug « flamme = goutte »: les deux
    dérivaient du même contour, si bien que « ça cartonne » et « hydratation »
    produisaient exactement la même pièce. Ce test compare le rendu réel de
    chaque découpe et refuse toute nouvelle paire indistinguable.
    """
    import numpy as np
    from PIL import Image

    rendered = {}
    for name in collage_shapes.pictogram_names():
        canvas = Image.new("RGBA", (72, 72), (0, 0, 0, 255))
        collage_shapes.draw_pictogram(name, canvas,
                                      (255, 255, 255, 255), (140, 140, 140, 255))
        rendered[name] = np.asarray(canvas.convert("L"), dtype=np.float32) / 255.0

    names = sorted(rendered)
    too_close = []
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            if frozenset({first, second}) in _INTENTIONAL_TWINS:
                continue
            distance = float(np.abs(rendered[first] - rendered[second]).mean())
            if distance < 0.05:
                too_close.append((round(distance, 4), first, second))
    assert too_close == [], f"découpes indistinguables: {too_close}"


def test_unknown_word_resolves_to_nothing_rather_than_to_anything():
    assert collage_shapes.resolve_strict("zorglub") is None
    assert lexicon.resolve("") is None


def test_the_legacy_resolver_still_always_returns_a_shape():
    """Contrat historique conservé pour les appelants directs."""
    fallback = collage_shapes.resolve_pictogram("zorglub")
    assert fallback in collage_shapes.PICTOGRAMS
    assert fallback == collage_shapes.resolve_pictogram("zorglub")   # stable


# --------------------------------------------------------------------------- #
# 3. La scène montre ce que la phrase NOMME
# --------------------------------------------------------------------------- #
def test_a_sentence_about_a_car_shows_a_car():
    """LE test du bug d'origine."""
    concept = _plan_one("ma voiture est tombée en panne le mois dernier")
    assert "car" in _pictograms(concept)


@pytest.mark.parametrize("text,expected", [
    ("j'ai enfin acheté ma maison cette année", "house"),
    ("je travaille toute la journée sur mon ordinateur", "laptop"),
    ("le colis est arrivé en deux jours", "box"),
    ("j'ai pris l'avion pour aller le chercher", "plane"),
    ("regarde le prix de ce flacon", "bottle"),
])
def test_the_named_thing_is_always_in_the_scene(text, expected):
    assert expected in _pictograms(_plan_one(text))


def test_the_subject_opens_the_scene():
    """L'objet nommé ouvre l'assemblage: c'est lui qu'on pose en premier."""
    concept = _plan_one("ma voiture me coûte trop cher en essence")
    assert collage_shapes.resolve_strict(concept.ordered_objects()[0].name) == "car"


def test_ugc_scenes_never_contain_an_undrawable_object():
    """Garantie de fond des moteurs UGC: tout objet retenu est dessinable."""
    phrases = [
        "ma voiture est tombée en panne le mois dernier",
        "des milliers d'avis clients recommandent ce produit",
        "la livraison arrive en 48h et le colis est nickel",
        "je te montre le résultat après une semaine d'utilisation",
        "franchement à ce prix-là c'est donné",
    ]
    for text in phrases:
        concept = _plan_one(text)
        assert len(concept.objects) >= ccfg.MIN_OBJECTS, text
        assert None not in _pictograms(concept), (text, concept.objects)


def test_a_scene_never_repeats_the_same_cutout():
    """Deux voitures n'illustrent rien de plus qu'une voiture."""
    concept = _plan_one("ma voiture, mon auto, mon véhicule, c'est ma vie")
    pictograms = _pictograms(concept)
    assert len(pictograms) == len(set(pictograms))


def test_grounding_can_be_switched_off(monkeypatch):
    """Le comportement historique reste atteignable par configuration."""
    monkeypatch.setenv("COLLAGE_GROUNDING", "0")
    ccfg.refresh()
    try:
        concept = _plan_one("ma voiture est tombée en panne")
        assert "car" not in _pictograms(concept)
    finally:
        monkeypatch.delenv("COLLAGE_GROUNDING", raising=False)
        ccfg.refresh()


# --------------------------------------------------------------------------- #
# 3bis. La composition: une scène qui se LIT en deux secondes
# --------------------------------------------------------------------------- #
def test_a_scene_never_becomes_a_sheet_of_stamps():
    """Au-delà de quatre pièces, l'œil n'a plus de point d'entrée."""
    concept = _plan_one("ma voiture, ma maison, mon ordinateur, mon téléphone, "
                        "mon café et mes lunettes")
    assert ccfg.MIN_OBJECTS <= len(concept.objects) <= ccfg.SCENE_OBJECTS_MAX


def test_the_subject_gets_the_biggest_cell():
    """Le sujet doit dominer: c'est lui qui porte le sens de la scène."""
    concept = _plan_one("ma voiture me coûte trop cher en essence")
    cells = concept.layout()
    assert cells[0][3] == max(cell[3] for cell in cells)


def test_the_rendered_subject_is_the_largest_piece():
    """La hiérarchie du gabarit doit survivre jusqu'au rendu."""
    from app.processing.collage.collage_video_service import LocalAssembleRenderer

    concept = _plan_one("ma voiture me coûte trop cher en essence")
    pieces = LocalAssembleRenderer(width=360, height=640, fps=12)._pictogram_pieces(concept)
    areas = [piece.layer.width * piece.layer.height for piece in pieces]
    assert areas[0] == max(areas)
    assert areas[0] > sorted(areas)[-2] * 1.3       # dominance VISIBLE


def test_two_consecutive_scenes_never_share_a_background():
    """Deux aplats identiques qui s'enchaînent effacent la coupe."""
    planner = CollageConceptPlanner(use_llm=False,
                                    profile=collage_profiles.UGC_PRODUCT, cache=None)
    concepts = planner.plan([
        _beat("des milliers d'avis clients recommandent ce produit", "a"),
        _beat("tout le monde le recommande autour de moi", "b"),
        _beat("les avis parlent d'eux-mêmes franchement", "c"),
    ])
    backgrounds = [c.background_color for c in concepts]
    assert all(a != b for a, b in zip(backgrounds, backgrounds[1:])), backgrounds


def test_filler_cutouts_do_not_repeat_from_one_scene_to_the_next():
    """Le remplissage tourne; seul le SUJET a le droit de revenir."""
    planner = CollageConceptPlanner(use_llm=False,
                                    profile=collage_profiles.UGC_PRODUCT, cache=None)
    concepts = planner.plan([
        _beat("des milliers d'avis clients recommandent ce produit", "a"),
        _beat("tout le monde le recommande autour de moi", "b"),
    ])
    first = [collage_shapes.resolve_strict(o.name) for o in concepts[0].ordered_objects()]
    second = [collage_shapes.resolve_strict(o.name) for o in concepts[1].ordered_objects()]
    # La pièce d'ouverture de la 2e scène ne rejoue pas celle de la 1re.
    assert second[0] != first[0]


# --------------------------------------------------------------------------- #
# 4. Les pièges du français parlé
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,forbidden,reason", [
    ("je te livre le colis demain", "book", "« livre » verbe n'est pas un livre"),
    ("je vais te montrer le résultat", "watch", "« montrer » n'est pas une montre"),
    ("c'est cher car je l'ai importé", "car", "« car » conjonction n'est pas une voiture"),
    ("son produit est incroyable", "music", "« son » possessif n'est pas du son"),
    ("le lien en bio pour commander", "chain", "« lien en bio » est un appel à l'achat"),
    ("au cours de la semaine dernière", "graduation", "« au cours de » n'est pas un cours"),
    ("je suis tout à fait d'accord avec toi", "handshake", "« d'accord » est un tic de langage"),
])
def test_french_traps_do_not_trigger_the_wrong_cutout(text, forbidden, reason):
    grounded = {entity.pictogram for entity in lexicon.ground(text)}
    assert forbidden not in grounded, reason


def test_delivery_wins_over_book_on_the_same_word():
    """« je te livre le colis » = un camion et un carton, pas un bouquin."""
    grounded = [entity.pictogram for entity in lexicon.ground("je te livre le colis")]
    assert grounded == ["truck", "box"]


# --------------------------------------------------------------------------- #
# 5. Le prompt image porte lui aussi le sujet littéral
# --------------------------------------------------------------------------- #
def test_the_image_prompt_names_the_literal_subject():
    """Le moteur éditorial génère une image: elle doit montrer la voiture."""
    concept = _plan_one("ma voiture est tombée en panne le mois dernier",
                        profile=collage_profiles.EDITORIAL)
    prompt = CollagePromptBuilder().build_image_prompt(concept)
    assert "car" in prompt
    assert "must be immediately recognisable" in prompt


def test_a_purely_abstract_sentence_keeps_its_metaphor():
    """Sans objet matériel nommé, la métaphore reste seule aux commandes."""
    concept = _plan_one("il faut oser, tout simplement",
                        profile=collage_profiles.EDITORIAL)
    prompt = CollagePromptBuilder().build_image_prompt(concept)
    assert "Visual metaphor to build:" in prompt


def test_the_planner_prompt_lists_the_drawable_vocabulary():
    """Un modèle qui ignore le vocabulaire propose des objets indessinables."""
    hint = lexicon.vocabulary_hint()
    assert "car" in hint and "house" in hint
    assert "{vocabulary}" in collage_profiles.UGC_PRODUCT.llm_instruction
