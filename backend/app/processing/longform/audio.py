"""Son d'une vidéo longue : voix traitée + SFX liés aux visuels + musique.

* la voix est ramenée à −18 LUFS (mesure réelle), filtrée (passe-haut 70 Hz)
  et légèrement compressée ;
* les SFX sont posés sur une piste écrite par blocs d'une minute (mémoire
  bornée même pour une heure), avec variation de hauteur/gain à chaque
  occurrence pour qu'un son ne se répète jamais à l'identique ;
* la musique (si fournie) tourne en boucle sous la voix, baissée
  automatiquement quand la personne parle (sidechain), fondus début/fin ;
* le mix final est normalisé en DEUX passes : −14 LUFS intégré, crête
  vraie ≤ −1 dBTP (norme YouTube).
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import wave
from typing import Dict, List, Optional

import numpy as np

from app.autoedit_engine import ffmpeg_utils

SR = 48000


def measure_loudness(path: str) -> dict:
    """Mesure EBU R128 via le filtre loudnorm (json)."""
    p = subprocess.run(
        [ffmpeg_utils.FFMPEG, "-nostdin", "-hide_banner", "-nostats", "-i", path,
         "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    txt = p.stderr
    s, e = txt.rfind("{"), txt.rfind("}")
    if s < 0:
        return {}
    try:
        return json.loads(txt[s:e + 1])
    except ValueError:
        return {}


def _load_sfx_library(names: List[str], out_dir: str) -> Dict[str, np.ndarray]:
    from app.autoedit_engine import sfx_lib
    os.makedirs(out_dir, exist_ok=True)
    lib: Dict[str, np.ndarray] = {}
    for n in sorted(set(names)):
        try:
            path = sfx_lib.generate(n, out_dir)
        except Exception:  # noqa: BLE001 — un SFX manquant ne bloque rien
            continue
        with wave.open(path, "rb") as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
            if w.getnchannels() > 1:
                x = x.reshape(-1, w.getnchannels()).mean(1)
            sr = w.getframerate()
        if sr != SR and len(x) > 1:
            idx = np.linspace(0, len(x) - 1, int(len(x) * SR / sr))
            x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
        lib[n] = x
    return lib


def _vary(x: np.ndarray, rng: random.Random) -> np.ndarray:
    """Petite variation de hauteur (±4 %) : jamais deux fois le même son."""
    f = rng.uniform(0.96, 1.04)
    n = max(2, int(len(x) / f))
    idx = np.linspace(0, len(x) - 1, n)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


def build_sfx_track(cues: List[dict], duration: float, out_wav: str,
                    work_dir: str, seed: int = 0) -> dict:
    """Écrit la piste SFX (mono 48 kHz) par blocs d'une minute."""
    rng = random.Random(seed)
    lib = _load_sfx_library([c["name"] for c in cues], os.path.join(work_dir, "sfx"))
    placed = []
    for c in cues:
        x = lib.get(c["name"])
        if x is None:
            continue
        y = _vary(x, rng) * (10 ** ((float(c.get("db", -15)) + rng.uniform(-1.0, 1.0)) / 20.0))
        placed.append((int(round(max(0.0, float(c["t"])) * SR)), y))
    total = int(round(duration * SR))
    block = SR * 60
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        for b0 in range(0, max(1, total), block):
            b1 = min(total, b0 + block)
            buf = np.zeros(max(0, b1 - b0), np.float32)
            for s0, y in placed:
                s1 = s0 + len(y)
                if s1 <= b0 or s0 >= b1:
                    continue
                a, b = max(s0, b0), min(s1, b1)
                buf[a - b0:b - b0] += y[a - s0:b - s0]
            w.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())
    counts: Dict[str, int] = {}
    for c in cues:
        counts[c.get("kind", "?")] = counts.get(c.get("kind", "?"), 0) + 1
    return {"cues": len(placed), "by_kind": counts}


def pick_music(music: Optional[str], seed: int) -> Optional[str]:
    """Fichier fourni, ou un titre du dossier LONGFORM_MUSIC_DIR (choisi par la graine)."""
    if music and os.path.isfile(music):
        return music
    d = music if (music and os.path.isdir(music)) else os.environ.get("LONGFORM_MUSIC_DIR", "")
    if d and os.path.isdir(d):
        tracks = sorted(f for f in os.listdir(d)
                        if f.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")))
        if tracks:
            return os.path.join(d, tracks[seed % len(tracks)])
    return None


def mix(voice_wav: str, sfx_wav: Optional[str], music: Optional[str], duration: float,
        out_wav: str, work_dir: str, music_db: float = -30.0) -> dict:
    """Mixe voix + SFX + musique puis normalise en 2 passes (−14 LUFS / −1 dBTP)."""
    v = measure_loudness(voice_wav)
    try:
        vi = float(v.get("input_i", "-23"))
    except (TypeError, ValueError):
        vi = -23.0
    if vi < -60:          # voix quasi muette : pas de gain absurde
        vi = -23.0
    voice_gain = max(-20.0, min(24.0, -18.0 - vi))

    inputs = [ffmpeg_utils.FFMPEG, "-nostdin", "-v", "error", "-y", "-i", voice_wav]
    graph = [f"[0:a]highpass=f=70,volume={voice_gain:.2f}dB,"
             f"acompressor=threshold=-22dB:ratio=2.5:attack=8:release=160:makeup=1.5,"
             f"aformat=channel_layouts=mono,asplit=2[v][vsc]"]
    mix_in = ["[v]"]
    idx = 1
    if sfx_wav and os.path.exists(sfx_wav):
        inputs += ["-i", sfx_wav]
        graph.append(f"[{idx}:a]aformat=channel_layouts=mono[s]")
        mix_in.append("[s]")
        idx += 1
    if music:
        inputs += ["-stream_loop", "-1", "-i", music]
        fade_out = max(0.0, duration - 3.0)
        graph.append(
            f"[{idx}:a]aformat=sample_rates={SR}:channel_layouts=mono,"
            f"atrim=0:{duration:.3f},asetpts=N/SR/TB,volume={music_db:.1f}dB,"
            f"afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out:.3f}:d=3[mraw];"
            f"[mraw][vsc]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=450[m]")
        mix_in.append("[m]")
        idx += 1
    else:
        graph.append("[vsc]anullsink")
    graph.append(f"{''.join(mix_in)}amix=inputs={len(mix_in)}:normalize=0:duration=first,"
                 f"atrim=0:{duration:.6f},aformat=sample_rates={SR}:channel_layouts=stereo[out]")
    pre = os.path.join(work_dir, "mix_pre.wav")
    ffmpeg_utils.run(inputs + ["-filter_complex", ";".join(graph), "-map", "[out]",
                               "-c:a", "pcm_s16le", pre])

    m = measure_loudness(pre)
    ln = "loudnorm=I=-14:TP=-1:LRA=11"
    try:
        ln += (f":measured_I={float(m['input_i']):.2f}:measured_TP={float(m['input_tp']):.2f}"
               f":measured_LRA={float(m['input_lra']):.2f}:measured_thresh={float(m['input_thresh']):.2f}"
               f":offset={float(m['target_offset']):.2f}:linear=true")
    except (KeyError, TypeError, ValueError):
        pass
    ffmpeg_utils.run([ffmpeg_utils.FFMPEG, "-nostdin", "-v", "error", "-y", "-i", pre,
                      "-af", f"{ln},aresample={SR},atrim=0:{duration:.6f}",
                      "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", out_wav])
    try:
        os.remove(pre)
    except OSError:
        pass
    final = measure_loudness(out_wav)
    return {
        "voice_input_lufs": round(vi, 1), "voice_gain_db": round(voice_gain, 1),
        "music": os.path.basename(music) if music else None,
        "final_lufs": _f(final.get("input_i")), "final_true_peak": _f(final.get("input_tp")),
    }


def _f(x) -> Optional[float]:
    try:
        return round(float(x), 1)
    except (TypeError, ValueError):
        return None
