"""Variété visuelle entre montages: layouts motion design, masques d'image,
designs de présentation B-roll et nouveaux templates de sous-titres.

Demande produit: chaque montage doit avoir des illustrations 3D différentes ET
des compositions différentes — jamais « le même carré avec l'image dedans et
le texte en bas ».
"""
from PIL import Image

from app.autoedit_engine import broll_anim as ba
from app.autoedit_engine import config as cfg
from app.autoedit_engine import motion_design as md
from app.autoedit_engine import subs_ass


# ---- motion design: layouts + masques ---------------------------------------
def test_new_layouts_are_registered():
    assert {"circle_spot", "polaroid_tilt", "arch_gate"} <= set(md.LAYOUTS)
    assert len(md.LAYOUTS) >= 11


def test_layout_shapes_break_the_square_monotony():
    shapes = set(md.LAYOUT_ILLU_SHAPES.values())
    assert {"circle", "polaroid", "arch"} <= shapes


def test_layout_sequence_covers_every_design_without_immediate_repeat():
    seq = md._layout_sequence("seed-a", 30)
    assert all(a != b for a, b in zip(seq, seq[1:]))
    assert set(md.LAYOUTS) <= set(seq)
    # Deux vidéos différentes ne déroulent pas les layouts dans le même ordre.
    assert md._layout_sequence("seed-a", 12) != md._layout_sequence("seed-b", 12)


def test_every_layout_composes_a_full_frame():
    illu = Image.new("RGBA", (256, 256), (90, 140, 220, 255))
    stage = md._stage_base()
    scene = {"kind": "idea", "headline": "TEST", "kicker": "OK",
             "icon": "money", "duration": 4.6}
    for layout in md.LAYOUTS:
        for il in (illu, None):
            frame = md._compose_frame({**scene, "layout": layout}, il, stage,
                                      1.5, 4.6)
            assert frame.size == (cfg.WIDTH, cfg.HEIGHT), layout


# ---- B-roll: designs de présentation ----------------------------------------
def test_broll_frame_styles_catalogued():
    assert set(cfg.BROLL_FRAME_STYLES) == {"brackets", "polaroid", "circle",
                                           "fullbleed"}


def test_broll_frame_style_rotation_is_seeded_and_covers_all_designs():
    imgs_a = [{"id": f"a{i}", "label": "x"} for i in range(8)]
    imgs_b = [{"id": f"b{i}", "label": "y"} for i in range(8)]
    styles_a = ba._video_frame_styles(imgs_a)
    # Reproductible pour un même job, et tous les designs sont utilisés.
    assert styles_a == ba._video_frame_styles(imgs_a)
    assert set(styles_a) == set(cfg.BROLL_FRAME_STYLES)
    # Un autre montage démarre ailleurs dans la rotation (offsets seedés).
    offsets = {ba._video_frame_styles([{"id": f"v{k}{i}", "label": ""}
                                       for i in range(4)])[0]
               for k in range(24)}
    assert len(offsets) >= 3


def test_broll_every_style_composes_a_full_frame():
    src = Image.new("RGBA", (320, 240), (200, 120, 60, 255))
    plate = ba._background_plate(src)
    for style in cfg.BROLL_FRAME_STYLES:
        main = ba._prepare_main(src, style)
        frame = ba._compose_frame(main, plate, "Label", "rise", 1.0, 3.0,
                                  frame_style=style)
        assert frame.size == (cfg.WIDTH, cfg.HEIGHT), style


# ---- nouveaux templates de sous-titres --------------------------------------
def _mini_vu():
    words = ["gagner", "de", "l'argent", "vite"]
    return {"segments": [{"text": " ".join(words), "start": 0, "end": 2,
                          "words": [{"word": w, "start": i * 0.4,
                                     "end": i * 0.4 + 0.35}
                                    for i, w in enumerate(words)]}]}


def test_beast_impact_template_builds_uppercase_glow_ass():
    ass = subs_ass.build_ass(_mini_vu(), [{"start": 0.0, "end": 2.0}],
                             template="beast_impact")
    assert "GAGNER" in ass          # MAJUSCULES
    assert "\\blur3" in ass         # glow sur le mot actif


def test_mint_wave_template_is_progressive_karaoke():
    tpl = cfg.ASS_TEMPLATES["mint_wave"]
    assert tpl["progressive"] and tpl["box"] and tpl["future"]
    ass = subs_ass.build_ass(_mini_vu(), [{"start": 0.0, "end": 2.0}],
                             template="mint_wave")
    assert "&H787878&" in ass       # mots à venir estompés


def test_default_template_is_not_handwritten():
    assert cfg.DEFAULT_TEMPLATE != "handwritten_note"


# ---- illustrations 3D: pool élargi ------------------------------------------
def test_3d_style_pool_is_wide_enough_for_montage_variety():
    assert len(cfg.MOTION_STYLE_3D_PREFIXES) >= 10
    assert len(cfg.MOTION_3D_STYLES) == len(cfg.MOTION_STYLE_3D_PREFIXES)
