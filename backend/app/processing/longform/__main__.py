"""Lance le moteur YouTube long en ligne de commande.

    cd backend
    python -m app.processing.longform VIDEO.mp4 --out rendu/ [--style auto]
        [--vu transcript_vu.json] [--music musique.mp3] [--no-popups]
        [--no-cards] [--no-captions] [--no-zoom] [--no-sfx] [--no-music]
        [--no-llm] [--keep]

Transcription : ElevenLabs Scribe si ELEVENLABS_API_KEY est défini, sinon
Whisper local. Titres de chapitres par l'IA si OPENROUTER_API_KEY est défini.
Écrit ``youtube_long_final.mp4``, ``chapitres.txt`` et ``rapport_montage.json``.
"""
from __future__ import annotations

import argparse
import json
import sys

from .pipeline import run_longform
from .styles import STYLES


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.processing.longform",
                                 description="Montage automatique d'une vidéo YouTube longue")
    ap.add_argument("video")
    ap.add_argument("--out", required=True, help="dossier de sortie")
    ap.add_argument("--mode", default="youtube_long",
                    choices=["youtube_long", "youtube_long_sobre", "youtube_long_energie"])
    ap.add_argument("--style", choices=["auto", *STYLES], help="force un style")
    ap.add_argument("--vu", help="transcript mot-à-mot déjà prêt (format _vu.json)")
    ap.add_argument("--music", help="fichier ou dossier de musique de fond")
    ap.add_argument("--language", help="code langue (ex: fr)")
    ap.add_argument("--cleanup", default="light", choices=["off", "light", "balanced", "aggressive"],
                    help="relecture IA des phrases redites (OpenRouter)")
    for flag in ("popups", "cards", "captions", "zoom", "sfx", "music-bed", "llm"):
        ap.add_argument(f"--no-{flag}", action="store_true")
    ap.add_argument("--keep", action="store_true", help="garde les fichiers intermédiaires")
    a = ap.parse_args(argv)

    opts = {
        "keyword_popups": not a.no_popups, "chapter_cards": not a.no_cards,
        "dynamic_captions": not a.no_captions, "zoom_cuts": not a.no_zoom,
        "sfx": not a.no_sfx, "music": not a.no_music_bed, "llm_titles": not a.no_llm,
        "cleanup_level": a.cleanup, "keep_intermediates": a.keep,
    }
    if a.style:
        opts["longform_style"] = a.style
    if a.vu:
        opts["transcript_vu"] = a.vu
    if a.music:
        opts["music_path"] = a.music
    if a.language:
        opts["language"] = a.language

    def progress(p: int, msg: str) -> None:
        print(f"[{p:3d}%] {msg}", file=sys.stderr, flush=True)

    res = run_longform(a.video, a.out, mode=a.mode, options=opts, progress_callback=progress)
    lf = res["longform"]
    print(json.dumps({
        "output": res["output_path"], "style": res["style"]["name"],
        "duree": f"{lf['cut']['source_duration']:.0f}s -> {lf['cut']['kept_duration']:.0f}s",
        "coupes": lf["cut"]["removed_counts"], "chapitres": lf["chapters_text"],
        "verifications": {k: lf["checks"][k] for k in
                          ("sync_ok", "av_diff_ms", "loudness_lufs", "loudness_ok")},
        "etapes_en_echec": res["steps_failed"],
    }, ensure_ascii=False, indent=2))
    return 0 if not res["steps_failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
