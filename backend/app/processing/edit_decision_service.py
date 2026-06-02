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
import re
from difflib import SequenceMatcher
from typing import Iterable

from app.processing.types import Cut, EditDecisionList, SilenceRange, Transcript, TranscriptSegment, Word

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
        repetition_similarity_threshold: float = 0.86,
        repetition_window_s: float = 45.0,
        low_confidence_threshold: float = 0.32,
        min_low_confidence_words: int = 2,
    ):
        # Défaut: union FR + EN
        self.filler_words: set[str] = filler_words or (
            DEFAULT_FILLER_WORDS_FR | DEFAULT_FILLER_WORDS_EN
        )
        self.max_silence_keep = max_silence_keep
        self.boundary_pad = boundary_pad
        self.repetition_similarity_threshold = repetition_similarity_threshold
        self.repetition_window_s = repetition_window_s
        self.low_confidence_threshold = low_confidence_threshold
        self.min_low_confidence_words = min_low_confidence_words

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
        smart_drop_ranges = self._detect_repetition_ranges(transcript) + self._detect_low_confidence_ranges(transcript)
        cuts = self._split_on_silences(cuts, long_silences)
        cuts = self._apply_drop_ranges(cuts, smart_drop_ranges)

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
                "repetition_ranges_count": sum(1 for r in smart_drop_ranges if r.reason == "repetition"),
                "low_confidence_ranges_count": sum(1 for r in smart_drop_ranges if r.reason == "low_confidence"),
                "smart_drop_ranges": [r.to_dict() for r in smart_drop_ranges],
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
    def _detect_repetition_ranges(self, transcript: Transcript) -> list[SilenceRange]:
        """Detect near-duplicate sentence/segment repetitions and drop later takes.

        This is the AutoEdit equivalent of the user's requested "video-use"
        editorial intelligence: transcript-aware analysis decides which take is
        repeated, while FFmpeg later applies the cut precisely.
        """
        ranges: list[SilenceRange] = []
        seen: list[tuple[float, float, str]] = []
        for seg in transcript.segments:
            normalized = self._normalize_segment_text(seg)
            if len(normalized.split()) < 3:
                continue
            for prev_start, _prev_end, prev_text in reversed(seen[-12:]):
                if seg.start - prev_start > self.repetition_window_s:
                    continue
                if SequenceMatcher(None, prev_text, normalized).ratio() >= self.repetition_similarity_threshold:
                    ranges.append(
                        SilenceRange(
                            start=max(0.0, seg.start - self.boundary_pad),
                            end=max(seg.start, seg.end + self.boundary_pad),
                            reason="repetition",
                        )
                    )
                    break
            seen.append((seg.start, seg.end, normalized))
        return self._merge_ranges(ranges)

    def _detect_low_confidence_ranges(self, transcript: Transcript) -> list[SilenceRange]:
        """Drop segments Whisper itself considers unreliable.

        Low-confidence spans often correspond to mumbled, noisy, or bad takes.
        We only drop when at least a few words have confidence metadata to avoid
        deleting content from providers that do not expose word confidence.
        """
        ranges: list[SilenceRange] = []
        for seg in transcript.segments:
            confident_words = [w for w in seg.words if w.confidence is not None]
            if len(confident_words) < self.min_low_confidence_words:
                continue
            avg = sum(float(w.confidence or 0.0) for w in confident_words) / len(confident_words)
            if avg <= self.low_confidence_threshold:
                ranges.append(
                    SilenceRange(
                        start=max(0.0, seg.start - self.boundary_pad),
                        end=max(seg.start, seg.end + self.boundary_pad),
                        reason="low_confidence",
                    )
                )
        return self._merge_ranges(ranges)

    def _normalize_segment_text(self, seg: TranscriptSegment) -> str:
        text = " ".join(w.text for w in seg.words) if seg.words else seg.text
        tokens = [
            _normalize(tok)
            for tok in re.findall(r"[\wÀ-ÿ'-]+", text.lower())
        ]
        return " ".join(t for t in tokens if t and t not in self.filler_words)

    def _merge_ranges(self, ranges: list[SilenceRange]) -> list[SilenceRange]:
        if not ranges:
            return []
        merged: list[SilenceRange] = []
        for r in sorted(ranges, key=lambda x: (x.start, x.end)):
            if not merged or r.start > merged[-1].end + 0.03 or r.reason != merged[-1].reason:
                merged.append(r)
            else:
                merged[-1] = SilenceRange(
                    start=merged[-1].start,
                    end=max(merged[-1].end, r.end),
                    reason=r.reason,
                )
        return merged

    def _apply_drop_ranges(self, cuts: list[Cut], ranges: list[SilenceRange]) -> list[Cut]:
        if not ranges:
            return cuts
        result = cuts
        for drop in sorted(ranges, key=lambda x: x.start):
            next_result: list[Cut] = []
            for cut in result:
                if not cut.keep or drop.end <= cut.source_start or drop.start >= cut.source_end:
                    next_result.append(cut)
                    continue
                if cut.source_start < drop.start:
                    next_result.append(
                        Cut(cut.source_start, max(cut.source_start, drop.start), True, cut.reason, cut.text)
                    )
                next_result.append(
                    Cut(
                        source_start=max(cut.source_start, drop.start),
                        source_end=min(cut.source_end, drop.end),
                        keep=False,
                        reason=drop.reason,
                    )
                )
                if drop.end < cut.source_end:
                    next_result.append(
                        Cut(min(cut.source_end, drop.end), cut.source_end, True, cut.reason, cut.text)
                    )
            result = next_result
        return result

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
