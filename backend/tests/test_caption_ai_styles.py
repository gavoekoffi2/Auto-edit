"""Tests des 3 styles de montage inspirés des vidéos Captions AI.

Réfs produit (TikTok @kakpobi9033, analysées image par image):
  * pill_editorial    — pilule blanche, karaoké progressif noir/gris,
                        bandeaux mots-clés « papier déchiré »
  * neon_hype         — MAJUSCULES condensées, mot actif cyan + glow,
                        mots-clés glitch chromatique
  * handwritten_note  — écriture manuscrite, cercle dessiné à la main,
                        scènes carnet crème
"""
from app.autoedit_engine import config as engine_config
from app.autoedit_engine import subs_ass
from app.api.v1.modes import MODE_DEFINITIONS
from app.processing.pipeline_v2 import MODE_TO_TEMPLATE, V2_MODE_PRESETS

STYLE_IDS = ["pill_editorial", "neon_hype", "handwritten_note"]

_VU = {
    "segments": [{
        "text": "la confiance que vous faites",
        "start": 0.0, "end": 2.5,
        "words": [
            {"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4}
            for i, w in enumerate(["la", "confiance", "que", "vous", "faites"])
        ],
    }]
}
_RANGES = [{"start": 0.0, "end": 3.0, "out_start": 0.0, "out_end": 3.0}]


def test_templates_exist_with_style_flags():
    tpl = engine_config.ASS_TEMPLATES["pill_editorial"]
    assert tpl["box"] and tpl["progressive"] and tpl["future"]
    tpl = engine_config.ASS_TEMPLATES["neon_hype"]
    assert tpl["uppercase"] and tpl["glow"]
    assert "handwritten_note" in engine_config.ASS_TEMPLATES


def test_popup_theme_follows_template():
    assert engine_config.TEMPLATE_POPUP_THEMES == {
        "pill_editorial": "editorial_collage",
        "neon_hype": "neon_glitch",
        "handwritten_note": "sketch",
    }
    # Les templates historiques gardent la pilule dorée.
    assert engine_config.TEMPLATE_POPUP_THEMES.get(
        "tiktok_yellow", engine_config.DEFAULT_POPUP_THEME) == "gold_chip"


def test_popup_sfx_pools_match_themes():
    pools = engine_config.POPUP_SFX_THEME_POOLS
    assert "paper_rip" in pools["editorial_collage"]
    assert "glitch" in pools["neon_glitch"]
    assert "pen_scribble" in pools["sketch"]
    # Chaque SFX référencé existe dans le vocabulaire du moteur.
    for pool in pools.values():
        assert set(pool) <= set(engine_config.SFX_NAMES)


def test_paper_rip_sfx_registered():
    assert "paper_rip" in engine_config.SFX_NAMES
    assert engine_config.SFX_GAINS["paper_rip"] > 0
    from app.autoedit_engine import sfx_lib
    assert "paper_rip" in sfx_lib.GENERATORS


def test_neon_hype_ass_is_uppercase_with_glow():
    ass = subs_ass.build_ass(_VU, _RANGES, template="neon_hype")
    assert "CONFIANCE" in ass
    assert "\\blur3" in ass          # glow sur le mot actif


def test_pill_editorial_ass_dims_upcoming_words():
    ass = subs_ass.build_ass(_VU, _RANGES, template="pill_editorial")
    assert "&HBBBBBB&" in ass        # mots à venir en gris
    assert "&H262626&" in ass        # mots prononcés en noir


def test_modes_catalog_exposes_the_three_styles():
    by_id = {m["id"]: m for m in MODE_DEFINITIONS}
    for style in STYLE_IDS:
        assert style in by_id, style
        d = by_id[style]["defaults"]
        assert d["subtitle_template"] == style
        assert d["visual_mode"] == "auto_fallback"   # B-roll IA + repli propre
        assert d["ai_broll"] is True
        assert by_id[style]["pipeline"] == "v2"


def test_pipeline_presets_and_template_mapping():
    for style in STYLE_IDS:
        assert MODE_TO_TEMPLATE[style] == style
        preset = V2_MODE_PRESETS[style]
        assert preset["subtitle_template"] == style
        assert preset["ai_broll"] is True
        assert preset["visual_mode"] == "auto_fallback"
    assert V2_MODE_PRESETS["pill_editorial"]["motion_preset"] == "editorial_paper"
    assert V2_MODE_PRESETS["neon_hype"]["motion_preset"] == "neon_social"
    assert V2_MODE_PRESETS["handwritten_note"]["motion_preset"] == "sketch_notes"


def test_job_schema_accepts_style_options():
    from app.schemas.job import JobOptions, JobCreate
    import uuid
    opts = JobOptions(subtitle_template="neon_hype", motion_preset="sketch_notes")
    assert opts.subtitle_template == "neon_hype"
    job = JobCreate(video_id=uuid.uuid4(), mode="pill_editorial")
    assert job.mode == "pill_editorial"
