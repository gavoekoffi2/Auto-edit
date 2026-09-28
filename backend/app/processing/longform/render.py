"""Assemblage image + son 1:1 d'une vidéo longue (aucune dérive de synchro).

Leçon de youtube-clean : encoder chaque coupe dans son propre fichier puis
les recoller arrondit chaque morceau à une image entière et laisse des trous
de timestamps aux raccords — sur une vidéo longue le visage finit une
demi-seconde en retard sur la voix. Ici il n'y a AUCUN fichier par coupe :

* son  : un seul fichier wav écrit d'un trait ; la plage k occupe les
  échantillons [P_k, P_k + N_k) ; fondus de 4 ms à chaque raccord ;
* image : UN encodeur sur une horloge fixe de 30 i/s ; l'image de sortie i
  (t = i/30) montre l'image source ``start_k + (t - P_k/SR)`` — les arrondis
  ne s'accumulent jamais ;
* le zoom alterné (qui masque les jump-cuts) et l'étalonnage sont appliqués
  au décodage de chaque plage, sans repasse.

La mémoire reste bornée (lecture/écriture en flux), même pour une heure.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import wave
from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np

from app.autoedit_engine import ffmpeg_utils

SR = 48000
FPS = 30
W, H = 1920, 1080
FADE_S = 0.004


@dataclass
class VideoInfo:
    width: int
    height: int
    duration: float
    has_audio: bool
    #: décalage (s) à ajouter au temps « audio » pour viser la bonne image avec
    #: ``-ss`` : l'audio extrait commence à sa 1re trame, alors que ``-ss`` compte
    #: depuis le début du conteneur (fréquent sur les .mov / vidéos de téléphone).
    video_offset: float = 0.0

    @property
    def landscape(self) -> bool:
        return self.width >= self.height


def probe_video(path: str) -> VideoInfo:
    """Résolution AFFICHÉE (rotation du téléphone comprise), durée, audio."""
    out = subprocess.check_output([
        ffmpeg_utils.FFPROBE, "-v", "error", "-show_streams", "-show_format",
        "-of", "json", path,
    ])
    j = json.loads(out)
    vs = [s for s in j.get("streams", []) if s.get("codec_type") == "video"]
    if not vs:
        raise RuntimeError("Aucune piste vidéo dans le fichier.")
    v = vs[0]
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    rot = 0
    try:
        rot = int(float((v.get("tags") or {}).get("rotate", 0)))
    except (TypeError, ValueError):
        rot = 0
    for sd in v.get("side_data_list") or []:
        if "rotation" in sd:
            try:
                rot = int(float(sd["rotation"]))
            except (TypeError, ValueError):
                pass
    if abs(rot) % 180 == 90:
        w, h = h, w
    dur = float((j.get("format") or {}).get("duration") or v.get("duration") or 0.0)
    auds = [s for s in j.get("streams", []) if s.get("codec_type") == "audio"]
    has_audio = bool(auds)

    def _st(x) -> float:
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0
    fmt_start = _st((j.get("format") or {}).get("start_time"))
    a_start = _st(auds[0].get("start_time")) if auds else fmt_start
    offset = max(0.0, min(5.0, a_start - fmt_start))
    return VideoInfo(w, h, dur, has_audio, round(offset, 4))


def extract_audio(src: str, out_wav: str, sr: int = SR, channels: int = 1) -> str:
    if not os.path.exists(out_wav):
        ffmpeg_utils.run([
            ffmpeg_utils.FFMPEG, "-y", "-i", src, "-vn", "-ac", str(channels),
            "-ar", str(sr), "-c:a", "pcm_s16le", out_wav,
        ])
    return out_wav


# --------------------------------------------------------------------------- #
# Timeline
# --------------------------------------------------------------------------- #
@dataclass
class Placed:
    start: float      # source (s)
    end: float
    p: int            # position de sortie en échantillons
    n: int            # longueur en échantillons
    zoom: float = 1.0
    cx: float = 0.5   # centre de cadrage (0..1)
    cy: float = 0.45

    @property
    def out_start(self) -> float:
        return self.p / SR

    @property
    def out_end(self) -> float:
        return (self.p + self.n) / SR


class Timeline:
    """Correspondance exacte source <-> sortie, partagée par tout le moteur."""

    def __init__(self, ranges: List[dict]):
        self.items: List[Placed] = []
        p = 0
        for r in ranges:
            n = int(round((float(r["end"]) - float(r["start"])) * SR))
            if n <= 0:
                continue
            self.items.append(Placed(float(r["start"]), float(r["end"]), p, n,
                                     float(r.get("zoom", 1.0)),
                                     float(r.get("cx", 0.5)), float(r.get("cy", 0.45))))
            p += n
        self.total_samples = p

    @property
    def duration(self) -> float:
        return self.total_samples / SR

    @property
    def n_frames(self) -> int:
        return math.ceil(self.total_samples / SR * FPS - 1e-9)

    def s2o(self, t: float) -> Optional[float]:
        for it in self.items:
            if it.start - 1e-6 <= t <= it.end + 1e-6:
                return it.out_start + min(t, it.end) - it.start
        return None

    def cut_points(self) -> List[float]:
        """Instants de sortie des raccords (début de chaque plage sauf la 1re)."""
        return [it.out_start for it in self.items[1:]]

    def to_json(self) -> list:
        return [{"src_start": it.start, "src_end": it.end,
                 "out_start": round(it.out_start, 4), "out_end": round(it.out_end, 4),
                 "zoom": it.zoom, "cx": round(it.cx, 3)} for it in self.items]


# --------------------------------------------------------------------------- #
# Son
# --------------------------------------------------------------------------- #
def build_voice(src_wav: str, tl: Timeline, out_wav: str) -> str:
    """Écrit la voix montée d'un trait (mono 48 kHz), fondus 4 ms aux raccords."""
    f = int(FADE_S * SR)
    ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)
    with wave.open(src_wav, "rb") as rd, wave.open(out_wav, "wb") as wr:
        assert rd.getframerate() == SR and rd.getnchannels() == 1
        total_src = rd.getnframes()
        wr.setnchannels(1)
        wr.setsampwidth(2)
        wr.setframerate(SR)
        for it in tl.items:
            s0 = int(round(it.start * SR))
            seg = np.zeros(it.n, np.float32)
            if s0 < total_src:
                rd.setpos(max(0, s0))
                raw = rd.readframes(min(it.n, total_src - s0))
                x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                seg[:len(x)] = x
            if it.n > 2 * f:
                seg[:f] *= ramp
                seg[-f:] *= ramp[::-1]
            wr.writeframes((np.clip(seg, -1, 1) * 32767).astype(np.int16).tobytes())
    return out_wav


# --------------------------------------------------------------------------- #
# Image
# --------------------------------------------------------------------------- #
def _geometry_filter(info: VideoInfo, zoom: float, cx: float, cy: float, grade: str) -> tuple[str, bool]:
    """Filtre de décodage d'une plage -> (filtre, est_complexe)."""
    z = max(1.0, zoom)
    sw, sh = int(round(W * z / 2) * 2), int(round(H * z / 2) * 2)
    x = f"'max(0,min(iw-{W},iw*{cx:.4f}-{W}/2))'"
    y = f"'max(0,min(ih-{H},ih*{cy:.4f}-{H}/2))'"
    tail = f",{grade}" if grade else ""
    if info.landscape:
        f = (f"fps={FPS},scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=bicubic,"
             f"crop={W}:{H}:{x}:{y}{tail},setsar=1,format=yuv420p")
        return f, False
    # Source verticale / carrée : fond flouté plein cadre + image entière au centre.
    fg_h = int(round(H * z / 2) * 2)
    f = (f"[0:v]fps={FPS},split=2[bg][fg];"
         f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
         f"boxblur=24:2,eq=brightness=-0.06[b];"
         f"[fg]scale=-2:{fg_h}{tail}[f];"
         f"[b][f]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,format=yuv420p[v]")
    return f, True


def _filter_path(p: str) -> str:
    """Échappe un chemin pour une option de filtre ffmpeg."""
    return p.replace("\\", "/").replace(":", r"\:").replace("'", r"\'").replace(",", r"\,")


def build_picture(source: str, info: VideoInfo, tl: Timeline, out_path: str,
                  grade: str = "", crf: int = 19, preset: str = "veryfast",
                  ass_path: Optional[str] = None, fonts_dir: Optional[str] = None,
                  progress: Optional[Callable[[float], None]] = None) -> dict:
    """Encode l'image montée : un seul encodeur, horloge 30 i/s exacte.

    L'habillage ASS (sous-titres, popups, cartes) est incrusté PAR CE MÊME
    encodeur : une seule compression pour toute la vidéo.
    """
    ffmpeg_utils.ensure_ffmpeg()
    NF = tl.n_frames
    FB = W * H * 3 // 2
    enc_cmd = [ffmpeg_utils.FFMPEG, "-nostdin", "-v", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{W}x{H}", "-r", str(FPS),
               "-i", "pipe:0"]
    if ass_path:
        sub = f"subtitles=filename='{_filter_path(ass_path)}'"
        if fonts_dir:
            sub += f":fontsdir='{_filter_path(fonts_dir)}'"
        enc_cmd += ["-vf", sub + ",format=yuv420p"]
    enc_cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-video_track_timescale", "30000",
                "-g", str(FPS * 4), out_path]
    enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)
    # Plan : une entrée par plage (images [f0, f1) de la sortie).
    plan = []
    for k, it in enumerate(tl.items):
        f0 = math.ceil(it.p / SR * FPS - 1e-9)
        f1 = NF if k == len(tl.items) - 1 else math.ceil((it.p + it.n) / SR * FPS - 1e-9)
        if f1 - f0 <= 0:
            continue
        plan.append((k, it, f0, f1, it.start + (f0 / FPS - it.p / SR) + info.video_offset))

    def start_decoder(entry):
        k, it, f0, f1, src_t = entry
        vf, complex_ = _geometry_filter(info, it.zoom, it.cx, it.cy, grade)
        cmd = [ffmpeg_utils.FFMPEG, "-nostdin", "-v", "error",
               "-ss", f"{max(0.0, src_t):.4f}", "-i", source]
        if complex_:
            cmd += ["-filter_complex", vf, "-map", "[v]"]
        else:
            cmd += ["-map", "0:v:0", "-vf", vf]
        cmd += ["-frames:v", str(f1 - f0), "-f", "rawvideo", "-pix_fmt", "yuv420p", "pipe:1"]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE)

    # Préchargement : les décodeurs suivants font leur recherche (seek +
    # décodage depuis l'image clé) PENDANT que la plage courante s'encode.
    prefetch = max(0, int(os.environ.get("LONGFORM_DECODE_PREFETCH", "2")))
    pending: list = []
    written = 0
    segs = []
    nxt = 0
    try:
        for idx, entry in enumerate(plan):
            while nxt < len(plan) and nxt <= idx + prefetch:
                pending.append(start_decoder(plan[nxt]))
                nxt += 1
            dec = pending.pop(0)
            k, it, f0, f1, src_t = entry
            nf = f1 - f0
            got, last = 0, None
            while got < nf:
                buf = dec.stdout.read(FB)
                if len(buf) < FB:
                    break
                enc.stdin.write(buf)
                last = buf
                got += 1
            dec.stdout.close()
            dec.wait()
            if dec.returncode != 0 or last is None:
                raise RuntimeError(
                    f"Décodage impossible de la plage {k} (source {src_t:.2f}s) — "
                    f"code {dec.returncode}.")
            # source plus courte que prévu (fin de fichier) : on tient la
            # dernière image, jamais de trou dans l'horloge
            while got < nf:
                enc.stdin.write(last)
                got += 1
            written += got
            segs.append({"f0": f0, "f1": f1, "src_t": round(src_t, 4)})
            if progress:
                progress(written / max(1, NF))
    finally:
        for d in pending:
            try:
                d.kill()
                d.wait()
            except Exception:  # noqa: BLE001
                pass
        if enc.stdin:
            try:
                enc.stdin.close()
            except BrokenPipeError:
                pass
        enc.wait()
    if written != NF:
        raise RuntimeError(f"Assemblage incomplet: {written}/{NF} images")
    if enc.returncode != 0:
        raise RuntimeError("L'encodeur vidéo a échoué pendant l'assemblage.")
    return {"frames": NF, "fps": FPS, "segments": segs}


def count_frames(path: str) -> int:
    out = subprocess.check_output([
        ffmpeg_utils.FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_packets",
        "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path,
    ]).decode().strip().split(",")[0]
    return int(out or 0)


def wav_duration(path: str) -> float:
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())
