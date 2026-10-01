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


# --------------------------------------------------------------------------- montage « Impact »
def prepare_product(path: str | None, max_w: int = 900) -> dict[str, Any]:
    """Photo produit → {img: data URL, cut: bool}. Fond uni détouré (le produit flotte sur le socle),
    sinon la photo est présentée entière dans un cadre — jamais recadrée au point de couper le produit."""
    import io
    import logging

    if not path or not Path(path).exists():
        return {"img": None, "cut": False}
    try:
        from PIL import Image

        from .brand import _has_real_alpha, detour
        im = Image.open(path); im.load()
        im = im.convert("RGBA") if _has_real_alpha(im) else detour(im)
        a = im.getchannel("A")
        transparent = sum(a.point(lambda v: 1 if v < 20 else 0).getdata()) / (im.width * im.height)
        cut = transparent > 0.08
        if cut:
            bbox = a.point(lambda v: 255 if v > 8 else 0).getbbox()
            if bbox:
                pad = max(4, int(0.03 * max(im.size)))
                x0, y0, x1, y1 = bbox
                im = im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))
        else:
            im = im.convert("RGB")
            side = min(im.size)  # cadre carré centré (la photo garde son sujet au centre)
            l, t = (im.width - side) // 2, (im.height - side) // 2
            im = im.crop((l, t, l + side, t + side))
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "PNG" if cut else "JPEG", **({"optimize": True} if cut else {"quality": 90}))
        mime = "png" if cut else "jpeg"
        return {"img": f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode(), "cut": cut}
    except Exception as e:  # noqa: BLE001 — une photo illisible ne bloque jamais la pub
        logging.getLogger(__name__).warning("photo produit ignorée: %s", e)
        return {"img": None, "cut": False}


def _hex_rgb(c: str) -> tuple[int, int, int]:
    h = (c or "#FFD60A").lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def compose_impact(board: Storyboard, voice: VoiceTrack, *, brand: str = "", product_name: str = "",
                   product_image: str | None = None, logo_path: str | None = None,
                   accent: str | None = None, keywords: list[str] | None = None) -> tuple[str, dict[str, Any]]:
    """Storyboard Impact + voix minutée → page HTML autonome (moteur web/impact.js)."""
    from .brand import prepare_logo
    from .impact_writer import IMPACT_SCENES

    shots: list[dict[str, Any]] = []
    for i, beat in enumerate(board.beats):
        start, end = voice.lines[i]
        words = [{"w": w.w, "s": w.s, "e": w.e} for w in (voice.line_words[i] if i < len(voice.line_words) else [])]
        sc = dict(beat.scene or {})
        if sc.get("type") not in IMPACT_SCENES:
            sc = {"type": "title", "lines": [beat.text]}
        shots.append({"start": start, "speechEnd": end, "words": words, "text": beat.text, "scene": sc})
    for i, sh in enumerate(shots):
        sh["start"] = 0.0 if i == 0 else round(max(0.0, sh["start"] - 0.12), 3)
    for i, sh in enumerate(shots):
        sh["end"] = round(shots[i + 1]["start"], 3) if i + 1 < len(shots) else round(voice.duration, 3)
    acc = accent if accent and len(accent.lstrip("#")) == 6 else "#FFD60A"
    r, g, b = _hex_rgb(acc)
    on_acc = "#09090D" if (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.55 else "#ffffff"
    prod = prepare_product(product_image)
    story = {"duration": round(voice.duration, 3), "shots": shots, "brand": brand,
             "product": {"img": prod["img"], "cut": prod["cut"], "name": product_name or brand},
             "logo": prepare_logo(logo_path) if logo_path else "", "keywords": keywords or []}
    html = (WEB / "impact.html").read_text(encoding="utf-8")
    for f in ["Anton", "Poppins-500", "Poppins-700", "Poppins-800"]:
        html = html.replace(f"__FONT_{f}__", base64.b64encode((WEB / "fonts" / f"{f}.woff2").read_bytes()).decode())
    html = (html.replace("__ACCENT__", acc).replace("__ACCENT_RGB__", f"{r},{g},{b}").replace("__ON_ACCENT__", on_acc)
                .replace("__STORY__", json.dumps(story, ensure_ascii=False).replace("</", "<\\/"))
                .replace("__ENGINE__", (WEB / "impact.js").read_text(encoding="utf-8")))
    return html, story
