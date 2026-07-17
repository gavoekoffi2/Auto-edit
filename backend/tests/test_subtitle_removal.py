"""Burned-in subtitle detection/removal (STEP 0) — pure image-level tests.

Pas de ffmpeg ni de vraie vidéo: on fabrique des frames synthétiques (PIL ->
numpy BGR) avec ou sans sous-titre incrusté et on prouve que:
  * un texte type sous-titre (large, centré, bas du cadre) est détecté,
  * une frame propre ne déclenche rien,
  * la bande n'est retenue que si elle est PERSISTANTE sur les frames,
  * le filtre delogo généré reste strictement dans le cadre.
"""
import os

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from PIL import Image, ImageDraw, ImageFont

from app.autoedit_engine import config as engine_config
from app.autoedit_engine import subtitle_removal as sr

W, H = 720, 1280
FONT_PATH = os.path.join(os.path.dirname(engine_config.__file__),
                         "assets", "fonts", "Poppins-Bold.ttf")


def _base_frame() -> Image.Image:
    """A frame with a gradient + a face-ish blob, NO subtitle."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        shade = 40 + int(60 * y / H)
        for x in range(0, W, 4):
            for dx in range(4):
                px[min(W - 1, x + dx), y] = (shade, shade + 10, shade + 25)
    d = ImageDraw.Draw(img)
    d.ellipse((W * 0.3, H * 0.15, W * 0.7, H * 0.45), fill=(180, 150, 130))
    return img


def _with_subtitle(text: str = "CECI EST UN SOUS TITRE") -> Image.Image:
    img = _base_frame()
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 44)
    d.text((W // 2, int(H * 0.86)), text, font=font, fill=(255, 255, 255),
           anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0))
    return img


def _bgr(img: Image.Image):
    return np.asarray(img.convert("RGB"))[:, :, ::-1].copy()


def test_subtitle_frame_produces_candidate_box():
    boxes = sr.subtitle_boxes(_bgr(_with_subtitle()))
    assert boxes, "burned subtitle line must be detected"
    x, y, w, h = max(boxes, key=lambda b: b[2])
    assert y > H * 0.6, "box must be in the lower band"
    assert w > W * 0.22 and w > h * 3, "box must look like a text LINE"


def test_clean_frame_produces_no_box():
    assert sr.subtitle_boxes(_bgr(_base_frame())) == []


def test_band_requires_persistence():
    with_text = sr.subtitle_boxes(_bgr(_with_subtitle()))
    without = []
    # 20 frames, subtitle visible on 14 -> persistent band found.
    per_frame = [with_text] * 14 + [without] * 6
    band = sr.aggregate_band(per_frame, W, H)
    assert band is not None
    assert band["hits"] >= 14
    # Subtitle-like box on only 2/20 frames -> ignored (ponctuel, pas un track).
    sparse = [with_text] * 2 + [without] * 18
    assert sr.aggregate_band(sparse, W, H) is None
    assert sr.aggregate_band([], W, H) is None


def test_delogo_filter_stays_inside_frame():
    with_text = sr.subtitle_boxes(_bgr(_with_subtitle()))
    band = sr.aggregate_band([with_text] * 10, W, H)
    assert band is not None
    assert band["x"] >= 1 and band["y"] >= 1
    assert band["x"] + band["w"] <= W - 1
    assert band["y"] + band["h"] <= H - 1
    flt = sr.build_delogo_filter(band)
    assert flt.startswith("delogo=x=") and f":w={band['w']}" in flt


def test_clean_source_is_noop_without_subtitles(tmp_path, monkeypatch):
    # detect -> None must return the ORIGINAL path untouched, flags off.
    monkeypatch.setattr(sr, "detect_burned_subtitles", lambda *a, **k: None)
    path, rep = sr.clean_source("input.mp4", str(tmp_path))
    assert path == "input.mp4"
    assert rep["source_subtitles_detected"] is False
    assert rep["source_subtitles_removed"] is False
