"""Brief → MP4 publicitaire complet (voix, animation, sons, musique).

    from app.explainer.pipeline import run_explainer
    result = run_explainer(brief_dict, workdir, progress=lambda pct, msg: ...)
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from . import audio, renderer
from .composer import compose_html
from .schema import Brief, Storyboard
from .templates import resolve_template
from .tts import synthesize
from .writer import sanitize, write_storyboard

logger = logging.getLogger(__name__)
Progress = Callable[[int, str], None]


def _noop(p: int, m: str) -> None:  # pragma: no cover
    logger.info("[%s%%] %s", p, m)


def run_explainer(brief: dict[str, Any] | Brief, workdir: str, *, storyboard: Optional[dict[str, Any]] = None,
                  progress: Optional[Progress] = None, fps: int = 30, sub: int = 3,
                  workers: Optional[int] = None) -> dict[str, Any]:
    prog = progress or _noop
    b = brief if isinstance(brief, Brief) else Brief.from_dict(brief)
    wd = Path(workdir); wd.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    from .montages import AUTO, auto_montage, resolve_format, resolve_montage
    b.format = resolve_format(b.format)
    if b.montage == AUTO or not b.montage:
        b.montage, why = auto_montage(b)
        logger.info("montage automatique : %s (%s)", b.montage, why)
    mont = resolve_montage(b.montage, b.format)
    b.montage = mont["id"]
    if mont["engine"] == "impact":
        return _run_impact(b, wd, mont, storyboard, prog, fps=fps, sub=sub, workers=workers, t0=t0)
    if mont["engine"] == "kit":
        return _run_kit(b, wd, mont, storyboard, prog, fps=fps, sub=sub, workers=workers, t0=t0)

    prog(3, "Écriture du script et du storyboard")
    board = sanitize(Storyboard.from_dict(storyboard), b) if storyboard else write_storyboard(b)
    (wd / "storyboard.json").write_text(json.dumps(board.to_dict(), ensure_ascii=False, indent=1))

    prog(12, "Enregistrement de la voix off")
    voice = synthesize([x.text for x in board.beats], str(wd / "voice.wav"), voice=b.voice,
                       pauses=[x.pause_after for x in board.beats])

    prog(20, "Composition des scènes")
    html, story = compose_html(board, voice, template_id=b.template, brand_color=b.brand_color, brand=b.business)
    page = wd / "page.html"; page.write_text(html, encoding="utf-8")
    ev = renderer.events(str(page), str(wd / "events.json"))
    if ev.get("errors"):
        logger.warning("erreurs page: %s", ev["errors"][:3])

    # aperçu (vignette) sur la révélation ou au 1/3
    shots = story["shots"]
    key = next((s for s in shots if s["scene"]["type"] in ("hero_reveal", "split_compare")), shots[min(1, len(shots) - 1)])
    thumb_t = min(story["duration"] - 0.1, (key["start"] + key["speechEnd"]) / 2 + 0.6)
    renderer.stills(str(page), [thumb_t], str(wd / "thumb"))

    prog(25, "Rendu de l'animation")
    renderer.video(str(page), story["duration"], str(wd / "video.mp4"), fps=fps, sub=sub, workers=workers,
                   progress=lambda f: prog(25 + int(63 * f), "Rendu de l'animation"))

    prog(90, "Sound design et mixage")
    tpl = resolve_template(b.template)
    turn = next((s["start"] for s in shots if s["scene"]["type"] in ("hero_reveal", "split_compare", "checklist")), story["duration"] * 0.3)
    audio.mix(str(wd / "voice.wav"), ev.get("events", []), story["duration"], str(wd / "mix.wav"),
              mood=tpl.get("music", "hopeful"), bpm=tpl.get("bpm", 96), turn=turn)

    prog(97, "Export final")
    out = wd / "pub.mp4"
    renderer.mux(str(wd / "video.mp4"), str(wd / "mix.wav"), str(out))
    thumbs = sorted((wd / "thumb").glob("*.png"))
    result = {
        "video_path": str(out),
        "thumbnail_path": str(thumbs[0]) if thumbs else None,
        "duration": round(story["duration"], 2),
        "script": [x.text for x in board.beats],
        "storyboard": board.to_dict(),
        "template": b.template, "angle": board.angle,
        "voice_provider": voice.provider,
        "notes": board.notes,
        "render_seconds": round(time.time() - t0, 1),
    }
    (wd / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    prog(100, "Terminé")
    return result


def _run_impact(b: Brief, wd: Path, mont: dict[str, Any], storyboard: Optional[dict[str, Any]], prog: Progress, *,
                fps: int, sub: int, workers: Optional[int], t0: float) -> dict[str, Any]:
    """Montage « Impact » : problème → agitation → bascule → solution → action."""
    from .composer import compose_impact
    from .impact_writer import sanitize_impact, write_impact

    prog(3, "Écriture du script (problème → solution)")
    board = sanitize_impact(Storyboard.from_dict(storyboard), b) if storyboard else write_impact(b)
    (wd / "storyboard.json").write_text(json.dumps(board.to_dict(), ensure_ascii=False, indent=1))

    prog(12, "Enregistrement de la voix off")
    voice = synthesize([x.text for x in board.beats], str(wd / "voice.wav"), voice=b.voice or "henri",
                       rate=mont.get("voice_rate", "+6%"), pauses=[x.pause_after for x in board.beats],
                       lead=0.25, tail=2.8, max_inner_pause=0.16)

    prog(20, "Composition des scènes")
    kw = [w for w in [b.business, b.offer] + list(b.benefits or []) for w in str(w).split() if len(w) > 3][:20]
    html, story = compose_impact(board, voice, brand=b.business, product_name=b.offer or b.business,
                                 product_image=b.product_image_path or None, logo_path=b.logo_path or None,
                                 accent=b.brand_color, keywords=kw)
    page = wd / "page.html"; page.write_text(html, encoding="utf-8")
    ev = renderer.events(str(page), str(wd / "events.json"))
    if ev.get("errors"):
        logger.warning("erreurs page: %s", ev["errors"][:3])
    # vignette = première image (WhatsApp / réseaux affichent l'image 0)
    renderer.stills(str(page), [0.0], str(wd / "thumb"))

    prog(25, "Rendu de l'animation")
    renderer.video(str(page), story["duration"], str(wd / "video.mp4"), fps=fps, sub=sub, workers=workers,
                   progress=lambda f: prog(25 + int(63 * f), "Rendu de l'animation"))

    prog(90, "Sound design et mixage")
    shots = story["shots"]
    turn = next((s["start"] for s in shots if s["scene"]["type"] in ("pivot", "product_reveal")), story["duration"] * 0.4)
    audio.mix(str(wd / "voice.wav"), ev.get("events", []), story["duration"], str(wd / "mix.wav"),
              mood=mont.get("music", "energetic"), bpm=mont.get("bpm", 100), turn=turn, music_db=-17, sfx_db=-5)

    prog(97, "Export final")
    out = wd / "pub.mp4"
    renderer.mux(str(wd / "video.mp4"), str(wd / "mix.wav"), str(out))
    thumbs = sorted((wd / "thumb").glob("*.png"))
    result = {
        "video_path": str(out), "thumbnail_path": str(thumbs[0]) if thumbs else None,
        "duration": round(story["duration"], 2), "script": [x.text for x in board.beats],
        "storyboard": board.to_dict(), "template": b.template, "montage": mont["id"], "angle": board.angle,
        "voice_provider": voice.provider, "notes": board.notes, "render_seconds": round(time.time() - t0, 1),
    }
    (wd / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    prog(100, "Terminé")
    return result


def _run_kit(b: Brief, wd: Path, mont: dict[str, Any], storyboard: Optional[dict[str, Any]], prog: Progress, *,
             fps: int, sub: int, workers: Optional[int], t0: float) -> dict[str, Any]:
    """Modes « kit » (Studio blanc, Dossier résultat, App 3D, Lifestyle offre, Événement), au format choisi."""
    from .composer import compose_kit
    from .motion_writer import sanitize_motion, write_motion

    mid = mont["id"]
    prog(3, "Écriture du script (problème → solution)")
    board = sanitize_motion(Storyboard.from_dict(storyboard), b, mid) if storyboard else write_motion(b, mid)
    (wd / "storyboard.json").write_text(json.dumps(board.to_dict(), ensure_ascii=False, indent=1))

    prog(12, "Enregistrement de la voix off")
    voice = synthesize([x.text for x in board.beats], str(wd / "voice.wav"), voice=b.voice or "henri",
                       rate=mont.get("voice_rate", "+6%"), pauses=[x.pause_after for x in board.beats],
                       lead=0.25, tail=2.8, max_inner_pause=0.16)

    prog(20, f"Composition des scènes ({mont['name']}, {b.format})")
    kw = [w for w in [b.business, b.offer] + list(b.benefits or []) for w in str(w).split() if len(w) > 3][:20]
    html, story, size = compose_kit(board, voice, montage=mid, fmt=b.format, brand=b.business, product_name=b.offer or b.business,
                                    product_image=b.product_image_path or None, logo_path=b.logo_path or None,
                                    photos=list(b.photo_paths or []), screens=list(b.screen_paths or []),
                                    accent=b.brand_color, keywords=kw)
    page = wd / "page.html"; page.write_text(html, encoding="utf-8")
    ev = renderer.events(str(page), str(wd / "events.json"), size=size)
    if ev.get("errors"):
        logger.warning("erreurs page: %s", ev["errors"][:3])
    renderer.stills(str(page), [0.0], str(wd / "thumb"), size=size)  # vignette = image 0

    prog(25, "Rendu de l'animation")
    renderer.video(str(page), story["duration"], str(wd / "video.mp4"), fps=fps, sub=sub, workers=workers, size=size,
                   progress=lambda f: prog(25 + int(63 * f), "Rendu de l'animation"))

    prog(90, "Sound design et mixage")
    shots = story["shots"]
    turn = next((s["start"] for s in shots if (s["scene"] or {}).get("role") in ("pivot", "reveal")), story["duration"] * 0.4)
    audio.mix(str(wd / "voice.wav"), ev.get("events", []), story["duration"], str(wd / "mix.wav"),
              mood=mont.get("music", "energetic"), bpm=mont.get("bpm", 100), turn=turn, music_db=-17, sfx_db=-5)

    prog(97, "Export final")
    out = wd / "pub.mp4"
    renderer.mux(str(wd / "video.mp4"), str(wd / "mix.wav"), str(out))
    thumbs = sorted((wd / "thumb").glob("*.png"))
    result = {
        "video_path": str(out), "thumbnail_path": str(thumbs[0]) if thumbs else None,
        "duration": round(story["duration"], 2), "script": [x.text for x in board.beats],
        "storyboard": board.to_dict(), "template": b.template, "montage": mid, "format": b.format, "size": list(size),
        "angle": board.angle, "voice_provider": voice.provider, "notes": board.notes, "render_seconds": round(time.time() - t0, 1),
    }
    (wd / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    prog(100, "Terminé")
    return result
