"""Tests du recadrage vertical intelligent (suivi de visage MVP)."""
from app.autoedit_engine import smart_crop as sc


def test_smooth_centers_fills_gaps_and_limits_step():
    # Trous comblés par les voisins; déplacement max par segment respecté.
    raw = [0.3, None, 0.9, None, None]
    out = sc.smooth_centers(raw, ema_alpha=1.0, max_step=0.2)
    assert len(out) == 5
    assert out[0] == 0.3
    for a, b in zip(out, out[1:]):
        assert abs(b - a) <= 0.2 + 1e-9      # jamais de saut brutal


def test_smooth_centers_all_none_defaults_to_center():
    assert sc.smooth_centers([None, None, None]) == [0.5, 0.5, 0.5]


def test_smooth_centers_clamps_out_of_range_values():
    out = sc.smooth_centers([1.7, -0.4], ema_alpha=1.0, max_step=1.0)
    assert 0.0 <= out[0] <= 1.0 and 0.0 <= out[1] <= 1.0


def test_crop_filter_shapes():
    f = sc.crop_filter(0.75)
    assert "force_original_aspect_ratio=increase" in f
    assert "crop=1080:1920" in f
    assert "0.7500" in f
    # centre borné dans [0, 1]
    assert "1.0000" in sc.crop_filter(2.0)
    assert "0.0000" in sc.crop_filter(-1.0)


def test_fixed_modes_do_not_need_opencv(tmp_path, monkeypatch):
    # Les modes fixes ne touchent ni ffprobe ni OpenCV.
    ranges = [{"start": 0, "end": 5}, {"start": 5, "end": 9}]
    centers, report = sc.plan_crop_centers("missing.mp4", ranges, mode="center")
    assert centers == [0.5, 0.5]
    assert report["engine"] == "fixed"
    centers, _ = sc.plan_crop_centers("missing.mp4", ranges, mode="left")
    assert centers == [sc.FIXED_CENTERS["left"]] * 2
    centers, _ = sc.plan_crop_centers("missing.mp4", ranges, mode="right")
    assert centers == [sc.FIXED_CENTERS["right"]] * 2


def test_auto_mode_falls_back_to_center_without_opencv(monkeypatch):
    monkeypatch.setattr(sc, "opencv_available", lambda: False)
    monkeypatch.setattr(sc, "source_is_landscape", lambda _s: True)
    ranges = [{"start": 0, "end": 5}]
    centers, report = sc.plan_crop_centers("x.mp4", ranges, mode="auto")
    assert centers == [0.5]
    assert report["fallback"] == "opencv_unavailable"


def test_auto_mode_skips_vertical_sources(monkeypatch):
    monkeypatch.setattr(sc, "source_is_landscape", lambda _s: False)
    ranges = [{"start": 0, "end": 5}]
    centers, report = sc.plan_crop_centers("x.mp4", ranges, mode="auto")
    assert centers == [0.5]
    assert report["fallback"] == "source_not_landscape"


def test_job_options_accept_smart_crop_mode():
    import pytest
    from app.schemas.job import JobOptions
    assert JobOptions(smart_crop_mode="auto").smart_crop_mode == "auto"
    with pytest.raises(ValueError):
        JobOptions(smart_crop_mode="diagonal")


def test_broken_cv2_without_haar_is_treated_as_unavailable(monkeypatch):
    """Non-régression: OpenCV 5.x (sans CascadeClassifier) => fallback centre,
    jamais un AttributeError qui tuerait le rendu (vu en staging Docker où
    scenedetect[opencv] tirait opencv-python 5.x par-dessus le headless <5)."""
    import sys, types
    fake = types.ModuleType("cv2")          # cv2 sans API Haar
    monkeypatch.setitem(sys.modules, "cv2", fake)
    assert sc.opencv_available() is False
    monkeypatch.setattr(sc, "source_is_landscape", lambda _s: True)
    centers, report = sc.plan_crop_centers("x.mp4", [{"start": 0, "end": 5}], mode="auto")
    assert centers == [0.5]
    assert report["fallback"] == "opencv_unavailable"
