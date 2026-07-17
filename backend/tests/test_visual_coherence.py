"""Tests cohérence visuelle: lumière 9:16, flash coupé, styles 3D variés,
suppression des sous-titres incrustés."""
import os
import shutil
import subprocess

import pytest

from app.autoedit_engine import config as cfg
from app.autoedit_engine import genimg
from app.autoedit_engine import subtitle_scrub as ss

_FFMPEG = shutil.which("ffmpeg")


# ---- lumière -----------------------------------------------------------------
def test_camera_flashes_disabled_by_default():
    """Le flash blanc plein écran (+ obturateur) est coupé par défaut: un seul
    langage lumière (light-leak réel) — pas de « brouillard »."""
    assert cfg.CAMERA_FLASHES_ENABLED is False


def test_light_leak_prepared_as_full_frame_cover():
    """L'asset 16:9 doit être converti en cover 1080x1920 (il ne couvrait
    qu'une bande du cadre vertical)."""
    import inspect
    from app.autoedit_engine import video_dynamics
    src = inspect.getsource(video_dynamics.prepare_light_leak_overlay_clip)
    assert "force_original_aspect_ratio=increase" in src
    assert "scale={config.WIDTH}:{config.HEIGHT}" in src
    assert "crop={config.WIDTH}:{config.HEIGHT}" in src


# ---- styles 3D variés ----------------------------------------------------------
def test_motion_3d_styles_are_varied_and_deterministic():
    names = {s["name"] for s in cfg.MOTION_3D_STYLES}
    assert len(names) >= 4                       # plusieurs familles distinctes
    for s in cfg.MOTION_3D_STYLES:
        assert "3D" in s["prefix"] or "3d" in s["prefix"].lower()
        assert "NO text" in s["prefix"]          # jamais de texte incrusté
    # Déterministe par seed; des seeds différents couvrent plusieurs familles.
    assert (genimg.pick_motion_3d_style("video-abc")["name"]
            == genimg.pick_motion_3d_style("video-abc")["name"])
    picked = {genimg.pick_motion_3d_style(f"video-{i}")["name"] for i in range(40)}
    assert len(picked) >= 3
    assert genimg.pick_motion_3d_style(None)["name"] == cfg.MOTION_3D_STYLES[0]["name"]


# ---- suppression des sous-titres incrustés -------------------------------------
def test_bottom_crop_filter_shape():
    f = ss.bottom_crop_filter(0.13)
    assert f.startswith("crop=iw:trunc(ih*0.87")
    # bande absurde => on garde au moins la moitié de l'image
    assert "0.50" in ss.bottom_crop_filter(0.9)


def test_job_options_remove_source_subtitles_flag():
    from app.schemas.job import JobOptions
    assert JobOptions(remove_source_subtitles=False).remove_source_subtitles is False
    assert JobOptions().remove_source_subtitles is None   # défaut engine = activé


@pytest.mark.skipif(_FFMPEG is None, reason="ffmpeg absent")
def test_detects_burned_subtitles_and_ignores_clean_video(tmp_path):
    """Détection réelle: vidéo avec sous-titres gravés -> bande ~10-20 %;
    même vidéo sans texte -> aucune détection (pas de faux positif)."""
    if ss._cv2() is None:
        pytest.skip("OpenCV absent")
    burned = tmp_path / "burned.mp4"
    clean = tmp_path / "clean.mp4"
    subprocess.run(
        [_FFMPEG, "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc2=size=480x854:duration=8:rate=8",
         "-vf", "boxblur=14,drawtext=text='Sous-titre gravé ici':fontsize=30:"
                "fontcolor=white:borderw=3:bordercolor=black:"
                "x=(w-text_w)/2:y=h*0.88",
         "-pix_fmt", "yuv420p", str(burned)], check=True, timeout=120)
    subprocess.run(
        [_FFMPEG, "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc2=size=480x854:duration=8:rate=8",
         "-vf", "boxblur=14", "-pix_fmt", "yuv420p", str(clean)],
        check=True, timeout=120)

    band, rep = ss.detect_burned_subtitles(str(burned))
    assert rep["detected"] and band is not None
    assert ss.MIN_BAND_FRAC <= band <= ss.MAX_BAND_FRAC

    band2, rep2 = ss.detect_burned_subtitles(str(clean))
    assert band2 is None and rep2["detected"] is False
