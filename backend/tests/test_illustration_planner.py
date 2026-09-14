"""Planner: does the engine put pictures in the right places, and only there?"""
from __future__ import annotations

import pytest

from app.illustration_engine import config
from app.illustration_engine.analyzer import ConceptDetector, analyze_transcript
from app.illustration_engine.planner import (
    ScenePlanner, StoryboardPlanner, TimingPlanner, VisualTypeSelector,
)
from app.illustration_engine.schemas.visual import (
    COMPARISON, INFOGRAPHIC, P_COMPARISON, P_LIST, P_NUMBER, P_STEPS, PROCESS,
    R_CONNECTOR, R_ITEM, R_NUMBER, R_TITLE, STATISTICS, VISUAL_TYPES,
    VisualOpportunity, WHITEBOARD,
)
from tests.illustration_fixtures import DEMO_SCRIPT, build_vu


@pytest.fixture(scope="module")
def demo():
    vu = build_vu(DEMO_SCRIPT)
    opportunities = analyze_transcript(vu)
    concepts = ConceptDetector().fit([o.text for o in opportunities])
    return vu, opportunities, concepts


def _board(demo, **kwargs):
    vu, opportunities, concepts = demo
    planner = StoryboardPlanner(concepts=concepts, **kwargs)
    return planner.plan(opportunities, vu, vu["duration"])


# --------------------------------------------------------------------------- #
# selection rules
# --------------------------------------------------------------------------- #
def test_storyboard_keeps_the_talking_head_as_the_backbone(demo):
    for intensity in ("low", "medium", "high"):
        board = _board(demo, intensity=intensity)
        ceiling = config.intensity_profile(intensity)["max_coverage"]
        assert board.coverage <= ceiling + 1e-6, intensity


def test_intensity_controls_how_many_scenes_appear(demo):
    counts = [len(_board(demo, intensity=i)) for i in ("low", "medium", "high")]
    assert counts == sorted(counts)
    assert counts[0] >= 1


@pytest.mark.parametrize("intensity", ["low", "medium", "high"])
def test_scenes_never_touch_and_keep_a_gap_of_face(demo, intensity):
    """However dense the edit, the face always comes back in between."""
    board = _board(demo, intensity=intensity)
    min_gap = config.intensity_profile(intensity)["min_gap"]
    scenes = sorted(board.scenes, key=lambda s: s.start)
    for previous, current in zip(scenes, scenes[1:]):
        assert current.start - previous.end >= min_gap - 1e-6


def test_a_denser_intensity_allows_a_shorter_gap():
    gaps = [config.intensity_profile(i)["min_gap"]
            for i in ("low", "medium", "high")]
    assert gaps == sorted(gaps, reverse=True)
    assert min(gaps) >= 5.0, "the talking head must still come back"


def test_scene_durations_stay_inside_the_pacing_rules(demo):
    board = _board(demo, intensity="high")
    for scene in board.scenes:
        assert config.MIN_SCENE_DUR - 1e-6 <= scene.duration <= config.MAX_SCENE_DUR + 1e-6


def test_opening_seconds_are_never_taken_over(demo):
    board = _board(demo, intensity="high")
    assert all(s.start >= config.MIN_START - 1e-6 for s in board.scenes)


def test_greetings_are_not_illustrated(demo):
    board = _board(demo, intensity="high")
    for scene in board.scenes:
        assert "bienvenue" not in scene.spoken_text.lower()
        assert "abonnez-vous" not in scene.spoken_text.lower()


def test_every_scene_clears_the_acceptance_threshold(demo):
    for intensity in ("low", "medium", "high"):
        threshold = config.intensity_profile(intensity)["threshold"]
        board = _board(demo, intensity=intensity)
        assert all(s.visual_score >= threshold for s in board.scenes)


def test_empty_opportunities_produce_an_explained_empty_board():
    board = StoryboardPlanner().plan([], {"duration": 60.0}, 60.0)
    assert len(board) == 0
    assert board.notes


# --------------------------------------------------------------------------- #
# type selection and diversity
# --------------------------------------------------------------------------- #
def test_selector_never_repeats_a_type_back_to_back():
    selector = VisualTypeSelector("professional")
    opportunity = VisualOpportunity(0, 5, "x", P_LIST, 0.9, 0.8)
    chosen = []
    for _ in range(6):
        chosen.append(selector.select(opportunity, chosen, 6))
    assert all(a != b for a, b in zip(chosen, chosen[1:]))


def test_selector_honours_a_whiteboard_style():
    selector = VisualTypeSelector("whiteboard")
    opportunity = VisualOpportunity(0, 5, "x", P_STEPS, 0.9, 0.8)
    assert selector.select(opportunity, [], 1) == WHITEBOARD


def test_selector_takes_a_provider_suggestion_when_valid():
    selector = VisualTypeSelector("professional")
    opportunity = VisualOpportunity(0, 5, "x", P_LIST, 0.9, 0.8)
    setattr(opportunity, "suggested_type", COMPARISON)
    assert selector.select(opportunity, [], 1) == COMPARISON


def test_pattern_maps_to_a_sensible_default_type():
    selector = VisualTypeSelector("professional")
    assert selector.select(VisualOpportunity(0, 5, "", P_NUMBER, .9, .8), [], 1) == STATISTICS
    assert selector.select(VisualOpportunity(0, 5, "", P_STEPS, .9, .8), [], 1) == PROCESS
    assert selector.select(VisualOpportunity(0, 5, "", P_LIST, .9, .8), [], 1) == INFOGRAPHIC


# --------------------------------------------------------------------------- #
# scene composition
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("visual_type", VISUAL_TYPES)
def test_every_visual_type_produces_a_usable_scene(visual_type):
    """No layout may return an empty frame — that is a decorative animation."""
    opportunity = VisualOpportunity(
        10.0, 16.0, "le produit, le trafic et la livraison", P_LIST, 0.85, 0.7,
        concepts=["produit", "trafic", "livraison"],
        items=["Produit", "Trafic", "Livraison"],
        numbers=[("87%", 87.0)], sides=("Avant", "Après"))
    scene = ScenePlanner("professional", "16:9").plan(
        opportunity, visual_type, "s1", 10.0, 16.0, title="TEST", subtitle="SUB")
    assert scene.elements, visual_type
    assert scene.animation_sequence, visual_type
    assert any(e.text or e.icon for e in scene.elements), visual_type
    # Every element is animated, and every animation points at a real element.
    ids = {e.element_id for e in scene.elements}
    assert {i.element_id for i in scene.animation_sequence} <= ids


@pytest.mark.parametrize("aspect,expect_wide", [("16:9", True), ("9:16", False),
                                                ("1:1", False)])
def test_layout_stays_inside_the_canvas_in_every_aspect(aspect, expect_wide):
    opportunity = VisualOpportunity(
        0, 6, "le produit, le trafic et la livraison", P_LIST, 0.9, 0.8,
        items=["Produit", "Trafic", "Livraison"], concepts=["produit"])
    planner = ScenePlanner("professional", aspect)
    assert planner.wide is expect_wide
    scene = planner.plan(opportunity, INFOGRAPHIC, "s1", 0.0, 6.0, title="T")
    for element in scene.elements:
        box = element.box
        assert -0.001 <= box.x and box.x + box.w <= 1.001, element.element_id
        assert -0.001 <= box.y and box.y + box.h <= 1.001, element.element_id


def test_process_scene_links_its_steps_in_order():
    opportunity = VisualOpportunity(
        0, 6, "x", P_STEPS, 0.9, 0.8, items=["Produit", "Trafic", "Livraison"])
    scene = ScenePlanner("professional", "16:9").plan(
        opportunity, PROCESS, "s1", 0.0, 6.0, title="T")
    nodes = [e for e in scene.ordered_elements() if e.role == R_ITEM]
    links = [e for e in scene.ordered_elements() if e.role == R_CONNECTOR]
    assert [n.text for n in nodes] == ["Produit", "Trafic", "Livraison"]
    assert len(links) == len(nodes) - 1
    for link in links:
        assert scene.element(link.connects[0]) and scene.element(link.connects[1])


def test_statistics_scene_carries_the_figure():
    opportunity = VisualOpportunity(0, 5, "87% échouent", P_NUMBER, 0.9, 0.8,
                                    numbers=[("87%", 87.0)])
    scene = ScenePlanner("professional", "16:9").plan(
        opportunity, STATISTICS, "s1", 0.0, 5.0, title="T")
    figure = next(e for e in scene.elements if e.role == R_NUMBER)
    assert figure.text == "87%"
    assert figure.value == 87.0


def test_reveals_are_ordered_and_finish_before_the_scene_ends():
    opportunity = VisualOpportunity(
        0, 6, "x", P_STEPS, 0.9, 0.8, items=["Un", "Deux", "Trois"])
    scene = ScenePlanner("professional", "16:9").plan(
        opportunity, PROCESS, "s1", 0.0, 6.0, title="T")
    starts = [i.start for i in scene.animation_sequence]
    assert starts == sorted(starts)
    assert max(i.end for i in scene.animation_sequence) <= scene.duration + 0.5


# --------------------------------------------------------------------------- #
# timing
# --------------------------------------------------------------------------- #
def test_timing_snaps_to_word_boundaries(demo):
    vu, _opportunities, _concepts = demo
    planner = TimingPlanner(vu, vu["duration"])
    starts = set(planner.starts)
    span = planner.plan(20.37, 26.4, target_duration=5.0)
    assert span is not None
    assert any(abs(span[0] - s) < 0.01 for s in starts)


def test_timing_refuses_the_tail_of_the_video(demo):
    vu, _o, _c = demo
    planner = TimingPlanner(vu, vu["duration"])
    assert planner.plan(vu["duration"] - 0.5, vu["duration"]) is None


def test_timing_shifts_a_scene_out_of_the_opening(demo):
    vu, _o, _c = demo
    planner = TimingPlanner(vu, vu["duration"])
    span = planner.plan(0.2, 5.0)
    assert span is not None and span[0] >= config.MIN_START - 1e-6


def test_element_windows_span_the_draw_budget():
    planner = TimingPlanner({}, 0.0)
    windows = planner.element_windows(0.0, 10.0, [1.0, 1.0, 2.0], draw_budget=0.75)
    assert len(windows) == 3
    assert windows[0][0] == 0.0
    assert windows[-1][1] == pytest.approx(7.5, abs=0.01)
    assert windows[2][1] - windows[2][0] > windows[0][1] - windows[0][0]
