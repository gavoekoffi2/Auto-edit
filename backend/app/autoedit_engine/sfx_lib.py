"""
SFX library — 19 sounds synthesised in numpy (48 kHz mono WAV).

Used by STEP 10 (mix_sfx).  Each generator returns a float32 array in [-1, 1];
``generate`` normalises it to the per-sound peak gain from ``config.SFX_GAINS``
and writes a 16-bit PCM WAV with the stdlib ``wave`` module (no scipy needed).

    from engine.sfx_lib import build_library
    paths = build_library("sfx/")            # -> {name: wav_path}
"""
from __future__ import annotations

import os
import wave
from typing import Callable, Dict

import numpy as np

from . import config

SR = config.SFX_SAMPLE_RATE


# --------------------------------------------------------------------------- #
# small DSP helpers (vectorised, no scipy)
# --------------------------------------------------------------------------- #
def _t(dur: float) -> np.ndarray:
    return np.linspace(0.0, dur, int(SR * dur), endpoint=False, dtype=np.float64)


def _sine(freq, t) -> np.ndarray:
    # freq may be scalar or an array (for sweeps), integrated via cumulative phase
    if np.isscalar(freq):
        phase = 2 * np.pi * freq * t
    else:
        dt = 1.0 / SR
        phase = 2 * np.pi * np.cumsum(freq) * dt
    return np.sin(phase)


def _noise(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(-1.0, 1.0, n)


def _lowpass(x: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return x
    kernel = np.ones(k) / k
    return np.convolve(x, kernel, mode="same")


def _highpass(x: np.ndarray, k: int) -> np.ndarray:
    return x - _lowpass(x, k)


def _exp_env(t: np.ndarray, decay: float) -> np.ndarray:
    return np.exp(-decay * t)


def _fade(x: np.ndarray, fin: float = 0.005, fout: float = 0.02) -> np.ndarray:
    n = len(x)
    ni = max(1, int(SR * fin))
    no = max(1, int(SR * fout))
    if ni < n:
        x[:ni] *= np.linspace(0.0, 1.0, ni)
    if no < n:
        x[-no:] *= np.linspace(1.0, 0.0, no)
    return x


def _norm(x: np.ndarray, peak: float) -> np.ndarray:
    m = np.max(np.abs(x)) or 1.0
    return (x / m) * peak


# --------------------------------------------------------------------------- #
# the 19 generators
# --------------------------------------------------------------------------- #
def _whoosh() -> np.ndarray:
    t = _t(0.5)
    env = np.sin(np.pi * t / t[-1]) ** 1.5            # swell in/out
    n = _lowpass(_noise(len(t), 1), 60)
    sweep = _sine(np.linspace(200, 1400, len(t)), t) * 0.3
    return _fade((n * env) + sweep * env)


def _swoosh(up: bool, seed: int) -> np.ndarray:
    t = _t(0.35)
    n = _noise(len(t), seed)
    if up:
        n = _highpass(n, 16)                  # brighter -> rising feel
        env = (t / t[-1]) ** 0.6
    else:
        n = _lowpass(n, 40)                   # darker -> falling feel
        env = (1 - t / t[-1]) ** 0.6
    env = env * np.sin(np.pi * t / t[-1])
    return _fade(n * env)


def _pop() -> np.ndarray:
    t = _t(0.12)
    return _fade(_sine(760, t) * _exp_env(t, 26))


def _boom() -> np.ndarray:
    t = _t(0.6)
    body = _sine(np.linspace(90, 55, len(t)), t) * _exp_env(t, 6)
    click = _highpass(_noise(len(t), 2), 8) * _exp_env(t, 120) * 0.4
    return _fade(body + click, fout=0.1)


def _impact() -> np.ndarray:
    t = _t(0.4)
    thud = _sine(np.linspace(120, 50, len(t)), t) * _exp_env(t, 9)
    crack = _noise(len(t), 3) * _exp_env(t, 55) * 0.6
    return _fade(thud + crack, fout=0.08)


def _sub_drop() -> np.ndarray:
    t = _t(0.7)
    body = _sine(np.linspace(120, 32, len(t)), t) * _exp_env(t, 4)
    return _fade(body, fout=0.12)


def _ding() -> np.ndarray:
    t = _t(0.6)
    tone = _sine(1280, t) + 0.4 * _sine(2560, t)
    return _fade(tone * _exp_env(t, 7), fout=0.1)


def _sparkle() -> np.ndarray:
    t = _t(0.5)
    out = np.zeros(len(t))
    for k, f in enumerate((2200, 3100, 4300, 5600)):
        start = int(len(t) * k / 6)
        env = np.zeros(len(t))
        seg = t[: len(t) - start]
        env[start:] = _exp_env(seg, 12)
        out += _sine(f, t) * env * 0.5
    return _fade(out, fout=0.1)


def _shutter() -> np.ndarray:
    t = _t(0.15)
    out = np.zeros(len(t))
    c1 = _noise(len(t), 4) * _exp_env(t, 120)
    half = len(t) // 2
    c2 = np.zeros(len(t))
    c2[half:] = (_noise(len(t), 5) * _exp_env(t, 100))[: len(t) - half]
    return _fade(c1 * 0.9 + c2, fout=0.01)


def _glitch() -> np.ndarray:
    t = _t(0.3)
    n = _highpass(_noise(len(t), 6), 6)
    # stutter gate
    gate = (np.floor(t * 50) % 2)
    gate = gate * (np.random.default_rng(7).uniform(0.4, 1.0, len(t)))
    return _fade(n * gate)


def _riser() -> np.ndarray:
    t = _t(1.0)
    env = (t / t[-1]) ** 2
    n = _lowpass(_noise(len(t), 8), 30) * env
    tone = _sine(np.linspace(200, 1000, len(t)), t) * env * 0.4
    return _fade(n + tone, fout=0.05)


def _transition() -> np.ndarray:
    t = _t(0.4)
    env = np.sin(np.pi * t / t[-1])
    sweep = _sine(np.linspace(400, 2200, len(t)), t)
    n = _lowpass(_noise(len(t), 9), 40) * 0.5
    return _fade((sweep + n) * env)


def _click() -> np.ndarray:
    t = _t(0.05)
    return _fade(_noise(len(t), 10) * _exp_env(t, 180), fin=0.0005, fout=0.005)


def _camera_flash() -> np.ndarray:
    # signature photo sound: shutter click + bright "tssh" tail
    t = _t(0.25)
    click = _noise(len(t), 11) * _exp_env(t, 130) * 0.9
    tail = _highpass(_noise(len(t), 12), 8) * _exp_env(t, 22) * 0.5
    return _fade(click + tail, fout=0.04)


def _chime() -> np.ndarray:
    t = _t(0.8)
    out = np.zeros(len(t))
    for f in (1046, 1318, 1568):                      # C6 / E6 / G6 major
        out += _sine(f, t) * _exp_env(t, 5)
    return _fade(out, fout=0.12)


def _digi_blip() -> np.ndarray:
    t = _t(0.12)
    sq = np.sign(_sine(np.linspace(700, 1400, len(t)), t))
    return _fade(sq * _exp_env(t, 30) * 0.6)


def _reverse_swell() -> np.ndarray:
    riser = _riser()
    return _fade(riser[::-1].copy(), fin=0.02, fout=0.01)


def _bass_hit() -> np.ndarray:
    t = _t(0.35)
    body = _sine(np.linspace(110, 45, len(t)), t) * _exp_env(t, 11)
    click = _noise(len(t), 13) * _exp_env(t, 90) * 0.3
    return _fade(body + click, fout=0.06)


# --------------------------------------------------------------------------- #
# v4.2 — professional additions
# --------------------------------------------------------------------------- #
def _shutter_burst() -> np.ndarray:
    """Rapid 3-shot camera burst (photo rafale)."""
    t = _t(0.42)
    out = np.zeros(len(t))
    one = _shutter()
    for k in range(3):
        start = int(SR * 0.125 * k)
        end = min(len(out), start + len(one))
        out[start:end] += one[: end - start] * (1.0 - 0.15 * k)
    return _fade(out, fout=0.03)


def _camera_focus() -> np.ndarray:
    """Autofocus double-beep right before a shot — subtle, high, short."""
    t = _t(0.22)
    out = np.zeros(len(t))
    beep = _sine(2300, _t(0.045)) * _exp_env(_t(0.045), 30)
    for start_s in (0.0, 0.11):
        start = int(SR * start_s)
        end = min(len(out), start + len(beep))
        out[start:end] += beep[: end - start]
    return _fade(out, fout=0.02)


def _pen_scribble() -> np.ndarray:
    """Pencil drawing on paper — gated filtered noise strokes (whiteboard)."""
    t = _t(1.0)
    n = _highpass(_noise(len(t), 31), 4)
    # stroke gate: bursts of varying length, like quick pencil strokes
    gate = np.zeros(len(t))
    rng = np.random.default_rng(32)
    pos = 0
    while pos < len(t):
        stroke = int(SR * rng.uniform(0.05, 0.16))
        gap = int(SR * rng.uniform(0.015, 0.05))
        end = min(len(t), pos + stroke)
        seg = np.sin(np.pi * np.linspace(0, 1, end - pos)) * rng.uniform(0.5, 1.0)
        gate[pos:end] = seg
        pos = end + gap
    return _fade(_lowpass(n * gate, 3), fout=0.08)


def _tape_stop() -> np.ndarray:
    """Tape-stop: a tone whose pitch collapses to zero (great as exit/riser)."""
    t = _t(0.55)
    freq = 660.0 * (1.0 - t / t[-1]) ** 1.6 + 18.0
    body = _sine(freq, t) * (1.0 - 0.55 * t / t[-1])
    hiss = _lowpass(_noise(len(t), 33), 25) * 0.18 * (1.0 - t / t[-1])
    return _fade(body + hiss, fout=0.06)


def _bubble() -> np.ndarray:
    """Liquid pop with an upward pitch flick — playful UI accent."""
    t = _t(0.14)
    freq = np.linspace(420, 1500, len(t)) ** 1.0
    return _fade(_sine(freq, t) * _exp_env(t, 24), fin=0.002, fout=0.02)


def _snap() -> np.ndarray:
    """Finger snap: sharp mid crack + tiny room tail."""
    t = _t(0.18)
    crack = _highpass(_noise(len(t), 34), 3) * _exp_env(t, 95)
    body = _sine(1900, t) * _exp_env(t, 70) * 0.4
    tail = _lowpass(_noise(len(t), 35), 18) * _exp_env(t, 22) * 0.25
    return _fade(crack + body + tail, fin=0.001, fout=0.04)


def _cinematic_hit() -> np.ndarray:
    """Trailer-style hit: sub punch + metallic ring + long airy tail."""
    t = _t(1.1)
    sub = _sine(np.linspace(95, 38, len(t)), t) * _exp_env(t, 5)
    ring = (_sine(523, t) + 0.6 * _sine(784, t) + 0.4 * _sine(1046.5, t)) * _exp_env(t, 6) * 0.35
    crack = _noise(len(t), 36) * _exp_env(t, 90) * 0.5
    air = _lowpass(_noise(len(t), 37), 55) * _exp_env(t, 3) * 0.22
    return _fade(sub + ring + crack + air, fout=0.25)


def _data_tick() -> np.ndarray:
    """Fast digital ticks — pairs with animated counters."""
    t = _t(0.30)
    out = np.zeros(len(t))
    tick = np.sign(_sine(2800, _t(0.012))) * _exp_env(_t(0.012), 240)
    rng = np.random.default_rng(38)
    for k in range(7):
        start = int(SR * (0.012 + 0.040 * k) * rng.uniform(0.92, 1.05))
        end = min(len(out), start + len(tick))
        if end > start:
            out[start:end] += tick[: end - start] * (1.0 - 0.09 * k)
    return _fade(out * 0.6, fout=0.03)


GENERATORS: Dict[str, Callable[[], np.ndarray]] = {
    "whoosh": _whoosh,
    "swoosh_up": lambda: _swoosh(True, 21),
    "swoosh_down": lambda: _swoosh(False, 22),
    "pop": _pop,
    "boom": _boom,
    "impact": _impact,
    "sub_drop": _sub_drop,
    "ding": _ding,
    "sparkle": _sparkle,
    "shutter": _shutter,
    "glitch": _glitch,
    "riser": _riser,
    "transition": _transition,
    "click": _click,
    "camera_flash": _camera_flash,
    "chime": _chime,
    "digi_blip": _digi_blip,
    "reverse_swell": _reverse_swell,
    "bass_hit": _bass_hit,
    "shutter_burst": _shutter_burst,
    "camera_focus": _camera_focus,
    "pen_scribble": _pen_scribble,
    "tape_stop": _tape_stop,
    "bubble": _bubble,
    "snap": _snap,
    "cinematic_hit": _cinematic_hit,
    "data_tick": _data_tick,
}


def _write_wav(path: str, samples: np.ndarray) -> None:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def generate(name: str, out_dir: str) -> str:
    if name not in GENERATORS:
        raise ValueError(f"unknown SFX '{name}'")
    samples = _norm(GENERATORS[name]().astype(np.float64), config.SFX_GAINS.get(name, 0.8))
    path = os.path.join(out_dir, f"{name}.wav")
    _write_wav(path, samples)
    return path


def build_library(out_dir: str) -> Dict[str, str]:
    """Generate every SFX and return {name: path}."""
    os.makedirs(out_dir, exist_ok=True)
    return {name: generate(name, out_dir) for name in config.SFX_NAMES}


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "sfx"
    paths = build_library(out)
    for n, p in paths.items():
        print(f"  {n:14s} {p}")
    print(f"[sfx_lib] wrote {len(paths)} sounds to {out}/")
