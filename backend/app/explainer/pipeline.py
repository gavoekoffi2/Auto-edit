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
