"""Camera-flash filter wiring in video_dynamics (no ffmpeg needed for this)."""
from app.autoedit_engine import video_dynamics as vd
from app.autoedit_engine import config


RANGES = [{"start": 0.0, "end": 5.0}, {"start": 6.0, "end": 11.0}]


def test_no_flash_keeps_filter_chain_unchanged():
    assert vd.build_flash_filter([]) == ""
    assert vd.build_flash_filter(None) == ""
    vf = vd.build_vf(RANGES)
    assert "eq=brightness" not in vf  # no flash filter when no key moments


def test_flash_filter_is_time_based_pulse_train():
    flt = vd.build_flash_filter([1.0, 4.5])
    assert flt.startswith("eq=brightness=")
    assert "eval=frame" in flt          # recomputed every frame (animated pulse)
    assert "t-1.000" in flt and "t-4.500" in flt
    assert str(config.FLASH_BRIGHTNESS) in flt


def test_build_vf_appends_flash_filter_with_key_moments():
    vf = vd.build_vf(RANGES, flash_times=[1.0, 9.0])
    assert "zoompan" in vf
    assert vf.count("eq=brightness") == 1


def test_zoom_expression_gets_synced_punch_at_flashes():
    base = vd.build_zoom_expr(RANGES)
    punched = vd.build_zoom_expr(RANGES, flash_times=[2.0])
    # The flash adds an extra gaussian punch term not present in the base curve.
    assert str(config.FLASH_PUNCH_AMP) in punched
    assert punched != base
