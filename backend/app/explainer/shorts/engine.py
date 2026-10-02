"""Moteur « Shorts face caméra » — des rushes bruts à une vidéo TikTok prête à poster.

    rushes (1 à 10 fichiers, filmés dans n'importe quel ordre)
      → transcription mot à mot de chaque rush + suivi du visage
      → découpage en passages (phrases)
      → reprises / faux départs / apartés: détection locale + arbitrage Jev
      → réalisateur LLM: ordre final du récit entre les rushes, chapitres,
        corrections de transcription, cartes animées
      → Jev: thème visuel, cadrage, vérification de chaque carte
      → versets: texte exact Louis Segond 1910 (jamais écrit par l'IA)
      → plans: silences coupés au mot près, zoom alterné à chaque coupe visible,
        recadrage centré sur le visage (fenêtre 4:5 sur fond flouté, ou plein 9:16)
      → habillage: bandeau de chapitre, sous-titres mot à mot, cartes, scènes
        plein écran — rendu par tranches et incrusté
      → voix nettoyée, SFX calés sur chaque animation, musique discrète, -14 LUFS
      → MP4 H.264 1080x1920 30 i/s
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .. import audio, renderer
from ..conf import setting
from . import director, jev, render, takes, timeline
from .rushes import load_rushes

logger = logging.getLogger(__name__)
Progress = Callable[[int, str], None]


def run_shorts(rush_paths: list[str], output_dir: str, *, captions: bool = True, music: bool = True,
               vocabulary: str = "", brand: str = "", language: Optional[str] = None, theme: Optional[str] = None,
               layout: Optional[str] = None, use_llm: bool = True, progress: Optional[Progress] = None,
               workers: Optional[int] = None) -> dict[str, Any]:
    if not rush_paths:
        raise ValueError("aucun rush fourni")
    prog = progress or (lambda p, m: logger.info("[%s%%] %s", p, m))
    wd = Path(output_dir); wd.mkdir(parents=True, exist_ok=True)
    work = wd / "shorts"; work.mkdir(exist_ok=True)
    n = max(1, min(workers or (os.cpu_count() or 2), 8))
    t0 = time.time(); steps: list[str] = []
    jev.reset_usage()

    # 1) transcription + visage
    hint = ", ".join(x for x in [brand, vocabulary] if x) or None
    model = setting("SHORTS_WHISPER_MODEL") or None
    rushes = load_rushes(rush_paths, str(work), language=language, hint=hint, model=model,
                         progress=lambda f, m: prog(2 + int(20 * f), m))
    steps.append("transcription")
    all_units = [u for r in rushes for u in r["units"]]
    if not all_units:
        raise RuntimeError("Aucune parole détectée dans les rushes.")
    lang = next((r["language"] for r in rushes if r.get("language")), "fr") or "fr"

    # 2) reprises et faux départs (Jev, sinon règles)
    prog(24, "Tri des prises (reprises, faux départs)")
    kept, take_report = takes.clean_takes(all_units)
    steps.append("takes")

    # 3) réalisateur (LLM) + décisions (Jev)
    prog(30, "Construction du récit et des animations")
    first = rushes[0]["info"]
    landscape = first["w"] > first["h"]
    hd = min(first["w"], first["h"]) >= 1080
    seed = hashlib.sha1("|".join(f"{p}:{os.path.getsize(p)}" for p in rush_paths).encode()).hexdigest()
    plan = director.direct(kept, language=lang, landscape=landscape, hd=hd, seed=seed, use_llm=use_llm)
    if theme in render.THEMES:
        plan["theme"] = theme
    if layout in ("cadre", "plein"):
        plan["layout"] = layout
    (work / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    steps.append("direction")

    # 4) timeline
    tl = timeline.build(rushes, plan, plan["layout"])
    if not tl["shots"]:
        raise RuntimeError("Rien à garder après le nettoyage des rushes.")
    cues, chapters = timeline.cues(plan, tl)
    groups = timeline.caption_groups(tl["words"]) if captions else []
    (work / "edit.json").write_text(json.dumps({"shots": tl["shots"], "cues": cues, "chapters": chapters}, ensure_ascii=False, indent=1))

    # 5) base 9:16
    prog(34, "Assemblage et recadrage 9:16")
    base = str(work / "base.mov")
    render.render_base(rushes, tl["shots"], plan["layout"], base, n, progress=lambda f: prog(34 + int(14 * f), "Assemblage et recadrage 9:16"))
    dur = tl["duration"]
    steps.append("base")

    # 6) habillage
    prog(49, "Motion design et sous-titres")
    page = render.compose_page({"duration": dur, "layout": plan["layout"], "tag": plan.get("tag") or "",
                                "chapters": chapters, "cues": cues, "groups": groups}, plan["theme"], str(work / "habillage.html"))
    ev = renderer.events(page, str(work / "events.json"))
    if ev.get("errors"):
        logger.warning("erreurs page Shorts: %s", ev["errors"][:3])
    picture = str(work / "picture.mp4")
    render.render_picture(page, base, dur, picture, n, progress=lambda f: prog(50 + int(38 * f), "Motion design et sous-titres"))
    steps.append("motion")

    # 7) son
    prog(89, "Voix, effets sonores et musique")
    voice = render.clean_voice(base, str(work / "voice.wav"))
    mood, bpm = render.THEME_SOUND.get(plan["theme"], ("hopeful", 90))
    mix = str(work / "mix.wav")
    audio.mix(voice, ev.get("events", []), dur, mix, mood=mood, bpm=bpm, turn=dur * 0.3,
              music_db=-26 if music else -120, sfx_db=-10)
    steps.append("sound")

    # 8) export
    prog(95, "Export final")
    out = str(wd / "final_shorts.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", picture, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", out], check=True)
    poster = str(wd / "poster.jpg")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{min(1.5, dur / 3):.2f}", "-i", out, "-frames:v", "1", "-q:v", "3", poster], check=True)
    except subprocess.CalledProcessError:
        poster = ""
    if (setting("SHORTS_KEEP_WORK", "0") or "0") != "1":
        for f in (base, picture, voice):
            try:
                os.unlink(f)
            except OSError:
                pass
    steps.append("export")
    prog(100, "Terminé")
    src_dur = sum(r["info"]["duration"] for r in rushes)
    return {
        "output_path": out, "poster_path": poster, "engine": "shorts", "duration": round(dur, 2),
        "source_duration": round(src_dur, 2), "rushes": len(rushes),
        "layout": plan["layout"], "theme": plan["theme"], "tag": plan.get("tag"),
        "chapters": chapters, "cards": [{"type": c["type"], "t0": round(c["t0"], 2)} for c in cues],
        "takes": {"retake_groups": take_report["retake_groups"], "dropped": len(take_report["dropped"]), "decider": take_report["decider"]},
        "direction": plan.get("info", {}), "jev_usage": dict(jev.USAGE),
        "shots": len(tl["shots"]), "sfx_count": len(ev.get("events", [])),
        "steps_completed": steps, "steps_failed": [], "render_seconds": round(time.time() - t0, 1),
    }


def _main() -> None:  # python -m app.explainer.shorts.engine out_dir rush1.mp4 rush2.mp4 …
    import sys
    logging.basicConfig(level=logging.INFO)
    res = run_shorts(sys.argv[2:], sys.argv[1])
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    _main()
