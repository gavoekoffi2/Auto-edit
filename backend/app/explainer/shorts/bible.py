"""Versets bibliques — texte EXACT de la Louis Segond 1910 (domaine public).

Le texte vient du fichier embarqué `data/lsg1910.txt.gz` (eBible.org, fraLSG,
« Public Domain »), jamais d'un LLM: une carte verset affiche donc toujours le
vrai texte, ou n'est pas affichée.

    lookup("Jean 14:6")            -> {"ref": "Jean 14:6", "text": "Jésus lui dit: …"}
    find_spoken_refs("… dans Jean chapitre 14 verset 6 …") -> ["Jean 14:6"]
"""
from __future__ import annotations

import gzip
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

DATA = Path(__file__).resolve().parent / "data" / "lsg1910.txt.gz"

# nom affiché -> code du fichier (BibleWorks), variantes acceptées
BOOKS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Genèse", "GEN", ("gn", "gen")), ("Exode", "EXO", ("ex",)), ("Lévitique", "LEV", ("lv",)), ("Nombres", "NUM", ("nb",)),
    ("Deutéronome", "DEU", ("dt",)), ("Josué", "JOS", ()), ("Juges", "JDG", ()), ("Ruth", "RUT", ()),
    ("1 Samuel", "1SA", ()), ("2 Samuel", "2SA", ()), ("1 Rois", "1KI", ()), ("2 Rois", "2KI", ()),
    ("1 Chroniques", "1CH", ()), ("2 Chroniques", "2CH", ()), ("Esdras", "EZR", ()), ("Néhémie", "NEH", ()),
    ("Esther", "EST", ()), ("Job", "JOB", ()), ("Psaumes", "PSA", ("psaume", "ps")), ("Proverbes", "PRO", ("proverbe", "pr")),
    ("Ecclésiaste", "ECC", ("qohelet",)), ("Cantique des cantiques", "SOL", ("cantique",)), ("Ésaïe", "ISA", ("isaie", "esaie")),
    ("Jérémie", "JER", ()), ("Lamentations", "LAM", ()), ("Ézéchiel", "EZE", ()), ("Daniel", "DAN", ()),
    ("Osée", "HOS", ()), ("Joël", "JOE", ()), ("Amos", "AMO", ()), ("Abdias", "OBA", ()), ("Jonas", "JON", ()),
    ("Michée", "MIC", ()), ("Nahum", "NAH", ()), ("Habacuc", "HAB", ()), ("Sophonie", "ZEP", ()), ("Aggée", "HAG", ()),
    ("Zacharie", "ZEC", ()), ("Malachie", "MAL", ()), ("Matthieu", "MAT", ("mt",)), ("Marc", "MAR", ("mc",)),
    ("Luc", "LUK", ("lc",)), ("Jean", "JOH", ("jn",)), ("Actes", "ACT", ("actes des apotres", "ac")), ("Romains", "ROM", ("rm",)),
    ("1 Corinthiens", "1CO", ()), ("2 Corinthiens", "2CO", ()), ("Galates", "GAL", ()), ("Éphésiens", "EPH", ()),
    ("Philippiens", "PHI", ()), ("Colossiens", "COL", ()), ("1 Thessaloniciens", "1TH", ()), ("2 Thessaloniciens", "2TH", ()),
    ("1 Timothée", "1TI", ()), ("2 Timothée", "2TI", ()), ("Tite", "TIT", ()), ("Philémon", "PHM", ()),
    ("Hébreux", "HEB", ()), ("Jacques", "JAM", ()), ("1 Pierre", "1PE", ()), ("2 Pierre", "2PE", ()),
    ("1 Jean", "1JO", ()), ("2 Jean", "2JO", ()), ("3 Jean", "3JO", ()), ("Jude", "JUD", ()), ("Apocalypse", "REV", ("ap",)),
]
MAX_CHARS = 230


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\b(premier|premiere|1er|1re|i)\s+", "1 ", s)
    s = re.sub(r"\b(deuxieme|second|seconde|2e|ii)\s+", "2 ", s)
    s = re.sub(r"\b(troisieme|3e|iii)\s+", "3 ", s)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9: -]", " ", s)).strip()


def _alias_table() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for name, code, alts in BOOKS:
        for a in (name, *alts):
            out[_norm(a)] = (name, code)
    return out


ALIASES = _alias_table()
_BOOK_RX = "|".join(sorted((re.escape(a) for a in ALIASES), key=len, reverse=True))


@lru_cache(maxsize=1)
def _verses() -> dict[str, str]:
    out: dict[str, str] = {}
    if not DATA.exists():
        return out
    with gzip.open(DATA, "rt", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^(\S+) (\d+):(\d+) (.*)$", line.rstrip("\n"))
            if m:
                t = m.group(4).replace("’", "'").strip()
                t = re.sub(r"([,;:.!?])(?=[A-Za-zÀ-ÿ«])", r"\1 ", t)  # « chemin,la vérité » -> « chemin, la vérité »
                out[f"{m.group(1)} {m.group(2)}:{m.group(3)}"] = t
    return out


def parse_ref(ref: str) -> Optional[tuple[str, str, int, int, int]]:
    """« Jean 6:67-68 » -> (nom affiché, code, chapitre, v1, v2)."""
    n = _norm(ref).replace(" : ", ":")
    m = re.match(rf"^({_BOOK_RX})\s+(\d+)\s*(?::|\s|verset|versets)+\s*(\d+)(?:\s*(?:-|a|au|et)\s*(\d+))?$", n)
    if not m:
        return None
    name, code = ALIASES[m.group(1)]
    ch, v1 = int(m.group(2)), int(m.group(3))
    v2 = int(m.group(4)) if m.group(4) else v1
    if v2 < v1 or v2 - v1 > 12:
        v2 = v1
    return name, code, ch, v1, v2


def _shorten(text: str, limit: int = MAX_CHARS, ell: bool = True) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    cut = cut[:max(cut.rfind(" "), limit // 2)].rstrip(" ,;:")
    return cut + ("…" if ell else "")


def _tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[-limit:]
    return cut[cut.find(" ") + 1:].lstrip(" ,;:")


def lookup(ref: str) -> Optional[dict[str, str]]:
    p = parse_ref(ref)
    if not p:
        return None
    name, code, ch, v1, v2 = p
    vs = _verses()
    parts = [vs.get(f"{code} {ch}:{v}") for v in range(v1, v2 + 1)]
    if not parts or any(x is None for x in parts):
        return None
    shown = f"{name} {ch}:{v1}" + (f"-{v2}" if v2 > v1 else "")
    if len(parts) > 2 and sum(len(x) for x in parts) > MAX_CHARS:
        text = _shorten(parts[0], MAX_CHARS // 2, ell=False) + " … " + _tail(parts[-1], MAX_CHARS // 2)
    else:
        text = _shorten(" ".join(parts))
    return {"ref": shown, "text": text, "version": "Louis Segond 1910"}


_SPOKEN = re.compile(rf"\b({_BOOK_RX})\s+(?:chapitre\s+)?(\d{{1,3}})\s*(?:verset|versets|:|v)\s*(\d{{1,3}})(?:\s*(?:a|au|et|-)\s*(\d{{1,3}}))?")


def find_spoken_refs(text: str) -> list[str]:
    """Références citées à voix haute (« Jean chapitre 14 verset 6 »)."""
    out = []
    for m in _SPOKEN.finditer(_norm(text)):
        ref = f"{ALIASES[m.group(1)][0]} {m.group(2)}:{m.group(3)}" + (f"-{m.group(4)}" if m.group(4) else "")
        if lookup(ref) and ref not in out:
            out.append(ref)
    return out
