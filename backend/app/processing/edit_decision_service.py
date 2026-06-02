"""Service de décision de montage — génère une EDL.

Inspiré de `browser-use/video-use`: à partir d'un `Transcript` mot-par-mot
et de plages silencieuses, on produit une liste de `Cut` (keep/drop) en:
  - supprimant les silences trop longs;
  - supprimant les "filler words" français/anglais courants;
  - alignant les coupes sur les frontières de mots pour ne pas couper en plein son.

Pas de LLM pour la phase 1. Une future v2.1 pourra injecter un `--re-evaluate`
via LLM pour scorer chaque cut.
"""
from __future__ import annotations

import logging
from typing import Iterable

from app.processing.types import Cut, EditDecisionList, SilenceRange, Transcript, Word

logger = logging.getLogger(__name__)


# Liste minimale, extensible via params. Insensible à la casse, comparée sur
# le texte du mot (sans ponctuation).
DEFAULT_FILLER_WORDS_FR = {
    "euh", "euhh", "euhm", "hum", "hmm",
    "bah", "ben", "donc", "voila", "voilà",
    "en fait", "tu vois", "tu sais",
    "genre", "style",
}
DEFAULT_FILLER_WORDS_EN = {
    "uh", "uhh", "um", "umm", "erm",
    "like", "you know", "i mean", "basically",
    "literally", "actually",
}


def _normalize(text: str) -> str:
    return text.strip().lower().strip(".,!?:;…\"'()[]")


class EditDecisionService:
    def __init__(
        self,
        filler_words: set[str] | None = None,
        max_silence_keep: float = 0.3,
        boundary_pad: float = 0.05,
    ):
        # Défaut: union FR + EN
        self.filler_words: set[str] = filler_words or (
            DEFAULT_FILLER_WORDS_FR | DEFAULT_FILLER_WORDS_EN
        )
        self.max_silence_keep = max_silence_keep
        self.boundary_pad = boundary_pad

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def build_edl(
        self,
        source_path: str,
        transcript: Transcript,
        silences: Iterable[SilenceRange],
        total_duration: float,
    ) -> EditDecisionList:
        """Construit l'EDL.

        Stratégie:
          1. Marque chaque mot comme `keep` ou `drop` selon `filler_words`.
          2. Convertit en cuts contigus.
          3. Découpe les cuts contenant un silence > `max_silence_keep`.
          4. Ajuste les bornes sur les frontières de mots (boundary_pad).
        """
        words = transcript.words
        if not words:
            # Pas de transcript exploitable → on garde toute la source.
            return EditDecisionList(
                source_path=source_path,
                cuts=[Cut(0.0, total_duration, keep=True, reason="keep")],
                total_kept_duration=total_duration,
                metadata={"strategy": "passthrough"},
            )

        keep_flags: list[tuple[Word, bool, str]] = []
        for w in words:
            norm = _normalize(w.text)
            if norm in self.filler_words:
                keep_flags.append((w, False, "filler_word"))
            else:
                keep_flags.append((w, True, "keep"))

        # 2. Cuts contigus par flag identique
        cuts: list[Cut] = []
        current_start: float = max(0.0, words[0].start - self.boundary_pad)
        current_keep: bool = keep_flags[0][1]
        current_reason: str = keep_flags[0][2]
        current_text_parts: list[str] = []

        for w, keep, reason in keep_flags:
            if keep == current_keep:
                current_text_parts.append(w.text)
                continue
            # flush
            cuts.append(
                Cut(
                    source_start=current_start,
                    source_end=max(current_start, w.start - self.boundary_pad),
                    keep=current_keep,
                    reason=current_reason,
                    text=" ".join(current_text_parts).strip() or None,
                )
            )
            current_start = max(0.0, w.start - self.boundary_pad)
            current_keep = keep
            current_reason = reason
            current_text_parts = [w.text]

        # dernier flush
        last_end = min(total_duration, words[-1].end + self.boundary_pad)
        cuts.append(
            Cut(
                source_start=current_start,
                source_end=max(current_start, last_end),
                keep=current_keep,
                reason=current_reason,
                text=" ".join(current_text_parts).strip() or None,
            )
        )

        # 3. Casse les cuts qui contiennent un silence interne trop long.
        long_silences = [s for s in silences if (s.end - s.start) > self.max_silence_keep]
        cuts = self._split_on_silences(cuts, long_silences)

        # 4. Fusionne les cuts adjacents de même flag (boundary pad peut créer
        # de mini-cuts).
        cuts = self._merge_adjacent(cuts)

        total_kept = sum(c.duration for c in cuts if c.keep)
        edl = EditDecisionList(
            source_path=source_path,
            cuts=cuts,
            total_kept_duration=round(total_kept, 3),
            metadata={
                "strategy": "filler+silence",
                "filler_words_used": sorted(self.filler_words),
                "max_silence_keep": self.max_silence_keep,
                "boundary_pad": self.boundary_pad,
                "source_duration": total_duration,
            },
        )
        logger.info(
            "[edit_decision] cuts=%d kept=%d (%.1fs / %.1fs)",
            len(cuts),
            sum(1 for c in cuts if c.keep),
            total_kept,
            total_duration,
        )
        return edl

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _split_on_silences(self, cuts: list[Cut], silences: list[SilenceRange]) -> list[Cut]:
        if not silences:
            return cuts
        result: list[Cut] = []
        for cut in cuts:
            if not cut.keep:
                result.append(cut)
                continue
            inner = [
                s for s in silences
                if s.start > cut.source_start + 0.01 and s.end < cut.source_end - 0.01
            ]
            if not inner:
                result.append(cut)
                continue
            cursor = cut.source_start
            for s in sorted(inner, key=lambda x: x.start):
                if s.start > cursor:
                    result.append(
                        Cut(
                            source_start=cursor,
                            source_end=s.start,
                            keep=True,
                            reason="keep",
                            text=cut.text,
                        )
                    )
                result.append(
                    Cut(
                        source_start=s.start,
                        source_end=s.end,
                        keep=False,
                        reason="silence",
                    )
                )
                cursor = s.end
            if cursor < cut.source_end:
                result.append(
                    Cut(
                        source_start=cursor,
                        source_end=cut.source_end,
                        keep=True,
                        reason="keep",
                        text=cut.text,
                    )
                )
        return result

    def _merge_adjacent(self, cuts: list[Cut]) -> list[Cut]:
        if not cuts:
            return cuts
        merged: list[Cut] = [cuts[0]]
        for cut in cuts[1:]:
            last = merged[-1]
            if (
                last.keep == cut.keep
                and last.reason == cut.reason
                and abs(cut.source_start - last.source_end) < 0.01
            ):
                merged[-1] = Cut(
                    source_start=last.source_start,
                    source_end=cut.source_end,
                    keep=last.keep,
                    reason=last.reason,
                    text=(last.text or "") + " " + (cut.text or "") if (last.text or cut.text) else None,
                )
            else:
                merged.append(cut)
        return merged
