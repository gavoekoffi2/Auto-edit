"""Timeline planning with motion-design scenes: priority, clamping, SFX design."""
import json

import pytest

from app.autoedit_engine import config as engine_config
from app.autoedit_engine import plan_overlays


@pytest.fixture()
def workdir(tmp_path):
    edl = {
        "ranges": [{"start": 0.0, "end": 30.0}],   # output = 30 s, 1:1 mapping
        "overlays": [],
        "transcripts_vu": str(tmp_path / "vu.json"),
    }
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps(edl), encoding="utf-8")

    motion = [{
        "id": "md_000", "mov": str(tmp_path / "md_000.mov"),
        "source_start": 10.0, "duration": 4.6, "kind": "idea",
        "events": {"entrance": 0.0, "elements": [0.42, 0.95], "exit": 4.38},
    }]
    motion_path = tmp_path / "_motion_clips.json"
    motion_path.write_text(json.dumps(motion), encoding="utf-8")

    broll = [
        # collides with the motion scene (10.0 - 14.6) -> must be dropped
        {"id": "br_000", "mov": str(tmp_path / "br_000.mov"),
         "source_start": 11.0, "duration": 3.0},
        # safe
        {"id": "br_001", "mov": str(tmp_path / "br_001.mov"),
         "source_start": 20.0, "duration": 3.0},
        # would end after the video -> must be dropped
        {"id": "br_002", "mov": str(tmp_path / "br_002.mov"),
         "source_start": 29.0, "duration": 3.0},
    ]
    broll_path = tmp_path / "_broll_clips.json"
    broll_path.write_text(json.dumps(broll), encoding="utf-8")

    return {"tmp": tmp_path, "edl": str(edl_path), "motion": str(motion_path),
            "broll": str(broll_path)}


def test_motion_has_priority_over_broll(workdir):
    res = plan_overlays.plan(workdir["edl"], None, workdir["broll"],
                             motion_json=workdir["motion"], outdir=str(workdir["tmp"]))

    overlays = res["overlays"]
    kinds = {o["id"]: o["kind"] for o in overlays}
    assert kinds.get("md_000") == "motion"
    assert "br_000" not in kinds, "B-roll colliding with a motion scene must be dropped"
    assert "br_001" in kinds
    assert "br_002" not in kinds, "B-roll past the end of the video must be dropped"

    # z-order: motion scenes are composited last (on top)
    ids = [o["id"] for o in overlays]
    assert ids.index("md_000") > ids.index("br_001")

    # motion mapped with its lead, clamped inside the timeline
    md = next(o for o in overlays if o["id"] == "md_000")
    assert md["start"] == pytest.approx(10.0 - engine_config.MOTION_LEAD, abs=0.01)
    assert md["end"] <= 30.0


def test_motion_sfx_design(workdir):
    res = plan_overlays.plan(workdir["edl"], None, workdir["broll"],
                             motion_json=workdir["motion"], outdir=str(workdir["tmp"]))
    cues = res["cues"]
    motion_cues = [c for c in cues if c["src"] == "motion"]
    md_start = 10.0 - engine_config.MOTION_LEAD

    times = sorted(c["t"] for c in motion_cues)
    # riser anticipation BEFORE the takeover
    assert any(abs(t - (md_start - engine_config.MOTION_RISER_LEAD)) < 0.02 for t in times)
    # entrance hit AT the takeover
    assert any(abs(t - md_start) < 0.02 for t in times)
    # one cue per animated element
    for et in (0.42, 0.95):
        assert any(abs(t - (md_start + et)) < 0.02 for t in times)
    # exit swoosh
    assert any(abs(t - (md_start + 4.38)) < 0.02 for t in times)

    riser_names = {c["sfx"] for c in motion_cues}
    assert riser_names & set(engine_config.MOTION_RISER_SFX)
    assert riser_names & set(engine_config.MOTION_ENTRANCE_SFX)

    # global rule: no two consecutive identical SFX
    ordered = sorted(cues, key=lambda c: c["t"])
    for a, b in zip(ordered, ordered[1:]):
        assert a["sfx"] != b["sfx"], f"consecutive duplicate SFX at {a['t']}/{b['t']}"


def test_plan_without_motion_keeps_legacy_behaviour(workdir):
    res = plan_overlays.plan(workdir["edl"], None, workdir["broll"],
                             motion_json=None, outdir=str(workdir["tmp"]))
    kinds = [o["kind"] for o in res["overlays"]]
    assert "motion" not in kinds
    assert kinds.count("broll") == 2          # br_000 + br_001 (br_002 past end)
    assert all(c["src"] != "motion" for c in res["cues"])


def test_sfx_cues_written_to_disk(workdir):
    plan_overlays.plan(workdir["edl"], None, None,
                       motion_json=workdir["motion"], outdir=str(workdir["tmp"]))
    cues = json.loads((workdir["tmp"] / "sfx_cues.json").read_text(encoding="utf-8"))
    assert cues, "sfx_cues.json must not be empty when a motion scene exists"
    # all referenced SFX exist in the synthesised library
    assert all(c["sfx"] in engine_config.SFX_NAMES for c in cues)
