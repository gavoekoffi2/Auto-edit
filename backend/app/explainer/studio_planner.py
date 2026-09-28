"""Plan de montage du Studio face caméra: ce qui apparaît, où, quand.

Contrairement au plan « Motion Pro » (animations plein écran seulement), le
Studio alterne comme un monteur humain:

  accroche      carte flottante sur l'image dès la 1re image (la question, la cible)
  flottants     cartes habillées, tampons, étiquettes posés PAR-DESSUS le visage
  plein écran   panneaux qui démontrent (question, liste, chiffre, solution…)
  appel         écran « écris en commentaire » avec les mots-clés tapés, duo TOI ↔ NOUS
  fin           carte de fin avec le logo, la phrase de clôture et l'au revoir

Chaque élément est calé sur les mots prononcés (champ « at »). Aucun texte à
l'écran n'est inventé: tout vient du discours (corrigé des fautes de
transcription les plus courantes).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from .facecam_planner import (_CTA, _context, _n, clauses, detect, merge_tokens, sentences)

logger = logging.getLogger(__name__)

FULL_SHARE = {"light": 0.20, "medium": 0.30, "heavy": 0.42}
FULL_MIN, FULL_MAX = 2.2, 8.0
FLOAT_MIN, FLOAT_MAX = 1.6, 7.0
FACE_BETWEEN_FULL = 1.3      # visage visible au moins 1,3 s entre deux plein écrans
GAP = 0.25                   # respiration entre deux éléments

# Fautes de transcription fréquentes (texte AFFICHÉ seulement; les temps ne bougent pas)
_FIXES = [
    (r"\bvos mieux que\b", "vaut mieux que"), (r"\b(\w+(?:ir|er|re)) vos mieux\b", r"\1 vaut mieux"), (r"\bvaut mieux que guéris\b", "vaut mieux que guérir"),
    (r"\bmieux que guéris\b", "mieux que guérir"), (r"\bdit[- ]moi\b", "dis-moi"), (r"\bdites[- ]moi\b", "dites-moi"),
    (r"\bindividualement\b", "individuellement"), (r"\best -ce\b", "est-ce"), (r"\brendez -vous\b", "rendez-vous"),
    (r"\bc'est a dire\b", "c'est-à-dire"), (r"\bpeut être\b(?= que)", "peut-être"), (r"\bquand même\b", "quand même"),
]
_NEG = re.compile(r"\b(ne|n')\s*\S+\s+(pas|plus|jamais|rien)\b|\bjamais\b|\battention\b|\bstop\b|\barr[êe]te[zr]?\b", re.I)
_OFFER = re.compile(r"\b(j'organise|je propose|nous proposons|on propose|je vous accompagne|nous offrons|j'offre|consultation|accompagnement|formation|en ligne|gratuit|rendez-vous individuel|individuellement|je vous aide|nous aidons)\b", re.I)
_BYE = re.compile(r"\b(à bient[ôo]t|a bient[ôo]t|merci|à la prochaine|au revoir|ciao|abonne[z-]?)", re.I)
_QWORD = re.compile(r"\b(pourquoi|comment|combien|quand|quel(?:le)?s?|qui|quoi)\b", re.I)
_ADJ_NOUN = re.compile(r"\b(beaux?|belles?|meilleurs?|meilleures?|grands?|grandes?|nouveaux?|nouvelles?|vrais?|vraies?|seule?s?)\s+([a-zà-ÿ'-]{4,})", re.I)
_COMMENT = re.compile(r"commentaire", re.I)
_CUE = re.compile(r"^(?:dites|dit|dis|[ée]crivez|[ée]crire|[ée]cri[st]?|mettez|mets?|tapez|tapes?|notez|notes?)(?:-moi|\s+moi|-nous|\s+nous)?\s*", re.I)


def fix_display(text: str) -> str:
    s = " " + (text or "") + " "
    for pat, rep in _FIXES:
        s = re.sub(pat, rep, s, flags=re.I)
    s = re.sub(r"\s+'", "'", s)
    s = re.sub(r"\s+([,.?!])", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def _txt(ws: list[dict[str, Any]]) -> str:
    return fix_display(" ".join(w["w"] for w in ws))


def _cap(s: str) -> str:
    s = re.sub(r"^(?:alors|et|donc|mais|bon|puis|ben)\s+(?=\S+\s)", "", (s or "").strip(" ,;:."), flags=re.I)
    return s[:1].upper() + s[1:] if s else s


def _short(s: str, n: int) -> str:
    w = s.split()
    return " ".join(w[:n]) + ("…" if len(w) > n else "")


def _at(ws: list[dict[str, Any]], pat: str) -> Optional[float]:
    r = re.compile(pat, re.I)
    return next((w["s"] for w in ws if r.search(w["w"])), None)


_IMPER = re.compile(r"^(?:n')?[a-zà-ÿ]{3,}(?:ons|ez)$", re.I)


def phrases(ws: list[dict[str, Any]], max_words: int = 7, pause: float = 0.18) -> list[list[dict[str, Any]]]:
    """Morceaux affichables: propositions, recoupées aux pauses (> 0,18 s), avant un
    impératif (« restons », « pensez ») et à 7 mots au plus."""
    out: list[list[dict[str, Any]]] = []
    for cl in clauses(ws):
        cur: list[dict[str, Any]] = []
        for k, w in enumerate(cl):
            prev = cl[k - 1] if k else None
            brk = bool(cur) and (
                (prev is not None and w["s"] - prev["e"] > pause)
                or (len(cur) >= 3 and _IMPER.match(_n(w["w"])) and _n(prev["w"]) not in ("nous", "vous", "on"))
                or len(cur) >= max_words)
            if brk:
                out.append(cur); cur = []
            cur.append(w)
        if cur:
            out.append(cur)
    return out


def studio_sentences(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Phrases du moteur, sans doublons de mots aux coupes et sans fragments orphelins."""
    clean: list[dict[str, Any]] = []
    for w in words:
        if clean and _n(w["w"]) == _n(clean[-1]["w"]) and w["s"] - clean[-1]["e"] < 0.3:
            continue  # mot compté deux fois de part et d'autre d'une coupe
        clean.append(w)
    sents = sentences(clean)
    merged: list[dict[str, Any]] = []
    for s in sents:
        short = len(s["words"]) < 4 or s["end"] - s["start"] < 1.0
        if merged and short and s["start"] - merged[-1]["end"] < 0.35 and not re.search(r"[.!?]$", merged[-1]["words"][-1]["w"]):
            m = merged[-1]
            m["words"] = m["words"] + s["words"]; m["end"] = s["end"]; m["text"] = m["text"] + " " + s["text"]
            continue
        merged.append(dict(s))
    for i, s in enumerate(merged):
        s["i"] = i
    return merged


# --------------------------------------------------------------------------- détections
def detect_end(sents: list[dict[str, Any]], duration: float) -> Optional[dict[str, Any]]:
    """Clôture: l'au revoir final + jusqu'à 2 phrases de conclusion juste avant.

    On raisonne sur les MOTS des 12 dernières secondes (les phrases de Whisper
    débordent souvent: « … restons dans | la prévention à bientôt »)."""
    words = [w for s in sents for w in s["words"]]
    tail = [w for w in words if w["s"] >= duration - 12]
    bi = None
    for i in range(len(tail) - 1, -1, -1):
        pair = tail[i]["w"] + " " + (tail[i + 1]["w"] if i + 1 < len(tail) else "")
        if _BYE.search(pair) or _BYE.search(tail[i]["w"]):
            bi = i
            if not re.match(r"^(à|a)$", _n(tail[i]["w"])) or i + 1 >= len(tail):
                break
            break
    if bi is None:
        return None
    bye_ws = tail[bi:]
    # la conclusion commence après le dernier appel (commentaire / rendez-vous)
    last_cta = max((w["e"] for w in tail[:bi] if re.search(r"commentaire|rendez", w["w"], re.I)), default=-1.0)
    pre = [w for w in tail[:bi] if w["s"] > last_cta]
    # proverbe « X vaut mieux que Y » (souvent la phrase de conclusion): gardé entier
    prov = None
    for i in range(len(pre) - 4):
        if _n(pre[i + 1]["w"]) in ("vaut", "vos", "vaux", "vau") and _n(pre[i + 2]["w"]) == "mieux" and _n(pre[i + 3]["w"]) == "que":
            prov = (i, i + 5)
    if prov:
        a, b = prov
        after = [c for c in phrases(pre[b:], 6, pause=0.4) if len(c) >= 3]
        chunks = [pre[a:b]] + after[:1]
    else:
        chunks = [c for c in phrases(pre, 6, pause=0.4) if len(c) >= 3]
    chunks = [c for c in chunks if not re.search(r"\b(vous savez|tu sais|je voudrais (vous|te) dire|ceci)\b", _txt(c), re.I)]
    lines = [{"text": _cap(_txt(c).strip(" ,.")), "at": c[0]["s"]} for c in chunks[-2:]]
    start = (lines[0]["at"] if lines else bye_ws[0]["s"]) - 0.2
    if duration - start < 2.2:
        start = max(0.0, duration - 2.2)
    return {"start": round(start, 3), "end": round(duration, 3),
            "scene": {"type": "end_card", "lines": lines,
                      "bye": {"text": _cap(_txt(bye_ws).strip(" .!")) + (" !" if not lines else ""), "at": bye_ws[0]["s"]}},
            "layout": "full", "tone": "light"}


def detect_comment_cta(sents: list[dict[str, Any]], words: list[dict[str, Any]], tone: str) -> Optional[dict[str, Any]]:
    idx = next((i for i, s in enumerate(sents) if _COMMENT.search(s["text"])), None)
    if idx is None:
        return None
    s = sents[idx]
    ws = s["words"]
    ci = next(i for i, w in enumerate(ws) if _COMMENT.search(w["w"]))
    after = []
    for w in ws[ci + 1:]:
        if _n(w["w"]) in ("et", "pour", "puis", "car", "parce") and after:
            break
        after.append(w)
        if re.search(r"[.!?]$", w["w"]):
            break
    before = []
    for w in reversed(ws[:ci]):
        if _n(w["w"]) in ("en", "dans", "les", "le", "un"):
            if before:
                break
            continue
        if _CUE.match(_n(w["w"])) or _n(w["w"]) in ("moi", "nous") and before:
            break
        before.insert(0, w)
        if len(before) >= 4:
            break
    src = after if len(after) >= 1 else before
    opts: list[dict[str, Any]] = []
    cur: list[dict[str, Any]] = []
    for w in src + [{"w": "|", "s": 0, "e": 0}]:
        if w["w"] == "|" or _n(w["w"]) == "ou":
            if cur:
                txt = _CUE.sub("", _txt(cur)).strip(" ,.;:")
                txt = re.sub(r"^(bien|alors)\s+", "", txt, flags=re.I)
                txt = _CUE.sub("", txt).strip(" ,.;:")
                if txt and len(txt.split()) <= 5:
                    first = next((x for x in cur if _n(x["w"]) not in ("bien", "dit", "dis", "dites", "moi", "nous")), cur[0])
                    opts.append({"text": txt, "at": first["s"]})
            cur = []
            continue
        if _n(w["w"]) == "bien" and not cur:
            continue
        cur.append(w)
    if not opts:
        return None
    # le passage s'étend aux phrases qui suivent tant qu'on parle de rendez-vous / toi et moi
    end_i = idx
    while end_i + 1 < len(sents) and re.search(r"rendez|toi et moi|vous et nous|ensemble|contact", sents[end_i + 1]["text"], re.I) \
            and sents[end_i + 1]["end"] - s["start"] < 11:
        end_i += 1
    span_ws = [w for x in sents[idx:end_i + 1] for w in x["words"]]
    duo_at = _at(span_ws, r"^(toi|vous)$") if re.search(r"\b(toi et moi|toi et nous|vous et nous|vous et moi)\b", " ".join(w["w"] for w in span_ws), re.I) else None
    rdv = _at(span_ws, r"^rendez")
    # départ: juste avant la phrase qui annonce le commentaire (clause précédente comprise si courte)
    st = ws[max(0, ci - 3)]["s"] if ci >= 3 else s["start"]
    end = sents[end_i]["end"]
    sc: dict[str, Any] = {"type": "comment_cta", "options": opts[:2]}
    if duo_at is not None:
        sc["duo_at"] = duo_at
    if rdv is not None:
        sc["stamp"] = "RENDEZ-VOUS" if "rendez" in " ".join(w["w"].lower() for w in span_ws) else ""
        sc["stamp_at"] = rdv
    return {"start": round(max(0.0, st - 0.2), 3), "end": round(end + 0.25, 3), "scene": sc, "layout": "full",
            "tone": "light"}


def hook_card(sents: list[dict[str, Any]], tone: str) -> Optional[dict[str, Any]]:
    if not sents:
        return None
    s = sents[0]
    ws = s["words"]
    txt = _txt(ws)
    m = re.search(r"\b(vous [êe]tes|tu es|êtes-vous|es-tu)\s+(?:un |une |des |le |la |l')?([^,.?!]{3,40})", txt, re.I)
    if m:
        target = re.split(r"\b(il|qui|que|et|mais|depuis|ça|au|à)\b", m.group(2), flags=re.I)[0].strip(" ,")
        title = _cap(" ".join(target.split()[:4])) + " ?"
    else:
        cl = clauses(ws)[0] if clauses(ws) else ws
        title = _cap(_short(_txt(cl), 6))
    end = min(s["end"] + 0.1, 5.5)
    if end < 1.4:
        return None
    sub = None
    rest = [c for c in phrases(ws)[1:] if _NEG.search(_txt(c))]
    sc: dict[str, Any] = {"type": "float_card", "title": title, "at": ws[0]["s"], "pos": "low", "hook": True}
    if rest:
        sub = _cap(_short(_txt(rest[0]), 6))
        sc["sub"] = sub; sc["sub_at"] = rest[0][0]["s"]
    return {"start": 0.05, "end": round(end, 3), "scene": sc, "layout": "float"}


def question_scene(s: dict[str, Any]) -> Optional[dict[str, Any]]:
    ws = s["words"]
    qi = next((i for i, w in enumerate(ws) if _QWORD.fullmatch(_n(w["w"]))), None)
    if qi is None:
        return None
    rest = ws[qi + 1:]
    sub = _cap(_short(_txt(rest).strip(" ?"), 7)) + " ?" if rest else ""
    before = ws[:qi]
    return {"type": "question", "title": _cap(ws[qi]["w"].strip(" ?,")), "at": ws[qi]["s"],
            "sub": sub or _cap(_short(_txt(before), 7)), "sub_at": (rest[0]["s"] if rest else ws[0]["s"])}


def float_candidates(s: dict[str, Any], ctx: dict[str, Any]) -> list[tuple[float, dict[str, Any], tuple[float, float]]]:
    ws = s["words"]
    txt = _txt(ws)
    out = []
    whole = (s["start"], s["end"])
    # tampon: négation / alerte (« ça ne va pas ? »)
    for cl in phrases(ws):
        ct = _txt(cl)
        if _NEG.search(ct) and len(cl) <= 7:
            i0 = next((i for i, w in enumerate(cl) if re.match(r"(ne|n'|ça|ca|jamais|attention|stop|pas)$", _n(w["w"]))), 0)
            seg = cl[max(0, i0 - 1):] if _n(cl[i0]["w"]) in ("ne", "n'") and i0 > 0 else cl[i0:]
            label = _cap(_short(_txt(seg).strip(" ,."), 5))
            if "?" in ct and not label.endswith("?"):
                label = label.rstrip(" ?") + " ?"
            out.append((6.0, {"type": "stamp_word", "text": label.upper(), "at": seg[0]["s"]},
                        (max(s["start"], seg[0]["s"] - 0.35), min(s["end"] + 0.2, seg[-1]["e"] + 1.0))))
            break
    # offre / solution → carte habillée avec badge
    if _OFFER.search(txt):
        cl = next((c for c in clauses(ws) if _OFFER.search(_txt(c))), ws)
        m = re.search(r"(consultations?|accompagnements?|formations?|rendez-vous|séances?|coaching|ateliers?|rencontres?)\s*(individuel\w*|personnalis\w*|gratuit\w*)?", txt, re.I)
        title = _cap((m.group(0) if m else _short(_txt(cl), 5)).strip())
        if m and "individu" in txt.lower() and "individu" not in title.lower():
            title += " individuelle"
        sc = {"type": "float_card", "kicker": "La solution", "title": title,
              "at": (_at(ws, re.escape(m.group(1)[:6])) if m else cl[0]["s"]) or cl[0]["s"], "pos": "low"}
        if re.search(r"en ligne", txt, re.I):
            sc["badge"] = "En ligne"; sc["badge_at"] = _at(ws, r"^ligne") or s["end"] - 0.4; sc["badge_icon"] = "globe"
        rest = [c for c in clauses(ws) if c is not cl and len(c) >= 3]
        if rest:
            sub = _cap(_short(_txt(rest[-1]), 7))
            if title.lower()[:12] not in sub.lower():
                sc["sub"] = sub; sc["sub_at"] = rest[-1][0]["s"]
        out.append((7.0, sc, whole))
    # « un beau pays », « le meilleur moment » → étiquette + carte citation
    m = _ADJ_NOUN.search(txt)
    if m:
        kw = f"{'un ' if not re.match(r'(meilleur|seul)', m.group(1), re.I) else 'le '}{m.group(1)} {m.group(2)}".upper()
        kw = re.sub(r"^UN BEAUX", "UN BEAU", kw)
        out.append((5.0, {"type": "keyword", "text": kw, "at": _at(ws, re.escape(m.group(1)[:4])) or s["start"]}, whole))
    # citation: la phrase clé elle-même (repli, garantit que l'image vit)
    if 5 <= len(ws) <= 26 and not _CTA.search(txt):
        filler = re.compile(r"\b(vous savez|tu sais|je voudrais (vous|te) dire|ceci|en fait|voilà)\b", re.I)
        cls = [c for c in phrases(ws, 7, pause=0.3) if len(c) >= 3 and not filler.search(_txt(c))]
        if not cls:
            return out
        best = max(cls, key=lambda c: sum(len(_n(w["w"])) >= 5 for w in c) + (3 if re.search(r"rendez|consult|gratuit|ligne", _txt(c), re.I) else 0))
        out.append((3.0, {"type": "float_card", "title": _cap(_short(_txt(best), 7)), "at": best[0]["s"], "pos": "low"},
                    (max(s["start"], best[0]["s"] - 0.35), s["end"])))
    return out


# --------------------------------------------------------------------------- planification
def _free(chosen: list[dict[str, Any]], a: float, b: float, full: bool) -> bool:
    for c in chosen:
        g = FACE_BETWEEN_FULL if (full and c["layout"] == "full") else (0.0 if (full or c["layout"] == "full") and b <= c["start"] else GAP)
        if not (b + g <= c["start"] or a >= c["end"] + g):
            return False
    return True


def plan_rules(words: list[dict[str, Any]], duration: float, density: str = "medium") -> list[dict[str, Any]]:
    words = merge_tokens(words)
    sents = studio_sentences(words)
    if not sents:
        return []
    ctx = _context(words, sents)
    tone = ctx["tone"]
    chosen: list[dict[str, Any]] = []
    end = detect_end(sents, duration)
    if end:
        chosen.append(end)
    cta = detect_comment_cta(sents, words, tone)
    if cta and end and cta["end"] > end["start"] - 0.05:
        cta["end"] = end["start"]  # bord à bord: l'appel enchaîne sur la carte de fin
    if cta and _free([c for c in chosen if c is not end], cta["start"], cta["end"], True) and cta["end"] - cta["start"] >= 2.0:
        chosen.append(cta)
    hook = hook_card(sents, tone)
    if hook and _free(chosen, hook["start"], hook["end"], False):
        chosen.append(hook)

    # plein écran (démonstrations)
    budget = FULL_SHARE.get(density, 0.3) * duration
    used = sum(c["end"] - c["start"] for c in chosen if c["layout"] == "full" and c["scene"]["type"] != "end_card")
    cands = []
    for s in sents:
        if s["start"] < 1.0:
            continue
        q = question_scene(s) if "?" in s["text"] or _QWORD.search(s["text"]) else None
        if q:
            cands.append((8.2, s, q, (s["start"] - 0.1, s["end"] + 0.15)))
        for sc, scene, span in detect(s, ctx):
            if scene["type"] in ("title_slam", "cta_button"):
                continue  # remplacés par question / comment_cta
            cands.append((sc, s, scene, span))
    cands.sort(key=lambda c: (-c[0], c[1]["start"]))
    types_used: list[str] = []
    for sc, s, scene, (a, b) in cands:
        if used >= budget:
            break
        a = max(1.0, a - 0.1)
        b = min(duration - 0.3, max(b, a + FULL_MIN), a + FULL_MAX)
        if b - a < FULL_MIN - 0.3 or not _free(chosen, a, b, True):
            continue
        if types_used.count(scene["type"]) >= (2 if scene["type"] in ("icon_cards", "checklist") else 1):
            continue
        chosen.append({"start": round(a, 3), "end": round(b, 3), "scene": scene, "layout": "full",
                       "tone": "dark" if scene["type"] in ("question",) else None, "text": s["text"]})
        types_used.append(scene["type"]); used += b - a

    # flottants: on remplit les moments de visage restants
    fl = []
    for s in sents:
        for sc, scene, span in float_candidates(s, ctx):
            fl.append((sc, s, scene, span))
    fl.sort(key=lambda c: (-c[0], c[1]["start"]))
    kinds: dict[str, int] = {}
    for sc, s, scene, (a, b) in fl:
        a = max(0.05, a - 0.1)
        if scene["type"] == "stamp_word":
            b = min(b, a + 2.4)
        b = min(duration - 0.3, max(b, a + FLOAT_MIN), a + FLOAT_MAX)
        # rogner contre les voisins plutôt que renoncer (un plein écran recouvre la
        # sortie d'un flottant: on peut finir pile à son début)
        for c in sorted(chosen, key=lambda x: x["start"]):
            g = 0.0 if c["layout"] == "full" else GAP
            if c["start"] < a < c["end"] + GAP:
                a = c["end"] + GAP
            if a < c["start"] < b + g:
                b = c["start"] - g
        if b - a < (0.9 if scene["type"] in ("stamp_word", "keyword") else FLOAT_MIN):
            continue
        if not _free(chosen, a, b, False):
            continue
        k = scene["type"]
        if kinds.get(k, 0) >= {"stamp_word": 2, "keyword": 2}.get(k, 9):
            continue
        # jamais deux flottants du même type collés
        prev = max((c for c in chosen if c["end"] <= a + 0.01), key=lambda c: c["end"], default=None)
        if prev and prev["scene"]["type"] == k and a - prev["end"] < 1.0:
            continue
        chosen.append({"start": round(a, 3), "end": round(b, 3), "scene": scene, "layout": "float", "text": s["text"]})
        kinds[k] = kinds.get(k, 0) + 1
    chosen.sort(key=lambda c: c["start"])
    for c in chosen:
        c.setdefault("text", "")
    return chosen


# --------------------------------------------------------------------------- IA (optionnelle)
def plan_llm(words: list[dict[str, Any]], duration: float, density: str, api_key: Optional[str]) -> list[dict[str, Any]]:
    from .writer import _extract_json, chat
    words = merge_tokens(words)
    sents = studio_sentences(words)
    listing = [{"i": s["i"], "t": [round(s["start"], 2), round(s["end"], 2)], "text": fix_display(s["text"])} for s in sents]
    prompt = f"""Tu es monteur vidéo senior (face caméra vertical, publicité Facebook/TikTok). Voici les phrases minutées:
{json.dumps(listing, ensure_ascii=False)}
Durée {duration:.1f} s. Construis le plan d'habillage comme un pro: quelque chose de vivant presque tout le temps, en alternant
- FLOTTANT (par-dessus le visage): float_card {{title, sub?, kicker?, badge?, pos:"low"|"top"}}, stamp_word {{text}} (négation, alerte), keyword {{text}} (lieu, thème en 2-4 mots)
- PLEIN ÉCRAN (le visage disparaît, ≈ {int(FULL_SHARE.get(density, .3) * 100)} % de la durée max): question {{title: mot interrogatif, sub}}, icon_cards {{items:[{{label,icon}}]}}, checklist, timer_ring {{value,unit}} (chiffre prononcé seulement), stat_number, hero_reveal {{name}}, comment_cta {{options:[{{text}}], stamp?}}, end_card {{lines:[{{text}}], bye:{{text}}}}.
Règles: accroche flottante dès 0,05 s; au moins 1,3 s de visage entre deux plein écrans; textes COURTS pris du discours (corrige l'orthographe de la transcription); jamais de chiffre non prononcé; la carte de fin couvre la conclusion et l'au revoir.
Chaque élément: {{"from": i, "to": j, "layout": "float"|"full", "scene": {{"type": ..., ...}}}} (i, j = index de phrases).
Réponds en JSON: {{"items": [...]}}"""
    data = _extract_json(chat(prompt, api_key, temperature=0.5, timeout=90))
    allowed = {"float_card", "stamp_word", "keyword", "question", "icon_cards", "checklist", "timer_ring", "stat_number",
               "hero_reveal", "comment_cta", "end_card", "crowd_select", "loss_drain", "split_compare"}
    spoken = " ".join(w["w"] for w in words)
    nums = set(re.findall(r"\d+", spoken))
    out: list[dict[str, Any]] = []
    for it in data.get("items", []):
        try:
            i, j = int(it["from"]), int(it.get("to", it["from"]))
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= i <= j < len(sents)):
            continue
        sc = dict(it.get("scene") or {})
        if sc.get("type") not in allowed:
            continue
        if sc["type"] in ("stat_number", "timer_ring") and not set(re.findall(r"\d+", str(sc.get("value", "")))) <= nums:
            continue
        layout = "full" if it.get("layout") == "full" or sc["type"] in ("question", "icon_cards", "checklist", "timer_ring",
                                                                          "stat_number", "hero_reveal", "comment_cta", "end_card",
                                                                          "crowd_select", "loss_drain", "split_compare") else "float"
        a = sents[i]["start"] - (0.15 if layout == "full" else 0.1)
        b = sents[j]["end"] + 0.15
        if sc["type"] == "end_card":
            b = duration
        if i == 0 and layout == "float":
            a = 0.05
        a = max(0.0 if layout == "float" else 1.0, a)
        if b - a < 1.2 or not _free(out, a, b, layout == "full"):
            continue
        # les « at » textuels restent des mots: le moteur web les retrouve
        out.append({"start": round(a, 3), "end": round(min(duration, b), 3), "scene": sc, "layout": layout,
                    "tone": "light" if sc["type"] in ("end_card", "comment_cta", "checklist", "hero_reveal") else None,
                    "text": " ".join(s["text"] for s in sents[i:j + 1])})
    out.sort(key=lambda c: c["start"])
    return out


def plan_studio(words: list[dict[str, Any]], duration: float, density: str = "medium",
                api_key: Optional[str] = None) -> tuple[list[dict[str, Any]], str]:
    from .writer import llm_available
    if llm_available(api_key):
        try:
            plan = plan_llm(words, duration, density, api_key)
            if len(plan) >= 3:
                return plan, "ia"
        except Exception as e:  # repli local, jamais bloquant
            logger.warning("plan IA du Studio échoué: %s", e)
    return plan_rules(words, duration, density), "regles"
