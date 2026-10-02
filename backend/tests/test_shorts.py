"""Moteur Shorts face caméra: Jev, versets, prises, réalisateur, timeline, branchement."""
from __future__ import annotations

import json

import pytest

from app.explainer.shorts import bible, director, jev, rushes, takes, timeline


def W(text: str, t0: float = 0.0, step: float = 0.4):
    return [{"w": x, "s": round(t0 + i * step, 3), "e": round(t0 + i * step + step * 0.8, 3)} for i, x in enumerate(text.split())]


def unit(uid: str, text: str, rush: int = 0, t0: float = 0.0):
    ws = W(text, t0)
    return {"id": uid, "rush": rush, "s": ws[0]["s"], "e": ws[-1]["e"], "words": ws, "text": text}


# ----------------------------------------------------------------- Jev
@pytest.fixture
def no_keys(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "TYPESAFE_API_KEY", "LLM_BASE_URL"):
        monkeypatch.setenv(k, "")
    monkeypatch.setattr("app.explainer.conf.setting", lambda name, default=None: default, raising=False)
    monkeypatch.setattr(jev, "setting", lambda name, default=None: default)


def test_jev_absent_returns_empty(no_keys):
    assert jev.available() is False
    assert jev.decide("x", {"q": jev.noul("?", "oui", "non")}) == {}


def test_jev_disabled_flag(monkeypatch):
    monkeypatch.setattr(jev, "setting", lambda n, d=None: {"OPENROUTER_API_KEY": "k", "JEV_ENABLED": "0"}.get(n, d))
    assert jev.endpoints() == []


def test_jev_request_shape_and_batching(monkeypatch):
    monkeypatch.setattr(jev, "setting", lambda n, d=None: {"OPENROUTER_API_KEY": "sk-or"}.get(n, d))
    calls = []

    class Resp:
        status_code = 200

        def __init__(self, body):
            self.body = body

        def json(self):
            return {"answers": {k: {"type": "noul", "noul": 0.9} for k in self.body["questions"]},
                    "usage": {"input_tokens": 100, "cost": 0.00001}}

    class Client:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers, json):
            calls.append((url, headers, json))
            return Resp(json)

    import httpx
    monkeypatch.setattr(httpx, "Client", Client)
    jev.reset_usage()
    qs = {f"q{i}": jev.noul(f"question {i}", "oui", "non") for i in range(jev.MAX_QUESTIONS + 5)}
    ans = jev.decide({"texte": "bonjour"}, qs)
    assert len(ans) == len(qs) and len(calls) == 2
    url, headers, body = calls[0]
    assert url == jev.OPENROUTER_DECISIONS_URL
    assert headers["Authorization"] == "Bearer sk-or"
    assert body["model"] == "typesafe/jev-1.13" and body["state"] == {"texte": "bonjour"}
    assert body["questions"]["q0"] == {"type": "noul", "instructions": "question 0", "criteria": {"true": "oui", "false": "non"}}
    assert jev.USAGE["calls"] == 2 and jev.USAGE["input_tokens"] == 200


def test_jev_readers():
    assert jev.p_true({"noul": 0.2}) == 0.2 and jev.p_true(None, 0.5) == 0.5
    assert jev.picked({"choice": "a", "confidence": 0.9}, 0.5) == "a"
    assert jev.picked({"choice": "a", "confidence": 0.2}, 0.5) is None
    assert jev.score("note", list("abcdefghijkl"))["criteria"] == list("abcdefghij")


# ----------------------------------------------------------------- versets
def test_verse_text_is_exact_lsg1910():
    v = bible.lookup("Jean 14:6")
    assert v["ref"] == "Jean 14:6"
    assert v["text"] == "Jésus lui dit: Je suis le chemin, la vérité, et la vie. Nul ne vient au Père que par moi."
    assert bible.lookup("Esaie 43:7")["ref"] == "Ésaïe 43:7"
    assert bible.lookup("Jean 6:67-68")["text"].endswith("Tu as les paroles de la vie éternelle.")
    assert bible.lookup("Jean 99:1") is None and bible.lookup("n'importe quoi") is None


def test_spoken_references():
    refs = bible.find_spoken_refs("Comme dit Jean chapitre 3 verset 16 et Romains 8 verset 28 à 30")
    assert refs == ["Jean 3:16", "Romains 8:28-30"]


# ----------------------------------------------------------------- rushes
def test_words_merge_elisions_and_units():
    vu = {"segments": [{"words": [{"word": "c", "start": 0.0, "end": 0.1}, {"word": "'est", "start": 0.1, "end": 0.3},
                                  {"word": "bon.", "start": 0.35, "end": 0.6}, {"word": "Jésus", "start": 2.0, "end": 2.3},
                                  {"word": "-Christ", "start": 2.3, "end": 2.6}, {"word": "vient", "start": 2.7, "end": 3.0}]}]}
    ws = rushes.words_of(vu)
    assert [w["w"] for w in ws] == ["c'est", "bon.", "Jésus-Christ", "vient"]
    us = rushes.split_units(ws, 1)
    assert [u["id"] for u in us] == ["B1", "B2"] and us[1]["text"] == "Jésus-Christ vient"


# ----------------------------------------------------------------- prises
def test_retakes_keep_last_complete_take(no_keys):
    us = [unit("A1", "Un vrai musulman peut devenir chrétien mais un vrai"),
          unit("A2", "Un vrai musulman peut devenir chrétien mais un vrai chrétien ne peut jamais devenir musulman.", t0=5),
          unit("A3", "Je t'explique pourquoi.", t0=12),
          unit("A4", "Mais non, un vrai chrétien, c'est quelqu'un qui...", t0=14)]
    kept, rep = takes.clean_takes(us)
    assert [u["id"] for u in kept] == ["A2", "A3"]
    assert rep["retake_groups"] == 1 and rep["decider"] == "rules"


def test_retakes_cross_rush_and_jev_choice(monkeypatch):
    us = [unit("A1", "Et c'est un processus, un vrai chrétien a reçu Jésus et il est né de nouveau."),
          unit("B1", "Et c'est un processus, un vrai chrétien a reçu Jésus et il est né de nouveau aussi.", rush=1)]
    assert takes.retake_groups(us) == [[0, 1]]
    monkeypatch.setattr(jev, "available", lambda: True)
    monkeypatch.setattr(jev, "decide", lambda state, qs: {"best_0": {"choice": "A1", "confidence": 0.8}, "retake_0": {"noul": 0.9}})
    kept, rep = takes.clean_takes(us)
    assert [u["id"] for u in kept] == ["A1"] and rep["decider"] == "jev"


def test_deliberate_repetition_kept_when_jev_says_so(monkeypatch):
    us = [unit("A1", "Jésus est le chemin, la vérité et la vie."), unit("A2", "Jésus est le chemin, la vérité et la vie.", t0=4)]
    monkeypatch.setattr(jev, "available", lambda: True)
    monkeypatch.setattr(jev, "decide", lambda state, qs: {"retake_0": {"noul": 0.1}} if "retake_0" in qs else {})
    kept, _ = takes.clean_takes(us)
    assert len(kept) == 2


# ----------------------------------------------------------------- réalisateur
UNITS = [unit("A1", "Un vrai musulman peut devenir chrétien.", t0=0),
         unit("A2", "Il n'y a point de chemin pour aller à Dieu sans Jésus.", t0=3),
         unit("A3", "Les animistes et les bodhistes adorent autre chose.", t0=8),
         unit("B1", "Abonnez-vous et dis-moi en commentaire.", rush=1, t0=0)]


def test_parse_plan_validates_llm_output():
    raw = json.dumps({
        "tag": "Enseignement", "order": ["A1", "A2", "ZZ9", "A2", "A3", "B1"],
        "fixes": [{"unit": "A3", "from": "bodhistes", "to": "bouddhistes"}, {"unit": "A1", "from": "absent", "to": "x"}],
        "chapters": [{"unit": "A1", "title": "Musulman ou chrétien ?"}, {"unit": "XX", "title": "?"}],
        "cards": [{"type": "verse", "unit": "A2", "ref": "Jean 14:6", "text": "TEXTE INVENTÉ", "say": "point de chemin"},
                  {"type": "verse", "unit": "A2", "ref": "Livre 1:1"},
                  {"type": "list", "unit": "A3", "items": [{"text": "Animistes", "say": "les animistes"}, {"text": "Bouddhistes", "say": "les bodhistes"}]},
                  {"type": "keyword", "unit": "A1", "text": "Converti", "say": "pas dans le texte"},
                  {"type": "inconnu", "unit": "A1"}]})
    p = director.parse_plan("Voici:\n```json\n" + raw + "\n```", UNITS)
    assert p["order"] == ["A1", "A2", "A3", "B1"]
    assert p["fixes"] == [{"unit": "A3", "from": "bodhistes", "to": "bouddhistes"}]
    assert p["chapters"] == [{"unit": "A1", "title": "Musulman ou chrétien ?"}]
    types = [c["type"] for c in p["cards"]]
    assert types == ["verse", "list", "keyword"]
    assert p["cards"][0]["text"].startswith("Jésus lui dit")       # texte LSG, jamais celui du LLM
    assert p["cards"][2]["say"] == ""                               # « say » absent du passage -> ignoré


def test_parse_plan_rejects_overcut_order():
    p = director.parse_plan(json.dumps({"order": ["A1"], "cards": []}), UNITS)
    assert p["order"] == [u["id"] for u in UNITS]


def test_rules_plan_finds_cta_and_spoken_verse():
    us = UNITS + [unit("B2", "Comme le dit Jean chapitre 14 verset 6.", rush=1, t0=4)]
    p = director.rules_plan(us)
    assert {c["type"] for c in p["cards"]} == {"cta", "verse"}


def test_jev_review_drops_unfaithful_cards(monkeypatch):
    plan = {"source": "llm", "tag": "Enseignement", "order": [u["id"] for u in UNITS], "cards": [
        {"type": "keyword", "unit": "A1", "text": "Converti", "emoji": "", "say": ""},
        {"type": "keyword", "unit": "A2", "text": "Inventé", "emoji": "", "say": ""}]}

    def decide(state, qs):
        assert "theme" in qs and "card_0" in qs and "tag" not in qs
        return {"theme": {"choice": "royal", "confidence": 0.8}, "card_0": {"noul": 0.9}, "card_1": {"noul": 0.05}}
    monkeypatch.setattr(jev, "decide", decide)
    r = director.jev_review(plan, UNITS, landscape=True, hd=False, seed="s")
    assert r["theme"] == "royal" and r["layout"] == "cadre" and r["decider"] == "jev"
    assert [c["text"] for c in r["cards"]] == ["Converti"] and r["cards_dropped"][0]["unit"] == "A2"


def test_direct_without_any_ai(no_keys):
    p = director.direct(UNITS, landscape=False, seed="abc")
    assert p["info"]["source"] == "rules" and p["layout"] == "plein" and p["theme"] in director.THEMES


# ----------------------------------------------------------------- timeline
def test_fixes_handle_elision_and_all_occurrences():
    out = timeline.apply_fixes(W("tout humain d'avoir tué en mariée, retourner en mariée."),
                               [{"from": "avoir tué", "to": "avoir Dieu"}, {"from": "en mariée", "to": "en arrière"}])
    assert " ".join(w["w"] for w in out) == "tout humain d'avoir Dieu en arrière, retourner en arrière."


def test_stutters_respect_accents():
    assert [w["w"] for w in timeline.drop_stutters(W("il a à son bord le le chemin nous nous"))] == \
        ["il", "a", "à", "son", "bord", "le", "chemin", "nous", "nous"]


def _rush(i, units_):
    ws = [w for u in units_ for w in u["words"]]
    return {"index": i, "id": rushes.letter(i), "path": f"/x/{i}.mp4", "info": {"w": 1280, "h": 720, "duration": 60.0, "audio": True},
            "words": ws, "units": units_, "faces": [[1.0, 640, 300, 200]]}


def test_build_reorders_across_rushes_and_maps_words():
    a = [unit("A1", "Bonjour à tous.", t0=0), unit("A2", "Abonnez-vous à la chaîne.", t0=10)]
    b = [unit("B1", "Voici le cœur du sujet.", rush=1, t0=2)]
    rs = [_rush(0, a), _rush(1, b)]
    plan = {"order": ["A1", "B1", "A2"], "fixes": [], "cards": [
        {"type": "keyword", "unit": "B1", "text": "Le cœur", "emoji": "", "say": "le cœur"},
        {"type": "cta", "unit": "A2", "label": "Abonne-toi", "sub": "", "say": "abonnez-vous"}],
        "chapters": [{"unit": "A1", "title": "Intro"}, {"unit": "B1", "title": "Le sujet"}]}
    tl = timeline.build(rs, plan, "cadre")
    assert [s["rush"] for s in tl["shots"]] == [0, 1, 0]
    assert [s["zoom"] for s in tl["shots"]] == [1.0, 1.13, 1.0]
    assert " ".join(w["w"] for w in tl["words"]) == "Bonjour à tous. Voici le cœur du sujet. Abonnez-vous à la chaîne."
    assert all(b_["s"] >= a_["s"] for a_, b_ in zip(tl["words"], tl["words"][1:]))
    assert abs(tl["duration"] - sum(s["dur"] for s in tl["shots"])) < 1e-6
    cues, chapters = timeline.cues(plan, tl)
    kw = next(c for c in cues if c["type"] == "keyword")
    heart = next(w for w in tl["words"] if w["w"] == "le" and w["s"] > tl["shots"][1]["out"])
    assert abs(kw["t0"] - (heart["s"] - 0.15)) < 1e-6
    assert [c["title"] for c in chapters] == ["Intro", "Le sujet"] and chapters[0]["t"] == 0.0


def test_low_zone_cards_never_overlap():
    words = W(" ".join(f"mot{i}" for i in range(60)))
    tl = {"words": words, "duration": 30.0, "unit_span": {"A1": (0.0, 10.0), "A2": (2.0, 12.0), "A3": (20.0, 30.0)}}
    plan = {"cards": [{"type": "keyword", "unit": u, "text": "x", "emoji": "", "say": ""} for u in ("A1", "A2", "A3")]}
    cues, _ = timeline.cues(plan, tl)
    for a, b in zip(cues, cues[1:]):
        assert a["t1"] <= b["t0"]


def test_caption_groups_short_lines():
    g = timeline.caption_groups(W("un deux trois quatre cinq six. sept"))
    assert [len(x["w"]) for x in g] == [4, 2, 1]


# ----------------------------------------------------------------- branchement
def test_mode_registered_and_schema():
    from app.api.v1.modes import MODE_DEFINITIONS
    from app.config import VALID_MODES
    from app.schemas.job import JobCreate, JobOptions
    assert "shorts_facecam" in VALID_MODES
    assert any(m["id"] == "shorts_facecam" and m["family"] == "studio" for m in MODE_DEFINITIONS)
    j = JobCreate(video_id="00000000-0000-0000-0000-000000000001", mode="shorts_facecam",
                  extra_video_ids=["00000000-0000-0000-0000-000000000002"], options={"shorts_theme": "braise", "shorts_layout": "plein"})
    assert len(j.extra_video_ids) == 1
    with pytest.raises(Exception):
        JobOptions(shorts_theme="arc-en-ciel")


def test_pipeline_dispatches_to_shorts(monkeypatch, tmp_path):
    from app.processing import pipeline_v2
    import app.explainer.shorts as shorts_pkg
    v1 = tmp_path / "a.mp4"; v1.write_bytes(b"x" * 10)
    v2 = tmp_path / "b.mp4"; v2.write_bytes(b"y" * 10)
    seen = {}

    def fake_run(rush_paths, output_dir, **kw):
        seen.update(paths=rush_paths, **kw)
        out = tmp_path / "out.mp4"; out.write_bytes(b"z")
        return {"output_path": str(out), "duration": 1.0, "cards": []}
    monkeypatch.setattr(shorts_pkg, "run_shorts", fake_run)
    monkeypatch.setattr("app.services.storage.get_absolute_path", lambda p: p)
    monkeypatch.setattr(pipeline_v2, "estimate_render_disk_gb", lambda p: 0)
    res = pipeline_v2.run_pipeline_v2(str(v1), str(tmp_path / "o"), mode="shorts_facecam",
                                      params={"rush_paths": [str(v1), str(v2)], "options": {"shorts_theme": "auto", "shorts_layout": "plein"}})
    assert res["engine"] == "shorts" and seen["paths"] == [str(v1), str(v2)]
    assert seen["theme"] is None and seen["layout"] == "plein"


def test_rules_order_single_outro_at_the_end(no_keys):
    us = [unit("A1", "Bonjour, aujourd'hui on parle de la foi.", t0=0), unit("A2", "Abonnez-vous à la chaîne.", t0=5),
          unit("B1", "Deuxième partie de l'explication.", rush=1, t0=0), unit("B2", "Abonne-toi et partage.", rush=1, t0=4),
          unit("B3", "Dis-moi en commentaire ce que tu en penses.", rush=1, t0=6)]
    assert director.rules_order(us) == ["A1", "B1", "B2", "B3"]


def test_rules_order_jev_picks_intro_rush(monkeypatch):
    us = [unit("A1", "Deuxième partie de l'explication.", t0=0), unit("B1", "Bonjour à tous, aujourd'hui je vais t'expliquer.", rush=1)]
    monkeypatch.setattr(jev, "available", lambda: True)
    monkeypatch.setattr(jev, "decide", lambda s, q: {"intro": {"choice": "r1", "confidence": 0.9}})
    assert director.rules_order(us) == ["B1", "A1"]
