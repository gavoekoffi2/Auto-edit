"""Habillage 16:9 d'une vidéo longue — un seul fichier ASS rendu en une passe.

* sous-titres en bas, ligne de 4 à 7 mots, mot prononcé mis en couleur
  (karaoké), léger pop à l'apparition ;
* popups mots-clés (chiffres, prix, mots d'emphase) — au plus un toutes les
  ~18 s, jamais sur une carte chapitre ;
* cartes chapitre PLEIN ÉCRAN animées (entrée glissée, titre qui se pose,
  sortie glissée) à chaque début de chapitre ;
* chaque visuel émet sa cue d'effet sonore (le son est lié à l'image, pas
  posé au hasard).

Tout le texte vient de ce que la personne DIT (transcript) : aucun chiffre
inventé.
"""
from __future__ import annotations

import random
import re
from typing import List, Optional, Tuple

from .styles import LongformStyle, ass_color
from .takes import norm

W, H = 1920, 1080

EMPHASIS = {
    "important", "importante", "essentiel", "essentielle", "secret", "secrets",
    "erreur", "erreurs", "gratuit", "gratuite", "gratuitement", "jamais",
    "toujours", "attention", "astuce", "astuces", "argent", "facile", "rapide",
    "rapidement", "problème", "problèmes", "solution", "solutions", "résultat",
    "résultats", "méthode", "stratégie", "clé", "clés", "danger", "piège",
    "pièges", "incroyable", "énorme", "simple", "puissant", "puissante",
    "bénéfice", "bénéfices", "client", "clients", "vente", "ventes", "business",
    "chiffre", "objectif", "succès", "échec", "preuve", "garantie",
}
NUM_WORDS = {
    "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
    "cent", "cents", "mille", "million", "millions", "milliard", "milliards",
}
UNITS = {
    "%", "pourcent", "pour", "euros", "euro", "€", "fcfa", "francs", "cfa",
    "dollars", "$", "minutes", "heures", "jours", "semaines", "mois", "ans",
    "années", "clients", "personnes", "abonnés", "vues", "étapes", "fois",
    "secondes", "k",
}


def _t(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


# --------------------------------------------------------------------------- #
# En-tête
# --------------------------------------------------------------------------- #
def header(st: LongformStyle) -> str:
    box = st.caption_box
    cap_primary = ass_color(st.caption_primary)
    cap_outline = ass_color(st.caption_box_color if box else st.caption_outline, 0)
    cap_back = ass_color(st.caption_box_color, 0 if box else 140)
    border_style = 3 if box else 1
    outline = 14 if box else st.caption_outline_px
    shadow = 0 if box else 2
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{st.caption_font},{st.caption_size},{cap_primary},{cap_primary},"
        f"{cap_outline},{cap_back},-1,0,0,0,100,100,0,0,{border_style},{outline},{shadow},2,"
        f"180,180,{st.caption_margin_v},1",
        f"Style: Popup,{st.title_font},64,{ass_color(st.popup_fg)},{ass_color(st.popup_fg)},"
        f"{ass_color(st.popup_bg)},{ass_color(st.popup_bg)},-1,0,0,0,100,100,1,0,3,22,0,9,"
        f"80,90,90,1",
        f"Style: CardBG,Arial,20,{ass_color(st.card_bg)},{ass_color(st.card_bg)},"
        f"{ass_color(st.card_bg)},{ass_color(st.card_bg)},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: CardLabel,{st.caption_font},40,{ass_color(st.card_accent)},"
        f"{ass_color(st.card_accent)},&H00000000,&H00000000,-1,0,0,0,100,100,6,0,1,0,0,5,"
        f"160,160,0,1",
        f"Style: CardTitle,{st.title_font},120,{ass_color(st.card_fg)},{ass_color(st.card_fg)},"
        f"&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,0,0,5,200,200,0,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    return "\n".join(lines) + "\n"


def _dlg(layer: int, a: float, b: float, style: str, text: str) -> str:
    return f"Dialogue: {layer},{_t(a)},{_t(b)},{style},,0,0,0,,{text}\n"


# --------------------------------------------------------------------------- #
# Sous-titres
# --------------------------------------------------------------------------- #
def chunk_words(words: List[dict], per_line: int) -> List[List[dict]]:
    chunks: List[List[dict]] = []
    cur: List[dict] = []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["start"] - w["end"]) if nxt else 9.0
        span = w["end"] - cur[0]["start"]
        ends = w["word"][-1:] in ".!?…"
        soft = w["word"][-1:] in ",;:"
        if (len(cur) >= per_line or gap > 0.5 or span > 3.2 or nxt is None
                or (ends and len(cur) >= 2) or (soft and len(cur) >= max(3, per_line - 2))):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def caption_events(words: List[dict], st: LongformStyle,
                   sfx: List[dict]) -> str:
    out = []
    hl = ass_color(st.caption_highlight)
    karaoke = st.caption_highlight.upper() != st.caption_primary.upper()
    chunks = chunk_words(words, st.words_per_line)
    for ci, ch in enumerate(chunks):
        a = ch[0]["start"]
        nxt_start = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else ch[-1]["end"] + 0.6
        b = min(ch[-1]["end"] + 0.35, nxt_start)
        texts = [_esc(w["word"].upper() if st.caption_uppercase else w["word"]) for w in ch]
        pop = r"{\fscx92\fscy92\t(0,110,\fscx100\fscy100)}"
        if not karaoke:
            out.append(_dlg(1, a, b, "Caption", pop + " ".join(texts)))
        else:
            for k, w in enumerate(ch):
                s = a if k == 0 else w["start"]
                e = ch[k + 1]["start"] if k + 1 < len(ch) else b
                if e <= s:
                    continue
                parts = []
                for j, tx in enumerate(texts):
                    if j == k:
                        parts.append(r"{\c" + hl + r"}" + tx + r"{\r}")
                    else:
                        parts.append(tx)
                lead = pop if k == 0 else ""
                out.append(_dlg(1, s, e, "Caption", lead + " ".join(parts)))
        if st.caption_click_db is not None:
            sfx.append({"t": a, "name": st.sfx_caption_click, "db": st.caption_click_db,
                        "kind": "caption"})
    return "".join(out)


# --------------------------------------------------------------------------- #
# Popups mots-clés
# --------------------------------------------------------------------------- #
def _is_unit(word: str) -> bool:
    raw = word.strip().lower().rstrip(",.;:!?…")
    return raw in UNITS or norm(raw) in UNITS


def _is_number(tok: str) -> bool:
    return bool(re.fullmatch(r"\d+([.,]\d+)?%?", tok)) or tok in NUM_WORDS


def find_keywords(words: List[dict], blocked: List[Tuple[float, float]],
                  every: float = 18.0) -> List[dict]:
    """Moments forts du discours -> [{start, end, text}] (texte = ce qui est dit).

    Les chiffres (prix, pourcentages, quantités) passent avant les mots
    d'emphase ; deux popups sont toujours espacés d'au moins ``every`` s.
    """
    cands: List[dict] = []
    n = len(words)
    for i, w in enumerate(words):
        t = w["start"]
        if t < 3.0:
            continue
        if any(a - 1.0 <= t <= b + 1.0 for a, b in blocked):
            continue
        tok = norm(w["word"])
        text = None
        prio = 1
        if _is_number(tok):
            prio = 2
            j = i + 1
            parts = [w["word"]]
            while j < n and j <= i + 3 and (_is_number(norm(words[j]["word"]))
                                          or _is_unit(words[j]["word"])):
                parts.append(words[j]["word"])
                j += 1
            if len(parts) >= 2 or re.search(r"\d", tok):
                text = " ".join(parts)
        elif tok in EMPHASIS and len(tok) >= 4:
            text = w["word"]
        if text:
            text = re.sub(r"[,.;:!?…]+$", "", text).strip()
            if text:
                cands.append({"start": t, "end": t + 1.7, "text": text, "prio": prio})
    picks: List[dict] = []
    for c in sorted(cands, key=lambda c: (-c["prio"], c["start"])):
        if all(abs(c["start"] - p["start"]) >= every for p in picks):
            picks.append(c)
    picks.sort(key=lambda c: c["start"])
    return [{k: v for k, v in p.items() if k != "prio"} for p in picks]


def popup_events(picks: List[dict], st: LongformStyle, sfx: List[dict],
                 rng: random.Random) -> str:
    out = []
    for p in picks:
        a, b = p["start"], p["end"]
        tx = _esc(p["text"].upper())
        anim = (r"{\fad(90,160)\fscx55\fscy55\t(0,140,\fscx112\fscy112)"
                r"\t(140,240,\fscx100\fscy100)}")
        out.append(_dlg(3, a, b, "Popup", anim + tx))
        if st.sfx_popup:
            sfx.append({"t": a, "name": rng.choice(st.sfx_popup), "db": st.sfx_db,
                        "kind": "popup"})
    return "".join(out)


# --------------------------------------------------------------------------- #
# Cartes chapitre plein écran
# --------------------------------------------------------------------------- #
CARD_S = 2.3
_FULL = r"m 0 0 l 1920 0 1920 1080 0 1080"


def card_events(chapters: List[dict], st: LongformStyle, sfx: List[dict],
                rng: random.Random, duration: float) -> Tuple[str, List[Tuple[float, float]]]:
    out = []
    spans: List[Tuple[float, float]] = []
    acc = ass_color(st.card_accent)
    for i, ch in enumerate(chapters):
        if i == 0:
            continue                               # la vidéo s'ouvre sur la personne
        a = float(ch["start"])
        if duration - a < CARD_S + 1.0:
            continue
        b = a + CARD_S
        spans.append((a, b))
        tin, tout = 0.28, 0.26
        # fond : entrée glissée depuis la gauche, sortie vers la droite
        out.append(_dlg(5, a, a + tin, "CardBG",
                        r"{\move(-1920,0,0,0)\p1}" + _FULL))
        out.append(_dlg(5, a + tin, b - tout, "CardBG", r"{\pos(0,0)\p1}" + _FULL))
        out.append(_dlg(5, b - tout, b, "CardBG",
                        r"{\move(0,0,1920,0)\p1}" + _FULL))
        # barre d'accent qui se dessine
        out.append(_dlg(6, a + tin, b - tout, "CardBG",
                        r"{\pos(760,640)\c" + acc + r"\p1\fscx0\t(0,380,\fscx100)}"
                        r"m 0 0 l 400 0 400 10 0 10"))
        label = f"PARTIE {i}"                      # l'intro (chapitre 0) ne compte pas
        out.append(_dlg(7, a + tin, b - tout, "CardLabel",
                        r"{\pos(960,360)\fad(160,120)}" + _esc(label)))
        title = _esc(ch["title"])
        size = 120 if len(title) <= 22 else (96 if len(title) <= 34 else 78)
        out.append(_dlg(7, a + tin + 0.05, b - tout, "CardTitle",
                        r"{\pos(960,520)\fs" + str(size) +
                        r"\fad(140,120)\fscx86\fscy86\t(0,260,\fscx100\fscy100)}" + title))
        if st.sfx_chapter:
            sfx.append({"t": a, "name": rng.choice(st.sfx_chapter),
                        "db": st.sfx_db + 1.0, "kind": "chapter"})
        sfx.append({"t": b - tout, "name": "whoosh", "db": st.sfx_db - 4.0,
                    "kind": "chapter_out"})
    return "".join(out), spans


def build_ass(words: List[dict], chapters: List[dict], st: LongformStyle,
              duration: float, seed: int = 0,
              captions: bool = True, popups: bool = True,
              cards: bool = True) -> Tuple[str, List[dict], dict]:
    """-> (contenu ASS, cues SFX, stats)."""
    rng = random.Random(seed)
    sfx: List[dict] = []
    body = header(st)
    card_txt, spans = card_events(chapters, st, sfx, rng, duration) if cards else ("", [])
    picks = find_keywords(words, spans) if popups else []
    if captions:
        body += caption_events(words, st, sfx)
    body += popup_events(picks, st, sfx, rng)
    body += card_txt
    sfx.sort(key=lambda c: c["t"])
    stats = {"caption_chunks": len(chunk_words(words, st.words_per_line)) if captions else 0,
             "keyword_popups": len(picks), "chapter_cards": len(spans),
             "popups": [p["text"] for p in picks]}
    return body, sfx, stats
