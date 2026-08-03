"""Moteur 3D procédural des scènes de motion design (`motion_3d`).

Demande produit: « le motion design ne fonctionne pas au niveau des montages,
il faut des motion design 3D, pas seulement des traits ». Le repli sans image IA
n'est donc plus un dessin au trait mais une VRAIE scène 3D — volumes ombrés,
caméra qui tourne, ombre de contact — rendue localement, sans crédit image.
"""
import math

import pytest

from app.autoedit_engine import config as engine_config
from app.autoedit_engine import content
from app.autoedit_engine import motion_3d as m3
from app.autoedit_engine import motion_design as md
from app.autoedit_engine import motion_presets as mp


# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #
def test_several_distinct_3d_styles_exist():
    assert len(m3.STYLES) >= 5
    names = [s.name for s in m3.STYLES]
    assert len(set(names)) == len(names)
    # Chaque style est une direction artistique réelle: fond, sol, matériau.
    for style in m3.STYLES:
        assert style.bg_top != style.bg_bottom
        assert 0.0 <= style.material.ambient <= 1.0
        assert style.material.diffuse > 0


def test_style_selection_is_stable_and_varies_across_videos():
    assert m3.select_style("transcript-A") == m3.select_style("transcript-A")
    seeds = [f"video-{i}" for i in range(40)]
    assert len({m3.select_style(s) for s in seeds}) >= 3
    assert m3.select_style(None) == m3.DEFAULT_STYLE


def test_every_preset_family_maps_to_a_real_style():
    for preset in mp.PRESETS:
        style = mp.style_3d_for(preset.name)
        if preset.illustration == "render3d":
            assert style in m3.STYLES_BY_NAME, preset.name
        else:
            assert style is None, preset.name


# --------------------------------------------------------------------------- #
# Modèles — un objet 3D pour CHAQUE concept que le moteur sait détecter
# --------------------------------------------------------------------------- #
def test_every_engine_icon_has_a_3d_model():
    """Aucune scène ne doit tomber sur le modèle par défaut faute de modèle."""
    icons = set(md.ICONS) | {content.DEFAULT_ICON}
    for rule in content.ICON_RULES:
        icons.add(rule[1] if hasattr(rule[0], "search") else rule[0])
    missing = sorted(icons - set(m3.MODELS))
    assert not missing, f"modèles 3D manquants: {missing}"


@pytest.mark.parametrize("icon", sorted(m3.MODELS))
def test_every_model_builds_valid_geometry(icon):
    parts = m3.model_for(icon)
    assert parts, icon
    for part in parts:
        assert part.kind in {"prism", "sphere"}
        if part.kind == "prism":
            assert part.poly and len(part.poly) >= 3
            assert part.depth > 0
            # Le modèle reste dans le repère unitaire: au-delà il sortirait
            # du cadre de la plaque quelle que soit sa taille.
            assert all(abs(x) <= 2.0 and abs(y) <= 2.0 for x, y in part.poly)
        else:
            assert part.r > 0


def test_unknown_icon_still_renders_a_scene():
    assert not m3.has_model("concept-inconnu")
    img = m3.render_plate("concept-inconnu", 120, 160, t=1.0)
    assert img.size == (120, 160)


# --------------------------------------------------------------------------- #
# Rendu
# --------------------------------------------------------------------------- #
def test_plate_is_opaque_and_correctly_sized():
    img = m3.render_plate("growth", 180, 240, t=1.2, style="clay_studio")
    assert img.mode == "RGBA"
    assert img.size == (180, 240)
    # Le studio est un décor PLEIN: la scène est une prise de contrôle du
    # cadre, rien de la vidéo ne doit transparaître dessous.
    assert img.split()[3].getextrema()[0] == 255


def test_the_object_actually_occupies_the_frame():
    """Une plaque quasi vide voudrait dire que la géométrie n'a pas été rendue."""
    plain = m3.render_plate("growth", 160, 200, t=0.0, style="iso_blocks")
    drawn = m3.render_plate("growth", 160, 200, t=2.0, style="iso_blocks")
    diff = sum(abs(a - b) for a, b in zip(plain.tobytes(), drawn.tobytes()))
    assert diff > 0, "l'objet 3D n'apparaît pas entre t=0 et t=2"


def test_camera_turns_so_the_volume_reads():
    """C'est la ROTATION qui fait lire le volume: deux instants ≠ deux images."""
    a = m3.render_plate("box", 140, 180, t=0.9, style="chrome_metal")
    b = m3.render_plate("box", 140, 180, t=2.6, style="chrome_metal")
    assert a.tobytes() != b.tobytes()


def test_render_is_reproducible():
    a = m3.render_plate("shield", 120, 150, t=1.5, style="glass_neon")
    b = m3.render_plate("shield", 120, 150, t=1.5, style="glass_neon")
    assert a.tobytes() == b.tobytes()


def test_palette_follows_the_family_ink():
    """Les couleurs de la famille de preset habillent l'objet: deux familles
    ne rendent pas la même scène dans les mêmes teintes."""
    warm = m3.render_plate("star", 120, 150, t=1.5, style="clay_studio",
                           accent=(255, 90, 40, 255), gold=(255, 210, 90, 255))
    cold = m3.render_plate("star", 120, 150, t=1.5, style="clay_studio",
                           accent=(40, 120, 255, 255), gold=(90, 240, 220, 255))
    assert warm.tobytes() != cold.tobytes()


def test_geometry_helpers_are_sane():
    ring = m3.annulus_poly(0.0, 0.0, 0.8, 0.5)
    assert len(ring) > 8
    turned = m3.rotate_poly([(1.0, 0.0)], math.pi / 2)
    assert turned[0][0] == pytest.approx(0.0, abs=1e-9)
    assert turned[0][1] == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# Intégration au moteur de montage
# --------------------------------------------------------------------------- #
def test_selecting_a_family_arms_its_3d_style():
    md.select_palette("seed", preset="clay_3d")
    assert md.FAMILY == "clay_3d"
    assert md.STYLE_3D == "clay_studio"
    # La famille manuscrite garde son dessin au trait (c'est son identité).
    md.select_palette("seed", preset="sketch_notes")
    assert md.STYLE_3D is None


def test_3d_can_be_switched_off_by_configuration(monkeypatch):
    """Rollback d'urgence: MOTION_3D=0 rend la main au repli historique."""
    monkeypatch.setattr(engine_config, "MOTION_3D_ENABLED", False)
    md.select_palette("seed", preset="clay_3d")
    assert md.STYLE_3D is None
    monkeypatch.setattr(engine_config, "MOTION_3D_ENABLED", True)
    md.select_palette("seed", preset="clay_3d")
    assert md.STYLE_3D == "clay_studio"


def test_plate_size_follows_the_layout():
    """La plaque 3D remplit exactement la zone d'illustration de sa composition."""
    for layout in md.LAYOUTS:
        scene = {"kind": "idea", "layout": layout}
        w, h = md._plate_size(scene)
        x0, y0, x1, y1 = md._illu_box("idea", layout)
        assert (w, h) == (x1 - x0, y1 - y0)
    # Les compositions "board" jouent dans la carte, pas dans le panneau.
    w, h = md._plate_size({"kind": "idea", "layout": "board_stage"})
    x0, y0, x1, y1 = md.BOARD_CARD
    assert (w, h) == (x1 - x0, y1 - y0)


def test_scene_renders_in_3d_and_reports_it(tmp_path, monkeypatch):
    frames = []

    class _FakePipe:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def write(self, frame):
            frames.append(frame)

    monkeypatch.setattr(md, "ProResPipe", _FakePipe)
    md.select_palette("seed-3d", preset="iso_3d")
    scene = {"id": "md_000", "kind": "idea", "headline": "CROISSANCE",
             "icon": "growth", "layout": "stage_center", "duration": 0.2,
             "excerpt": "Ton chiffre d'affaires double.", "concepts": []}
    out = md.render_scene(scene, str(tmp_path / "s.mov"))
    assert out["render3d"] == "iso_blocks"
    assert out["illustrated"] is False        # aucun crédit image consommé
    assert frames, "aucune image écrite"
    # La scène est ANIMÉE: deux images consécutives diffèrent.
    assert len(frames) >= 2 and frames[0].tobytes() != frames[-1].tobytes()
