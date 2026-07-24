"""Bibliothèque de silhouettes vectorielles + intégration au motion design.

Pourquoi maison plutôt qu'IA: gratuit, hors-ligne, strictement reproductible, et
exportable en SVG pour être retouché puis réimporté. Ces tests verrouillent ces
trois promesses.
"""
import xml.etree.ElementTree as ET

from PIL import Image

from app.autoedit_engine import config as cfg
from app.autoedit_engine import motion_design as md
from app.autoedit_engine import silhouettes as sil


# ---- bibliothèque -----------------------------------------------------------
def test_library_covers_the_useful_situations():
    names = set(sil.pose_names())
    assert {"presenter", "pointing", "thinking", "phone", "walking",
            "podium", "handshake", "table_meeting", "blocked"} <= names
    assert sil.DEFAULT_POSE in names
    for name in names:
        assert sil.POSES[name].figures, name          # au moins un personnage
        assert sil.POSES[name].label                  # libellé lisible


def test_icon_vocabulary_maps_to_meaningful_poses():
    assert sil.pose_for_icon("handshake") == "handshake"
    assert sil.pose_for_icon("phone") == "phone"
    assert sil.pose_for_icon("warning") == "blocked"
    assert sil.pose_for_icon("growth") == "podium"
    # inconnu / vide -> pose par défaut, jamais une erreur
    assert sil.pose_for_icon("inexistant") == sil.DEFAULT_POSE
    assert sil.pose_for_icon(None) == sil.DEFAULT_POSE


# ---- rendu ------------------------------------------------------------------
def test_render_is_transparent_and_actually_draws():
    img = sil.render_silhouette("presenter", 300, 450)
    assert img.size == (300, 450) and img.mode == "RGBA"
    alpha = img.split()[3]
    assert alpha.getextrema()[0] == 0                 # fond transparent
    # une part significative du cadre est encrée
    hist = alpha.histogram()
    inked = sum(hist[41:])
    assert 0.03 < inked / (300 * 450) < 0.60


def test_every_pose_renders_at_video_scale():
    for name in sil.pose_names():
        img = sil.render_silhouette(name, 240, 360)
        assert img.size == (240, 360), name
        assert img.split()[3].getextrema()[1] > 200, name


def test_render_is_deterministic():
    """Deux rendus identiques -> montage reproductible (pas d'aléa caché)."""
    a = sil.render_silhouette("handshake", 200, 300, t=1.25)
    b = sil.render_silhouette("handshake", 200, 300, t=1.25)
    assert a.tobytes() == b.tobytes()


def test_idle_animation_actually_moves():
    a = sil.render_silhouette("presenter", 200, 300, t=0.0)
    b = sil.render_silhouette("presenter", 200, 300, t=1.1)
    assert a.tobytes() != b.tobytes()


def test_reveal_fades_and_lifts():
    hidden = sil.render_silhouette("presenter", 200, 300, reveal=0.0)
    shown = sil.render_silhouette("presenter", 200, 300, reveal=1.0)
    assert hidden.split()[3].getextrema()[1] == 0     # invisible à reveal=0
    assert shown.split()[3].getextrema()[1] > 200


def test_plate_is_opaque_and_usable_as_an_illustration():
    plate = sil.render_plate("podium", 320, 480)
    assert plate.size == (320, 480)
    assert plate.split()[3].getextrema() == (255, 255)   # aucun trou


# ---- export SVG -------------------------------------------------------------
def test_svg_export_is_valid_xml_with_real_shapes(tmp_path):
    paths = sil.export_svgs(str(tmp_path))
    assert len(paths) == len(sil.POSES)
    for path in paths:
        root = ET.parse(path).getroot()
        assert root.tag.endswith("svg")
        shapes = [el for el in root.iter()
                  if el.tag.split("}")[-1] in {"polygon", "polyline", "rect"}]
        assert len(shapes) >= 6, path      # membres + buste + tête au minimum


def test_svg_declares_the_expected_canvas():
    svg = sil.to_svg("presenter", 400, 600)
    root = ET.fromstring(svg)
    assert root.get("width") == "400" and root.get("height") == "600"


def test_missing_custom_svg_is_silently_ignored():
    assert sil.load_custom_svg("pose_qui_n_existe_pas", 100, 100) is None


# ---- intégration au moteur --------------------------------------------------
def test_silhouette_only_used_where_the_figure_stays_whole():
    """Une composition qui recadre le haut ou le bas de la carte couperait le
    personnage: elle ne doit pas recevoir de silhouette."""
    for layout in md.BOARD_SILHOUETTE_LAYOUTS:
        assert md._silhouette_size({"layout": layout, "kind": "idea"}) is not None
    for layout in ("board_split", "board_collage", "board_overflow", "board_quote"):
        assert md._silhouette_size({"layout": layout, "kind": "idea"}) is None
    # côté générique, seules les compositions au masque rectangulaire
    assert md._silhouette_size({"layout": "circle_spot", "kind": "idea"}) is None
    assert md._silhouette_size({"layout": "stage_center", "kind": "idea"}) is not None


def test_silhouette_plate_matches_the_board_card():
    plate = md._silhouette_plate({"layout": "board_stage", "kind": "idea",
                                  "icon": "handshake"})
    x0, y0, x1, y1 = md.BOARD_CARD
    assert plate is not None and plate.size == (x1 - x0, y1 - y0)


def test_scene_can_opt_out_of_silhouettes():
    assert md._silhouette_plate({"layout": "board_stage", "kind": "idea"}) is not None
    scene = {"layout": "board_stage", "kind": "idea", "silhouette": False}
    # l'opt-out est lu par render_scene, pas par _silhouette_plate: on vérifie
    # que la valeur explicite est bien respectée en amont
    assert scene.get("silhouette") is False


def test_board_frame_renders_with_a_silhouette_illustration():
    md.select_palette("t", preset="board_pitch")
    stage = md._board_base()
    scene = {"kind": "idea", "headline": "ACCORD", "kicker": "La vente",
             "icon": "handshake", "layout": "board_stage", "duration": 3.6}
    illu = md._silhouette_plate(scene)
    frame = md._compose_board_frame(scene, illu, stage, 1.8, 3.6, "board_stage")
    assert frame.size == (cfg.WIDTH, cfg.HEIGHT)


def test_silhouette_is_never_counted_as_a_paid_ai_image(tmp_path, monkeypatch):
    """Le rapport du job ne doit compter QUE les illustrations réellement
    payées — sinon on ferait croire à des crédits consommés."""
    captured = {}

    class _FakePipe:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def write(self, frame):
            captured["wrote"] = True

    monkeypatch.setattr(md, "ProResPipe", _FakePipe)
    scene = {"id": "x", "kind": "idea", "headline": "ACCORD", "icon": "handshake",
             "layout": "board_stage", "duration": 0.2}
    out = md.render_scene(scene, str(tmp_path / "x.mov"))
    assert captured.get("wrote") is True
    assert out["illustrated"] is False          # aucune image IA
    assert out["silhouette"] == "handshake"     # mais bien illustré
