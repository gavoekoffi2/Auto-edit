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
    "cta_detail": "Commande en 2 minutes sur WhatsApp", "tone": "tu", "template": "neon", "montage": "classique",
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
    assert r["field"] == "domain"
    answers = ["🍲 Restauration & alimentation", "Délices de Lomé", "Des gâteaux sur commande",
               "Gâteaux faits maison, décorés au prénom, livrés frais le jour même", "Les mamans actives",
               "Elles n'ont jamais le temps de préparer un beau gâteau pour l'anniversaire", "Du stress, un gâteau de dernière minute raté, des invités déçus",
               "Un beau gâteau livré à la maison sans aucun stress", "Livraison gratuite\nPersonnalisé", "non", "non", "non", "WhatsApp pour commander",
               "Passer", "Passer", "Passer", "Tutoiement", "Vertical 9:16 — TikTok", "Explicatif illustré", "Henri", "Néon énergie", "Choisis pour moi"]
    for a in answers:
        assert not r["done"], r
        r = interview_turn(r["brief"], a, api_key="")
    assert r["done"]
    b = brief_from_interview(r["brief"])
    assert b.domain == "food" and b.montage == "classique" and b.voice == "henri"
    assert b.business == "Délices de Lomé" and b.tone == "tu" and b.template == "neon"
    assert b.benefits == ["Livraison gratuite", "Personnalisé"]
    assert b.proof == "" and b.price == "" and b.contact_phone == "" and b.angle in ANGLES
    assert "WhatsApp" in b.cta_action


def test_interview_digs_vague_answers_once():
    r = interview_turn(None, api_key="")
    for a in ["Services", "Clean Pro", "Nettoyage de bureaux"]:
        r = interview_turn(r["brief"], a, api_key="")
    r = interview_turn(r["brief"], "Nettoyage", api_key="")          # trop vague -> l'agent creuse
    assert r["field"] == "product_desc" and "plus" in r["reply"]
    r = interview_turn(r["brief"], "Produits écologiques, équipe de nuit, contrat sans engagement", api_key="")
    assert r["field"] == "audience"
    assert "écologiques" in r["brief"]["product_desc"] and r["brief"]["product_desc"].startswith("Nettoyage")


def test_interview_ignores_client_file_paths():
    b = brief_from_interview({"business": "X", "offer": "Y", "product_image_path": "/etc/passwd", "logo_path": "/etc/shadow"})
    assert b.product_image_path == "" and b.logo_path == ""


def test_impact_fallback_follows_problem_to_action():
    from app.explainer.impact_writer import IMPACT_SCENES, PHASES, write_impact
    b = Brief.from_dict({**BRIEF, "montage": "impact", "domain": "food", "price": "5 000 FCFA", "contact_phone": "+22893708178",
                         "consequences": "stress, gâteau raté, invités déçus"})
    board = write_impact(b, api_key="")
    types = _types(board)
    assert all(t in IMPACT_SCENES for t in types)
    phases = [IMPACT_SCENES[t]["phase"] for t in types if IMPACT_SCENES[t]["phase"] != "*"]
    order = [PHASES.index(p) for p in phases]
    assert order == sorted(order), phases                      # problème -> agitation -> bascule -> solution -> action
    assert types[0] == "hook_question" and types[-1] == "cta" and "pivot" in types
    assert board.beats[-1].scene["phone"] == "+228 93 70 81 78"
    assert "quatre-vingt-un" in board.beats[-1].text           # numéro prononcé en lettres
    assert any(t == "price_offer" for t in types)


def test_impact_never_shows_price_not_given():
    from app.explainer.impact_writer import sanitize_impact
    b = Brief.from_dict({**BRIEF, "montage": "impact"})
    board = Storyboard(angle="pas", template="x", beats=[Beat("Accroche.", {"type": "hook_question", "lines": ["Accroche"]}),
                                                          Beat("Seulement 2000 F.", {"type": "price_offer", "price": "2000 F"})])
    out = sanitize_impact(board, b)
    assert "price_offer" not in _types(out) and _types(out)[-1] == "cta"


def test_phone_formatting_and_speech():
    from app.explainer.impact_writer import format_phone, fr_number, spoken_phone
    assert format_phone("+228 93-70-81-78") == "+228 93 70 81 78"
    assert format_phone("93708178") == "93 70 81 78"
    assert [fr_number(n) for n in (21, 71, 80, 81, 93, 228)] == ["vingt-et-un", "soixante-et-onze", "quatre-vingts", "quatre-vingt-un", "quatre-vingt-treize", "deux-cent-vingt-huit"]
    assert spoken_phone("+228 93 70 81 78").startswith("plus deux-cent-vingt-huit, quatre-vingt-treize")


def test_compose_impact_page(tmp_path):
    from app.explainer.composer import compose_impact
    from app.explainer.impact_writer import fallback_impact
    b = Brief.from_dict({**BRIEF, "montage": "impact", "contact_phone": "+22893708178"})
    board = fallback_impact(b)
    t = 0.3; lines = []; lw = []
    for beat in board.beats:
        ws = []
        for w in beat.text.split():
            ws.append(Word(w, t, t + .2)); t += .25
        lines.append((ws[0].s, ws[-1].e)); lw.append(ws); t += .3
    v = VoiceTrack(str(tmp_path / "v.wav"), t + 2, [w for x in lw for w in x], lines, lw)
    html, story = compose_impact(board, v, brand=b.business, product_name=b.offer, accent="#22E3FF")
    assert "window.STORY=" in html and "SCENES.hook_question" in html and "__" not in html.split("<script>")[0][-200:]
    assert story["shots"][0]["start"] == 0.0 and story["shots"][-1]["scene"]["type"] == "cta"
    assert "--acc:#22E3FF" in html


def test_squeeze_shortens_long_inner_silence():
    import numpy as np
    from app.explainer.tts import SR, _squeeze
    tone = (np.sin(np.linspace(0, 2000, SR // 2)) * .5).astype(np.float32)
    a = np.concatenate([tone, np.zeros(SR, np.float32), tone])
    out, ws = _squeeze(a, [Word("a", 0.0, .5), Word("b", 1.5, 2.0)], .16)
    assert len(out) / SR < 1.3 and ws[1].s < 0.8


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

    assert {m["id"] for m in cat["montages"] if m["available"]} >= {"impact", "classique"} and len(cat["montages"]) >= 6
    assert cat["domains"] and cat["voices"]
    r = c.post("/api/v1/ads/interview", json={}, headers=h).json()
    assert not r["done"] and r["field"] == "domain"
    r = c.post("/api/v1/ads/interview", json={"brief": r["brief"], "answer": "Vente en ligne"}, headers=h).json()
    assert r["field"] == "business"
    r = c.post("/api/v1/ads/interview", json={"brief": r["brief"], "answer": "Délices de Lomé"}, headers=h).json()
    assert r["field"] == "offer"
    si = c.post("/api/v1/ads/script", json={"brief": {**BRIEF, "montage": "impact"}}, headers=h)
    assert si.status_code == 200 and si.json()["storyboard"]["beats"][-1]["scene"]["type"] == "cta"

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


def test_interview_format_and_automatic_montage():
    from app.explainer.interview import next_step
    b = {"_asked": [st for st in ("domain", "business", "offer", "product_desc", "audience", "problem", "consequences", "promise", "benefits",
                                  "price", "proof", "contact_phone", "cta_detail", "product_asset", "logo_asset", "photo_assets", "tone")],
         "domain": "education", "business": "Prépa Canada", "offer": "Préparation TCF Canada", "_current": "tone"}
    r = interview_turn(b, "Tutoiement", api_key="")
    assert r["field"] == "format" and r["format_picker"]
    r = interview_turn(r["brief"], "Pour YouTube", api_key="")
    assert r["brief"]["format"] == "16:9" and r["field"] == "montage"
    assert "Impact produit" not in r["suggestions"]          # Impact n'existe qu'en vertical
    r = interview_turn(r["brief"], "✨ Choix automatique (recommandé)", api_key="")
    assert r["brief"]["montage"] == "auto" and "Dossier résultat" in r["reply"]


def test_auto_montage_routes_by_domain_format_and_history():
    from app.explainer.montages import auto_montage, resolve_montage
    assert auto_montage({"domain": "education", "offer": "Prépa TCF Canada", "format": "9:16"})[0] == "dossier"
    assert auto_montage({"domain": "appli", "offer": "Application de budget", "format": "9:16"})[0] == "app"
    assert auto_montage({"domain": "evenement", "offer": "Festival", "format": "1:1"})[0] == "event"
    assert auto_montage({"domain": "digital", "offer": "Formation Excel", "format": "4:5"})[0] == "studio"
    assert auto_montage({"domain": "ecommerce", "offer": "Crème", "format": "16:9"})[0] != "impact"
    assert auto_montage({"domain": "ecommerce", "offer": "Crème", "format": "9:16"}, ["impact"])[0] != "impact"
    assert resolve_montage("impact", "16:9")["engine"] == "kit"


def test_kit_montages_map_every_role_to_their_own_scenes():
    from app.explainer.motion_writer import MAPPERS, STUDIO_ROLES_SCENES, write_motion
    b = Brief.from_dict({**BRIEF, "price": "5 000 FCFA", "contact_phone": "+22890000000", "consequences": "Du stress; des invités déçus"})
    for mid in ("studio", "dossier", "app", "lifestyle", "event"):
        assert mid in MAPPERS
        board = write_motion(b, mid, api_key="")
        types = [x.scene["type"] for x in board.beats]
        assert all(t in STUDIO_ROLES_SCENES[mid] for t in types), (mid, types)
        assert board.beats[-1].scene["role"] == "cta" and board.beats[-1].scene["phone"]
        assert "5 000 FCFA" in " ".join(x.text for x in board.beats)


def test_compose_kit_sizes_per_format(tmp_path):
    from app.explainer.composer import compose_kit
    from app.explainer.motion_writer import write_motion
    from app.explainer.tts import VoiceTrack
    b = Brief.from_dict(BRIEF)
    board = write_motion(b, "event", api_key="")
    n = len(board.beats)
    v = VoiceTrack(wav_path="", duration=n * 2.0, words=[], lines=[(i * 2.0, i * 2.0 + 1.6) for i in range(n)], line_words=[[] for _ in range(n)], provider="test")
    for fmt, size in (("9:16", (1080, 1920)), ("4:5", (1080, 1350)), ("1:1", (1080, 1080)), ("16:9", (1920, 1080))):
        html, story, wh = compose_kit(board, v, montage="event", fmt=fmt, brand=b.business)
        assert wh == size and story["format"]["w"] == size[0] and "KIT.register" in html and "__" not in html.split("<script>")[0][-200:]
