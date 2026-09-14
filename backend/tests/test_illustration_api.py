"""Charges utiles de l'API d'illustration.

La logique vit dans `illustration_engine.bridge` et non dans le routeur, donc
elle se teste sans base de données ni chaîne d'authentification — même
séparation que `api/v1/modes.py` pour le catalogue de modes.
"""
from __future__ import annotations

import pytest

from app.illustration_engine import config
from app.illustration_engine.bridge import (
    analyze_passage, capabilities, plan_only)
from app.illustration_engine.schemas.visual import VISUAL_TYPES
from app.illustration_engine.styles import STYLES
from tests.illustration_fixtures import DEMO_SCRIPT, build_vu


# --------------------------------------------------------------------------- #
# GET /illustrations/capabilities
# --------------------------------------------------------------------------- #
def test_capabilities_describes_this_deployment():
    caps = capabilities()
    assert caps["enabled"] is True
    assert set(caps["styles"]) == set(STYLES)
    assert set(caps["visual_types"]) == set(VISUAL_TYPES)
    assert caps["intensities"] == ["high", "low", "medium"]
    assert caps["ai_modes"] == ["offline", "free", "cloud"]
    assert set(caps["aspects"]) == {"16:9", "9:16", "1:1"}


def test_capabilities_is_honest_about_the_optional_engine():
    """The UI must not promise hand-drawing on a host that lacks the package."""
    from app.illustration_engine.renderers import animator_available
    assert capabilities()["whiteboard_animator"] is animator_available()


def test_capabilities_publishes_the_score_bands():
    bands = capabilities()["score_bands"]
    assert bands["none"] == [0.0, config.SCORE_NONE]
    assert bands["strongly_recommended"] == [config.SCORE_RECOMMENDED, 1.0]
    # The bands tile [0, 1] without gaps or overlaps.
    edges = [bands[k] for k in ("none", "optional", "recommended",
                                "strongly_recommended")]
    for lower, upper in zip(edges, edges[1:]):
        assert lower[1] == upper[0]


# --------------------------------------------------------------------------- #
# POST /illustrations/analyze
# --------------------------------------------------------------------------- #
def test_analyze_explains_a_structured_passage():
    result = analyze_passage(
        "Pour réussir en e-commerce, vous devez maîtriser trois choses : "
        "le produit, le trafic et la livraison.")
    assert result["pattern"] == "list"
    assert result["items"] == ["Produit", "Trafic", "Livraison"]
    assert result["band"] == "strongly_recommended"
    assert result["suggested_title"]
    assert result["reason"]


def test_analyze_declines_a_greeting():
    result = analyze_passage("Salut à tous, bienvenue, abonnez-vous !")
    assert result["pattern"] == "keyword"
    assert result["band"] == "none"


def test_analyze_surfaces_the_domains_it_recognised():
    result = analyze_passage("Le client paie par mobile money et reçoit son colis.")
    assert "mobile_money" in result["domains"]
    assert "delivery" in result["domains"]


def test_analyze_is_json_serialisable():
    import json
    json.dumps(analyze_passage("87% des boutiques échouent la première année."))


def test_analyze_survives_an_empty_passage():
    result = analyze_passage("")
    assert result["pattern"] == "keyword"
    assert result["visual_score"] >= 0.0


# --------------------------------------------------------------------------- #
# POST /illustrations/storyboard
# --------------------------------------------------------------------------- #
def test_storyboard_preview_returns_a_plan_without_rendering(tmp_path):
    plan = plan_only(build_vu(DEMO_SCRIPT), intensity="high")
    assert plan["plan"], "the preview must list what would be illustrated"
    assert plan["provider"] == "heuristic"
    assert 0.0 <= plan["coverage"] <= 0.30
    assert plan["storyboard"]["scenes"]
    # Nothing was written anywhere.
    assert not list(tmp_path.iterdir())


def test_storyboard_preview_honours_style_and_intensity():
    low = plan_only(build_vu(DEMO_SCRIPT), intensity="low")
    high = plan_only(build_vu(DEMO_SCRIPT), intensity="high")
    assert len(high["plan"]) >= len(low["plan"])
    whiteboard = plan_only(build_vu(DEMO_SCRIPT), style="whiteboard",
                           intensity="high")
    assert whiteboard["style"] == "whiteboard"


def test_storyboard_preview_entries_carry_what_the_ui_shows():
    plan = plan_only(build_vu(DEMO_SCRIPT), intensity="high")
    for entry in plan["plan"]:
        assert set(entry) >= {"scene_id", "at", "start", "duration",
                              "visual_type", "concept", "visual_score"}
        assert ":" in entry["at"]
        assert entry["duration"] > 0


def test_storyboard_preview_explains_an_empty_result():
    plan = plan_only({"duration": 0.0, "segments": []})
    assert plan["plan"] == []
    assert plan["notes"], "an empty plan must say why"


def test_storyboard_preview_is_json_serialisable():
    import json
    json.dumps(plan_only(build_vu(DEMO_SCRIPT), intensity="medium"))
