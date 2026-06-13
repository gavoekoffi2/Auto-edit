"""Transcription provider selection (ElevenLabs Scribe vs local Whisper)."""
from app.processing.pipeline_v2 import _choose_transcription_provider as choose


def test_auto_prefers_elevenlabs_when_key_present():
    assert choose("auto", True) == "elevenlabs"


def test_auto_falls_back_to_whisper_without_key():
    assert choose("auto", False) == "whisper"
    assert choose(None, False) == "whisper"


def test_forced_whisper_ignores_key():
    assert choose("whisper", True) == "whisper"


def test_forced_elevenlabs_needs_key():
    assert choose("elevenlabs", True) == "elevenlabs"
    # forced but no key -> can't, so Whisper
    assert choose("elevenlabs", False) == "whisper"


def test_case_insensitive():
    assert choose("ElevenLabs", True) == "elevenlabs"
    assert choose("WHISPER", True) == "whisper"
