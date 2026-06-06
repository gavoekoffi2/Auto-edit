"""Tests for the Whisper -> Auto Edit engine bridge (pipeline_v2).

These are light and CI-safe: they exercise the pure-Python transcript bridge
and the mode->template mapping, with no ffmpeg / Whisper / network needed.
"""
import json

from app.processing.pipeline_v2 import _transcript_to_vu, MODE_TO_TEMPLATE
from app.processing.types import Transcript, TranscriptSegment, Word


def test_transcript_to_vu_maps_word_timestamps(tmp_path):
    tr = Transcript(
        language="fr",
        text="bonjour le monde",
        segments=[
            TranscriptSegment(
                start=0.0, end=1.2, text="bonjour le monde",
                words=[Word("bonjour", 0.0, 0.4), Word("le", 0.45, 0.6), Word("monde", 0.65, 1.2)],
            )
        ],
    )
    vu_path = _transcript_to_vu(tr, str(tmp_path), str(tmp_path / "missing.mp4"))
    vu = json.load(open(vu_path, encoding="utf-8"))

    assert vu["language"] == "fr"
    assert len(vu["segments"]) == 1
    words = vu["segments"][0]["words"]
    assert [w["word"] for w in words] == ["bonjour", "le", "monde"]
    assert vu["duration"] >= 1.2


def test_transcript_to_vu_synthesizes_missing_words(tmp_path):
    # A segment with text but no per-word timestamps must get words synthesised
    # by splitting the span evenly, so the engine still has word-level data.
    tr = Transcript(
        language="en",
        text="hello world here",
        segments=[TranscriptSegment(start=2.0, end=5.0, text="hello world here", words=[])],
    )
    vu_path = _transcript_to_vu(tr, str(tmp_path), str(tmp_path / "x.mp4"))
    vu = json.load(open(vu_path, encoding="utf-8"))

    words = vu["segments"][0]["words"]
    assert [w["word"] for w in words] == ["hello", "world", "here"]
    assert words[0]["start"] == 2.0
    assert abs(words[-1]["end"] - 5.0) < 0.01


def test_mode_to_template_known_modes():
    assert MODE_TO_TEMPLATE["business_premium_african"] == "gold_lux"
    assert MODE_TO_TEMPLATE["tiktok_viral"] == "tiktok_yellow"
    assert MODE_TO_TEMPLATE["publicite_locale"] == "bold_box"
