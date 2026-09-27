"""Sound design + musique + mixage (100 % synthèse numpy, aucun fichier sous licence).

Les repères SFX viennent de la page (window.EVENTS): chaque animation déclare
son son. La musique suit la dramaturgie: tension avant la révélation de la
solution, puis l'humeur du template (hopeful / energetic / calm).
"""
from __future__ import annotations

import subprocess
from typing import Any, Callable

import numpy as np

SR = 48000
_rng = np.random.default_rng(7)


def _lp(x: np.ndarray, fc) -> np.ndarray:
    """Passe-bas 1 pôle (fc scalaire ou tableau), vectorisé par blocs."""
    fc_arr = np.broadcast_to(np.asarray(fc, dtype=float), x.shape)
    a = np.exp(-2 * np.pi * fc_arr / SR)
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)):
        s = (1 - a[i]) * x[i] + a[i] * s
        y[i] = s
    return y


def _noise_band(n: int, f0: float, f1: float) -> np.ndarray:
    x = _rng.standard_normal(n); fc = np.geomspace(f0, f1, n)
    return _lp(x, fc * 1.6) - _lp(x, fc * 0.6)


def _norm(y: np.ndarray, amp: float) -> np.ndarray:
    m = np.abs(y).max() or 1.0
    return amp * y / m


def _t(d: float) -> np.ndarray:
    return np.arange(int(d * SR)) / SR


def whoosh(d=0.45, f0=300, f1=4000, amp=0.5):
    n = int(d * SR); x = _noise_band(n, f0, f1); u = np.arange(n) / n
    return _norm(x * np.sin(np.pi * u) ** 1.5, amp)


def impact(amp=0.9, d=1.1):
    t = _t(d); f = 45 + 80 * np.exp(-t * 18)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.0)
    crack = _lp(_rng.standard_normal(len(t)) * np.exp(-t * 40), 3000)
    return _norm(boom + 0.6 * crack, amp)


def pop(f=900, amp=0.35, d=0.12):
    t = _t(d); ff = f * (1 + 1.2 * np.exp(-t * 60))
    return amp * np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-t * 38)


def click(amp=0.45):
    t = _t(0.05)
    return _norm(_rng.standard_normal(len(t)) * np.exp(-t * 300) + np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 120), amp)


def tick(amp=0.16, f=3200):
    t = _t(0.03); return amp * np.sin(2 * np.pi * f * t) * np.exp(-t * 220)


def tock(amp=0.16, f=1300):
    t = _t(0.06); return amp * np.sin(2 * np.pi * f * t) * np.exp(-t * 80)


def thud(amp=0.5):
    t = _t(0.35); f = 90 + 60 * np.exp(-t * 30)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14) + 0.2 * _lp(_rng.standard_normal(len(t)), 900) * np.exp(-t * 30)
    return _norm(y, amp)


def ding(f=1318.5, amp=0.3, d=1.1):
    t = _t(d)
    y = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * k) for m, a, k in [(1, 1, 3), (2.76, .45, 6), (5.4, .25, 9), (8.93, .12, 12)])
    return _norm(y, amp)


def coin(amp=0.2):
    f = _rng.uniform(2800, 4200); t = _t(0.25)
    y = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * k) for m, a, k in [(1, 1, 18), (1.47, .6, 22), (2.09, .4, 30)])
    return _norm(y, amp)


def riser(d=1.2, amp=0.45):
    t = _t(d); u = t / d; f = 200 * (1 + 7 * u ** 2)
    y = 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.8 * _noise_band(len(t), 400, 8000)
    return _norm(y * u ** 2, amp)


def shimmer(d=1.3, amp=0.22):
    n = int(d * SR); y = np.zeros(n)
    for _ in range(18):
        s = int(_rng.uniform(0, 0.6) * SR); f = _rng.uniform(2500, 7000); m = min(n - s, int(0.5 * SR)); tt = np.arange(m) / SR
        y[s:s + m] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 9)
    return _norm(y, amp)


def heartbeat(amp=0.55):
    n = int(0.5 * SR); y = np.zeros(n)
    for dd, a in [(0, 1), (0.16, 0.7)]:
        s = int(dd * SR); m = int(0.2 * SR); tt = np.arange(m) / SR
        y[s:s + m] += a * np.sin(2 * np.pi * 50 * tt) * np.exp(-tt * 22)
    return amp * y


def stamp(amp=0.85):
    a = impact(amp * 0.7, 0.6); b = thud(amp * 0.8); b = np.pad(b, (0, len(a) - len(b)))
    return a + b


def pencil(d=0.3, amp=0.35):
    """Crayon sur papier: souffle aigu, grain irrégulier."""
    n = int(d * SR); t = np.arange(n) / SR
    x = _noise_band(n, 1800, 7000)
    grain = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * _rng.uniform(18, 30) * t + _rng.uniform(0, 3)))
    env = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 0.6
    return _norm(x * grain * env, amp)


def paper(d=0.5, amp=0.3):
    n = int(d * SR); u = np.arange(n) / n
    return _norm(_noise_band(n, 300, 3500) * np.sin(np.pi * u) ** 1.2, amp)


def tear(d=0.7, amp=0.6):
    n = int(d * SR); t = np.arange(n) / SR; y = _noise_band(n, 600, 6000) * np.exp(-t * 3) * 0.5
    for _ in range(70):
        s = int(_rng.uniform(0, d * 0.85) * SR); m = int(0.006 * SR)
        y[s:s + m] += _rng.standard_normal(min(m, n - s)) * _rng.uniform(0.4, 1.0)
    return _norm(y, amp)


def glitch(d=0.35, amp=0.3):
    n = int(d * SR); y = np.zeros(n); k = 0
    while k < n:
        m = int(_rng.uniform(0.012, 0.04) * SR); f = _rng.uniform(200, 3000); tt = np.arange(min(m, n - k)) / SR
        y[k:k + len(tt)] = np.sign(np.sin(2 * np.pi * f * tt)) * _rng.uniform(0.2, 1.0) * (_rng.uniform() > 0.25)
        k += m
    return _norm(_lp(y, 6000), amp)


def scan(d=0.9, amp=0.22):
    t = _t(d); u = t / d; f = 700 + 1900 * u
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.6 + 0.4 * np.sin(2 * np.pi * 18 * t)) * np.sin(np.pi * u)
    return _norm(y, amp)


# nom -> fabrique (appelée à chaque occurrence: petites variations naturelles)
LIB: dict[str, Callable[[], np.ndarray]] = {
    "tick": lambda: tick(0.14, _rng.uniform(2900, 3500)),
    "tock": lambda: tock(0.15, _rng.choice([1000, 1400])),
    "impact": lambda: impact(0.6, 0.9),
    "impact_big": lambda: impact(0.85, 1.4),
    "whoosh": lambda: whoosh(0.45, 250, 5000, 0.45),
    "whoosh_deep": lambda: whoosh(0.6, 120, 2500, 0.55),
    "whoosh_rev": lambda: whoosh(0.8, 5000, 200, 0.4),
    "pop": lambda: pop(_rng.uniform(750, 1100), 0.32),
    "pop_low": lambda: pop(420, 0.28),
    "pop_high": lambda: pop(1400, 0.2),
    "blip": lambda: pop(_rng.uniform(1100, 1500), 0.15, 0.08),
    "ding": lambda: ding(_rng.choice([1318.5, 1568.0, 1760.0]), 0.22, 1.0),
    "coin": lambda: coin(0.12),
    "stamp": lambda: stamp(0.85),
    "riser": lambda: riser(1.2, 0.4),
    "riser_short": lambda: riser(0.7, 0.25),
    "shimmer": lambda: shimmer(1.4, 0.22),
    "ping": lambda: ding(2637.0, 0.35, 0.6),
    "thud": lambda: thud(0.4),
    "click": lambda: click(0.55),
    "heartbeat": lambda: heartbeat(0.6),
    "pencil": lambda: pencil(_rng.uniform(0.22, 0.4), 0.35),
    "paper": lambda: paper(0.5, 0.3),
    "tear": lambda: tear(0.7, 0.6),
    "glitch": lambda: glitch(0.35, 0.3),
    "scan": lambda: scan(0.9, 0.22),
}


def sfx_track(events: list[dict[str, Any]], duration: float) -> np.ndarray:
    out = np.zeros(int((duration + 2) * SR))
    last: dict[str, float] = {}
    for e in events:
        name = e.get("sfx"); t = float(e.get("t", 0)); g = float(e.get("gain", 1))
        if name not in LIB or t < 0 or t > duration:
            continue
        if name in ("tick", "coin", "tock") and t - last.get(name, -9) < 0.02:
            continue
        last[name] = t
        sig = LIB[name]() * g
        s = int(t * SR); e_ = min(len(out), s + len(sig)); out[s:e_] += sig[:e_ - s]
    return out[:int(duration * SR)]


# ----------------------------------------------------------------- musique
_nf = lambda m: 440 * 2 ** ((m - 69) / 12)  # noqa: E731


def music_track(duration: float, mood: str, bpm: float, turn: float) -> np.ndarray:
    """Tension (mineur, pulsations) jusqu'à `turn`, puis progression positive."""
    N = int(duration * SR); mus = np.zeros(N)

    def note(f, s, d, amp, kind):
        n = int(d * SR); tt = np.arange(n) / SR; s0 = int(s * SR)
        if s0 >= N or n <= 0:
            return
        if kind == "pad":
            y = sum(np.sin(2 * np.pi * f * (1 + det) * tt + ph) for det, ph in [(0, 0), (0.004, 1), (-0.004, 2)]) / 3
            e = np.minimum(1, tt / 0.4) * np.minimum(1, np.maximum(0, d - tt) / 0.5)
        elif kind == "pluck":
            y = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt); e = np.exp(-tt * 7)
        else:
            y = np.sin(2 * np.pi * f * tt) + 0.2 * np.sin(4 * np.pi * f * tt); e = np.minimum(1, tt / 0.01) * np.exp(-tt * 2.5)
        e_ = min(N, s0 + n); mus[s0:e_] += amp * (y * e)[:e_ - s0]

    beat = 60 / bpm
    # tension: ré mineur
    t = 0.0; chords = [[50, 57, 65], [46, 53, 62], [45, 52, 61], [50, 57, 65]]; i = 0
    while t < turn - 0.05:
        d = min(beat * 8, turn - t); ch = chords[i % 4]
        for m in ch:
            note(_nf(m), t, d + 0.3, 0.09, "pad")
        note(_nf(ch[0] - 12), t, d, 0.2, "bass"); t += d; i += 1
    b = 0; t = 0.0
    while t < turn:
        note(_nf([62, 65, 69, 65][b % 4]), t, 0.4, 0.035, "pluck"); b += 1; t += beat / 2
    # partie positive
    progs = {"hopeful": [[53, 60, 65, 69], [48, 55, 64, 67], [50, 57, 62, 65], [46, 53, 62, 65]],
             "energetic": [[45, 52, 60, 64], [41, 48, 57, 60], [48, 55, 64, 67], [43, 50, 59, 62]],
             "calm": [[48, 55, 64, 67], [45, 52, 60, 64], [41, 48, 57, 64], [43, 50, 59, 62]]}
    prog = progs.get(mood, progs["hopeful"])
    kick_amp = {"energetic": 0.34, "hopeful": 0.28, "calm": 0.0}.get(mood, 0.28)
    b = 0; t = turn
    while t < duration:
        ch = prog[(b // 4) % 4]
        if b % 4 == 0:
            for m in ch[1:]:
                note(_nf(m), t, min(beat * 4, duration - t), 0.065, "pad")
            note(_nf(ch[0] - 12), t, min(beat * 4, duration - t), 0.2, "bass")
        arp = [ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 12]
        note(_nf(arp[b % 4]), t, 0.5, 0.045, "pluck"); note(_nf(arp[(b + 1) % 4]), t + beat / 2, 0.5, 0.035, "pluck")
        k0 = int(t * SR); n = int(0.3 * SR); tt = np.arange(n) / SR
        if kick_amp and k0 + n < N:
            mus[k0:k0 + n] += kick_amp * np.sin(2 * np.pi * np.cumsum(50 + 100 * np.exp(-tt * 35)) / SR) * np.exp(-tt * 9)
        h0 = int((t + beat / 2) * SR); n2 = int(0.05 * SR)
        if mood != "calm" and h0 + n2 < N:
            mus[h0:h0 + n2] += 0.05 * _rng.standard_normal(n2) * np.exp(-np.arange(n2) / SR * 90)
        b += 1; t += beat
    fade = int(1.5 * SR)
    if N > fade:
        mus[N - fade:] *= np.linspace(1, 0, fade)
    return mus


def _read(path: str) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "pipe:1"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).astype(float)


def mix(voice_wav: str, events: list[dict[str, Any]], duration: float, out_wav: str, *,
        mood: str = "hopeful", bpm: float = 96, turn: float | None = None,
        music_db: float = -16, sfx_db: float = -6) -> str:
    vo = _read(voice_wav); N = int(duration * SR)
    vo = np.pad(vo, (0, max(0, N - len(vo))))[:N]
    rms = lambda x: float(np.sqrt(np.mean(x[np.abs(x) > 1e-4] ** 2))) if np.any(np.abs(x) > 1e-4) else 1.0  # noqa: E731
    vo *= 0.25 / rms(vo)
    env = np.convolve(np.abs(vo), np.ones(int(0.08 * SR)) / int(0.08 * SR), "same"); env /= (env.max() or 1)
    duck = np.clip(env * 4, 0, 1)
    mus = music_track(duration, mood, bpm, turn if turn is not None else duration * 0.3)
    mus *= (0.25 / rms(mus)) * 10 ** (music_db / 20) * (1 - 0.55 * duck)
    sfx = sfx_track(events, duration)
    sfx = np.pad(sfx, (0, max(0, N - len(sfx))))[:N]
    sfx *= (0.25 / rms(sfx)) * 10 ** (sfx_db / 20) * (1 - 0.35 * duck)
    m = vo + mus + sfx; m /= (np.abs(m).max() or 1) / 0.9
    st = np.stack([m, m], 1).astype(np.float32)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "pipe:0",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), out_wav], input=st.tobytes(), check=True)
    return out_wav
