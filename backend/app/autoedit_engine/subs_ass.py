"""
STEP 11 — Animated subtitles (ASS / libass).

PlayRes 1080x1920, captions centred at y ~ 1500 (clear of the overlays above
and the TikTok UI below).  Word-level timestamps come from _vu.json and are
remapped to OUTPUT time through the EDL ranges (s2o); words inside cuts are
dropped.

Look:
  * chunks of 2-3 words
  * the active word switches to the highlight colour and zooms to hl_scale=145%
    (mandatory — 115-125 was too subtle)
  * each chunk pops in from 40% -> 100% (\\fscx\\fscy + \\t)
  * 5 selectable templates (tiktok_yellow / neon_pop / bold_box / gold_lux /
    bangers_fun)

Usage:
    python -m engine.subs_ass edl.json -o master.ass [--template tiktok_yellow]
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import config
from .timeline import s2o

HOLD = 0.12          # seconds the last word of a chunk lingers
GAP_BREAK = 0.45     # start a new chunk if the pause before the next word exceeds this
POPIN_MS = 130       # pop-in duration (matches the 0.13 s overlay fade-in)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    cs = int(round((s - int(s)) * 100))
    s = int(s)
    if cs == 100:
        cs = 0
        s += 1
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _c(color8: str) -> str:
    """Style colour '&H00BBGGRR' -> inline override '&HBBGGRR&'."""
    hexpart = color8.replace("&H", "").replace("&", "")
    return "&H" + hexpart[-6:] + "&"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").strip()


def output_words(vu: dict, ranges: List[dict]) -> List[dict]:
    """Flatten words with OUTPUT timestamps (words inside cuts are dropped)."""
    out: List[dict] = []
    for seg in vu.get("segments", []):
        for w in seg.get("words", []):
            o_start = s2o(float(w["start"]), ranges)
            if o_start is None:
                continue
            o_end = s2o(float(w["end"]), ranges)
            if o_end is None or o_end <= o_start:
                o_end = o_start + (float(w["end"]) - float(w["start"]))
            text = _escape(w["word"])
            if text:
                out.append({"word": text, "start": o_start, "end": o_end})
    out.sort(key=lambda w: w["start"])
    return out


def chunk_words(words: List[dict]) -> List[List[dict]]:
    """Group into chunks of 2-3 words, breaking on long pauses / punctuation."""
    chunks: List[List[dict]] = []
    cur: List[dict] = []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["start"] - w["end"]) if nxt else 0.0
        ends_sentence = w["word"][-1:] in ".!?…"
        if (len(cur) >= config.SUBS_CHUNK_MAX
                or (len(cur) >= config.SUBS_CHUNK_MIN and (gap > GAP_BREAK or ends_sentence))
                or nxt is None):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


# --------------------------------------------------------------------------- #
# ASS building
# --------------------------------------------------------------------------- #
def _style_line(tpl: dict) -> str:
    border_style = 3 if tpl.get("box") else 1
    back = "&H64000000" if tpl.get("box") else "&H00000000"
    return (
        "Style: Main,{font},{size},{primary},{primary},{outline},{back},"
        "{bold},0,0,0,100,100,0,0,{bs},{ow},{shadow},5,60,60,60,1"
    ).format(
        font=tpl["font"], size=tpl["size"], primary=tpl["primary"],
        outline=tpl["outline"], back=back, bold=tpl.get("bold", 0),
        bs=border_style, ow=tpl["outline_w"], shadow=tpl.get("shadow", 0),
    )


def _header(tpl: dict) -> str:
    return "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {config.WIDTH}",
        f"PlayResY: {config.HEIGHT}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
         "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
         "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
         "MarginL, MarginR, MarginV, Encoding"),
        _style_line(tpl),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])


def _word_state(chunk: List[dict], active: int, popin: bool, tpl: dict) -> str:
    """Build the Text field for one karaoke state of a chunk.

    Template flags (all optional):
      * ``progressive`` + ``future``: spoken words keep the primary colour and
        upcoming words are dimmed (Captions-AI pill look) instead of the
        default "only the active word changes colour".
      * ``uppercase``: render every word in capitals (hype/Beast look).
      * ``glow``: the active word gets a soft coloured glow (\\blur + border).
    """
    primary = _c(tpl["primary"])
    highlight = _c(tpl["highlight"])
    future = _c(tpl["future"]) if tpl.get("future") else None
    progressive = bool(tpl.get("progressive")) and future is not None
    hl = tpl["hl_scale"]
    pre = f"{{\\pos({config.WIDTH // 2},{config.ZONE_SUBS_Y})}}"
    parts: List[str] = []
    for j, w in enumerate(chunk):
        is_active = j == active
        if progressive:
            # spoken (j < active): primary — active: highlight — upcoming: dimmed
            color = highlight if is_active else (primary if j < active else future)
        else:
            color = highlight if is_active else primary
        target = hl if is_active else 100
        glow = ""
        if is_active and tpl.get("glow"):
            glow = f"\\3c{highlight}\\bord{tpl.get('outline_w', 4) + 2}\\blur3"
        if popin:
            ov = (f"{{\\1c{color}{glow}\\fscx{config.SUBS_POPIN_FROM}\\fscy{config.SUBS_POPIN_FROM}"
                  f"\\t(0,{POPIN_MS},\\fscx{target}\\fscy{target})}}")
        else:
            ov = f"{{\\1c{color}{glow}\\fscx{target}\\fscy{target}}}"
        word = w["word"].upper() if tpl.get("uppercase") else w["word"]
        parts.append(ov + word + "{\\r}")
    return pre + " ".join(parts)


def build_ass(vu: dict, ranges: List[dict], template: str = config.DEFAULT_TEMPLATE) -> str:
    tpl = config.ASS_TEMPLATES.get(template, config.ASS_TEMPLATES[config.DEFAULT_TEMPLATE])
    lines = [_header(tpl)]

    words = output_words(vu, ranges)
    chunks = chunk_words(words)
    for ci, chunk in enumerate(chunks):
        next_start = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else None
        for i, w in enumerate(chunk):
            st = w["start"]
            if i + 1 < len(chunk):
                en = chunk[i + 1]["start"]
            else:
                en = w["end"] + HOLD
                if next_start is not None:        # don't overlap the next chunk
                    en = min(en, next_start)
            if en <= st:
                en = st + 0.1
            text = _word_state(chunk, active=i, popin=(i == 0), tpl=tpl)
            lines.append(
                f"Dialogue: 0,{_ass_time(st)},{_ass_time(en)},Main,,0,0,0,,{text}"
            )
    return "\n".join(lines) + "\n"


def generate(edl_path: str, out_path: str, template: str = config.DEFAULT_TEMPLATE) -> str:
    with open(edl_path, "r", encoding="utf-8") as fh:
        edl = json.load(fh)
    vu = json.load(open(edl["transcripts_vu"], encoding="utf-8"))
    ass = build_ass(vu, edl["ranges"], template=template)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(ass)
    n_dialogue = ass.count("\nDialogue:")
    print(f"[subs_ass] template={template}, {n_dialogue} karaoke states -> {out_path}")
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Animated ASS subtitles (karaoke, hl_scale=145)")
    ap.add_argument("edl", help="edl.json")
    ap.add_argument("-o", "--out", default="master.ass")
    ap.add_argument("--template", default=config.DEFAULT_TEMPLATE,
                    choices=list(config.ASS_TEMPLATES.keys()))
    args = ap.parse_args(argv)
    generate(args.edl, args.out, template=args.template)
    return 0


if __name__ == "__main__":
    sys.exit(main())
