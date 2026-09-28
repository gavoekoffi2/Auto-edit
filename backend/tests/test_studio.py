"""Moteur Studio face caméra: ADN de style, anti-répétition, plan, page, logo."""
import json
from pathlib import Path

import pytest

from app.explainer import styles as S
from app.explainer.studio import compose_studio
from app.explainer.studio_planner import fix_display, plan_rules, studio_sentences


def _words(text_with_pauses: str, start: float = 0.1, dur: float = 0.28):
    """« mot mot | mot » : '|' = pause de 0,6 s."""
    out, t = [], start
    for tok in text_with_pauses.split():
        if tok == "|":
            t += 0.6
            continue
        out.append({"w": tok, "s": round(t, 3), "e": round(t + dur, 3)})
        t += dur + 0.06
    return out


SPEECH = _words(
    "Vous êtes demandeur d'asile, depuis trois ans au Canada, mais ça ne va pas. | "
    "Est-ce que vous vous êtes posé la question pour savoir pourquoi ça ne va pas? | "
    "Nous sommes au Canada, un beau pays, et chacun rêve de vivre ici. | "
    "Alors moi j'organise des consultations individuelles en ligne pour parler de ces problèmes. | "
    "Écrivez en commentaire demandeur d'asile ou bien dites-moi je suis intéressé et pour que toi et moi prenions rendez-vous. | "
    "Prévenir vaut mieux que guérir, restons dans la prévention. | À bientôt.")
DUR = SPEECH[-1]["e"] + 0.4


def test_curated_styles_are_mutually_distinct():
    ids = list(S.STYLES)
    assert len(ids) >= 14
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            assert S.distance(S.STYLES[a], S.STYLES[b]) >= S.MIN_DISTANCE, (a, b)


def test_every_gene_value_is_known_by_the_web_engine():
    js = (Path(S.__file__).parent / "web" / "studio.js").read_text()
    for st in S.STYLES.values():
        assert st["chrome"] in S.CHROMES and st["panel"] in S.PANELS and st["transition"] in S.TRANSITIONS
        assert f"'{st['chrome']}'" in js or f"case '{st['chrome']}'" in js or st["chrome"] == "clean"
        assert st["captions"]["style"] in S.CAPTIONS


def test_twenty_videos_in_a_row_never_look_like_the_recent_ones():
    history, ids = [], []
    for k in range(20):
        st = S.choose_style("demandeur d'asile au Canada", history=history, seed=("v", k))
        recent = history[:S.HISTORY_WINDOW]
        assert all(S.distance(st, h) >= S.MIN_DISTANCE - 1 for h in recent), k
        assert st["id"] not in [h["id"] for h in history[:6]]
        history.insert(0, st["fingerprint"])
        ids.append(st["id"])
    assert len(set(ids)) >= 15
    assert any(i.startswith("invente_") for i in ids)  # le moteur invente quand les styles écrits ont servi


def test_topic_affinity_picks_a_fitting_style_first():
    st = S.choose_style("je vous montre le code et la sécurité des données de votre logiciel", seed="x")
    assert st["id"] in ("terminal_tech", "neon_energie", "suisse_minimal", "notification")
    st = S.choose_style("visa pour étudier au Canada, voyage et ambassade", seed="y")
    assert st["id"] == "carte_postale" and st["motif"] == "maple"


def test_invented_style_is_complete_and_readable():
    st = S.invent_style("seed-1", [S.fingerprint(s) for s in S.STYLES.values()][:8])
    for k in ("palette", "chrome", "panel", "transition", "captions", "badge", "motion", "sound"):
        assert k in st
    c = S.resolve_colors(st)
    assert c["onAccent"] in ("#FFFFFF", st["palette"]["ink"])


def test_requested_style_and_brand_color():
    st = S.choose_style("x", requested="dossier_confidentiel", brand_color="#123456", seed=1)
    assert st["id"] == "dossier_confidentiel" and st["palette"]["accent"] == "#123456"


def test_mutation_is_deterministic_but_seed_dependent():
    a = S.mutate(S.STYLES["solaire"], "s1"); b = S.mutate(S.STYLES["solaire"], "s1"); c = S.mutate(S.STYLES["solaire"], "s2")
    assert a == b and (a["variant"] != c["variant"] or a["palette"] != c["palette"])


def test_display_fixes_common_whisper_errors():
    assert fix_display("prévenir vos mieux que guéris") == "prévenir vaut mieux que guérir"
    assert fix_display("dit moi je suis intéressé") == "dis-moi je suis intéressé"


def test_plan_has_hook_stamp_question_cta_and_end_card():
    plan = plan_rules(SPEECH, DUR, "medium")
    types = [c["scene"]["type"] for c in plan]
    assert plan[0]["layout"] == "float" and plan[0]["start"] < 0.2          # accroche dès la 1re image
    assert "question" in types
    # la négation « ça ne va pas » est soulignée: tampon, ou sous-titre de l'accroche
    assert "stamp_word" in types or "ne va pas" in plan[0]["scene"].get("sub", "").lower()
    cta = next(c for c in plan if c["scene"]["type"] == "comment_cta")
    assert [o["text"].lower() for o in cta["scene"]["options"]] == ["demandeur d'asile", "je suis intéressé"]
    assert cta["scene"].get("duo_at") is not None and cta["scene"].get("stamp") == "RENDEZ-VOUS"
    end = plan[-1]
    assert end["scene"]["type"] == "end_card" and end["end"] == pytest.approx(DUR, abs=0.01)
    assert "vaut mieux que guérir" in end["scene"]["lines"][0]["text"]
    # aucun chevauchement, et jamais deux plein écrans sans visage entre eux (sauf appel → fin)
    for a, b in zip(plan, plan[1:]):
        assert b["start"] >= a["end"] - 0.01
        if a["layout"] == b["layout"] == "full" and a["scene"]["type"] != "comment_cta":
            assert b["start"] - a["end"] >= 1.2


def test_on_screen_text_comes_from_the_speech():
    spoken = " ".join(w["w"].lower() for w in SPEECH)
    for c in plan_rules(SPEECH, DUR, "heavy"):
        sc = c["scene"]
        for key in ("title", "text"):
            if sc.get(key):
                first = sc[key].lower().replace(" ", " ").strip(" ?").split()[0]
                assert first.strip("'") in spoken, sc[key]


def test_sentences_have_no_duplicate_words_at_cuts():
    ws = [{"w": "pas?", "s": 1.0, "e": 1.2}, {"w": "pas?", "s": 1.25, "e": 1.3}, {"w": "Alors", "s": 1.4, "e": 1.6}]
    assert sum(1 for s in studio_sentences(ws) for w in s["words"] if w["w"] == "pas?") == 1


def test_compose_page_contains_style_logo_and_studio_engine():
    st = S.choose_style("x", requested="notification", seed=2)
    html = compose_studio(plan_rules(SPEECH, DUR), SPEECH, DUR, st, logo="data:image/png;base64,AAAA", brand="FINAB")
    assert "CF_STUDIO_INIT" in html and '"chrome": "notification"' in html and "FINAB" in html
    assert html.index("CF_STUDIO_INIT") < html.index("CutForge — moteur")  # extension chargée avant le moteur


def test_logo_is_detoured_and_trimmed(tmp_path):
    from PIL import Image, ImageDraw

    from app.explainer.brand import prepare_logo
    im = Image.new("RGB", (400, 200), "white")
    ImageDraw.Draw(im).rectangle([120, 60, 280, 140], fill="red")
    ImageDraw.Draw(im).rectangle([180, 90, 220, 110], fill="white")  # blanc INTERNE: doit rester opaque
    p = tmp_path / "logo.jpg"; im.save(p, quality=95)
    url = prepare_logo(str(p))
    assert url.startswith("data:image/png;base64,")
    import base64, io
    out = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert out.mode == "RGBA" and out.width < 250                    # rogné au contenu
    assert out.getpixel((2, 2))[3] == 0                                # fond transparent
    assert out.getpixel((out.width // 2, out.height // 2))[3] == 255  # blanc interne conservé


def test_job_options_accept_studio_fields():
    from app.schemas.job import JobCreate
    j = JobCreate(video_id="00000000-0000-0000-0000-000000000001", mode="studio_facecam",
                  options={"studio_style": "invent", "logo_asset": "a" * 32, "brand_name": "FINAB"})
    assert j.options.studio_style == "invent"
    with pytest.raises(Exception):
        JobCreate(video_id="00000000-0000-0000-0000-000000000001", options={"studio_style": "nope"})


def test_studio_mode_is_in_catalog():
    from app.api.v1.modes import FAMILIES, MODE_DEFINITIONS
    m = next(m for m in MODE_DEFINITIONS if m["id"] == "studio_facecam")
    assert m["family"] == "studio" and any(f["id"] == "studio" for f in FAMILIES)


def test_every_montage_mode_has_its_own_grammar_in_web_engine():
    js = (Path(S.__file__).parent / "web" / "studio.js").read_text()
    assert len(S.MONTAGES) >= 15
    for m in S.MONTAGES:
        assert js.count(f"{m}: {{") >= 2, m  # une géométrie (MONTAGES) + une grammaire de scènes (GRAM)
    # chaque grammaire nomme des variantes réellement implémentées
    import re
    for q, c, e, s_, k in re.findall(r"\{ q: '(\w+)', c: '(\w+)', e: '(\w+)', s: '(\w+)', k: '(\w+)' \}", js):
        for name, table in ((q, "QV"), (c, "CV"), (e, "EV_"), (s_, "SV"), (k, "KV")):
            assert f"{table}.{name} = " in js or name in ("dial", "watermark", "cards", "classic", "stamp", "pill"), name


def test_every_montage_is_used_by_at_least_one_written_style():
    used = {st["montage"] for st in S.STYLES.values()}
    assert used == set(S.MONTAGES)


def test_consecutive_videos_never_reuse_the_last_two_montage_modes():
    history = []
    for k in range(25):
        st = S.choose_style("un sujet quelconque", history=history, seed=("m", k))
        assert st["montage"] not in [h["montage"] for h in history[:2]], k
        history.insert(0, st["fingerprint"])
