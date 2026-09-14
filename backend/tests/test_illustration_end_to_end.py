"""End-to-end: the mission's acceptance scenario, plus the six content types.

These run the full director (analysis -> storyboard -> scene design -> SFX)
without touching ffmpeg, so they assert the engine's *decisions*. Clip encoding
is covered separately and skipped when ffmpeg is absent.
"""
from __future__ import annotations

import os

import pytest

from app.illustration_engine import IllustrationDirector, config
from app.illustration_engine.bridge import is_active, plan_only, run, spans
from app.illustration_engine.schemas.visual import (
    COMPARISON, CONCEPT, DIAGRAM, FLOWCHART, INFOGRAPHIC, KINETIC_TYPOGRAPHY,
    MOTION_GRAPHICS, PROCESS, STATISTICS, TIMELINE, WHITEBOARD)
from tests.illustration_fixtures import (
    DEMO_SCRIPT, MISSION_SCRIPT, build_vu, has_ffmpeg)


# --------------------------------------------------------------------------- #
# the mission's acceptance scenario
# --------------------------------------------------------------------------- #
def test_mission_scenario_produces_the_three_pillars():
    """"trois choses : le produit, le trafic et la livraison" must become a
    scene naming Produit, Trafic and Livraison, drawn or animated."""
    vu = build_vu(MISSION_SCRIPT)
    board = IllustrationDirector(style="professional", intensity="high",
                                 aspect="16:9").storyboard(vu)
    assert len(board) >= 1

    scene = next(s for s in board.scenes if "produit" in s.spoken_text.lower())
    # 5. whiteboard or motion graphics (or any of their explanatory cousins)
    assert scene.visual_type in (WHITEBOARD, INFOGRAPHIC, PROCESS,
                                 MOTION_GRAPHICS, FLOWCHART, TIMELINE)
    # 6-8. the three items exist as their own elements
    labels = " ".join(e.text for e in scene.elements).lower()
    for pillar in ("produit", "trafic", "livraison"):
        assert pillar in labels, pillar
    # 9. they are animated, in order
    assert len(scene.animation_sequence) >= 3
    starts = [i.start for i in scene.animation_sequence]
    assert starts == sorted(starts)
    # 10. SFX are attached
    assert scene.sfx
    # 11. it is synchronised with the passage that is actually being spoken
    assert scene.start >= config.MIN_START
    assert scene.duration >= config.MIN_SCENE_DUR


def test_mission_scenario_leaves_the_greeting_alone():
    board = IllustrationDirector(intensity="high").storyboard(
        build_vu(MISSION_SCRIPT))
    assert all("bienvenue" not in s.spoken_text.lower() for s in board.scenes)


# --------------------------------------------------------------------------- #
# visual tests A-F: one per content type
# --------------------------------------------------------------------------- #
LEAD = ["Bonjour à tous, on démarre tout de suite avec le sujet du jour."]

CASES = {
    "A_education": (
        LEAD + ["Pour apprendre efficacement, il faut trois habitudes : "
                "la répétition, la pratique et le repos.",
                "Chacune de ces habitudes se travaille séparément."],
        {INFOGRAPHIC, WHITEBOARD, PROCESS, MOTION_GRAPHICS, FLOWCHART, TIMELINE}),
    "B_business": (
        LEAD + ["Premièrement vous validez le marché, ensuite vous construisez "
                "l'offre, enfin vous recrutez l'équipe.",
                "C'est la séquence que suivent toutes les entreprises solides."],
        {PROCESS, WHITEBOARD, FLOWCHART, TIMELINE, INFOGRAPHIC, MOTION_GRAPHICS}),
    "C_ai": (
        LEAD + ["L'intelligence artificielle est un système qui apprend à "
                "partir de données pour prédire un résultat.",
                "Voilà la définition la plus simple que je peux vous donner."],
        {CONCEPT, KINETIC_TYPOGRAPHY, MOTION_GRAPHICS, WHITEBOARD,
         INFOGRAPHIC, DIAGRAM, PROCESS, FLOWCHART, TIMELINE}),
    "D_statistics": (
        LEAD + ["En réalité, 87% des boutiques en ligne ferment dès la "
                "première année d'activité.",
                "Ce chiffre explique presque tout le reste."],
        {STATISTICS, INFOGRAPHIC, MOTION_GRAPHICS}),
    "E_process": (
        LEAD + ["Le client envoie sa commande, le serveur traite le paiement, "
                "puis l'entrepôt expédie le colis au domicile.",
                "Chaque étape peut casser si elle est mal reliée."],
        {DIAGRAM, FLOWCHART, PROCESS, MOTION_GRAPHICS, INFOGRAPHIC, TIMELINE}),
    "F_comparison": (
        LEAD + ["Avant, les vendeurs perdaient des heures à encaisser ; "
                "maintenant, le mobile money règle le paiement en dix secondes.",
                "La différence de productivité est énorme."],
        {COMPARISON, MOTION_GRAPHICS, INFOGRAPHIC, WHITEBOARD}),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_each_content_type_gets_an_explanatory_scene(case):
    script, allowed = CASES[case]
    board = IllustrationDirector(intensity="high", aspect="16:9").storyboard(
        build_vu(script))
    assert len(board) >= 1, f"{case}: nothing was illustrated"
    scene = board.scenes[0]
    assert scene.visual_type in allowed, f"{case}: got {scene.visual_type}"
    # The scene must carry content, not decoration.
    assert any(e.text for e in scene.elements), case
    assert scene.animation_sequence, case
    assert scene.title, case


# --------------------------------------------------------------------------- #
# the whole director
# --------------------------------------------------------------------------- #
def test_director_is_deterministic():
    vu = build_vu(DEMO_SCRIPT)
    first = IllustrationDirector(intensity="high").storyboard(vu)
    second = IllustrationDirector(intensity="high").storyboard(vu)
    assert [s.to_dict() for s in first.scenes] == [s.to_dict() for s in second.scenes]


def test_director_works_with_no_api_key_at_all(monkeypatch):
    for key in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "GEMINI_API_KEY", "FREELLM_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    board = IllustrationDirector(ai_mode="offline", intensity="high").storyboard(
        build_vu(DEMO_SCRIPT))
    assert len(board) >= 1
    assert board.provider == "heuristic"


def test_director_refuses_to_illustrate_an_empty_transcript():
    board = IllustrationDirector().storyboard({"duration": 0.0, "segments": []})
    assert len(board) == 0
    assert board.notes


def test_director_reports_what_it_did(tmp_path):
    result = IllustrationDirector(intensity="high", preview=True).run(
        build_vu(DEMO_SCRIPT), str(tmp_path), write_json=False)
    report = result.report
    assert report["enabled"] is True
    assert report["ai_mode"] == "offline"
    assert report["scenes_planned"] >= 1
    assert report["plan"]
    assert "coverage" in report and report["coverage"] <= 0.30


def test_preview_mode_shrinks_the_canvas():
    full = IllustrationDirector(preview=False, aspect="16:9")
    preview = IllustrationDirector(preview=True, aspect="16:9")
    assert preview.width < full.width and preview.height < full.height
    assert preview.fps <= full.fps


# --------------------------------------------------------------------------- #
# pipeline bridge (the legacy contract)
# --------------------------------------------------------------------------- #
def test_bridge_is_active_by_default():
    assert is_active(do_motion=True)
    assert not is_active(do_motion=False)


def test_bridge_can_be_switched_off_by_env(monkeypatch):
    from app.illustration_engine import bridge
    monkeypatch.setattr(bridge.config, "ENABLED", False)
    assert not bridge.is_active(do_motion=True)


def test_bridge_picks_the_aspect_from_the_montage_canvas():
    from app.illustration_engine.bridge import aspect_for
    assert aspect_for(1920, 1080) == "16:9"
    assert aspect_for(1080, 1920) == "9:16"
    assert aspect_for(1080, 1080) == "1:1"


def test_bridge_spans_match_the_legacy_helper():
    clips = [{"source_start": 10.0, "duration": 5.0},
             {"source_start": 30.0, "duration": 4.0},
             {"source_start": "bad", "duration": 1.0}]
    assert spans(clips) == [(10.0, 15.0), (30.0, 34.0)]


def test_plan_only_never_renders_anything(tmp_path):
    plan = plan_only(build_vu(DEMO_SCRIPT), intensity="high")
    assert plan["plan"]
    assert plan["provider"] == "heuristic"
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(not has_ffmpeg(), reason="ffmpeg not available")
def test_bridge_emits_the_legacy_clip_records(tmp_path):
    clips, report = run(build_vu(DEMO_SCRIPT), str(tmp_path),
                        intensity="high", width=640, height=360, fps=12,
                        preview=True)
    assert clips, report
    for clip in clips:
        for key in ("id", "source_start", "duration", "mov", "events"):
            assert key in clip, key
        assert os.path.exists(clip["mov"])
    assert report["engine"] == "illustration_engine"
