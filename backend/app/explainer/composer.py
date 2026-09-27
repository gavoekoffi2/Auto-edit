"""Storyboard + voix minutée + template → page HTML autonome (window.seek)."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .schema import Storyboard
from .templates import SCENE_CATALOG, resolve_template
from .tts import VoiceTrack

WEB = Path(__file__).resolve().parent / "web"
FONTS = ["Anton", "Bebas", "DMSerif", "Poppins-500", "Poppins-700", "Poppins-800"]


def build_shots(board: Storyboard, voice: VoiceTrack) -> list[dict[str, Any]]:
    """Regroupe les phrases en plans: une phrase dont la scène vaut « continue »
    prolonge le plan précédent (ex: écran partagé sur 3 phrases)."""
    shots: list[dict[str, Any]] = []
    for i, beat in enumerate(board.beats):
        start, end = voice.lines[i]
        words = [{"w": w.w, "s": w.s, "e": w.e} for w in (voice.line_words[i] if i < len(voice.line_words) else [])]
        stype = (beat.scene or {}).get("type") or "continue"
        if stype == "continue" and shots:
            sh = shots[-1]
            sh["speechEnd"] = end; sh["words"].extend(words); sh["text"] += " " + beat.text
            continue
        if stype == "continue" or stype not in SCENE_CATALOG:
            beat.scene = {"type": "title_slam", "title": beat.text}
            stype = "title_slam"
        tone = beat.scene.get("tone") or SCENE_CATALOG[stype]["tone"]
        shots.append({"start": start, "speechEnd": end, "words": words, "text": beat.text,
                      "scene": beat.scene, "tone": tone})
    for i, sh in enumerate(shots):
        sh["start"] = 0.0 if i == 0 else round(max(0.0, sh["start"] - 0.12), 3)
    for i, sh in enumerate(shots):
        sh["end"] = round(shots[i + 1]["start"], 3) if i + 1 < len(shots) else round(voice.duration, 3)
    return shots


def compose_html(board: Storyboard, voice: VoiceTrack, *, template_id: str, brand_color: str | None = None,
                 brand: str = "") -> tuple[str, dict[str, Any]]:
    tpl = resolve_template(template_id, brand_color)
    shots = build_shots(board, voice)
    story = {"duration": round(voice.duration, 3), "template": tpl, "shots": shots, "brand": brand}
    html = (WEB / "page.html").read_text(encoding="utf-8")
    for f in FONTS:
        html = html.replace(f"__FONT_{f}__", base64.b64encode((WEB / "fonts" / f"{f}.woff2").read_bytes()).decode())
    head = {"Anton": "'Anton'", "Bebas": "'Bebas'", "DMSerif": "'DMSerif'"}.get(tpl.get("head_font", "Anton"), "'Anton'")
    html = (html.replace("__HEAD_FONT__", head).replace("__ACCENT__", tpl["colors"]["accent"])
                .replace("__RADIUS__", str(tpl.get("radius", 36)))
                .replace("__STORY__", json.dumps(story, ensure_ascii=False).replace("</", "<\\/"))
                .replace("__ENGINE__", (WEB / "engine.js").read_text(encoding="utf-8")))
    return html, story
