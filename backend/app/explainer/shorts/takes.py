"""Nettoyage des prises: reprises (même phrase dite plusieurs fois, dans un rush
ou d'un rush à l'autre), faux départs, apartés de tournage, phrases de remplissage.

Détection locale (comparaison de textes) -> ARBITRAGE par Jev (quelle prise
garder ? reprise ou répétition voulue ? faux départ ?) -> repli sur des règles
si Jev n'est pas disponible. Le LLM ne voit ensuite qu'un transcript déjà
dédoublonné: c'est là que Jev fait économiser des jetons.
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any

from . import jev
from .rushes import is_filler, norm

logger = logging.getLogger(__name__)

META = re.compile(r"\b(je recommence|on recommence|je reprends|on reprend|attends|attendez|coupe|on coupe|pardon|excuse[sz]? moi|"
                  r"c est bon|ca tourne|je refais|on refait|non non)\b")


def _toks(u: dict[str, Any]) -> list[str]:
    return norm(u["text"]).split()


def _prefix(a: list[str], b: list[str]) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _similar(a: list[str], b: list[str], cross: bool) -> bool:
    if len(a) < 3 or len(b) < 3:
        return False
    short = min(len(a), len(b))
    if not cross and _prefix(a, b) >= 3 and _prefix(a, b) / short >= 0.6:
        return True   # même début: la phrase a été recommencée
    r = SequenceMatcher(None, a, b, autojunk=False).ratio()
    return r >= (0.72 if cross else 0.62)


def retake_groups(units: list[dict[str, Any]], window: int = 6) -> list[list[int]]:
    """Groupes d'indices (dans `units`) qui sont des prises de la même phrase."""
    toks = [_toks(u) for u in units]
    parent = list(range(len(units)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            same = units[i]["rush"] == units[j]["rush"]
            if same and j - i > window:
                break
            if _similar(toks[i], toks[j], cross=not same):
                parent[find(j)] = find(i)
    groups: dict[int, list[int]] = {}
    for i in range(len(units)):
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def rule_best(units: list[dict[str, Any]], g: list[int]) -> int:
    """Règle de monteur: la DERNIÈRE prise complète (on recommence jusqu'à ce que ce soit bon)."""
    n = {i: len(_toks(units[i])) for i in g}
    longest = max(n.values())
    ok = [i for i in g if n[i] >= 0.8 * longest]
    return max(ok, key=lambda i: (units[i]["rush"], units[i]["s"]))


def rule_false_start(units: list[dict[str, Any]], i: int) -> bool:
    u = units[i]
    t = _toks(u)
    if not t or is_filler(u) or META.search(" ".join(t)) or re.search(r"(\.\.\.|…)$", u["text"].strip()):
        return True  # vide, remplissage, aparté, phrase laissée en suspens
    nxt = units[i + 1] if i + 1 < len(units) and units[i + 1]["rush"] == u["rush"] else None
    if nxt and len(t) <= 4 and not re.search(r"[.?!]$", u["text"]):
        nt = _toks(nxt)
        if nt and nt[0] == t[0]:
            return True
    return False


def _ctx(units: list[dict[str, Any]], a: int, b: int) -> str:
    return "\n".join(f"{units[k]['id']}: {units[k]['text']}" for k in range(max(0, a), min(len(units), b)))


def clean_takes(units: list[dict[str, Any]], use_jev: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Renvoie (unités gardées dans l'ordre d'origine, rapport)."""
    report: dict[str, Any] = {"retake_groups": 0, "dropped": [], "decider": "rules"}
    drop: dict[int, str] = {}
    ask = use_jev and jev.available()

    # 1) reprises
    groups = retake_groups(units)
    report["retake_groups"] = len(groups)
    answers: dict[str, Any] = {}
    if ask and groups:
        qs: dict[str, Any] = {}
        for k, g in enumerate(groups):
            crit = {units[i]["id"]: f"Prise {units[i]['id']} : « {units[i]['text']} »" for i in g}
            qs[f"best_{k}"] = jev.choice(
                "Ces prises disent la même phrase: l'orateur a recommencé. Laquelle garder dans le montage final ? "
                "La bonne prise est complète, fluide, sans hésitation ni phrase abandonnée; à qualité égale, la plus récente.", crit)
            qs[f"retake_{k}"] = jev.noul(
                f"Les passages {', '.join(units[i]['id'] for i in g)} sont des REPRISES de la même phrase "
                "(l'orateur s'est repris ou a refait la prise) et non une répétition voulue pour insister.",
                "reprise de tournage: une seule doit rester", "répétition voulue: toutes doivent rester")
        state = "\n\n".join(f"Groupe {k}:\n" + "\n".join(f"{units[i]['id']}: {units[i]['text']}" for i in g)
                            for k, g in enumerate(groups))
        answers = jev.decide("Transcript de rushes vidéo face caméra (français). " + state, qs)
        if answers:
            report["decider"] = "jev"
    for k, g in enumerate(groups):
        if jev.p_true(answers.get(f"retake_{k}"), 1.0) < 0.3:
            continue  # répétition volontaire: on garde tout
        best_id = jev.picked(answers.get(f"best_{k}"), min_conf=0.35)
        best = next((i for i in g if units[i]["id"] == best_id), None)
        if best is None:
            best = rule_best(units, g)
        for i in g:
            if i != best:
                drop[i] = f"reprise (gardée: {units[best]['id']})"

    # 2) faux départs, apartés, remplissage
    cand = [i for i in range(len(units)) if i not in drop and
            (len(_toks(units[i])) <= 8 or not re.search(r"[.?!]$", units[i]["text"]) or units[i]["text"].endswith("..")
             or META.search(norm(units[i]["text"])))]
    fs_answers: dict[str, Any] = {}
    if ask and cand:
        for a in range(0, len(cand), jev.MAX_QUESTIONS):
            chunk = cand[a:a + jev.MAX_QUESTIONS]
            state = "Transcript de rushes vidéo face caméra (français), un passage par ligne:\n" + _ctx(units, chunk[0] - 4, chunk[-1] + 5)
            qs = {f"fs_{i}": jev.noul(
                f"Le passage {units[i]['id']} (« {units[i]['text']} ») doit être COUPÉ au montage: faux départ, phrase abandonnée "
                "puis reformulée juste après, hésitation, aparté de tournage (« je recommence », « attends »…) ou remplissage sans contenu.",
                "à couper", "contenu utile à garder") for i in chunk}
            fs_answers.update(jev.decide(state, qs))
        if fs_answers:
            report["decider"] = "jev"
    for i in cand:
        p = jev.p_true(fs_answers.get(f"fs_{i}"))
        if p is None:
            if rule_false_start(units, i):
                drop[i] = "faux départ / remplissage"
        elif p >= 0.7 or (p >= 0.5 and is_filler(units[i])):
            drop[i] = f"faux départ (Jev {p:.2f})"

    kept = [u for i, u in enumerate(units) if i not in drop]
    report["dropped"] = [{"id": units[i]["id"], "text": units[i]["text"][:80], "why": why} for i, why in sorted(drop.items())]
    return kept, report
