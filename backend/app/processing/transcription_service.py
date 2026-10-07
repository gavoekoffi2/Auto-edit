"""Wrapper de transcription pour le pipeline V2.

Deux moteurs **locaux et gratuits**, un seul contrat de sortie :

* **faster-whisper** (CTranslate2) quand il est disponible — 4 à 5 fois plus
  rapide qu'openai-whisper sur CPU, avec une empreinte mémoire bien moindre en
  `int8`. C'est ce qui rend la transcription locale réaliste sur un VPS sans GPU ;
* **openai-whisper** sinon, le comportement historique.

Les deux produisent des `Word`/`TranscriptSegment`/`Transcript` typés avec
`text`, `start`, `end`, `confidence` et le segment parent, et persistent
`transcript.json`, `words.json` et `subtitles.srt`.

Aucune API payante n'est requise : ElevenLabs Scribe reste une accélération
optionnelle décidée en amont par `pipeline_v2`, jamais une dépendance.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from app.processing.types import Transcript, TranscriptSegment, Word

logger = logging.getLogger(__name__)

BACKEND_AUTO = "auto"
BACKEND_FASTER = "faster_whisper"
BACKEND_OPENAI = "whisper"
VALID_BACKENDS = (BACKEND_AUTO, BACKEND_FASTER, BACKEND_OPENAI)

_DEFAULT_PROMPT = (
    "Transcription en français correct, ponctuée. Sujets: business, "
    "vente en ligne, marketing, mobile money, entrepreneuriat."
)

# Model cache, keyed by (backend, name, compute_type): loading a model is the
# expensive part, and a Celery worker transcribes many videos in its lifetime.
_faster_cache: Dict[tuple, Any] = {}


def faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 - absent or broken install, same answer
        return False


class TranscriptionService:
    def __init__(self, model_name: str = "base", word_timestamps: bool = True,
                 backend: Optional[str] = None, compute_type: Optional[str] = None):
        self.model_name = model_name
        self.word_timestamps = word_timestamps
        requested = (backend or os.getenv("WHISPER_BACKEND", BACKEND_AUTO) or
                     BACKEND_AUTO).strip().lower()
        if requested not in VALID_BACKENDS:
            requested = BACKEND_AUTO
        self.requested_backend = requested
        self.compute_type = (compute_type
                             or os.getenv("WHISPER_COMPUTE_TYPE", "int8")).strip()

    # ------------------------------------------------------------------ #
    def resolve_backend(self) -> str:
        """Which engine will actually run."""
        if self.requested_backend == BACKEND_OPENAI:
            return BACKEND_OPENAI
        if faster_whisper_available():
            return BACKEND_FASTER
        if self.requested_backend == BACKEND_FASTER:
            logger.warning("[transcription_service] faster-whisper demandé mais "
                           "absent — repli sur openai-whisper")
        return BACKEND_OPENAI

    @staticmethod
    def _language() -> Optional[str]:
        return (os.getenv("WHISPER_LANGUAGE", "") or "").strip() or None

    @staticmethod
    def _initial_prompt() -> Optional[str]:
        return os.getenv("WHISPER_INITIAL_PROMPT", _DEFAULT_PROMPT) or None

    # ------------------------------------------------------------------ #
    def transcribe(self, video_path: str, output_dir: str) -> Transcript:
        """Transcrit une vidéo localement et renvoie un `Transcript` typé."""
        backend = self.resolve_backend()
        logger.info("[transcription_service] transcribing %s (backend=%s, "
                    "model=%s)", video_path, backend, self.model_name)

        if backend == BACKEND_FASTER:
            try:
                raw_segments, language, text = self._run_faster(video_path)
            except Exception as exc:  # noqa: BLE001 - never lose a job over it
                logger.warning("[transcription_service] faster-whisper a échoué "
                               "(%s) — repli sur openai-whisper", exc)
                backend = BACKEND_OPENAI
                raw_segments, language, text = self._run_openai(video_path)
        else:
            raw_segments, language, text = self._run_openai(video_path)

        transcript = self._to_transcript(raw_segments, language, text)
        self._persist(transcript, raw_segments, output_dir)
        logger.info("[transcription_service] done: backend=%s lang=%s "
                    "segments=%d words=%d", backend, transcript.language,
                    len(transcript.segments), len(transcript.words))
        return transcript

    # -- engines -------------------------------------------------------- #
    def _run_openai(self, video_path: str) -> Tuple[List[dict], str, str]:
        # Import paresseux: whisper coûte cher à importer.
        from app.processing import transcribe as v1
        import whisper  # noqa: F401 - fail early and clearly if missing

        model = v1._get_model(self.model_name)
        # Anti-hallucination / anti-répétition + meilleure précision :
        #  - condition_on_previous_text=False : empêche Whisper de boucler et de
        #    RÉPÉTER des phrases (cause classique des passages fantômes).
        #  - temperature fallback + seuils : rejette les segments incohérents.
        #  - language/initial_prompt : biaise le vocabulaire (réduit tech->tête).
        decode_kwargs: Dict[str, Any] = dict(
            verbose=False,
            word_timestamps=self.word_timestamps,
            condition_on_previous_text=False,
            temperature=(0.0, 0.2, 0.4, 0.6),
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
            initial_prompt=self._initial_prompt(),
        )
        language = self._language()
        if language:
            decode_kwargs["language"] = language
        try:
            result = model.transcribe(video_path, **decode_kwargs)
        except TypeError:
            # Older/newer whisper signatures: retry with the safe core subset.
            result = model.transcribe(
                video_path, verbose=False,
                word_timestamps=self.word_timestamps,
                condition_on_previous_text=False,
            )
        return (result.get("segments", []) or [],
                result.get("language", "unknown"),
                str(result.get("text", "")).strip())

    def _run_faster(self, video_path: str) -> Tuple[List[dict], str, str]:
        """faster-whisper, normalised into the openai-whisper segment shape."""
        from faster_whisper import WhisperModel

        key = (BACKEND_FASTER, self.model_name, self.compute_type)
        model = _faster_cache.get(key)
        if model is None:
            logger.info("[transcription_service] loading faster-whisper %s "
                        "(compute_type=%s)", self.model_name, self.compute_type)
            model = WhisperModel(self.model_name, device="cpu",
                                 compute_type=self.compute_type)
            _faster_cache[key] = model

        segments_iter, info = model.transcribe(
            video_path,
            language=self._language(),
            word_timestamps=self.word_timestamps,
            condition_on_previous_text=False,
            temperature=[0.0, 0.2, 0.4, 0.6],
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
            initial_prompt=self._initial_prompt(),
            vad_filter=True,
        )

        raw: List[dict] = []
        texts: List[str] = []
        for segment in segments_iter:          # lazy generator: this is the work
            words = []
            for word in (getattr(segment, "words", None) or []):
                words.append({
                    "word": word.word,
                    "start": float(word.start),
                    "end": float(word.end),
                    # faster-whisper exposes a log-prob-derived probability.
                    "probability": float(getattr(word, "probability", 0.0) or 0.0),
                })
            raw.append({
                "start": float(segment.start),
                "end": float(segment.end),
                "text": (segment.text or "").strip(),
                "words": words,
            })
            texts.append((segment.text or "").strip())

        language = getattr(info, "language", None) or "unknown"
        return raw, language, " ".join(t for t in texts if t).strip()

    # -- shared post-processing ----------------------------------------- #
    @staticmethod
    def _to_transcript(raw_segments: List[dict], language: str,
                       text: str) -> Transcript:
        segments: List[TranscriptSegment] = []
        for seg in raw_segments:
            words: List[Word] = []
            for w in seg.get("words", []) or []:
                # Word object: {word, start, end, probability}
                words.append(Word(
                    text=str(w.get("word", "")).strip(),
                    start=float(w.get("start", seg.get("start", 0.0))),
                    end=float(w.get("end", seg.get("end", 0.0))),
                    confidence=w.get("probability"),
                ))
            segments.append(TranscriptSegment(
                start=float(seg.get("start", 0.0)),
                end=float(seg.get("end", 0.0)),
                text=str(seg.get("text", "")).strip(),
                words=words,
            ))
        return Transcript(language=language or "unknown", text=text,
                          segments=segments)

    @staticmethod
    def _persist(transcript: Transcript, raw_segments: List[dict],
                 output_dir: str) -> None:
        from app.processing import transcribe as v1

        os.makedirs(output_dir, exist_ok=True)
        # Compat v1 — transcript.json et subtitles.srt
        v1._write_srt(raw_segments, os.path.join(output_dir, "subtitles.srt"))
        with open(os.path.join(output_dir, "transcript.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(transcript.to_dict(), handle, ensure_ascii=False, indent=2)
        # Words-only file (utile pour debug + EDL)
        with open(os.path.join(output_dir, "words.json"), "w",
                  encoding="utf-8") as handle:
            json.dump([w.to_dict() for w in transcript.words], handle,
                      ensure_ascii=False, indent=2)
