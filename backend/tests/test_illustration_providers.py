"""Providers: the engine must degrade gracefully, never hard-fail."""
from __future__ import annotations

import pytest

from app.illustration_engine import config
from app.illustration_engine.analyzer import SemanticAnalyzer
from app.illustration_engine.providers import (
    ChatSemanticProvider, CloudProvider, FreeLLMAPIProvider,
    LocalSemanticProvider, provider_chain, resolve_provider,
)
from app.illustration_engine.providers.base import Refinement, SemanticProvider
from app.illustration_engine.schemas.visual import COMPARISON, P_LIST


@pytest.fixture(scope="module")
def units():
    analyzer = SemanticAnalyzer()
    return [
        analyzer.analyze_text("Il y a trois choses : le produit, le trafic et "
                              "la livraison.", 10.0, 16.0),
        analyzer.analyze_text("87% des boutiques échouent.", 20.0, 25.0),
    ]


# --------------------------------------------------------------------------- #
# chain and fallbacks
# --------------------------------------------------------------------------- #
def test_offline_chain_never_reaches_the_network():
    chain = provider_chain("offline")
    assert [p.name for p in chain] == ["local"]
    assert not any(p.network for p in chain)


def test_free_chain_falls_back_to_local():
    assert [p.name for p in provider_chain("free")] == ["freellmapi", "local"]


def test_cloud_chain_falls_back_through_free_to_local():
    assert [p.name for p in provider_chain("cloud")] == [
        "cloud", "freellmapi", "local"]


def test_unknown_mode_is_treated_as_offline():
    assert [p.name for p in provider_chain("banana")] == ["local"]


def test_offline_resolution_keeps_the_heuristics(units):
    refinements, provider = resolve_provider(units, "offline")
    assert refinements == []
    assert provider == "heuristic"


def test_free_mode_is_inert_until_it_is_configured(units):
    """MIT code upstream is not a licence to use the services behind it."""
    provider = FreeLLMAPIProvider(base_url="", model="")
    assert not provider.available()
    refinements, name = resolve_provider(units, "free")
    assert refinements == [] and name == "heuristic"


def test_cloud_provider_needs_url_model_and_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert not CloudProvider(base_url="https://x/v1", model="m").available()
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert CloudProvider(base_url="https://x/v1", model="m",
                         api_key_env="OPENROUTER_API_KEY").available()


def test_a_provider_that_raises_is_swallowed(units):
    class Exploding(SemanticProvider):
        name = "exploding"
        network = True

        def available(self):
            return True

        def _refine(self, units):
            raise RuntimeError("upstream is down")

    assert Exploding().refine(units) == []


def test_a_provider_that_returns_nothing_falls_through(units, monkeypatch):
    class Silent(FreeLLMAPIProvider):
        def available(self):
            return True

        def _refine(self, units):
            return []

    monkeypatch.setattr(
        "app.illustration_engine.providers.FreeLLMAPIProvider", Silent)
    refinements, name = resolve_provider(units, "free")
    assert refinements == [] and name == "heuristic"


# --------------------------------------------------------------------------- #
# validation of model output
# --------------------------------------------------------------------------- #
def test_refinements_pointing_outside_the_transcript_are_dropped():
    validated = SemanticProvider._validate(
        [{"index": 0, "pattern": "list"},
         {"index": 99, "pattern": "list"},
         {"index": -1, "pattern": "list"}], n_units=2)
    assert [r.index for r in validated] == [0]


def test_invalid_patterns_and_types_are_discarded_not_trusted():
    validated = SemanticProvider._validate(
        [{"index": 0, "pattern": "telepathy", "visual_type": "hologram",
          "visual_score": 5.0}], n_units=1)
    assert validated[0].pattern == ""
    assert validated[0].visual_type == ""
    assert validated[0].visual_score == 1.0      # clamped, not rejected


def test_duplicate_indices_keep_only_the_first():
    validated = SemanticProvider._validate(
        [{"index": 0, "title": "A"}, {"index": 0, "title": "B"}], n_units=1)
    assert len(validated) == 1 and validated[0].title == "A"


def test_garbage_entries_do_not_crash_validation():
    assert SemanticProvider._validate(["nonsense", None, 42, {}], n_units=3) == []


# --------------------------------------------------------------------------- #
# reply parsing
# --------------------------------------------------------------------------- #
def test_parses_a_bare_json_array():
    assert ChatSemanticProvider.parse('[{"index": 0}]') == [{"index": 0}]


def test_parses_a_fenced_json_array():
    assert ChatSemanticProvider.parse(
        '```json\n[{"index": 1}]\n```') == [{"index": 1}]


def test_parses_json_buried_in_prose():
    assert ChatSemanticProvider.parse(
        'Voici le plan :\n[{"index": 2}]\nBonne journée.') == [{"index": 2}]


def test_parses_an_object_wrapper():
    assert ChatSemanticProvider.parse('{"scenes": [{"index": 0}]}') == [{"index": 0}]


def test_unparseable_replies_yield_nothing():
    assert ChatSemanticProvider.parse("désolé, je ne peux pas") == []
    assert ChatSemanticProvider.parse("") == []


# --------------------------------------------------------------------------- #
# how refinements reach the plan
# --------------------------------------------------------------------------- #
def test_a_refinement_only_overwrites_the_fields_it_filled():
    from app.illustration_engine.director import IllustrationDirector
    from app.illustration_engine.schemas.visual import VisualOpportunity

    opportunity = VisualOpportunity(
        0, 5, "texte", P_LIST, 0.5, 0.4, items=["Un", "Deux"])
    IllustrationDirector._apply_refinements(
        [opportunity], [Refinement(index=0, visual_score=0.95,
                                   visual_type=COMPARISON)])
    assert opportunity.visual_score == 0.95
    assert opportunity.pattern == P_LIST            # untouched
    assert opportunity.items == ["Un", "Deux"]      # untouched
    assert getattr(opportunity, "suggested_type") == COMPARISON
