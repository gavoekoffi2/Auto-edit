"""Moteur Motion Pro (face caméra + animations plein écran)."""
import re

import pytest

from app.explainer import facecam_planner as fp


def _words(text: str, t0: float = 0.0, step: float = 0.34):
    out, t = [], t0
    for tok in text.split():
        out.append({"w": tok, "s": round(t, 3), "e": round(t + step - 0.04, 3)})
        t += step + (0.6 if re.search(r"[.!?]$", tok) else 0.0)
    return out


SCRIPT = (
    "Bonjour à tous. Cette vidéo est pour les avocats, les médecins, les commerçants et les infirmiers. "
    "Chaque année vous payez trop d'impôt sur vos revenus sans le savoir. "
    "La vraie réponse existe: grâce à l'assurance universelle vous protégez votre famille. "
    "Il y a une différence entre vous et un salarié. "
    "Je prends seulement trente minutes pour tout vous expliquer. "
    "Alors cliquez sur le lien en bas et écrivez-moi aujourd'hui."
)


def test_merge_tokens_rejoins_whisper_fragments():
    ws = [{"w": "d", "s": 0, "e": .1}, {"w": "'entreprise,", "s": .1, "e": .5}, {"w": "savez", "s": .6, "e": .8},
          {"w": "-vous", "s": .8, "e": 1.0}, {"w": "l'", "s": 1.1, "e": 1.2}, {"w": "assurance", "s": 1.2, "e": 1.6}]
    assert [w["w"] for w in fp.merge_tokens(ws)] == ["d'entreprise,", "savez-vous", "l'assurance"]


def test_list_detection_keeps_nouns_not_verbs():
    d = fp.detect_list(_words("pour les avocats, les médecins, les commerçants et les infirmiers."))
    assert d and [l for l, _ in d["items"]] == ["Avocats", "Médecins", "Commerçants", "Infirmiers"]
    assert fp.detect_list(_words("Revenez-moi, cliquez sur le lien, sur ces biens, à la retraite.")) is None


def test_solution_name_is_extracted():
    names = fp.solution_names(fp.merge_tokens(_words("grâce à l' assurance universelle vous gagnez.")))
    assert names and names[0][0] == "Assurance universelle"


def test_plan_rules_illustrates_the_speech():
    words = _words(SCRIPT)
    dur = words[-1]["e"] + 0.5
    plan = fp.plan_rules(words, dur, "heavy")
    types = [c["scene"]["type"] for c in plan]
    assert "icon_cards" in types and "cta_button" in types and "hero_reveal" in types
    assert "timer_ring" in types
    timer = next(c["scene"] for c in plan if c["scene"]["type"] == "timer_ring")
    assert timer["value"] == 30  # « trente » prononcé → 30, jamais inventé
    for a, b in zip(plan, plan[1:]):
        gap = b["start"] - a["end"]
        assert gap >= fp.MIN_FACE_GAP - 1e-6 or abs(gap) < 1e-6  # visage entre deux, ou enchaînement bord à bord
    for c in plan:
        assert c["start"] >= fp.HOOK_FACE
        assert fp.MIN_LEN - 0.7 <= c["end"] - c["start"] <= fp.MAX_LEN + 1e-6


def test_density_controls_the_amount_of_motion():
    words = _words(SCRIPT)
    dur = words[-1]["e"] + 0.5
    tot = {d: sum(c["end"] - c["start"] for c in fp.plan_rules(words, dur, d)) for d in ("light", "heavy")}
    assert tot["light"] < tot["heavy"]


def test_no_number_invented_without_speech():
    plan = fp.plan_rules(_words("Bonjour. Aujourd'hui je vous parle de votre avenir et de votre famille. Protégez vos proches maintenant."), 12, "heavy")
    for c in plan:
        assert c["scene"]["type"] not in ("timer_ring", "stat_number")


def test_compose_overlay_is_transparent_story():
    from app.explainer.facecam import compose_overlay
    words = fp.merge_tokens(_words(SCRIPT))
    plan = fp.plan_rules(words, words[-1]["e"] + 0.5, "medium")
    html = compose_overlay(plan, words, words[-1]["e"] + 0.5, "solaire", None)
    assert '"overlay": true' in html and "__STORY__" not in html and "__ENGINE__" not in html


def test_motion_pro_modes_listed_with_their_template():
    from app.api.v1 import modes
    from app.config import VALID_MODES
    from app.explainer.templates import TEMPLATES
    mp = [m for m in modes.MODE_DEFINITIONS if m["id"].startswith("motion_pro_")]
    assert {m["defaults"]["motion_template"] for m in mp} == set(TEMPLATES)
    assert all(m["family"] == "motion_pro" and m["id"] in VALID_MODES for m in mp)
    assert any(f["id"] == "motion_pro" for f in modes.FAMILIES)


def test_job_options_validate_motion_fields():
    from pydantic import ValidationError

    from app.schemas.job import JobOptions
    assert JobOptions(motion_template="neon", motion_density="heavy", brand_color="#12AB9f").motion_template == "neon"
    with pytest.raises(ValidationError):
        JobOptions(motion_template="inconnu")
    with pytest.raises(ValidationError):
        JobOptions(motion_density="max")


def test_pipeline_v2_delegates_motion_pro(tmp_path, monkeypatch):
    from app.explainer import facecam
    from app.processing import pipeline_v2
    src = tmp_path / "in.mp4"; src.write_bytes(b"x" * 100)
    seen = {}

    def fake(video, out, **kw):
        seen.update(kw)
        p = tmp_path / "final.mp4"; p.write_bytes(b"y" * 10)
        return {"output_path": str(p), "cutaways": [{"type": "cta_button"}], "steps_completed": ["export"], "planner": "regles"}
    monkeypatch.setattr(facecam, "run_facecam", fake)
    monkeypatch.setattr(pipeline_v2, "estimate_render_disk_gb", lambda *_: 0, raising=False)
    res = pipeline_v2.run_pipeline_v2(str(src), str(tmp_path / "o"), mode="motion_pro_neon",
                                      params={"options": {"motion_density": "light"}})
    assert res["engine"] == "motion_pro" and res["output_path"].endswith("final.mp4")
    assert seen["template"] == "neon" and seen["density"] == "light"
