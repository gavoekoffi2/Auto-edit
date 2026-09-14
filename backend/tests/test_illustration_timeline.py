"""Timeline: are the pictures still on the words after the montage cut?"""
from __future__ import annotations

import json
import os

import pytest

from app.illustration_engine.planner import ScenePlanner
from app.illustration_engine.schemas.render_job import (
    IllustrationTimeline, RenderedIllustration, TimelineItem)
from app.illustration_engine.schemas.storyboard import Storyboard
from app.illustration_engine.schemas.visual import (
    INFOGRAPHIC, P_LIST, VisualOpportunity)
from app.illustration_engine.timeline import (
    build_batch_filter, build_timeline, narration_weights, output_duration,
    place_scene, resolve_overlaps, source_to_output, to_output_overlays,
    write_manifest,
)

RANGES = [{"start": 0.0, "end": 10.0},
          {"start": 15.0, "end": 25.0},
          {"start": 30.0, "end": 40.0}]


def make_scene(scene_id="s1", start=16.0, end=21.0):
    opportunity = VisualOpportunity(
        start, end, "le produit, le trafic et la livraison", P_LIST, 0.9, 0.8,
        items=["Produit", "Trafic", "Livraison"], concepts=["produit"])
    return ScenePlanner("professional", "16:9").plan(
        opportunity, INFOGRAPHIC, scene_id, start, end, title="T", subtitle="S")


def make_clip(scene, path="/tmp/x.mov"):
    return RenderedIllustration(
        scene_id=scene.scene_id, path=path, duration=scene.duration,
        renderer="motion_graphics",
        events={"entrance": 0.0, "elements": [0.3, 0.9], "exit": 4.5},
        width=1920, height=1080)


# --------------------------------------------------------------------------- #
# source -> output mapping
# --------------------------------------------------------------------------- #
def test_source_maps_onto_the_cut_timeline():
    assert source_to_output(5.0, RANGES) == pytest.approx(5.0)
    assert source_to_output(16.0, RANGES) == pytest.approx(11.0)
    assert source_to_output(31.0, RANGES) == pytest.approx(21.0)


def test_output_duration_is_the_sum_of_kept_ranges():
    assert output_duration(RANGES) == pytest.approx(30.0)


def test_scene_is_shifted_by_the_cut_not_left_behind():
    scene = make_scene(start=16.0, end=21.0)
    span = place_scene(scene, RANGES, 30.0)
    assert span is not None
    assert span[0] == pytest.approx(11.0)
    assert span[1] - span[0] == pytest.approx(scene.duration, abs=0.01)


def test_scene_beyond_the_output_is_dropped():
    scene = make_scene(start=39.5, end=44.0)
    assert place_scene(scene, RANGES, 30.0) is None


def test_scene_without_an_edl_keeps_its_own_times():
    scene = make_scene(start=16.0, end=21.0)
    assert place_scene(scene, [], 60.0) == (16.0, 21.0)


def test_overlapping_placements_are_resolved_to_one():
    a, b = make_scene("a"), make_scene("b")
    kept = resolve_overlaps([(10.0, 15.0, a), (14.0, 19.0, b)])
    assert [s.scene_id for _s, _e, s in kept] == ["a"]


def test_narration_weights_follow_the_spoken_text():
    scene = make_scene()
    weights = narration_weights(scene)
    assert len(weights) == len(scene.elements)
    assert all(w >= 0 for w in weights)
    assert sum(weights) == pytest.approx(1.0, abs=0.01)


# --------------------------------------------------------------------------- #
# legacy contract
# --------------------------------------------------------------------------- #
def test_timeline_emits_the_legacy_clip_contract():
    """`plan_overlays` reads these exact keys — they cannot drift."""
    scene = make_scene()
    board = Storyboard(scenes=[scene], source_duration=60.0)
    timeline = build_timeline(board, {scene.scene_id: make_clip(scene)})
    clips = timeline.to_legacy_motion_clips()
    assert len(clips) == 1
    clip = clips[0]
    for key in ("id", "kind", "source_start", "source_end", "duration", "mov",
                "illustrated", "events"):
        assert key in clip, key
    assert clip["source_start"] == pytest.approx(scene.start)
    assert set(clip["events"]) >= {"entrance", "elements", "exit"}


def test_output_overlays_are_ready_for_the_compositor(tmp_path):
    clip_path = tmp_path / "s1.mov"
    clip_path.write_bytes(b"0" * 2048)
    scene = make_scene(start=16.0, end=21.0)
    board = Storyboard(scenes=[scene], source_duration=60.0)
    timeline = build_timeline(board, {scene.scene_id: make_clip(scene, str(clip_path))})
    overlays = to_output_overlays(timeline, RANGES, 30.0)
    assert len(overlays) == 1
    assert overlays[0]["start"] == pytest.approx(11.0)
    assert overlays[0]["end"] > overlays[0]["start"]
    assert overlays[0]["mov"] == str(clip_path)


def test_manifest_is_written_and_readable(tmp_path):
    scene = make_scene()
    board = Storyboard(scenes=[scene], source_duration=60.0)
    timeline = build_timeline(board, {scene.scene_id: make_clip(scene)})
    path = write_manifest(timeline, str(tmp_path / "m.json"), board)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["legacy_motion_clips"]
    assert data["storyboard"]["scenes"]
    assert data["plan"][0]["visual_type"] == INFOGRAPHIC


# --------------------------------------------------------------------------- #
# compositing graph
# --------------------------------------------------------------------------- #
def test_batch_filter_overlays_onto_the_original_video():
    overlays = [{"mov": "a.mov", "start": 1.0, "end": 5.0},
                {"mov": "b.mov", "start": 9.0, "end": 12.0}]
    graph = build_batch_filter(overlays)
    # The original footage is input 0 and stays the base of the chain.
    assert graph.startswith("[0:v]") or "[0:v][c1]overlay" in graph
    assert "enable='between(t,1.000,5.000)'" in graph
    assert "enable='between(t,9.000,12.000)'" in graph
    assert graph.endswith("null[outv]")


def test_compositor_copies_through_when_there_is_nothing_to_burn(tmp_path):
    from app.illustration_engine.timeline import composite_illustrations
    base = tmp_path / "base.mp4"
    base.write_bytes(b"video")
    out = tmp_path / "out.mp4"
    result = composite_illustrations(str(base), [], str(out))
    assert os.path.exists(result)
    assert open(result, "rb").read() == b"video"
