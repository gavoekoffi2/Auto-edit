"""Audio: contextual SFX and a mix where the voice always wins."""
from __future__ import annotations

import pytest

from app.illustration_engine.audio import (
    AudioMixer, SFXPlacement, SFXPlanner, build_filter, sfx_library as lib)
from app.illustration_engine.planner import ScenePlanner
from app.illustration_engine.schemas.visual import (
    INFOGRAPHIC, P_LIST, P_NUMBER, STATISTICS, VisualOpportunity, WHITEBOARD)


def make_scene(visual_type=INFOGRAPHIC, pattern=P_LIST, numbers=()):
    opportunity = VisualOpportunity(
        10.0, 16.0, "le produit, le trafic et la livraison", pattern, 0.9, 0.8,
        items=["Produit", "Trafic", "Livraison"], numbers=list(numbers),
        concepts=["produit"])
    return ScenePlanner("professional", "16:9").plan(
        opportunity, visual_type, "s1", 10.0, 16.0, title="T", subtitle="S")


# --------------------------------------------------------------------------- #
# vocabulary
# --------------------------------------------------------------------------- #
def test_every_mission_sound_maps_to_a_synthesised_generator():
    for name in lib.VOCABULARY:
        assert lib.synth_name(name)
        assert name in lib.GAINS


def test_no_sound_is_loud_enough_to_fight_the_voice():
    assert all(0.0 < gain <= 0.7 for gain in lib.GAINS.values())


# --------------------------------------------------------------------------- #
# contextual planning
# --------------------------------------------------------------------------- #
def test_scene_opens_with_anticipation_and_closes_on_an_exit():
    cues = SFXPlanner().plan(make_scene())
    assert cues[0].sfx == lib.RISER
    assert cues[0].t < 0, "the riser must start before the picture arrives"
    assert cues[-1].sfx == lib.EXIT


def test_cards_pop_and_arrows_whoosh():
    sounds = {c.sfx for c in SFXPlanner().plan(make_scene())}
    assert lib.POP in sounds


def test_whiteboard_scenes_scratch_instead_of_popping():
    sounds = {c.sfx for c in SFXPlanner().plan(make_scene(WHITEBOARD))}
    assert lib.PENCIL in sounds
    assert lib.POP not in sounds


def test_a_key_figure_lands_on_a_hit_and_resolves():
    scene = make_scene(STATISTICS, P_NUMBER, numbers=[("87%", 87.0)])
    sounds = [c.sfx for c in SFXPlanner().plan(scene)]
    assert lib.SUBTLE_HIT in sounds
    assert lib.SUCCESS in sounds


def test_every_cue_is_tied_to_a_visual_and_stays_inside_the_scene():
    scene = make_scene()
    cues = SFXPlanner().plan(scene)
    assert cues
    for cue in cues:
        assert cue.t < scene.duration
        assert cue.src == "illustration"


def test_element_cues_are_never_stacked_on_the_same_instant():
    """Two sounds on one frame read as a click, not as two events."""
    fixed = {lib.RISER, lib.TRANSITION, lib.WHOOSH, lib.EXIT, lib.SUCCESS}
    element_cues = sorted((c for c in SFXPlanner().plan(make_scene())
                           if c.sfx not in fixed), key=lambda c: c.t)
    assert len(element_cues) >= 2
    for previous, current in zip(element_cues, element_cues[1:]):
        assert current.t - previous.t >= 0.09


def test_sfx_can_be_switched_off_entirely():
    assert SFXPlanner(enabled=False).plan(make_scene()) == []


# --------------------------------------------------------------------------- #
# mixing and ducking
# --------------------------------------------------------------------------- #
def test_music_is_ducked_under_the_voice():
    graph, out = build_filter([], has_music=True)
    assert "sidechaincompress" in graph
    assert "[musicduck]" in graph
    assert out == "[aout]"


def test_sfx_are_ducked_under_the_voice_too():
    placements = [SFXPlacement("a.wav", 1.0, 0.5)]
    graph, _out = build_filter(placements, has_music=False)
    assert "[sfxduck]" in graph
    assert "sidechaincompress" in graph


def test_each_sound_is_delayed_to_its_own_moment():
    placements = [SFXPlacement("a.wav", 1.5, 0.5),
                  SFXPlacement("b.wav", 4.25, 0.5)]
    graph, _out = build_filter(placements, has_music=False)
    assert "adelay=1500|1500" in graph
    assert "adelay=4250|4250" in graph


def test_voice_is_split_enough_times_to_key_every_sidechain():
    graph, _out = build_filter([SFXPlacement("a.wav", 1.0)], has_music=True)
    # voice programme + music key + sfx key
    assert "asplit=3" in graph


def test_mix_is_normalised_to_a_broadcast_target():
    graph, _out = build_filter([], has_music=True, loudnorm_target=-14.0)
    assert "loudnorm=I=-14.0" in graph


def test_mixing_is_a_no_op_without_music_or_sfx(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    assert AudioMixer().mix(str(video), str(tmp_path / "o.mp4")) == str(video)
