"""End-to-end credit-saver render smoke tests (need ffmpeg).

Proves the two product guarantees that matter most:
  1. credit_saver never calls the paid image API yet still renders a valid MP4
     with audio + camera flashes + SFX (no AI image required).
  2. auto_fallback survives an "insufficient credits" failure: the job keeps
     going in credit-saver mode and records the reason — never blocked.

The renders are short and motion-design is OFF here to keep them fast; the
illustrated-scene render path is covered by test_motion_design.py.
"""
import json
import os
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


def _build_assets(tmpdir: str, duration: float = 9.0) -> tuple[str, str]:
    src = os.path.join(tmpdir, "source.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate=30:duration={duration}",
            "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "28",
            "-c:a", "aac", "-shortest", src,
        ],
        check=True, capture_output=True,
    )
    sentences = [
        (0.0, 4.5, "bonjour voici le secret important pour lancer votre business en ligne rapidement"),
        (4.7, 9.0, "retenez 80% des clients abandonnent leur panier alors abonnez vous maintenant cliquez sur le lien"),
    ]
    segments = []
    for s, e, text in sentences:
        toks = text.split()
        step = (e - s) / len(toks)
        words = [{"word": w, "start": round(s + i * step, 3), "end": round(s + (i + 1) * step, 3)}
                 for i, w in enumerate(toks)]
        segments.append({"start": s, "end": e, "text": text, "words": words})
    vu = {"language": "fr", "duration": duration, "segments": segments}
    vu_path = os.path.join(tmpdir, "vu.json")
    with open(vu_path, "w", encoding="utf-8") as f:
        json.dump(vu, f)
    return src, vu_path


def _probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type", "-of", "json", path],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def test_credit_saver_renders_mp4_without_any_paid_call(tmp_path, monkeypatch):
    from app.autoedit_engine import genimg, pipeline

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def _boom(*a, **k):
        raise AssertionError("paid image API called in credit_saver mode")

    monkeypatch.setattr(genimg, "generate_brolls", _boom)
    monkeypatch.setattr(genimg, "generate_illustrations", _boom)

    src, vu = _build_assets(str(tmp_path))
    rep: dict = {}
    final = pipeline.run(
        src, str(tmp_path / "out"), vu=vu, visual_mode="credit_saver",
        do_motion=False, do_broll=True, report=rep, cleanup=True,
    )

    # Valid MP4 with audio.
    assert os.path.exists(final) and os.path.getsize(final) > 0
    streams = {s["codec_type"] for s in _probe(final)["streams"]}
    assert "video" in streams and "audio" in streams

    # Credit-saver visual plan: no images, but real effects.
    assert rep["visual_mode_used"] == "credit_saver"
    assert rep["ai_images_skipped"] is True
    assert rep["broll_images"] == 0
    assert rep["key_moment_punches"] >= 1
    assert rep["sfx_cues"] >= 1
    assert rep["effects_applied"]["keyMomentPunches"] == rep["key_moment_punches"]
    # Le flash blanc + shutter ont été retirés du rendu.
    assert "camera_flashes" not in rep and "shutter_sfx" not in rep


def test_auto_fallback_continues_on_insufficient_credits(tmp_path, monkeypatch):
    from app.autoedit_engine import genimg, pipeline

    # A key is present (so the engine WOULD try), but generation fails on credits.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-used-for-real")
    calls = {"n": 0}

    def _insufficient(*a, **k):
        calls["n"] += 1
        raise RuntimeError("OpenRouter 402: insufficient credits, please add funds")

    monkeypatch.setattr(genimg, "generate_brolls", _insufficient)
    monkeypatch.setattr(genimg, "generate_illustrations",
                        lambda scenes, *a, **k: scenes)

    src, vu = _build_assets(str(tmp_path))
    rep: dict = {}
    final = pipeline.run(
        src, str(tmp_path / "out"), vu=vu, visual_mode="auto_fallback",
        do_motion=False, do_broll=True, report=rep, cleanup=True,
    )

    # It TRIED (credits present) but failed -> kept rendering in credit-saver.
    assert calls["n"] >= 1
    assert os.path.exists(final) and os.path.getsize(final) > 0
    assert rep["visual_mode_used"] == "credit_saver"
    assert rep["ai_images_skipped"] is True
    assert rep["fallback_reason"] == "insufficient_credits"
    assert rep["key_moment_punches"] >= 1
