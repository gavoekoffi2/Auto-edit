"""Moteur « Pub explicative »: script, garde-fous, entretien, composition, audio, API."""
import json
import re

import pytest

from app.explainer.interview import brief_from_interview, interview_turn
from app.explainer.schema import Beat, Brief, Storyboard
from app.explainer.templates import ANGLES, SCENE_CATALOG, TEMPLATES, resolve_template
from app.explainer.tts import VoiceTrack, Word
from app.explainer.writer import fallback_storyboard, sanitize, write_storyboard

BRIEF = {
    "business": "Délices de Lomé", "offer": "des gâteaux d'anniversaire sur commande",
    "audience": "Mamans actives, entreprises", "problem": "pas le temps de préparer un beau gâteau",
    "promise": "un gâteau magnifique livré à domicile",
    "benefits": ["Livraison gratuite à Lomé", "Personnalisé avec le prénom", "Commande en 2 minutes"],
    "cta_detail": "Commande en 2 minutes sur WhatsApp", "tone": "tu", "template": "neon",
}


def _types(board):
    return [b.scene.get("type") for b in board.beats]


@pytest.mark.parametrize("angle", list(ANGLES))
def test_fallback_storyboard_every_angle_is_valid(angle, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    b = Brief.from_dict({**BRIEF, "angle": angle})
    board = write_storyboard(b, api_key="")
    types = _types(board)
    assert types[-1] == "end_card"
    assert "cta_button" in types
    assert all(t in SCENE_CATALOG or t == "continue" for t in types)
    assert types[0] != "continue"
    assert all(b.text.strip() for b in board.beats)
    # jamais deux fois la même scène d'affilée (hors « continue »)
    real = [t for t in types if t != "continue"]
    assert all(a != c for a, c in zip(real, real[1:]))


def test_tutoiement_adapts_cta():
    board = fallback_storyboard(Brief.from_dict({**BRIEF, "tone": "tu", "cta_action": "Cliquez sur le bouton en bas"}))
    assert any(b.text.startswith("Clique sur") for b in board.beats)


def test_sanitize_removes_invented_numbers():
    b = Brief.from_dict({**BRIEF, "proof": ""})
    board = Storyboard(angle="douleur", template="neon", beats=[
        Beat("80 % des mamans manquent de temps.", {"type": "stat_number", "value": "80%", "label": "des mamans"}),
        Beat("Commande maintenant.", {"type": "cta_button"}),
    ])
    out = sanitize(board, b)
    assert out.beats[0].scene["type"] != "stat_number"
    assert out.beats[-1].scene["type"] == "end_card"


def test_sanitize_keeps_client_provided_number():
    b = Brief.from_dict({**BRIEF, "proof": "Plus de 500 gâteaux livrés"})
    board = Storyboard(angle="douleur", template="neon", beats=[
        Beat("Plus de 500 gâteaux livrés.", {"type": "stat_number", "value": "500+", "label": "gâteaux livrés"})])
    assert sanitize(board, b).beats[0].scene["type"] == "stat_number"


def test_template_accent_contrast_and_brand_color():
    tpl = resolve_template("prestige", "#0a7d3b")
    assert tpl["colors"]["accent"] == "#0a7d3b"
    assert tpl["colors"]["onAccent"] == "#ffffff"          # accent sombre -> texte blanc
    assert resolve_template("neon")["colors"]["onAccent"] == "#0B1B3A"  # cyan clair -> texte sombre
    assert resolve_template("inconnu")["id"] == "prestige"
    assert len(TEMPLATES) >= 3


def test_interview_without_key_reaches_complete_brief():
    r = interview_turn(None, api_key="")
    answers = ["Délices de Lomé", "Des gâteaux sur commande", "Les mamans actives", "Pas le temps",
               "Un beau gâteau livré", "Livraison gratuite\nPersonnalisé", "non", "WhatsApp pour commander",
               "Tutoiement", "Néon énergie", "Choisis pour moi"]
    for a in answers:
        assert not r["done"]
        r = interview_turn(r["brief"], a, api_key="")
    assert r["done"]
    b = brief_from_interview(r["brief"])
    assert b.business == "Délices de Lomé" and b.tone == "tu" and b.template == "neon"
    assert b.benefits == ["Livraison gratuite", "Personnalisé"]
    assert b.proof == "" and b.angle in ANGLES
    assert "WhatsApp" in b.cta_action


def test_compose_merges_continue_beats_into_one_shot(tmp_path):
    from app.explainer.composer import build_shots, compose_html
    board = Storyboard(angle="douleur", template="prestige", beats=[
        Beat("Deux médecins.", {"type": "title_slam", "title": "Deux médecins"}),
        Beat("Le premier perd.", {"type": "split_compare", "a": {"label": "A"}, "b": {"label": "B", "at": "second"}}),
        Beat("Le second gagne.", {"type": "continue"}),
        Beat("Clique.", {"type": "cta_button"}),
    ])
    lines = [(0.3, 1.2), (1.5, 2.6), (2.9, 4.0), (4.3, 5.0)]
    lw = [[Word("Deux", 0.3, 0.6), Word("médecins", 0.6, 1.2)], [Word("Le", 1.5, 1.6)], [Word("second", 3.0, 3.4)], [Word("Clique", 4.3, 5.0)]]
    v = VoiceTrack("x.wav", 7.0, [w for l in lw for w in l], lines, lw)
    shots = build_shots(board, v)
    assert [s["scene"]["type"] for s in shots] == ["title_slam", "split_compare", "cta_button"]
    assert shots[0]["start"] == 0.0 and shots[-1]["end"] == 7.0
    assert shots[1]["speechEnd"] == 4.0 and any(w["w"] == "second" for w in shots[1]["words"])
    html, story = compose_html(board, v, template_id="editorial")
    assert "__" not in re.sub(r"__proto__", "", html.split("<script>window.STORY=")[0])  # placeholders remplacés
    data = json.loads(html.split("window.STORY=")[1].split(";</script>")[0])
    assert data["template"]["id"] == "editorial" and len(data["shots"]) == 3


def test_sfx_track_places_sounds():
    import numpy as np
    from app.explainer.audio import SR, sfx_track
    tr = sfx_track([{"t": 0.5, "sfx": "impact"}, {"t": 1.0, "sfx": "pop"}, {"t": 9.0, "sfx": "inconnu"}], 3.0)
    assert len(tr) == 3 * SR
    assert np.abs(tr[: int(0.45 * SR)]).max() == 0
    assert np.abs(tr[int(0.5 * SR): int(0.7 * SR)]).max() > 0


# --------------------------------------------------------------------------- API
from tests.test_api_e2e import _auth, _signup, env  # noqa: E402,F401


def test_ads_api_flow_and_free_quota(env, monkeypatch):
    from app.workers import tasks
    queued = []
    monkeypatch.setattr(tasks.process_ad_project_task, "delay", lambda pid: queued.append(pid))
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    c = env["client"]
    tok = _signup(c)
    h = _auth(tok)

    cat = c.get("/api/v1/ads/catalog").json()
    assert {t["id"] for t in cat["templates"]} >= {"prestige", "neon", "editorial"}

    r = c.post("/api/v1/ads/interview", json={}, headers=h).json()
    assert not r["done"] and r["field"] == "business"
    r = c.post("/api/v1/ads/interview", json={"brief": r["brief"], "answer": "Délices de Lomé"}, headers=h).json()
    assert r["field"] == "offer"

    s = c.post("/api/v1/ads/script", json={"brief": BRIEF}, headers=h)
    assert s.status_code == 200 and s.json()["storyboard"]["beats"][-1]["scene"]["type"] == "end_card"

    ids = []
    for _ in range(2):
        r = c.post("/api/v1/ads", json={"brief": BRIEF}, headers=h)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    assert queued == ids
    # quota Free: 2 pubs / mois
    assert c.post("/api/v1/ads", json={"brief": BRIEF}, headers=h).status_code == 429

    lst = c.get("/api/v1/ads", headers=h).json()
    assert len(lst) == 2 and lst[0]["status"] == "pending"
    assert c.get(f"/api/v1/ads/{ids[0]}/video", headers=h).status_code == 400  # pas encore prête
    assert c.post(f"/api/v1/ads/{ids[0]}/cancel", headers=h).json()["status"] == "cancelled"

    # un autre utilisateur ne voit rien
    other = _auth(_signup(c, email="kofi@example.com"))
    assert c.get(f"/api/v1/ads/{ids[1]}", headers=other).status_code == 404
    assert c.delete(f"/api/v1/ads/{ids[1]}", headers=h).status_code == 204


def test_ads_requires_minimal_brief(env, monkeypatch):
    c = env["client"]
    h = _auth(_signup(c))
    assert c.post("/api/v1/ads", json={"brief": {"business": ""}}, headers=h).status_code == 400
