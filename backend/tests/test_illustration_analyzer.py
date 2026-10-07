"""Analyzer: does the engine understand what the speaker is doing?"""
from __future__ import annotations

import pytest

from app.illustration_engine.analyzer import (
    ConceptDetector, ImportanceDetector, SemanticAnalyzer,
    VisualOpportunityDetector, analyze_transcript, band,
    BAND_NONE, BAND_STRONG,
)
from app.illustration_engine.analyzer.semantic_analyzer import (
    extract_list_items, extract_sides, extract_steps,
)
from app.illustration_engine.schemas.visual import (
    P_ARCHITECTURE, P_COMPARISON, P_DEFINITION, P_KEYWORD, P_LIST, P_NUMBER,
    P_PROBLEM, P_STEPS,
)
from tests.illustration_fixtures import DEMO_SCRIPT, build_vu


@pytest.fixture(scope="module")
def analyzer():
    return SemanticAnalyzer()


# --------------------------------------------------------------------------- #
# pattern detection
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    ("Pour réussir en e-commerce, vous devez maîtriser trois choses : "
     "le produit, le trafic et la livraison.", P_LIST),
    ("Premièrement vous trouvez un bon produit, ensuite vous attirez du "
     "trafic, enfin vous assurez la livraison.", P_STEPS),
    ("Avant, les vendeurs perdaient des heures ; maintenant, le mobile money "
     "règle le paiement en dix secondes.", P_COMPARISON),
    ("87% des boutiques en ligne échouent la première année.", P_NUMBER),
    ("Le problème, c'est que personne ne suit ses marges. La solution est un "
     "tableau de bord hebdomadaire.", P_PROBLEM),
    ("L'intelligence artificielle est un système qui apprend à partir de "
     "données.", P_DEFINITION),
    ("Le client envoie sa commande, le serveur traite le paiement, puis "
     "l'entrepôt expédie le colis.", P_ARCHITECTURE),
    ("Salut à tous, bienvenue, abonnez-vous à la chaîne.", P_KEYWORD),
])
def test_detects_discourse_pattern(analyzer, text, expected):
    assert analyzer.analyze_text(text, 10.0, 17.0).pattern == expected


def test_english_patterns_are_detected(analyzer):
    unit = analyzer.analyze_text(
        "First you find a good product, then you drive traffic, "
        "finally you handle shipping.", 5.0, 12.0)
    assert unit.pattern == P_STEPS
    assert len(unit.items) >= 2


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #
def test_list_items_are_extracted_as_labels():
    items = extract_list_items(
        "vous devez maîtriser trois choses : le produit, le trafic et la "
        "livraison.", expected=3)
    assert items == ["Produit", "Trafic", "Livraison"]


def test_steps_drop_the_verb_scaffolding():
    steps = extract_steps(
        "Premièrement vous trouvez un bon produit, ensuite vous attirez du "
        "trafic, enfin vous assurez la livraison.")
    assert steps == ["Bon Produit", "Trafic", "Livraison"]


def test_step_label_stops_at_its_own_sentence():
    steps = extract_steps(
        "D'abord le produit, ensuite le trafic, enfin la livraison. "
        "C'est vraiment la base de tout le système.")
    assert all("base" not in step.lower() for step in steps)


def test_comparison_sides_are_both_filled():
    left, right = extract_sides(
        "Avant, les vendeurs perdaient des heures ; maintenant, le mobile "
        "money règle le paiement.")
    assert left and right and left != right


def test_numbers_need_a_unit_or_real_magnitude(analyzer):
    unit = analyzer.analyze_text("Il faut 3 étapes pour y arriver.", 0.0, 4.0)
    assert unit.pattern != P_NUMBER      # "3 étapes" is a list, not a statistic
    stat = analyzer.analyze_text("Le chiffre d'affaires a bondi de 240%.", 0.0, 4.0)
    assert stat.numbers and stat.numbers[0][1] == 240.0


# --------------------------------------------------------------------------- #
# concepts
# --------------------------------------------------------------------------- #
def test_concepts_read_in_the_order_the_speaker_used():
    detector = ConceptDetector().fit(["le produit, le trafic et la livraison"])
    concepts = detector.concepts("le produit, le trafic et la livraison", limit=3)
    assert concepts.index("produit") < concepts.index("trafic") < concepts.index("livraison")


def test_headline_never_cuts_mid_word():
    detector = ConceptDetector()
    headline = detector.headline(
        "le produit, le trafic, la livraison et la rentabilité globale", 4)
    assert not headline.endswith("-")
    for word in headline.split():
        assert len(word) > 2


def test_structural_markers_are_not_concepts():
    detector = ConceptDetector()
    headline = detector.headline(
        "premièrement le produit, ensuite le trafic, enfin la livraison", 4)
    assert "PREMIEREMENT" not in headline and "ENSUITE" not in headline


def test_domain_detection_covers_african_commerce():
    detector = ConceptDetector()
    domains = detector.domains("le client paie par mobile money puis reçoit "
                               "son colis par livraison")
    assert "mobile_money" in domains
    assert "delivery" in domains


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def test_greeting_scores_below_the_animation_floor(analyzer):
    detector = VisualOpportunityDetector(120.0, ConceptDetector())
    unit = analyzer.analyze_text(
        "Salut à tous, bienvenue dans cette vidéo, abonnez-vous.", 2.0, 8.0)
    assert band(detector.score(unit)) == BAND_NONE


def test_structured_list_is_strongly_recommended(analyzer):
    detector = VisualOpportunityDetector(120.0, ConceptDetector())
    unit = analyzer.analyze_text(
        "Pour réussir en e-commerce, vous devez maîtriser trois choses : "
        "le produit, le trafic et la livraison.", 20.0, 27.0)
    assert band(detector.score(unit)) == BAND_STRONG


def test_a_list_with_nothing_extractable_scores_lower(analyzer):
    """Material matters: an empty scene is the decorative animation we refuse."""
    detector = VisualOpportunityDetector(120.0, ConceptDetector())
    rich = analyzer.analyze_text(
        "Il y a trois piliers : le produit, le trafic, la livraison.", 10.0, 17.0)
    bare = analyzer.analyze_text(
        "Il y a trois piliers et c'est comme ça.", 10.0, 17.0)
    assert detector.score(rich) > detector.score(bare)


def test_importance_is_not_visual_score(analyzer):
    """A passage can matter rhetorically and still have nothing to draw."""
    unit = analyzer.analyze_text(
        "C'est vraiment très important, croyez-moi, retenez bien ça.", 30.0, 36.0)
    importance = ImportanceDetector(120.0).score(unit)
    visual = VisualOpportunityDetector(120.0, ConceptDetector()).score(unit)
    assert importance > visual


# --------------------------------------------------------------------------- #
# whole transcript
# --------------------------------------------------------------------------- #
def test_analyze_transcript_covers_the_whole_video():
    opportunities = analyze_transcript(build_vu(DEMO_SCRIPT))
    assert opportunities
    patterns = {o.pattern for o in opportunities}
    assert {P_LIST, P_STEPS, P_COMPARISON, P_NUMBER} <= patterns
    assert all(o.end > o.start for o in opportunities)
    starts = [o.start for o in opportunities]
    assert starts == sorted(starts)


def test_empty_transcript_yields_nothing():
    assert analyze_transcript({}) == []
    assert analyze_transcript({"segments": []}) == []
