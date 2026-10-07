"""PRÉCISION du collage: les pièces amènent à l'écran ce que la personne DIT.

Demande produit: « il faut que ça soit précis — ce que la personne dit, les
papiers de collage l'amènent à l'écran; on ne parle pas de quelque chose et ils
amènent autre chose ».

Deux défauts corrigés ici et verrouillés par ces tests:

  1. un objet inconnu tombait sur une découpe TIRÉE AU SORT (empreinte du mot):
     on parlait de garantie, l'écran montrait une chaussure;
  2. les objets venaient d'une bibliothèque de métaphores indexée sur UNE
     intention dominante, jamais des mots réellement prononcés.
"""
from app.processing.collage import collage_shapes as cs
from app.processing.collage.collage_concept_planner import (
    CollageConceptPlanner,
    spoken_objects,
)


# --------------------------------------------------------------------------- #
# Résolution mot -> découpe
# --------------------------------------------------------------------------- #
def test_unknown_word_never_picks_a_random_shape():
    """Sans correspondance, la découpe est NEUTRE et le signalé comme tel."""
    pictogram, matched = cs.resolve_pictogram_ex("zzzqwerty")
    assert matched is False
    assert pictogram == cs.DEFAULT_PICTOGRAM
    # Deux mots inconnus différents ne doivent plus donner deux formes
    # arbitraires et sans rapport avec le propos.
    assert cs.resolve_pictogram("zzzqwerty") == cs.resolve_pictogram("xxxazerty")


def test_spoken_words_resolve_to_the_right_cutout():
    expected = {
        "colis": "box", "livraison": "truck", "camion": "truck",
        "prix": "tag", "tarif": "tag", "francs": "coins", "paiement": "coins",
        "garantie": "shield", "sécurité": "shield", "clients": "person",
        "avis": "star", "adorent": "heart", "recommandent": "thumb_up",
        "crème": "jar", "flacon": "bottle", "heures": "clock",
        "téléphone": "phone", "croissance": "arrow_up", "cadeau": "gift",
        "panier": "cart", "cadenas": "lock",
    }
    for word, pictogram in expected.items():
        assert cs.resolve_pictogram_ex(word) == (pictogram, True), word


def test_french_false_friends_are_rejected():
    """Le français décline par la FIN: un fragment interne est un faux ami.

    « franchement » ne parle pas d'argent (franc), « éviter » n'est pas rapide
    (vite), « important » n'est pas une porte (porte). Avant, chacun de ces mots
    posait une pièce sans rapport sur l'écran.
    """
    for word in ("franchement", "important", "visite", "photo", "causer",
                 "surface", "installation", "freelance", "démarche"):
        _, matched = cs.resolve_pictogram_ex(word)
        assert matched is False, word


def test_multi_word_object_names_still_resolve():
    """Le planner nomme ses objets en langage naturel: ça doit continuer."""
    assert cs.resolve_pictogram_ex("open hand")[0] == "hand"
    assert cs.resolve_pictogram_ex("coin stack")[0] == "coins"
    assert cs.resolve_pictogram_ex("pot de crème hydratante")[0] == "jar"
    assert cs.resolve_pictogram_ex("upward arrow")[0] == "arrow_up"


def test_every_rule_targets_an_existing_pictogram():
    for pictogram, _ in cs._KEYWORD_RULES:
        assert pictogram in cs.PICTOGRAMS, pictogram


# --------------------------------------------------------------------------- #
# Extraction des objets depuis le discours
# --------------------------------------------------------------------------- #
def test_spoken_objects_follow_the_order_of_speech():
    text = "Le colis part aujourd'hui, tu paies le prix affiché et tu reçois le camion demain."
    words = spoken_objects(text)
    assert words[0] == "colis"
    assert "prix" in words
    picto = [cs.resolve_pictogram(w) for w in words]
    assert "box" in picto and "tag" in picto and "truck" in picto


def test_spoken_objects_never_repeat_the_same_cutout():
    text = "Le prix, le tarif et la promo sont affichés."
    picto = [cs.resolve_pictogram(w) for w in spoken_objects(text)]
    assert len(picto) == len(set(picto))


def test_sentence_without_showable_word_yields_nothing():
    assert spoken_objects("Franchement je pense que finalement c'est mieux") == []


# --------------------------------------------------------------------------- #
# Planner heuristique (le chemin des moteurs UGC, sans aucune clé API)
# --------------------------------------------------------------------------- #
def _concepts(texts):
    beats = [{"id": f"b{i}", "source_start": i * 10.0, "source_end": i * 10.0 + 6.0,
              "text": t} for i, t in enumerate(texts)]
    return CollageConceptPlanner(use_llm=False).plan(beats)


def test_pieces_illustrate_what_the_speaker_says():
    concept = _concepts([
        "Le colis part le jour même, tu le reçois en 48 heures par le camion de livraison."
    ])[0]
    picto = {cs.resolve_pictogram(o.name) for o in concept.objects}
    assert {"box", "truck", "clock"} <= picto


def test_price_and_guarantee_are_shown_not_paraphrased():
    concept = _concepts([
        "Le prix est de 15 000 francs et la garantie te rembourse si tu n'es pas satisfait."
    ])[0]
    picto = {cs.resolve_pictogram(o.name) for o in concept.objects}
    assert {"tag", "coins", "shield"} <= picto


def test_generic_sentence_still_produces_a_readable_scene():
    """Aucun mot illustrable: la bibliothèque du profil reprend la main plutôt
    que de laisser un trou dans le montage."""
    concept = _concepts([
        "Franchement, je pensais que ce serait beaucoup plus compliqué que ça."
    ])[0]
    assert len(concept.objects) >= 2
    assert concept.metaphor


def test_unresolvable_library_objects_are_dropped_when_speech_provides_better():
    """La bibliothèque ne doit plus imposer une forme neutre alors qu'un mot
    prononcé savait devenir une vraie découpe."""
    concept = _concepts([
        "Mes clients laissent des avis 5 étoiles, ils adorent et ils recommandent."
    ])[0]
    resolved = [cs.resolve_pictogram_ex(o.name)[1] for o in concept.objects]
    assert all(resolved), [o.name for o in concept.objects]


def test_planner_stays_deterministic():
    text = "Le colis arrive en 48 heures avec la garantie."
    first = [o.name for o in _concepts([text])[0].objects]
    second = [o.name for o in _concepts([text])[0].objects]
    assert first == second
