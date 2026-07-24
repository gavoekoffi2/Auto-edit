"""Style « Board de présentation » — répliqué d'une vidéo de référence
(motion design 3D publicitaire).

Langage visuel à préserver: un panneau vert sapin texturé qui NE BOUGE PAS
(titre serif en haut à droite, label serif à gauche, pile de flyers) et une
grande carte 9:16 claire qui rejoue chaque idée. D'un beat à l'autre seule la
carte change — c'est ce qui donne la sensation d'une vraie présentation.
"""
from PIL import Image

import pytest

from app.autoedit_engine import config as cfg
from app.autoedit_engine import motion_design as md
from app.autoedit_engine import motion_presets as mp
from app.autoedit_engine import subs_ass
from app.autoedit_engine.fonts import load_font


# ---- famille de couleurs ----------------------------------------------------
def test_board_preset_exists_and_is_opt_in_only():
    preset = mp.preset_for("board_pitch")
    assert preset.name == "board_pitch"
    # Fond vert sombre + encre crème: jamais tiré au hasard, sinon il casserait
    # les autres templates.
    assert "board_pitch" in mp.STYLE_ONLY_PRESETS
    assert preset.bg_top[1] > preset.bg_top[0] and preset.bg_top[1] > preset.bg_top[2]
    assert preset.ink[0] > 220 and preset.ink[1] > 220


def test_board_preset_never_enters_the_random_rotation():
    picked = {mp.choose_preset(f"job-{i}").name for i in range(300)}
    assert "board_pitch" not in picked


# ---- compositions de carte --------------------------------------------------
def test_board_layouts_are_declared():
    # Le style doit offrir BEAUCOUP de compositions différentes: la demande
    # produit est explicite — « il ne faut pas que ce soit figé ».
    assert len(md.BOARD_LAYOUTS) >= 9
    assert {"board_stage", "board_quote", "board_split", "board_number",
            "board_overflow", "board_sandwich", "board_collage",
            "board_annotated", "board_showcase"} == set(md.BOARD_LAYOUTS)
    # Elles vivent à part: jamais mélangées à la rotation générique.
    assert not set(md.BOARD_LAYOUTS) & set(md.LAYOUTS)
    # Le décor « coins vague » ne s'applique qu'à une partie des cartes, sinon
    # il redeviendrait lui-même une signature figée.
    assert md.BOARD_WAVE_LAYOUTS < set(md.BOARD_LAYOUTS)


def test_board_layout_sequence_is_seeded_and_cycles():
    n = len(md.BOARD_LAYOUTS)
    seq = md._board_layout_sequence("seed-a", n)
    assert len(seq) == n
    assert set(seq) == set(md.BOARD_LAYOUTS)                       # toutes utilisées
    assert all(a != b for a, b in zip(seq, seq[1:]))
    assert seq == md._board_layout_sequence("seed-a", n)           # reproductible
    starts = {md._board_layout_sequence(f"v{i}", 1)[0] for i in range(40)}
    assert len(starts) >= 4                                        # varie par vidéo


def test_board_card_stays_clear_of_the_subtitle_band():
    """La carte ne doit jamais passer sous les sous-titres brûlés."""
    _, _, _, y1 = md.BOARD_CARD
    assert y1 < cfg.ZONE_SUBS_Y - 40


def test_board_card_keeps_a_9_16_shape():
    x0, y0, x1, y1 = md.BOARD_CARD
    ratio = (x1 - x0) / (y1 - y0)
    assert 0.52 < ratio < 0.60


# ---- rendu ------------------------------------------------------------------
def _illu():
    return Image.new("RGBA", (256, 256), (90, 140, 220, 255))


@pytest.fixture(scope="module")
def board_stage():
    md.select_palette("test", preset="board_pitch")
    return md._board_base()


def test_board_base_is_fully_opaque_green(board_stage):
    assert board_stage.size == (cfg.WIDTH, cfg.HEIGHT)
    assert board_stage.split()[3].getextrema() == (255, 255)      # aucun trou
    r, g, b, _ = board_stage.getpixel((cfg.WIDTH // 2, 200))
    assert g > r and g > b                                         # vraiment vert


def test_every_board_layout_composes_a_full_frame(board_stage):
    scene = {"kind": "idea", "headline": "AUTOMATISER", "kicker": "La méthode",
             "spoken_line": "tu perds des ventes chaque jour sans le savoir",
             "value": 36, "raw": "36", "duration": 4.4}
    for layout in md.BOARD_LAYOUTS:
        for illu in (_illu(), None):                # avec et sans image IA
            for t in (0.0, 0.35, 2.0, 4.3):
                frame = md._compose_board_frame({**scene, "layout": layout},
                                                illu, board_stage, t, 4.4, layout)
                assert frame.size == (cfg.WIDTH, cfg.HEIGHT), (layout, t)


def test_board_survives_empty_text(board_stage):
    """Un beat sans titre ni phrase ne doit pas casser le rendu."""
    for layout in md.BOARD_LAYOUTS:
        frame = md._compose_board_frame({"kind": "idea", "layout": layout},
                                        None, board_stage, 1.5, 4.0, layout)
        assert frame.size == (cfg.WIDTH, cfg.HEIGHT)


def test_compose_frame_routes_board_layouts(board_stage):
    """`_compose_frame` doit basculer sur le board sans passer par l'arbre
    de composition générique (sinon on perdrait le panneau)."""
    scene = {"kind": "idea", "headline": "TEST", "layout": "board_stage",
             "duration": 4.0}
    frame = md._compose_frame(scene, _illu(), board_stage, 1.5, 4.0)
    assert frame.size == (cfg.WIDTH, cfg.HEIGHT)


def test_card_content_slides_in_then_out():
    """Le contenu entre par la droite et sort par la gauche — la carte, elle,
    ne bouge jamais (signature de la référence)."""
    bw = 620
    start, _ = md._board_content_offset(0.10, 4.4, bw)
    settled, fade_mid = md._board_content_offset(1.5, 4.4, bw)
    leaving, fade_end = md._board_content_offset(4.35, 4.4, bw)
    assert start > bw * 0.3            # arrive depuis la droite
    assert settled == 0                # posé au centre
    assert leaving < -bw * 0.3         # repart vers la gauche
    assert fade_mid == 1.0 and fade_end < 0.4


# ---- typographie ------------------------------------------------------------
def test_playfair_serif_is_bundled():
    """Le serif éditorial fait tout le cachet du style: il doit être embarqué
    dans le repo, pas dépendre des polices système de la machine."""
    from app.autoedit_engine import fonts
    for family in ("Playfair", "Playfair Italic"):
        path = fonts._find_font_file(family)
        assert path and "autoedit_engine/assets/fonts" in path, family
    # et il rend un texte de largeur non nulle
    assert load_font("Playfair", 80).getbbox("Essentiel")[2] > 0


# ---- sous-titres assortis ---------------------------------------------------
def test_board_subtitle_template_matches_the_style():
    tpl = cfg.ASS_TEMPLATES["board_serif"]
    assert tpl["box"] and tpl["progressive"] and tpl["future"]
    vu = {"segments": [{"text": "vendre plus vite", "start": 0, "end": 1.6,
                        "words": [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35}
                                  for i, w in enumerate(["vendre", "plus", "vite"])]}]}
    ass = subs_ass.build_ass(vu, [{"start": 0.0, "end": 1.6}], template="board_serif")
    assert "Dialogue:" in ass
    assert "&H909C96&" in ass          # mots à venir estompés (karaoké progressif)


# ---- câblage produit --------------------------------------------------------
def test_board_mode_is_selectable_and_wired_end_to_end():
    from app.api.v1 import modes
    from app.config import VALID_MODES
    from app.processing.pipeline_v2 import MODE_TO_TEMPLATE, V2_MODE_PRESETS
    from app.schemas.job import JobOptions

    by_id = {m["id"]: m for m in modes.MODE_DEFINITIONS}
    assert "board_pitch" in by_id
    d = by_id["board_pitch"]["defaults"]
    assert d["subtitle_template"] == "board_serif"
    assert d["motion_preset"] == "board_pitch"
    assert d["motion_design"] is True

    assert "board_pitch" in VALID_MODES
    assert MODE_TO_TEMPLATE["board_pitch"] == "board_serif"
    assert V2_MODE_PRESETS["board_pitch"]["motion_preset"] == "board_pitch"
    # le schéma d'API doit accepter le couple exposé par le catalogue
    JobOptions(subtitle_template="board_serif", motion_preset="board_pitch")
