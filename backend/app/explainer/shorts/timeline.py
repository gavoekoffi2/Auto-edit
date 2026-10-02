"""Timeline: passages gardés -> plans (rush, début, fin), mots dans le temps final,
cartes / chapitres / sous-titres calés au mot près."""
from __future__ import annotations

import re
from typing import Any, Optional

from .rushes import face_x, norm

FPS = 30
GAP = 0.42        # silence entre deux mots au-delà duquel on coupe
KEEP = 0.16       # silence laissé après le dernier mot d'un plan
LEAD = 0.07       # marge avant le premier mot
NO_STUTTER = {"nous", "vous", "tres", "si", "bien", "plus", "non", "oui"}


# ----------------------------------------------------------------- corrections
def apply_fixes(words: list[dict[str, Any]], fixes: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = [dict(w) for w in words]
    for f in fixes:
        a = norm(f["from"]).split()
        if not a:
            continue
        i = 0
        while i < len(out):  # toutes les occurrences
            toks = [norm(w["w"]) for w in out]
            # un mot peut contenir plusieurs jetons normalisés (« c'est » -> « c est »)
            flat, k = [], i
            while k < len(out) and len(flat) < len(a) + 1:
                flat += toks[k].split(); k += 1
                if flat[:len(a)] == a and len(flat) == len(a):
                    break
            # « d'avoir tué » -> « avoir tué » commence après l'élision: on garde « d' »
            pre = re.match(r"^\w+['’]", out[i]["w"]) if len(flat) == len(a) + 1 else None
            off = 1 if pre and flat[1:] == a else 0
            if (flat[:len(a)] == a and len(flat) == len(a)) or off:
                seg = out[i:k]; s0, e0 = seg[0]["s"], seg[-1]["e"]
                trail = re.search(r"[.,;:?!…]+$", seg[-1]["w"])
                new = f["to"].split()
                if off:
                    new[0] = pre.group(0) + new[0]
                if trail and not re.search(r"[.,;:?!…]$", new[-1]):
                    new[-1] += trail.group(0)
                rep = [{"w": t, "s": round(s0 + (e0 - s0) * j / len(new), 3), "e": round(s0 + (e0 - s0) * (j + 1) / len(new), 3)}
                       for j, t in enumerate(new)]
                out[i:k] = rep
                i += len(rep)
                continue
            i += 1
    return out


def drop_stutters(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """« le le chemin » -> « le chemin » (sauf « nous nous », « vous vous »…)."""
    out = []
    low = lambda x: re.sub(r"[^\w'’-]", "", x.lower())  # noqa: E731  (accents gardés: « a à » n'est pas un bégaiement)
    for i, w in enumerate(words):
        n = norm(w["w"])
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt and n and low(w["w"]) == low(nxt["w"]) and n not in NO_STUTTER and len(n) <= 6 and nxt["s"] - w["e"] < 0.6:
            continue
        out.append(w)
    return out


# ----------------------------------------------------------------- plans
def build(rushes: list[dict[str, Any]], plan: dict[str, Any], layout: str) -> dict[str, Any]:
    units = {u["id"]: u for r in rushes for u in r["units"]}
    fixes: dict[str, list[dict[str, str]]] = {}
    for f in plan.get("fixes", []):
        fixes.setdefault(f["unit"], []).append(f)
    pos_index = {r["index"]: {id(w): i for i, w in enumerate(r["words"])} for r in rushes}

    pieces: list[dict[str, Any]] = []      # {rush, t0, t1, words[(w, s_src, e_src)], unit}
    for uid in plan["order"]:
        u = units.get(uid)
        if not u:
            continue
        r = rushes[u["rush"]]
        allw = r["words"]
        idx = pos_index[u["rush"]]
        ws = drop_stutters(u["words"])
        if not ws:
            continue
        groups = [[ws[0]]]
        for w in ws[1:]:
            (groups.append([w]) if w["s"] - groups[-1][-1]["e"] > GAP else groups[-1].append(w))
        fixed_all = apply_fixes(ws, fixes.get(uid, []))
        for g in groups:
            i0, i1 = idx.get(id(g[0])), idx.get(id(g[-1]))
            prev_e = allw[i0 - 1]["e"] if i0 else 0.0
            next_s = allw[i1 + 1]["s"] if (i1 is not None and i1 + 1 < len(allw)) else r["info"]["duration"]
            t0 = max(g[0]["s"] - LEAD, prev_e + 0.02, 0.0)
            t1 = min(g[-1]["e"] + KEEP, next_s - 0.04, r["info"]["duration"])
            if t1 - t0 < 0.12:
                continue
            gw = [w for w in fixed_all if g[0]["s"] - 0.01 <= w["s"] <= g[-1]["e"]]
            pieces.append({"rush": u["rush"], "t0": t0, "t1": t1, "words": gw, "unit": uid})

    # plans contigus d'un même rush: une seule coupe en moins
    merged: list[dict[str, Any]] = []
    for p in pieces:
        m = merged[-1] if merged else None
        if m and m["rush"] == p["rush"] and 0 <= p["t0"] - m["t1"] < 0.06:
            m["t1"] = p["t1"]; m["words"] += p["words"]; m["units"].append(p["unit"])
        else:
            merged.append({**p, "units": [p["unit"]]})

    shots, words, unit_span = [], [], {}
    pos = 0.0
    zoom = 1.0
    z2 = 1.13 if layout == "cadre" else 1.12
    last: Optional[tuple[int, float]] = None
    for k, p in enumerate(merged):
        r = rushes[p["rush"]]
        jump = last is None or last[0] != p["rush"] or abs(p["t0"] - last[1]) > 1.2
        if jump and k:
            zoom = z2 if zoom == 1.0 else 1.0
        frames = max(1, round((p["t1"] - p["t0"]) * FPS))   # durée entière en images: aucune dérive
        d = frames / FPS
        shots.append({"rush": p["rush"], "t0": round(p["t0"], 3), "dur": round(d, 6), "frames": frames, "out": round(pos, 6), "zoom": zoom,
                      "cx": face_x(r["faces"], (p["t0"] + p["t1"]) / 2, r["info"]["w"])})
        for w in p["words"]:
            s = pos + w["s"] - p["t0"]; e = pos + w["e"] - p["t0"]
            if s < pos + d:
                words.append({"w": w["w"], "s": round(max(pos, s), 3), "e": round(min(pos + d, max(e, s + 0.05)), 3)})
        for uid in p["units"]:
            a, b = unit_span.get(uid, (pos, pos + d))
            unit_span[uid] = (min(a, pos), max(b, pos + d))
        pos += d
        last = (p["rush"], p["t1"])
    return {"shots": shots, "words": words, "duration": round(sum(x["frames"] for x in shots) / FPS, 6), "unit_span": unit_span}


# ----------------------------------------------------------------- repères
class Finder:
    def __init__(self, words: list[dict[str, Any]]):
        self.w = words
        self.n = [norm(x["w"]).split() for x in words]

    def at(self, phrase: str, t_min: float, t_max: float) -> Optional[float]:
        p = norm(phrase).split()
        if not p:
            return None
        for i, w in enumerate(self.w):
            if w["s"] < t_min - 1e-6:
                continue
            if w["s"] > t_max:
                break
            flat, k = [], i
            while k < len(self.w) and len(flat) < len(p):
                flat += self.n[k]; k += 1
            if flat[:len(p)] == p:
                return w["s"]
        return None


def _fixed(say: str, fixes: list[dict[str, str]]) -> str:
    out = " " + norm(say) + " "
    for f in fixes:
        out = out.replace(" " + norm(f["from"]) + " ", " " + norm(f["to"]) + " ")
    return out.strip()


def _dur_verse(text: str) -> float:
    return max(5.0, min(10.0, len(text) / 17))


def cues(plan: dict[str, Any], tl: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Cartes et chapitres -> repères horodatés pour la page d'habillage."""
    F = Finder(tl["words"])
    fixes = plan.get("fixes", [])
    span = tl["unit_span"]
    D = tl["duration"]
    out: list[dict[str, Any]] = []
    for c in plan.get("cards", []):
        if c["unit"] not in span:
            continue
        us, ue = span[c["unit"]]
        lim = min(D, ue + 10)

        def at(say: str, after: float, default: float) -> float:
            t = F.at(say, after - 0.05, lim) if say else None
            if t is None and say and fixes:  # « say » copié avant correction (« bodhistes » -> « bouddhistes »)
                t = F.at(_fixed(say, fixes), after - 0.05, lim)
            return t if t is not None else default

        t = c["type"]
        q: dict[str, Any] = {"type": t}
        start = at(c.get("say") or c.get("say_a") or "", us, us + 0.3)
        if t == "compare":
            rows, cur = [], start
            for j, r in enumerate(c["rows"]):
                a_t = at(r.get("say", ""), cur, cur + (0.0 if j == 0 else 1.6))
                rows.append({"a": r["a"], "b": r["b"], "ok": r["ok"], "at": a_t, "at_ok": a_t + 0.7}); cur = a_t + 0.1
            q.update(rows=rows, t0=rows[0]["at"] - 0.4, t1=rows[-1]["at_ok"] + 3.0)
        elif t in ("list", "steps"):
            items, cur = [], None
            for j, it in enumerate(c["items"]):
                base = start if cur is None else cur + 1.3
                a_t = at(it.get("say", ""), start if cur is None else cur + 0.1, base)
                items.append({"text": it["text"], "emoji": it.get("emoji", ""), "at": a_t}); cur = a_t
            items.sort(key=lambda x: x["at"])
            q.update(items=items, title=c.get("title", ""), t0=items[0]["at"] - 0.25, t1=items[-1]["at"] + 3.5)
        elif t == "verse":
            q.update(ref=c["ref"], text=c["text"], t0=start - 0.15, t1=start + _dur_verse(c["text"]))
        elif t == "contrast":
            a_t = at(c.get("say_a", ""), us, us + 0.3); b_t = at(c.get("say_b", ""), a_t + 0.1, a_t + 1.5)
            q.update(a=c["a"], b=c["b"], at_a=a_t, at_b=b_t, t0=a_t - 0.15, t1=b_t + 3.0)
        elif t == "versus":
            a_t = at(c.get("say_a", ""), us, us + 0.3); x_t = at(c.get("say_x", ""), a_t + 0.1, a_t + 1.2)
            b_t = at(c.get("say_b", ""), x_t, x_t + 1.0)
            q.update(a=c["a"], b=c["b"], at_a=a_t, at_x=x_t, at_b=b_t, t0=a_t - 0.15, t1=b_t + 3.0)
        elif t == "alert":
            q.update(title=c["title"], sub=c.get("sub", ""), t0=start - 0.2, t1=start + 4.5)
        elif t == "keyword":
            q.update(text=c["text"], emoji=c.get("emoji", ""), t0=start - 0.15, t1=start + 3.0)
        elif t == "full":
            q.update(style=c.get("style", "statement"), title=c["title"], sub=c.get("sub", ""), emoji=c.get("emoji", ""),
                     t0=start - 0.1, t1=start + 3.6, at_fill=start + 1.0)
        elif t == "cta":
            q.update(label=c.get("label", "Abonne-toi"), sub=c.get("sub", ""), t0=start, t1=D + 1, at_c=start + 1.6)
        q["t0"] = max(0.0, q["t0"])
        out.append(q)
    out.sort(key=lambda c: c["t0"])
    # zone basse: jamais deux cartes à la fois
    low = [c for c in out if c["type"] != "full"]
    keep = []
    for k, c in enumerate(low):
        nxt = low[k + 1]["t0"] if k + 1 < len(low) else D + 1
        if keep and c["t0"] < keep[-1]["t1"] - 0.05:
            continue
        c["t1"] = min(c["t1"], nxt - 0.05) if c["type"] != "cta" else c["t1"]
        if c["t1"] - c["t0"] >= 1.6:
            keep.append(c)
    fulls, last_end = [], -99.0
    for c in (c for c in out if c["type"] == "full"):
        if c["t0"] >= last_end + 20 and c["t1"] <= D:
            fulls.append(c); last_end = c["t1"]
    chapters = []
    for ch in plan.get("chapters", []):
        if ch["unit"] in span:
            chapters.append({"t": round(span[ch["unit"]][0], 3), "title": ch["title"]})
    chapters.sort(key=lambda x: x["t"])
    if chapters and chapters[0]["t"] < 1.0:
        chapters[0]["t"] = 0.0
    return sorted(keep + fulls, key=lambda c: c["t0"]), chapters


def caption_groups(words: list[dict[str, Any]], max_words: int = 4, max_chars: int = 20) -> list[dict[str, Any]]:
    G, cur = [], []
    for k, t in enumerate(words):
        cur.append(t)
        nxt = words[k + 1] if k + 1 < len(words) else None
        chars = sum(len(x["w"]) + 1 for x in cur)
        if not nxt or len(cur) >= max_words or chars > max_chars or re.search(r"[.,?!:;…]$", t["w"]) or nxt["s"] - t["e"] > 0.3:
            G.append({"s": cur[0]["s"], "e": cur[-1]["e"],
                      "w": [{"t": re.sub(r"[.,;:]+$", "", x["w"]), "s": x["s"], "e": x["e"]} for x in cur]})
            cur = []
    for k, g in enumerate(G):
        n = G[k + 1] if k + 1 < len(G) else None
        g["end"] = n["s"] if n and n["s"] - g["e"] < 0.5 else g["e"] + 0.3
    return G
