"""Voix off + minutage mot par mot.

Fournisseurs:
  * ``elevenlabs`` — licence commerciale, utilisé si ELEVENLABS_API_KEY existe.
  * ``edge``       — voix neuronales Microsoft via edge-tts, sans clé. Pratique
    pour démarrer, mais service non officiel: pas de garantie ni de licence
    commerciale. À remplacer en production payante.

Chaque phrase est synthétisée séparément (ce qui donne des pauses maîtrisées),
nettoyée de ses silences, puis concaténée. Le minutage des mots vient du
fournisseur (WordBoundary / alignment) — pas besoin de Whisper.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import ssl
import subprocess
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SR = 48000
DEFAULT_EDGE_VOICE = "fr-FR-RemyMultilingualNeural"
EDGE_VOICES = {
    "remy": "fr-FR-RemyMultilingualNeural", "henri": "fr-FR-HenriNeural",
    "vivienne": "fr-FR-VivienneMultilingualNeural", "denise": "fr-FR-DeniseNeural",
    "thierry_ca": "fr-CA-ThierryNeural", "antoine_ca": "fr-CA-AntoineNeural", "sylvie_ca": "fr-CA-SylvieNeural",
}
DEFAULT_ELEVEN_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # voix multilingue par défaut


@dataclass
class Word:
    w: str
    s: float
    e: float


@dataclass
class VoiceTrack:
    wav_path: str
    duration: float
    words: list[Word]
    lines: list[tuple[float, float]]              # (début, fin) de chaque phrase
    line_words: list[list[Word]] = field(default_factory=list)
    provider: str = "edge"


def _decode(data: bytes) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "pipe:1"],
                         input=data, capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).copy()


def _trim(a: np.ndarray, thr: float = 0.01) -> tuple[np.ndarray, float]:
    idx = np.where(np.abs(a) > thr)[0]
    if not len(idx):
        return a, 0.0
    s = max(0, idx[0] - int(0.03 * SR))
    e = min(len(a), idx[-1] + int(0.06 * SR))
    return a[s:e], s / SR


# ----------------------------------------------------------------- edge-tts
def _edge_ssl_patch() -> None:
    """Derrière un proxy TLS (CI, sandbox), edge-tts doit faire confiance au CA local."""
    bundle = os.environ.get("EXPLAINER_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if not bundle or not os.path.exists(bundle):
        return
    try:
        import edge_tts.communicate as _c  # type: ignore
        _c._SSL_CTX = ssl.create_default_context(cafile=bundle)
    except Exception:  # pragma: no cover
        pass


async def _edge_line(text: str, voice: str, rate: str) -> tuple[bytes, list[Word]]:
    import edge_tts  # type: ignore
    _edge_ssl_patch()
    kw = {"rate": rate}
    try:
        comm = edge_tts.Communicate(text, voice, boundary="WordBoundary", **kw)
    except TypeError:  # anciennes versions
        comm = edge_tts.Communicate(text, voice, **kw)
    audio = bytearray(); words: list[Word] = []
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            s = chunk["offset"] / 1e7; d = chunk["duration"] / 1e7
            words.append(Word(chunk["text"], s, s + d))
    return bytes(audio), words


def _edge(lines: list[str], voice: str, rate: str) -> list[tuple[np.ndarray, list[Word]]]:
    async def run():
        return [await _edge_line(t, voice, rate) for t in lines]
    res = asyncio.run(run())
    return [(_decode(a), w) for a, w in res]


# ----------------------------------------------------------------- ElevenLabs
def _eleven(lines: list[str], voice: str, api_key: str, speed: float = 1.0) -> list[tuple[np.ndarray, list[Word]]]:
    import httpx
    out = []
    with httpx.Client(timeout=120) as cl:
        for i, text in enumerate(lines):
            vs = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35}
            if abs(speed - 1.0) > 0.01:
                vs["speed"] = max(0.7, min(1.2, speed))
            r = cl.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps",
                        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                        json={"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": vs,
                              # continuité de l'intonation d'une phrase à l'autre
                              "previous_text": " ".join(lines[max(0, i - 2):i]),
                              "next_text": lines[i + 1] if i + 1 < len(lines) else ""})
            r.raise_for_status()
            data = r.json()
            audio = _decode(base64.b64decode(data["audio_base64"]))
            al = data.get("alignment") or {}
            chars = al.get("characters") or []; cs = al.get("character_start_times_seconds") or []; ce = al.get("character_end_times_seconds") or []
            words: list[Word] = []; cur = ""; st = None; en = 0.0
            for ch, a, b in zip(chars, cs, ce):
                if ch.isspace():
                    if cur:
                        words.append(Word(cur, st or 0.0, en)); cur = ""; st = None
                    continue
                if st is None:
                    st = a
                cur += ch; en = b
            if cur:
                words.append(Word(cur, st or 0.0, en))
            out.append((audio, words))
    return out


def _squeeze(a: np.ndarray, words: list[Word], max_gap: float) -> tuple[np.ndarray, list[Word]]:
    """Raccourcit les silences internes trop longs (hésitations) et recale les mots."""
    h = int(0.01 * SR)
    if len(a) < 4 * h:
        return a, words
    env = np.sqrt(np.convolve(a.astype(np.float64) ** 2, np.ones(h) / h, "same"))[::h]
    thr = max(0.006, float(env.max()) * 0.03)
    quiet = env < thr
    keep = np.ones(len(a), bool); cuts: list[tuple[float, float]] = []
    i = 0; n = len(quiet); mg = int(max_gap / 0.01)
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if j - i > mg and i > 0 and j < n:
                s0, s1 = (i + mg // 2) * h, (j - mg // 2) * h
                keep[s0:s1] = False; cuts.append((s0 / SR, (s1 - s0) / SR))
            i = j
        else:
            i += 1
    if not cuts:
        return a, words
    def shift(t: float) -> float:
        return t - sum(d for c, d in cuts if c < t)
    return a[keep], [Word(w.w, round(shift(w.s), 3), round(shift(w.e), 3)) for w in words]


# ----------------------------------------------------------------- public
def synthesize(lines: list[str], out_wav: str, *, voice: Optional[str] = None, rate: str = "+5%",
               pauses: Optional[list[float]] = None, lead: float = 0.3, tail: float = 2.6,
               provider: Optional[str] = None, max_inner_pause: float = 0.0) -> VoiceTrack:
    """Synthétise les phrases, les enchaîne et renvoie le minutage global."""
    from .conf import setting
    key = setting("ELEVENLABS_API_KEY")
    eleven_id = None
    if voice and voice.startswith("eleven:"):
        eleven_id = voice.split(":", 1)[1] or setting("ELEVENLABS_VOICE_ID") or DEFAULT_ELEVEN_VOICE
        voice = None
    # une voix edge choisie explicitement reste edge, même si une clé ElevenLabs existe
    prov = provider or ("elevenlabs" if key and (eleven_id or not voice) else "edge")
    speed = 1.0 + (float(rate.strip("%")) / 100 if re.fullmatch(r"[+-]\d+%", rate or "") else 0.0)
    parts: list[tuple[np.ndarray, list[Word]]]
    if prov == "elevenlabs" and key:
        try:
            parts = _eleven(lines, eleven_id or voice or DEFAULT_ELEVEN_VOICE, key, speed=speed)
        except Exception as e:  # repli gratuit
            logger.warning("ElevenLabs indisponible (%s), repli edge-tts", e)
            prov = "edge"
    if prov != "elevenlabs":
        v = EDGE_VOICES.get(voice or "", voice) if voice else DEFAULT_EDGE_VOICE
        if not v or "Neural" not in v:
            v = DEFAULT_EDGE_VOICE
        parts = _edge(lines, v, rate)
    pauses = pauses or [0.35] * len(lines)
    pos = lead; segs = []; words: list[Word] = []; spans = []; per_line = []
    for i, (a, ws) in enumerate(parts):
        a, off = _trim(a)
        if max_inner_pause:
            a, ws = _squeeze(a, [Word(w.w, max(0.0, w.s - off), max(0.0, w.e - off)) for w in ws], max_inner_pause)
            off = 0.0
        dur = len(a) / SR
        lw = [Word(w.w, round(pos + max(0.0, w.s - off), 3), round(pos + max(0.0, w.e - off), 3)) for w in ws]
        segs.append((pos, a)); spans.append((round(pos, 3), round(pos + dur, 3))); words.extend(lw); per_line.append(lw)
        pos += dur + (pauses[i] if i < len(pauses) else 0.35)
    total = pos + tail
    buf = np.zeros(int(total * SR) + 1, np.float32)
    for p, a in segs:
        s = int(p * SR); buf[s:s + len(a)] += a
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0", out_wav],
                   input=buf.tobytes(), check=True)
    return VoiceTrack(out_wav, total, words, spans, per_line, prov)
