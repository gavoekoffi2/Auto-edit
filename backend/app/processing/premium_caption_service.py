"""Premium word-level captions for AutoEdit Pipeline V2.

Generates ASS subtitles inspired by Captions.ai/Reels edits:
- no heavy black rectangle hiding the video;
- bold outlined typography;
- 3-5 word chunks;
- active word highlighted in cyan/yellow;
- per-word pop feel via rapid event changes and subtle fade.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from app.processing.types import Transcript, Word


@dataclass
class PremiumCaptionConfig:
    width: int = 1080
    height: int = 1920
    max_words_per_line: int = 4
    max_chunk_duration: float = 2.2
    min_chunk_duration: float = 0.45
    margin_v: int = 360
    font_name: str = "Arial"
    base_font_size: int = 82
    active_font_size: int = 96
    active_colors: tuple[str, ...] = ("&H002CF7FF", "&H0000E5FF", "&H006DFF7A")  # cyan, yellow, green


class PremiumCaptionService:
    def __init__(self, config: PremiumCaptionConfig | None = None):
        self.config = config or PremiumCaptionConfig()

    def write_ass(self, transcript: Transcript, out_path: str) -> str | None:
        words = [w for w in transcript.words if (w.text or "").strip() and w.end > w.start]
        if not words:
            return None

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        chunks = self._chunk_words(words)
        cfg = self.config
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {cfg.width}",
            f"PlayResY: {cfg.height}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            (
                f"Style: Premium,{cfg.font_name},{cfg.base_font_size},&H00FFFFFF,&H000000FF,"
                "&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,2,2,70,70,"
                f"{cfg.margin_v},1"
            ),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        for chunk_i, chunk in enumerate(chunks):
            c_start = max(0.0, chunk[0].start - 0.03)
            c_end = max(c_start + cfg.min_chunk_duration, chunk[-1].end + 0.05)
            for active_i, active in enumerate(chunk):
                start = max(c_start, active.start - 0.02)
                # Keep current line until the next word starts, then update highlight.
                if active_i + 1 < len(chunk):
                    end = max(start + 0.10, chunk[active_i + 1].start)
                else:
                    end = c_end
                text = self._format_chunk(chunk, active_i, chunk_i)
                lines.append(
                    f"Dialogue: 10,{_ass_time(start)},{_ass_time(end)},Premium,,0,0,0,,{{\\fad(45,45)}}{text}"
                )

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return out_path

    def _chunk_words(self, words: list[Word]) -> list[list[Word]]:
        cfg = self.config
        chunks: list[list[Word]] = []
        current: list[Word] = []
        for w in words:
            clean = _clean_word(w.text)
            if not clean:
                continue
            ww = Word(text=clean, start=w.start, end=w.end, confidence=w.confidence)
            if not current:
                current = [ww]
                continue
            duration_if_added = ww.end - current[0].start
            sentence_break = bool(re.search(r"[.!?…]$", current[-1].text))
            if (
                len(current) >= cfg.max_words_per_line
                or duration_if_added > cfg.max_chunk_duration
                or sentence_break
            ):
                chunks.append(current)
                current = [ww]
            else:
                current.append(ww)
        if current:
            chunks.append(current)
        return chunks

    def _format_chunk(self, chunk: list[Word], active_index: int, chunk_index: int) -> str:
        cfg = self.config
        active_color = cfg.active_colors[chunk_index % len(cfg.active_colors)]
        parts: list[str] = []
        for i, w in enumerate(chunk):
            text = _escape_ass_text(_clean_word(w.text).upper())
            if i == active_index:
                # Pop/highlight active word. Border remains black for readability.
                parts.append(
                    f"{{\\c{active_color}\\fs{cfg.active_font_size}\\fscx108\\fscy108}}{text}{{\\rPremium}}"
                )
            else:
                parts.append(text)
        return " ".join(parts)


def _clean_word(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _escape_ass_text(text: str) -> str:
    return text.replace("{", "").replace("}", "").replace("\n", r"\N")


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
