"""Transcription locale: faster-whisper si présent, openai-whisper sinon.

Ces tests ne téléchargent aucun modèle. Ils vérifient le choix du moteur, la
chaîne de repli, et surtout que les deux moteurs produisent le MÊME contrat
(`text`, `start`, `end`, `confidence`, segment parent) — c'est ce contrat que
consomme le moteur d'illustration.
"""
from __future__ import annotations

import json
import os
import sys
import types

import pytest

from app.processing import transcription_service as svc
from app.processing.transcription_service import (
    BACKEND_FASTER, BACKEND_OPENAI, TranscriptionService)


# --------------------------------------------------------------------------- #
# choix du moteur
# --------------------------------------------------------------------------- #
def test_auto_prefers_faster_whisper_when_installed(monkeypatch):
    monkeypatch.setattr(svc, "faster_whisper_available", lambda: True)
    assert TranscriptionService("small").resolve_backend() == BACKEND_FASTER


def test_auto_falls_back_to_openai_whisper(monkeypatch):
    monkeypatch.setattr(svc, "faster_whisper_available", lambda: False)
    assert TranscriptionService("small").resolve_backend() == BACKEND_OPENAI


def test_forced_openai_ignores_a_present_faster_whisper(monkeypatch):
    monkeypatch.setattr(svc, "faster_whisper_available", lambda: True)
    service = TranscriptionService("small", backend="whisper")
    assert service.resolve_backend() == BACKEND_OPENAI


def test_forced_faster_whisper_degrades_rather_than_crashing(monkeypatch):
    monkeypatch.setattr(svc, "faster_whisper_available", lambda: False)
    service = TranscriptionService("small", backend="faster_whisper")
    assert service.resolve_backend() == BACKEND_OPENAI


def test_unknown_backend_is_treated_as_auto():
    assert TranscriptionService("small", backend="banana").requested_backend == "auto"


def test_compute_type_defaults_to_int8_for_cpu_vps():
    assert TranscriptionService("small").compute_type == "int8"


def test_env_can_pin_the_backend(monkeypatch):
    monkeypatch.setenv("WHISPER_BACKEND", "whisper")
    assert TranscriptionService("small").requested_backend == "whisper"


# --------------------------------------------------------------------------- #
# normalisation vers le contrat commun
# --------------------------------------------------------------------------- #
RAW = [
    {"start": 0.0, "end": 2.0, "text": "Bonjour à tous",
     "words": [
         {"word": "Bonjour", "start": 0.0, "end": 0.6, "probability": 0.98},
         {"word": "à", "start": 0.6, "end": 0.8, "probability": 0.91},
         {"word": "tous", "start": 0.8, "end": 2.0, "probability": 0.95},
     ]},
    {"start": 2.2, "end": 4.0, "text": "on démarre", "words": []},
]


def test_segments_become_typed_words_with_confidence():
    transcript = TranscriptionService._to_transcript(RAW, "fr", "Bonjour à tous on démarre")
    assert transcript.language == "fr"
    assert len(transcript.segments) == 2
    words = transcript.segments[0].words
    assert [w.text for w in words] == ["Bonjour", "à", "tous"]
    assert words[0].start == 0.0 and words[0].end == 0.6
    assert words[0].confidence == pytest.approx(0.98)
    # A segment without word timings still yields a usable segment.
    assert transcript.segments[1].text == "on démarre"


def test_persisted_files_match_the_engine_contract(tmp_path):
    transcript = TranscriptionService._to_transcript(RAW, "fr", "Bonjour à tous")
    TranscriptionService._persist(transcript, RAW, str(tmp_path))
    for name in ("transcript.json", "words.json", "subtitles.srt"):
        assert (tmp_path / name).exists(), name
    words = json.loads((tmp_path / "words.json").read_text(encoding="utf-8"))
    assert words and {"text", "start", "end"} <= set(words[0])


# --------------------------------------------------------------------------- #
# le moteur rapide, simulé (aucun modèle téléchargé)
# --------------------------------------------------------------------------- #
class _FakeWord:
    def __init__(self, word, start, end, probability):
        self.word, self.start, self.end, self.probability = word, start, end, probability


class _FakeSegment:
    def __init__(self, start, end, text, words):
        self.start, self.end, self.text, self.words = start, end, text, words


class _FakeInfo:
    language = "fr"


def _install_fake_faster_whisper(monkeypatch, fail=False):
    module = types.ModuleType("faster_whisper")

    class WhisperModel:
        def __init__(self, *args, **kwargs):
            if fail:
                raise RuntimeError("modèle indisponible")
            self.args, self.kwargs = args, kwargs

        def transcribe(self, path, **kwargs):
            segments = [_FakeSegment(0.0, 2.0, " Bonjour à tous", [
                _FakeWord(" Bonjour", 0.0, 0.6, 0.98),
                _FakeWord(" tous", 0.6, 2.0, 0.94),
            ])]
            return iter(segments), _FakeInfo()

    module.WhisperModel = WhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    svc._faster_cache.clear()


def test_faster_whisper_output_is_normalised(monkeypatch):
    _install_fake_faster_whisper(monkeypatch)
    monkeypatch.setattr(svc, "faster_whisper_available", lambda: True)
    raw, language, text = TranscriptionService("tiny")._run_faster("video.mp4")
    assert language == "fr"
    assert text == "Bonjour à tous"
    assert raw[0]["words"][0]["word"].strip() == "Bonjour"
    assert raw[0]["words"][0]["probability"] == pytest.approx(0.98)


def test_faster_whisper_failure_falls_back_to_openai(monkeypatch, tmp_path):
    """A missing model must degrade to the other engine, never fail the job."""
    _install_fake_faster_whisper(monkeypatch, fail=True)
    monkeypatch.setattr(svc, "faster_whisper_available", lambda: True)

    called = {}

    def _fake_openai(self, path):
        called["yes"] = True
        return RAW, "fr", "Bonjour à tous on démarre"

    monkeypatch.setattr(TranscriptionService, "_run_openai", _fake_openai)
    transcript = TranscriptionService("tiny").transcribe("v.mp4", str(tmp_path))
    assert called.get("yes") is True
    assert len(transcript.words) == 3


def test_transcribe_writes_everything_the_pipeline_expects(monkeypatch, tmp_path):
    _install_fake_faster_whisper(monkeypatch)
    monkeypatch.setattr(svc, "faster_whisper_available", lambda: True)
    transcript = TranscriptionService("tiny").transcribe("v.mp4", str(tmp_path))
    assert transcript.language == "fr"
    assert len(transcript.words) == 2
    assert os.path.exists(os.path.join(str(tmp_path), "transcript.json"))


# --------------------------------------------------------------------------- #
# le contrat consommé par le moteur d'illustration
# --------------------------------------------------------------------------- #
def test_transcript_feeds_the_illustration_engine(monkeypatch):
    """Whisper's word-level output is exactly what the analyzer reads."""
    from app.illustration_engine.analyzer import SemanticAnalyzer

    transcript = TranscriptionService._to_transcript(
        [{"start": 0.0, "end": 6.0,
          "text": "Il y a trois choses : le produit, le trafic et la livraison.",
          "words": [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.4,
                     "probability": 0.9}
                    for i, w in enumerate(
                        "Il y a trois choses : le produit, le trafic et la "
                        "livraison.".split())]}],
        "fr", "Il y a trois choses")
    vu = {"language": transcript.language, "duration": 6.0, "segments": [
        {"text": s.text, "start": s.start, "end": s.end,
         "words": [{"word": w.text, "start": w.start, "end": w.end}
                   for w in s.words]}
        for s in transcript.segments]}
    units = SemanticAnalyzer().analyze(vu)
    assert units and units[0].pattern == "list"
    assert units[0].items == ["Produit", "Trafic", "Livraison"]
