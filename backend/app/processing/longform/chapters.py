"""Chapitres YouTube d'une vidéo longue (sur la timeline de SORTIE).

Règles YouTube : premier chapitre à 00:00, au moins 3 chapitres, chacun
d'au moins 10 s. On découpe aux changements de sujet :

* dissimilarité lexicale entre la fenêtre avant et la fenêtre après chaque
  début de phrase (mots pleins, mots vides français retirés) ;
* bonus pour les marqueurs de structure (« deuxièmement », « passons à »,
  « étape », « pour conclure »…) et pour les longues pauses coupées au montage.

Les titres viennent de l'IA si une clé OpenRouter existe (titres courts en
français, sans inventer), sinon des mots-clés dominants du chapitre.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Optional

from . import llm
from .takes import norm

STOPWORDS = set("""
a à au aux avec ce ces cet cette c ça ceci cela d de des du dans donc elle elles en encore est et été être
eu fait faire fais il ils je j l la le les leur leurs lui ma mais me mes moi mon même n ne ni nos notre nous
on ont ou où par pas peu plus pour qu que quel quelle qui s sa sans se ses si son sont sur ta te tes toi ton
tous tout toute toutes tu un une vos votre vous y très bien alors voilà quoi bon ben euh ah oui non ok okay
comme ai as avait avez avons aussi parce puis car là ici cest cest-à-dire juste vraiment chose choses fois
va vais vas vont veux veut peut peux dit dire faut the and to of is it that you this for on with are be
""".split())

STRUCTURE_MARKERS = [
    "premièrement", "deuxièmement", "troisièmement", "ensuite", "maintenant",
    "passons", "passons à", "on passe", "étape", "numéro", "point numéro",
    "première chose", "deuxième chose", "troisième chose", "dernière chose",
    "pour conclure", "en conclusion", "pour finir", "enfin", "parlons",
    "revenons", "la question", "le premier", "le deuxième", "le troisième",
    "astuce", "erreur numéro", "secret",
]


def sentences(words_out: List[dict]) -> List[dict]:
    """Mots (temps de sortie) -> phrases {start, end, text, tokens}."""
    out: List[dict] = []
    cur: List[dict] = []
    for i, w in enumerate(words_out):
        cur.append(w)
        nxt = words_out[i + 1] if i + 1 < len(words_out) else None
        end_punct = w["word"][-1:] in ".!?…"
        gap = (nxt["start"] - w["end"]) if nxt else 99
        if end_punct or gap > 0.7 or len(cur) >= 40 or nxt is None:
            text = " ".join(x["word"] for x in cur)
            toks = [t for t in (norm(x["word"]) for x in cur) if t]
            out.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": text,
                        "tokens": toks, "gap_before": float(cur[0].get("gap_before", 0.0))})
            cur = []
    return out


def _bag(sents: List[dict]) -> Counter:
    c: Counter = Counter()
    for s in sents:
        c.update(t for t in s["tokens"] if len(t) > 2 and t not in STOPWORDS)
    return c


def _cos(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    num = sum(a[k] * b[k] for k in set(a) & set(b))
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0


def _marker_bonus(text: str) -> float:
    t = " ".join(norm(x) for x in text.split()[:8])
    return 0.35 if any(m in t for m in STRUCTURE_MARKERS) else 0.0


def plan_boundaries(sents: List[dict], duration: float) -> List[int]:
    """Indices des phrases qui ouvrent un chapitre (0 inclus)."""
    if duration < 120 or len(sents) < 6:
        return [0]
    target = min(360.0, max(90.0, duration / 7.0))
    k = max(3, int(round(duration / target)))
    min_gap = target * 0.55
    win = 45.0
    scores: List[tuple] = []
    for i in range(1, len(sents)):
        t = sents[i]["start"]
        if t < 25.0 or duration - t < 25.0:
            continue
        before = [s for s in sents[:i] if s["start"] >= t - win]
        after = [s for s in sents[i:] if s["start"] <= t + win]
        sim = _cos(_bag(before), _bag(after))
        score = (1.0 - sim) + _marker_bonus(sents[i]["text"]) \
            + min(0.25, sents[i].get("gap_before", 0.0) * 0.15)
        scores.append((score, i))
    scores.sort(reverse=True)
    chosen: List[int] = []
    for score, i in scores:
        t = sents[i]["start"]
        if all(abs(t - sents[j]["start"]) >= min_gap for j in chosen):
            chosen.append(i)
        if len(chosen) >= k - 1:
            break
    return [0] + sorted(chosen)


def _keyword_title(sents: List[dict]) -> str:
    bag = _bag(sents)
    words = [w for w, _ in bag.most_common(3)]
    if not words:
        return "Suite"
    return " · ".join(w.capitalize() for w in words[:2])


def _llm_titles(chunks: List[str]) -> Optional[List[str]]:
    joined = "\n\n".join(f"[{i + 1}] {c[:1400]}" for i, c in enumerate(chunks))
    prompt = (
        "Tu es monteur YouTube. Voici les chapitres d'une vidéo, dans l'ordre. "
        "Donne un titre de chapitre court (2 à 6 mots), en français, clair et "
        "accrocheur, fidèle au contenu (n'invente rien). Le premier chapitre "
        "s'appelle souvent « Introduction » s'il présente la vidéo. Réponds "
        f"UNIQUEMENT par un tableau JSON de {len(chunks)} chaînes.\n\n{joined}"
    )
    res = llm.ask_json(prompt)
    if isinstance(res, list) and len(res) == len(chunks) and all(isinstance(x, str) for x in res):
        return [re.sub(r"\s+", " ", x).strip().strip('"')[:60] or "Suite" for x in res]
    return None


def build_chapters(words_out: List[dict], duration: float,
                   use_llm: bool = True) -> dict:
    sents = sentences(words_out)
    idx = plan_boundaries(sents, duration)
    groups: List[List[dict]] = []
    for a, b in zip(idx, idx[1:] + [len(sents)]):
        groups.append(sents[a:b])
    starts = [0.0] + [sents[i]["start"] for i in idx[1:]]
    titles = None
    source = "keywords"
    if use_llm and len(groups) >= 2:
        titles = _llm_titles([" ".join(s["text"] for s in g) for g in groups])
        if titles:
            source = "llm"
    if not titles:
        titles = ["Introduction"] + [_keyword_title(g) for g in groups[1:]]
    chapters = [{"start": round(max(0.0, st - (0.15 if i else 0.0)), 3), "title": t}
                for i, (st, t) in enumerate(zip(starts, titles))]
    # YouTube: >= 3 chapitres de >= 10 s, sinon la liste est ignorée.
    valid = len(chapters) >= 3 and all(
        (b["start"] - a["start"]) >= 10 for a, b in zip(chapters, chapters[1:])) and \
        duration - chapters[-1]["start"] >= 10
    return {"chapters": chapters, "titles_source": source, "youtube_valid": valid,
            "text": youtube_text(chapters)}


def fmt_ts(t: float) -> str:
    t = int(max(0, t))
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def youtube_text(chapters: List[dict]) -> str:
    return "\n".join(f"{fmt_ts(c['start'])} {c['title']}" for c in chapters)
