"""Tests de la fonctionnalité « Clips » (vidéo longue -> shorts viraux)."""
import json

import pytest

from app.processing import viral_moments as vm
from app.processing.clips_pipeline import _slice_vu
from app.services.video_download import SourceURLError, validate_source_url


def _vu(n_sentences: int = 20, words_per_sentence: int = 12) -> dict:
    segments = []
    t = 0.0
    for i in range(n_sentences):
        words = []
        for j in range(words_per_sentence):
            words.append({"word": f"mot{i}_{j}", "start": round(t, 2),
                          "end": round(t + 0.35, 2)})
            t += 0.4
        segments.append({
            "text": " ".join(w["word"] for w in words),
            "start": words[0]["start"], "end": words[-1]["end"],
            "words": words,
        })
        t += 0.3
    return {"language": "fr", "duration": round(t, 2), "segments": segments}


# --------------------------------------------------------------------------- #
# validation d'URL (anti-SSRF)
# --------------------------------------------------------------------------- #
def test_validate_source_url_accepts_public_https():
    assert validate_source_url("https://www.youtube.com/watch?v=x") \
        .startswith("https://www.youtube.com")


@pytest.mark.parametrize("bad", [
    "",
    "ftp://example.com/video.mp4",
    "file:///etc/passwd",
    "http://127.0.0.1/internal",
    "http://localhost:8000/admin",
    "http://169.254.169.254/latest/meta-data",
    "http://[::1]/",
    "http://10.0.0.5/video",
    "http://192.168.1.10/x",
])
def test_validate_source_url_rejects_bad_urls(bad):
    with pytest.raises(SourceURLError):
        validate_source_url(bad)


# --------------------------------------------------------------------------- #
# détection des moments viraux
# --------------------------------------------------------------------------- #
def test_validate_moments_snaps_and_removes_overlaps():
    vu = _vu()
    raw = [
        {"start": 2.0, "end": 40.0, "title": "A", "score": 90},
        {"start": 30.0, "end": 70.0, "title": "B (chevauche A)", "score": 50},
        {"start": 60.0, "end": 62.0, "title": "trop court", "score": 99},
        {"start": "x", "end": 100},        # invalide
    ]
    kept = vm._validate(raw, vu, max_clips=5, min_len=15.0, max_len=90.0)
    assert [m["title"] for m in kept] == ["A"]
    # snap: le début tombe sur une frontière de phrase du transcript
    seg_starts = {s["start"] for s in vu["segments"]}
    assert kept[0]["start"] in seg_starts


def test_heuristic_moments_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    vu = _vu()
    moments, provider = vm.detect_viral_moments(vu, max_clips=3)
    assert provider == "heuristic"
    assert 1 <= len(moments) <= 3
    for m in moments:
        assert m["end"] - m["start"] >= vm.MIN_CLIP_S
        assert m["end"] <= vu["duration"]
    # pas de chevauchement
    for a, b in zip(moments, moments[1:]):
        assert a["end"] <= b["start"]


def test_llm_moments_used_when_available(monkeypatch):
    vu = _vu()
    monkeypatch.setattr(
        vm, "llm_moments",
        lambda *a, **k: [{"start": 0.0, "end": 45.0, "title": "Hook",
                          "hook": "h", "reason": "r", "score": 88}],
    )
    moments, provider = vm.detect_viral_moments(vu, max_clips=3)
    assert provider == "llm"
    assert moments[0]["title"] == "Hook"


# --------------------------------------------------------------------------- #
# découpe du transcript par clip
# --------------------------------------------------------------------------- #
def test_slice_vu_shifts_times_to_zero():
    vu = _vu()
    clip = _slice_vu(vu, 10.0, 30.0)
    assert clip["duration"] == 20.0
    assert clip["segments"], "clip transcript must not be empty"
    first_word = clip["segments"][0]["words"][0]
    assert 0.0 <= first_word["start"] < 1.0
    last_word = clip["segments"][-1]["words"][-1]
    assert last_word["end"] <= 20.0 + 0.5
    # aucun mot hors fenêtre
    for seg in clip["segments"]:
        for w in seg["words"]:
            assert w["start"] >= -0.01


def test_slice_vu_empty_outside_speech():
    vu = _vu(n_sentences=2)
    clip = _slice_vu(vu, 500.0, 520.0)
    assert clip["segments"] == []


# --------------------------------------------------------------------------- #
# schéma API
# --------------------------------------------------------------------------- #
def test_clips_create_schema_requires_exactly_one_source():
    import uuid
    from app.schemas.job import ClipsCreate

    ClipsCreate(source_url="https://youtube.com/watch?v=1")     # ok
    ClipsCreate(video_id=uuid.uuid4())                          # ok
    with pytest.raises(ValueError):
        ClipsCreate()
    with pytest.raises(ValueError):
        ClipsCreate(source_url="https://x.com/v", video_id=uuid.uuid4())
    with pytest.raises(ValueError):
        ClipsCreate(source_url="https://x.com/v", mode="not_a_mode")


def test_clips_job_type_registered():
    from app.config import VALID_JOB_TYPES
    assert "clips" in VALID_JOB_TYPES


def test_job_options_max_clips_bounds():
    from app.schemas.job import JobOptions
    assert JobOptions(max_clips=5).max_clips == 5
    with pytest.raises(ValueError):
        JobOptions(max_clips=0)
    with pytest.raises(ValueError):
        JobOptions(max_clips=11)
