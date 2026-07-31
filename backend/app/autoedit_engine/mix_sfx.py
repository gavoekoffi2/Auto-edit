"""
STEP 10 — SFX mix + loudnorm.

Generates the 19-sound numpy library (once), delays each cue to its time with a
-60 ms lead (to anticipate the attack), mixes everything under the voice, then
normalises to -14 LUFS / -1 dBTP / LRA 11.

    [i:a]adelay=ms|ms,volume=g[si]
    [0:a][s1]..[sN]amix=inputs=N+1:normalize=0[mix]
    [mix]loudnorm=I=-14:TP=-1:LRA=11[outa]

Usage:
    python -m engine.mix_sfx composite_nosfx.mp4 sfx_cues.json \
        -o composite_withsfx.mp4 [--sfxdir sfx]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

from . import config
from . import ffmpeg_utils
from . import sfx_lib


def _delay_ms(t: float, offset: float = config.SFX_OFFSET) -> int:
    return max(0, int(round((t + offset) * 1000)))


def _build_filter(cues: List[dict], sfx_index: Dict[str, str]) -> tuple[str, list]:
    """Return (filter_complex, ordered list of input paths after the video).

    Humanisation: each cue gets a deterministic micro pitch/gain variation
    (asetrate resample + volume) so a sound that recurs — camera_flash, pops —
    never plays back twice exactly the same. This is what separates a "static"
    SFX pass from a professional one.

    Un fichier SFX n'est ouvert QU'UNE FOIS, quel que soit le nombre de fois où
    il est joué: chaque son est dupliqué dans le graphe par ``asplit``. Avant,
    une entrée ffmpeg était ajoutée PAR cue — un montage long (des centaines de
    cues) dépassait la limite d'entrées/descripteurs et le mixage échouait,
    emportant tout le rendu. La bibliothèque ne compte que 19 sons: le nombre
    d'entrées est désormais borné par 19, pas par la durée de la vidéo.
    """
    inputs: List[str] = []
    input_index: Dict[str, int] = {}
    parts: List[str] = []
    sfx_labels: List[str] = []

    # 1) Une entrée par SON DISTINCT réellement utilisé, dédupliquée.
    usage: Dict[str, int] = {}
    playable = [c for c in cues if sfx_index.get(c.get("sfx")) is not None]
    for cue in playable:
        usage[cue["sfx"]] = usage.get(cue["sfx"], 0) + 1
    for name in usage:
        inputs.append(sfx_index[name])
        input_index[name] = len(inputs)         # 0 = la vidéo
    # 2) asplit: autant de copies que d'occurrences (une seule copie = pas de
    #    asplit, le flux d'entrée est utilisé directement).
    copy_labels: Dict[str, List[str]] = {}
    for name, count in usage.items():
        idx = input_index[name]
        if count == 1:
            copy_labels[name] = [f"[{idx}:a]"]
            continue
        labels = [f"[c{idx}_{k}]" for k in range(count)]
        parts.append(f"[{idx}:a]asplit={count}{''.join(labels)}")
        copy_labels[name] = labels
    copy_cursor: Dict[str, int] = {name: 0 for name in usage}

    sr = config.SFX_SAMPLE_RATE
    seen_count: Dict[str, int] = {}
    for ci, cue in enumerate(playable, start=1):
        label = f"[s{ci}]"

        # The real light-leak asset must play in lockstep with its own video
        # overlay (no anticipation offset, no pitch/speed "humanisation" —
        # that would shift its duration and desync it from the light passage).
        is_light_leak = cue["sfx"] == "light_leak_original"

        # Variation index advances per occurrence OF THE SAME sound, so the
        # first hit of every sound stays at its designed pitch.
        k = seen_count.get(cue["sfx"], 0)
        seen_count[cue["sfx"]] = k + 1
        if is_light_leak:
            ms = _delay_ms(float(cue["t"]), offset=0.0)
            pitch = 1.0
            gain = config.SFX_BUS_GAIN
        else:
            ms = _delay_ms(float(cue["t"]))
            pitch = config.SFX_PITCH_VARIANTS[k % len(config.SFX_PITCH_VARIANTS)]
            gain = config.SFX_BUS_GAIN * config.SFX_GAIN_VARIANTS[k % len(config.SFX_GAIN_VARIANTS)]

        src = copy_labels[cue["sfx"]][copy_cursor[cue["sfx"]]]
        copy_cursor[cue["sfx"]] += 1
        chain = src
        if abs(pitch - 1.0) > 1e-3:
            chain += f"asetrate={int(round(sr * pitch))},aresample={sr},"
        chain += f"adelay={ms}|{ms},volume={gain:.3f}{label}"
        parts.append(chain)
        sfx_labels.append(label)

    if not sfx_labels:                           # no SFX -> just loudnorm voice
        parts.append(f"[0:a]{config.LOUDNORM}[outa]")
        return ";".join(parts), inputs

    if len(sfx_labels) + 1 <= max(2, int(config.SFX_MIX_BATCH)):
        # Sous le seuil: exactement l'ancien graphe (une seule passe amix).
        parts.append(
            "[0:a]" + "".join(sfx_labels) +
            f"amix=inputs={len(sfx_labels) + 1}:normalize=0:duration=first"
            ":dropout_transition=0[mix]"
        )
    else:
        # Bus SFX mixé en cascade, PUIS ajouté à la voix. La voix reste la
        # référence de durée (`duration=first`) — un SFX en fin de montage ne
        # peut donc pas allonger la piste au-delà de l'image.
        parts.append(_amix_tree(sfx_labels, "sfxbus"))
        parts.append(
            "[0:a][sfxbus]amix=inputs=2:normalize=0:duration=first"
            ":dropout_transition=0[mix]"
        )
    parts.append(f"[mix]{config.LOUDNORM}[outa]")
    return ";".join(parts), inputs


def _amix_tree(labels: List[str], out_label: str) -> str:
    """Mixe *labels* en CASCADE de `amix` bornés à ``config.SFX_MIX_BATCH``.

    `amix` avec des centaines d'entrées alloue un buffer par entrée et sature la
    mémoire du worker sur les montages longs. Un arbre de sommes bornées donne
    le MÊME signal (avec `normalize=0`, amix est une somme, donc associative) à
    coût mémoire constant.
    """
    batch = max(2, int(config.SFX_MIX_BATCH))
    stages: List[str] = []
    current = list(labels)
    level = 0
    while len(current) > batch:
        nxt: List[str] = []
        for i in range(0, len(current), batch):
            chunk = current[i:i + batch]
            if len(chunk) == 1:
                nxt.append(chunk[0])
                continue
            label = f"[mx{level}_{i // batch}]"
            stages.append(
                "".join(chunk) +
                f"amix=inputs={len(chunk)}:normalize=0:duration=longest"
                f":dropout_transition=0{label}"
            )
            nxt.append(label)
        current, level = nxt, level + 1
    if len(current) == 1:
        stages.append(f"{current[0]}anull[{out_label}]")
    else:
        stages.append(
            "".join(current) +
            f"amix=inputs={len(current)}:normalize=0:duration=longest"
            f":dropout_transition=0[{out_label}]"
        )
    return ";".join(stages)


def mix(video: str, cues_path: str, out_path: str, sfxdir: str = "sfx") -> str:
    ffmpeg_utils.ensure_ffmpeg()
    with open(cues_path, "r", encoding="utf-8") as fh:
        cues = json.load(fh)

    paths = sfx_lib.build_library(sfxdir)         # the 19 sounds (48 kHz mono)

    filt, inputs = _build_filter(cues, paths)
    cmd: List[str] = [ffmpeg_utils.FFMPEG, "-y", "-i", video]
    for p in inputs:
        cmd += ["-i", p]
    ffmpeg_utils.run_filter(
        cmd, filt,
        ["-map", "0:v", "-map", "[outa]",
         "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         out_path],
        complex_graph=True,
    )
    print(f"[mix_sfx] {len(cues)} SFX cues ({len(inputs)} sons distincts) mixés, "
          f"loudnorm -14 LUFS -> {out_path}")
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Mix SFX + loudnorm -> composite_withsfx.mp4")
    ap.add_argument("video", help="composite_nosfx.mp4")
    ap.add_argument("cues", help="sfx_cues.json")
    ap.add_argument("-o", "--out", default="composite_withsfx.mp4")
    ap.add_argument("--sfxdir", default="sfx")
    ap.add_argument("--print-filter", action="store_true")
    args = ap.parse_args(argv)
    if args.print_filter:
        cues = json.load(open(args.cues, encoding="utf-8"))
        # use dummy paths just to render the filter graph
        idx = {n: f"{args.sfxdir}/{n}.wav" for n in config.SFX_NAMES}
        filt, _ = _build_filter(cues, idx)
        print(filt)
        return 0
    mix(args.video, args.cues, args.out, sfxdir=args.sfxdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
