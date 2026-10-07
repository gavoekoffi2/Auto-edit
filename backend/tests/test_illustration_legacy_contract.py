"""Le contrat avec le pipeline de montage EXISTANT.

Le nouveau moteur remplace l'étape 4 du montage. Tout l'aval — planification
des overlays, cues SFX, exclusion B-roll, compositing — est resté inchangé,
et ne doit le rester que si la forme des enregistrements produits est
exactement celle que l'ancien `motion_design.render_all()` émettait.

Ces tests exercent le VRAI `plan_overlays`, sans le modifier ni le simuler :
c'est ce qui empêche le contrat de dériver en silence.
"""
from __future__ import annotations

import json
import os

import pytest

from app.illustration_engine import bridge
from tests.illustration_fixtures import DEMO_SCRIPT, build_vu, has_ffmpeg

pytestmark = pytest.mark.skipif(not has_ffmpeg(), reason="ffmpeg not available")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    """Exactement l'appel que fait `pipeline.py` à l'étape 4."""
    work = tmp_path_factory.mktemp("legacy_contract")
    clips, report = bridge.run(
        build_vu(DEMO_SCRIPT), str(work / "motion_clips"),
        intensity="high", width=1080, height=1920, fps=12,
        workdir=str(work), preview=True)
    return clips, report, work


def test_engine_produces_clips(rendered):
    clips, report, _work = rendered
    assert clips, report
    assert report["engine"] == "illustration_engine"


def test_aspect_is_taken_from_the_montage_canvas(rendered):
    """Le pipeline vertical existant doit continuer à rendre en vertical."""
    _clips, report, _work = rendered
    assert report["aspect"] == "9:16"


def test_clip_records_carry_every_legacy_key(rendered):
    clips, _report, _work = rendered
    for clip in clips:
        for key in ("id", "kind", "source_start", "source_end", "duration",
                    "mov", "illustrated", "events"):
            assert key in clip, key
        assert os.path.exists(clip["mov"])
        assert set(clip["events"]) >= {"entrance", "elements", "exit"}
        assert isinstance(clip["events"]["elements"], list)


def test_unmodified_plan_overlays_consumes_the_output(rendered, tmp_path):
    """Le VRAI planificateur d'overlays du montage, tel quel."""
    from app.autoedit_engine import plan_overlays

    clips, _report, _work = rendered
    vu = build_vu(DEMO_SCRIPT)

    motion_json = tmp_path / "_motion_clips.json"
    motion_json.write_text(json.dumps(clips, ensure_ascii=False), encoding="utf-8")
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps({
        "ranges": [{"start": 0.0, "end": vu["duration"]}],
        "duration": vu["duration"], "overlays": [],
    }), encoding="utf-8")

    plan_overlays.plan(str(edl_path), None, None,
                       motion_json=str(motion_json), outdir=str(tmp_path))

    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    motions = [o for o in edl["overlays"] if o.get("kind") == "motion"]
    assert len(motions) == len(clips)
    for overlay in motions:
        assert overlay["end"] > overlay["start"]
        assert os.path.exists(overlay["mov"])
    starts = [o["start"] for o in motions]
    assert starts == sorted(starts)


def test_events_drive_the_legacy_sfx_planner(rendered, tmp_path):
    """Les `events` du moteur doivent produire de vrais cues sonores."""
    from app.autoedit_engine import plan_overlays

    clips, _report, _work = rendered
    vu = build_vu(DEMO_SCRIPT)
    motion_json = tmp_path / "_motion_clips.json"
    motion_json.write_text(json.dumps(clips, ensure_ascii=False), encoding="utf-8")
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps({
        "ranges": [{"start": 0.0, "end": vu["duration"]}],
        "duration": vu["duration"], "overlays": [],
    }), encoding="utf-8")

    plan_overlays.plan(str(edl_path), None, None,
                       motion_json=str(motion_json), outdir=str(tmp_path))

    cues = json.loads((tmp_path / "sfx_cues.json").read_text(encoding="utf-8"))
    assert cues
    assert {c["src"] for c in cues} == {"motion"}
    # Anticipation before the picture, elements during, exit at the end.
    assert any(c["sfx"] in ("riser", "reverse_swell", "tape_stop") for c in cues)
    assert all(0.0 <= c["t"] <= vu["duration"] for c in cues)


def test_broll_exclusion_spans_match_the_clips(rendered):
    """Le B-roll et les popups doivent éviter exactement ces intervalles."""
    clips, _report, _work = rendered
    spans = bridge.spans(clips)
    assert len(spans) == len(clips)
    for (start, end), clip in zip(spans, clips):
        assert start == pytest.approx(clip["source_start"])
        assert end == pytest.approx(clip["source_start"] + clip["duration"])
    for previous, current in zip(spans, spans[1:]):
        assert current[0] >= previous[1], "les spans ne doivent pas se chevaucher"
