"""Coupe de la voix d'une vidéo longue — la dernière prise gagne.

Règles (méthode youtube-clean, adaptée au français) :

* la parole est découpée en « passages » aux pauses >= ``gap_split`` ;
* passages ne contenant que des tics (« euh », « donc », « bon »…) : retirés ;
* marqueurs de reprise en fin de passage (« je reprends », « on recommence »,
  « coupe ça »…) : le passage est coupé au marqueur ;
* faux départs : un passage aussitôt redit (en entier ou en préfixe) par le
  suivant disparaît ;
* phrases répétées plus loin (reprise après une erreur) : la plus ANCIENNE
  disparaît, la dernière prise reste ;
* bégaiements (« il faut il faut ») : la première occurrence disparaît ;
* aucun micro-fragment isolé (< ``min_fragment`` s) qui ferait un double
  jump-cut : il est rattaché à son voisin ou signalé ;
* les points de coupe tombent dans le creux d'énergie (RMS, trames de 10 ms)
  du silence entre deux mots, avec un peu d'air naturel conservé.

Tout est déterministe et traçable : chaque passage retiré apparaît dans le
rapport avec sa raison et son texte, pour que le créateur voie ce qui a été
coupé.
"""
from __future__ import annotations

import difflib
import re
import wave
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

_PUNCT = re.compile(r"[^\wàâäéèêëïîôöùûüÿçœæ' ]+", re.UNICODE)

FILLERS = {
    "euh", "heu", "hum", "hm", "hmm", "ah", "eh", "bah", "ben", "hein", "bon",
    "voilà", "donc", "alors", "en fait", "genre", "quoi", "ouais", "ok", "okay",
    "du coup", "tu vois", "vous voyez", "uh", "um", "so",
}

RETAKE_MARKERS = [
    "je reprends", "je recommence", "on recommence", "on reprend", "je refais",
    "on refait", "coupe ça", "coupez", "attends je", "non attends", "pardon je",
    "recommençons", "reprenons", "je me suis trompé", "je me suis trompée",
    "c'est pas bon", "encore une fois", "let me start again", "cut that",
]


@dataclass
class TakeConfig:
    gap_split: float = 0.40        # pause qui sépare deux passages
    lead_air: float = 0.08         # air conservé avant un passage (silence)
    tail_air: float = 0.10         # air conservé après un passage (silence)
    micro_air: float = 0.03        # marge aux coupes « intelligentes »
    max_join_gap: float = 0.22     # silence max conservé à un raccord
    min_fragment: float = 0.80     # sous ce seuil un passage isolé est suspect
    retake_similarity: float = 0.78
    retake_max_words: int = 30
    repeat_similarity: float = 0.80
    repeat_min_words: int = 4
    repeat_window_s: float = 90.0  # une reprise redit la phrase dans ce délai
    stutter_min_span: float = 0.30
    snap_to_trough: bool = True


def norm(token: str) -> str:
    return _PUNCT.sub("", (token or "").lower()).strip()


def flatten_words(vu: dict) -> List[dict]:
    words: List[dict] = []
    for seg in vu.get("segments", []):
        for w in seg.get("words", []):
            if (w.get("word") or "").strip():
                words.append({"word": w["word"].strip(),
                              "start": float(w["start"]), "end": float(w["end"])})
    words.sort(key=lambda w: w["start"])
    # Scribe rend parfois des mots qui se chevauchent de quelques ms.
    for a, b in zip(words, words[1:]):
        if b["start"] < a["end"]:
            a["end"] = max(a["start"], b["start"])
    return words


def _tokens(run: Sequence[dict]) -> List[str]:
    return [t for t in (norm(w["word"]) for w in run) if t]


def _similar(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _text(run: Sequence[dict]) -> str:
    return " ".join(w["word"] for w in run)


def is_filler_run(run: Sequence[dict]) -> bool:
    toks = _tokens(run)
    if not toks:
        return True
    if " ".join(toks) in FILLERS:
        return True
    i = 0
    while i < len(toks):
        two = " ".join(toks[i:i + 2])
        if two in FILLERS:
            i += 2
        elif toks[i] in FILLERS:
            i += 1
        else:
            return False
    return True


def split_runs(words: List[dict], gap: float) -> List[List[dict]]:
    if not words:
        return []
    runs: List[List[dict]] = [[words[0]]]
    for prev, nxt in zip(words, words[1:]):
        if nxt["start"] - prev["end"] >= gap:
            runs.append([nxt])
        else:
            runs[-1].append(nxt)
    return runs


def trim_retake_marker(run: List[dict]) -> Tuple[List[dict], bool]:
    """Coupe le passage au marqueur de reprise s'il est en fin de passage."""
    toks = [norm(w["word"]) for w in run]
    best: Optional[int] = None
    for marker in RETAKE_MARKERS:
        m = marker.split()
        n = len(m)
        for i in range(len(toks) - n, -1, -1):
            if toks[i:i + n] == m:
                if len(toks) - (i + n) <= 5:      # seulement en FIN de passage
                    best = i if best is None else min(best, i)
                break
    if best is None:
        return run, False
    return run[:best], True


def _starts_same(a: List[str], b: List[str], sim: float) -> bool:
    """b recommence a (a est un préfixe approximatif de b)."""
    if len(b) <= len(a):
        return False
    return _similar(a, b[:len(a)]) >= sim


def select_takes(runs: List[List[dict]], cfg: TakeConfig,
                 removed: List[dict]) -> List[List[dict]]:
    """Faux départs + répétitions éloignées : la DERNIÈRE prise gagne."""
    toks = [_tokens(r) for r in runs]
    n = len(runs)
    drop = [False] * n

    # 1) faux départs / doublons immédiats (a puis b qui redit a)
    for i in range(n - 1):
        a = toks[i]
        if not (2 <= len(a) <= cfg.retake_max_words):
            continue
        # on regarde les 2 passages suivants (un « euh » peut s'intercaler)
        for j in (i + 1, i + 2):
            if j >= n:
                break
            b = toks[j]
            if not b:
                continue
            if _starts_same(a, b, cfg.retake_similarity) or (
                    abs(len(a) - len(b)) <= 2 and _similar(a, b) >= cfg.retake_similarity):
                drop[i] = True
                removed.append({"reason": "faux_depart" if j == i + 1 else "phrase_repetee",
                                "start": runs[i][0]["start"],
                                "end": runs[i][-1]["end"], "text": _text(runs[i])})
                break
            # une phrase abandonnée dont la fin reprend au début du suivant
            k = min(len(a), len(b), 6)
            if k >= 3 and len(a) <= 12 and _similar(a[:k], b[:k]) >= 0.85:
                drop[i] = True
                removed.append({"reason": "phrase_abandonnee", "start": runs[i][0]["start"],
                                "end": runs[i][-1]["end"], "text": _text(runs[i])})
                break

    # 2) répétitions éloignées (reprise d'une phrase ratée plus tard)
    for i in range(n):
        if drop[i] or len(toks[i]) < cfg.repeat_min_words:
            continue
        t_i = runs[i][0]["start"]
        for j in range(i + 1, n):
            if runs[j][0]["start"] - t_i > cfg.repeat_window_s:
                break
            if drop[j] or len(toks[j]) < cfg.repeat_min_words:
                continue
            a, b = toks[i], toks[j]
            if _similar(a, b) >= cfg.repeat_similarity or (
                    len(a) >= 6 and _starts_same(a, b, cfg.repeat_similarity)):
                drop[i] = True
                removed.append({"reason": "phrase_repetee", "start": runs[i][0]["start"],
                                "end": runs[i][-1]["end"], "text": _text(runs[i])})
                break
    return [r for k, r in enumerate(runs) if not drop[k]]


def split_stutters(run: List[dict], cfg: TakeConfig,
                   removed: List[dict]) -> List[Tuple[List[dict], bool, bool]]:
    """Retire les répétitions immédiates (1 à 3 mots). -> [(sous-passage, micro_debut, micro_fin)]."""
    toks = [norm(w["word"]) for w in run]
    out: List[Tuple[List[dict], bool, bool]] = []
    cur: List[dict] = []
    cur_micro = False
    i = 0
    while i < len(run):
        cut = 0
        for k in (3, 2, 1):
            if i + 2 * k > len(run):
                continue
            first, second = toks[i:i + k], toks[i + k:i + 2 * k]
            if first == second and all(first):
                if run[i + k]["start"] - run[i]["start"] >= cfg.stutter_min_span:
                    cut = k
                    break
        if cut:
            removed.append({"reason": "begaiement", "start": run[i]["start"],
                            "end": run[i + cut - 1]["end"], "text": _text(run[i:i + cut])})
            if cur:
                out.append((cur, cur_micro, True))
            cur, cur_micro = [], True
            i += cut
        else:
            cur.append(run[i])
            i += 1
    if cur:
        out.append((cur, cur_micro, False))
    return out


# --------------------------------------------------------------------------- #
# Audio : creux d'énergie pour poser les coupes
# --------------------------------------------------------------------------- #
class Envelope:
    """Énergie RMS par trames de 10 ms d'un wav mono 16 kHz."""

    HOP = 0.010

    def __init__(self, rms: np.ndarray):
        self.rms = rms

    @classmethod
    def from_wav(cls, path: str) -> "Envelope":
        with wave.open(path, "rb") as w:
            sr = w.getframerate()
            ch = w.getnchannels()
            hop = int(sr * cls.HOP)
            frames = []
            chunk = hop * 6000                     # ~1 min par lecture
            while True:
                raw = w.readframes(chunk)
                if not raw:
                    break
                x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                if ch > 1:
                    x = x.reshape(-1, ch).mean(1)
                n = len(x) // hop
                if n:
                    frames.append(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) / 32768.0)
        rms = np.concatenate(frames) if frames else np.zeros(1, np.float32)
        return cls(rms)

    def trough(self, lo: float, hi: float) -> float:
        """Instant (s) de plus faible énergie dans [lo, hi]."""
        a, b = int(lo / self.HOP), int(hi / self.HOP)
        a, b = max(0, a), min(len(self.rms), b)
        if b - a < 2:
            return (lo + hi) / 2.0
        k = int(np.argmin(self.rms[a:b]))
        return (a + k + 0.5) * self.HOP


# --------------------------------------------------------------------------- #
# Construction des plages conservées
# --------------------------------------------------------------------------- #
def _pieces_to_ranges(pieces: List[Tuple[List[dict], bool, bool]], words: List[dict],
                      cfg: TakeConfig, duration: float,
                      env: Optional[Envelope]) -> List[dict]:
    starts = [w["start"] for w in words]
    ends = [w["end"] for w in words]
    import bisect

    def prev_word_end(t: float) -> float:
        i = bisect.bisect_left(starts, t - 1e-6) - 1
        return ends[i] if i >= 0 else 0.0

    def next_word_start(t: float) -> float:
        i = bisect.bisect_right(ends, t + 1e-6)
        while i < len(starts) and starts[i] < t:
            i += 1
        return starts[i] if i < len(starts) else duration

    ranges: List[dict] = []
    for piece, micro_s, micro_e in pieces:
        if not piece:
            continue
        s_word, e_word = piece[0]["start"], piece[-1]["end"]
        lead = cfg.micro_air if micro_s else cfg.lead_air
        tail = cfg.micro_air if micro_e else cfg.tail_air
        lo = max(prev_word_end(s_word), s_word - lead)
        hi = min(next_word_start(e_word), e_word + tail)
        start, end = lo, hi
        if env is not None and cfg.snap_to_trough:
            # le creux d'énergie entre le mot voisin et notre mot, sans
            # jamais entamer notre premier / dernier mot
            if s_word - lo > 0.02:
                start = env.trough(lo, max(lo + 0.01, s_word - 0.01))
            if hi - e_word > 0.02:
                end = env.trough(min(hi - 0.01, e_word + 0.02), hi)
        start = max(0.0, start)
        end = min(duration, end) if duration else end
        if ranges and start < ranges[-1]["end"]:
            start = ranges[-1]["end"]
        if end - start > 0.05:
            ranges.append({"start": round(start, 3), "end": round(end, 3),
                           "text": _text(piece), "n_words": len(piece)})
    return ranges


def _merge_contiguous(ranges: List[dict], cfg: TakeConfig) -> List[dict]:
    """Fusionne les plages séparées par un simple souffle (pas de vraie coupe)."""
    out: List[dict] = []
    for r in ranges:
        if out and r["start"] - out[-1]["end"] <= min(0.06, cfg.max_join_gap):
            out[-1]["end"] = r["end"]
            out[-1]["text"] += " " + r["text"]
            out[-1]["n_words"] += r["n_words"]
        else:
            out.append(dict(r))
    return out


def _resolve_micro_fragments(ranges: List[dict], cfg: TakeConfig,
                             report: dict) -> List[dict]:
    """Rattache les fragments < min_fragment à un voisin proche (même prise)."""
    out: List[dict] = []
    flagged = []
    for r in ranges:
        dur = r["end"] - r["start"]
        if dur < cfg.min_fragment and out and r["start"] - out[-1]["end"] <= 0.60:
            out[-1]["end"] = r["end"]                 # garde la pause naturelle
            out[-1]["text"] += " " + r["text"]
            out[-1]["n_words"] += r["n_words"]
            continue
        out.append(dict(r))
    # Second passage : un fragment encore isolé se colle au SUIVANT s'il est proche.
    final: List[dict] = []
    i = 0
    while i < len(out):
        r = out[i]
        dur = r["end"] - r["start"]
        if (dur < cfg.min_fragment and i + 1 < len(out)
                and out[i + 1]["start"] - r["end"] <= 0.60):
            nxt = dict(out[i + 1])
            nxt["start"] = r["start"]
            nxt["text"] = r["text"] + " " + nxt["text"]
            nxt["n_words"] += r["n_words"]
            out[i + 1] = nxt
            i += 1
            continue
        if dur < cfg.min_fragment:
            flagged.append({"start": r["start"], "end": r["end"], "text": r["text"]})
        final.append(r)
        i += 1
    report["micro_fragments"] = flagged
    return final


def build_ranges(vu: dict, cfg: Optional[TakeConfig] = None,
                 env: Optional[Envelope] = None,
                 duration: Optional[float] = None) -> Tuple[List[dict], dict]:
    """vu (transcript mot-à-mot) -> (plages source conservées, rapport)."""
    cfg = cfg or TakeConfig()
    words = flatten_words(vu)
    report: dict = {"removed": []}
    if not words:
        return [], report
    duration = float(duration or vu.get("duration") or words[-1]["end"])
    removed: List[dict] = report["removed"]

    runs = split_runs(words, cfg.gap_split)
    kept_runs: List[List[dict]] = []
    for r in runs:
        if is_filler_run(r):
            removed.append({"reason": "tic_de_langage", "start": r[0]["start"],
                            "end": r[-1]["end"], "text": _text(r)})
            continue
        trimmed, had_marker = trim_retake_marker(r)
        if had_marker:
            cut = r[len(trimmed):]
            removed.append({"reason": "marqueur_reprise", "start": cut[0]["start"],
                            "end": cut[-1]["end"], "text": _text(cut)})
        if trimmed and not is_filler_run(trimmed):
            kept_runs.append(trimmed)

    kept_runs = select_takes(kept_runs, cfg, removed)

    pieces: List[Tuple[List[dict], bool, bool]] = []
    for r in kept_runs:
        # tics en tête / en queue de passage (« euh donc … »)
        while len(r) > 1 and norm(r[0]["word"]) in {"euh", "heu", "hum", "hm", "hmm", "uh", "um"}:
            removed.append({"reason": "tic_de_langage", "start": r[0]["start"],
                            "end": r[0]["end"], "text": r[0]["word"]})
            r = r[1:]
        while len(r) > 1 and norm(r[-1]["word"]) in {"euh", "heu", "hum", "hm", "hmm", "uh", "um"}:
            removed.append({"reason": "tic_de_langage", "start": r[-1]["start"],
                            "end": r[-1]["end"], "text": r[-1]["word"]})
            r = r[:-1]
        pieces.extend(split_stutters(r, cfg, removed))

    ranges = _pieces_to_ranges(pieces, words, cfg, duration, env)
    ranges = _merge_contiguous(ranges, cfg)
    ranges = _resolve_micro_fragments(ranges, cfg, report)

    kept = sum(r["end"] - r["start"] for r in ranges)
    report.update({
        "source_duration": round(duration, 3),
        "kept_duration": round(kept, 3),
        "removed_duration": round(max(0.0, duration - kept), 3),
        "ranges": len(ranges),
        "removed_counts": _count(removed),
    })
    removed.sort(key=lambda x: x["start"])
    return ranges, report


def _count(removed: List[dict]) -> dict:
    out: dict = {}
    for r in removed:
        out[r["reason"]] = out.get(r["reason"], 0) + 1
    return out


# --------------------------------------------------------------------------- #
# Vérifications texte (passe B de youtube-clean) sur la version coupée
# --------------------------------------------------------------------------- #
def repeated_ngrams(ranges: List[dict], n: int = 5) -> List[str]:
    """5-grammes présents deux fois dans le texte final -> à inspecter."""
    toks: List[str] = []
    for r in ranges:
        toks.extend(t for t in (norm(x) for x in r["text"].split()) if t)
    seen: dict = {}
    dup = []
    for i in range(len(toks) - n + 1):
        g = " ".join(toks[i:i + n])
        if g in seen and i - seen[g] >= n:
            dup.append(g)
        seen.setdefault(g, i)
    return sorted(set(dup))


def source_to_output(t: float, ranges: List[dict]) -> Optional[float]:
    """Temps source -> temps de sortie (None si t est dans une coupe)."""
    acc = 0.0
    for r in ranges:
        if r["start"] - 1e-6 <= t <= r["end"] + 1e-6:
            return acc + (t - r["start"])
        acc += r["end"] - r["start"]
    return None
