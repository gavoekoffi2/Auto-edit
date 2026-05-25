"""Wrapper de transcription pour le pipeline V2.

S'appuie sur le module v1 `transcribe.py` (Whisper local) pour ne pas
réinventer la roue, mais expose des `Word`/`TranscriptSegment`/`Transcript`
typés et persiste un `words.json` mot-par-mot quand Whisper le fournit.

Plus tard on pourra ajouter un `provider="api"` (OpenAI/Replicate) sans
changer le contrat.
"""
from __future__ import annotations

import json
import os
import logging
from typing import Optional

from app.processing.types import Transcript, TranscriptSegment, Word

logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(self, model_name: str = "base", word_timestamps: bool = True):
        self.model_name = model_name
        self.word_timestamps = word_timestamps

    def transcribe(self, video_path: str, output_dir: str) -> Transcript:
        """Transcrit une vidéo avec Whisper local et renvoie un `Transcript` typé.

        Écrit aussi:
          - `transcript.json` (compat v1)
          - `words.json` (mot par mot, utile pour l'EDL)
        """
        # Import paresseux: whisper coûte cher à importer.
        from app.processing import transcribe as v1
        import whisper  # noqa: F401  (sanity check — laisse échouer tôt si manquant)

        model = v1._get_model(self.model_name)

        logger.info(f"[transcription_service] transcribing {video_path} (model={self.model_name})")
        result = model.transcribe(
            video_path,
            verbose=False,
            word_timestamps=self.word_timestamps,
        )

        segments: list[TranscriptSegment] = []
        for seg in result.get("segments", []):
            words: list[Word] = []
            for w in seg.get("words", []) or []:
                # Whisper word object: {word, start, end, probability}
                words.append(
                    Word(
                        text=w.get("word", "").strip(),
                        start=float(w.get("start", seg.get("start", 0.0))),
                        end=float(w.get("end", seg.get("end", 0.0))),
                        confidence=w.get("probability"),
                    )
                )
            segments.append(
                TranscriptSegment(
                    start=float(seg.get("start", 0.0)),
                    end=float(seg.get("end", 0.0)),
                    text=str(seg.get("text", "")).strip(),
                    words=words,
                )
            )

        transcript = Transcript(
            language=result.get("language", "unknown"),
            text=str(result.get("text", "")).strip(),
            segments=segments,
        )

        # Compat v1 — transcript.json et subtitles.srt
        v1._write_srt(result.get("segments", []), os.path.join(output_dir, "subtitles.srt"))
        with open(os.path.join(output_dir, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump(transcript.to_dict(), f, ensure_ascii=False, indent=2)

        # Words-only file (utile pour debug + EDL)
        with open(os.path.join(output_dir, "words.json"), "w", encoding="utf-8") as f:
            json.dump([w.to_dict() for w in transcript.words], f, ensure_ascii=False, indent=2)

        logger.info(
            f"[transcription_service] done: lang={transcript.language} "
            f"segments={len(transcript.segments)} words={len(transcript.words)}"
        )
        return transcript
