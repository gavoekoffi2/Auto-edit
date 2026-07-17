"""Key-moment accent wiring in video_dynamics (no ffmpeg needed for this).

Le flash blanc plein écran a été RETIRÉ (demande produit): un moment clé ne
reçoit plus qu'un punch-zoom synchronisé — la seule lumière du montage est le
light-leak réel, composité plein cadre 9:16 avec son propre son.
"""
from app.autoedit_engine import video_dynamics as vd
from app.autoedit_engine import config


RANGES = [{"start": 0.0, "end": 5.0}, {"start": 6.0, "end": 11.0}]


def test_no_white_flash_filter_even_with_key_moments():
    # The blinding eq-brightness pulse must never come back, with or without
    # key moments — only the (separate) warm eq pulse of motion transitions
    # may add an eq filter, and that is driven by eq_light_times only.
    assert not hasattr(vd, "build_flash_filter")
    vf = vd.build_vf(RANGES)
    assert "eq=brightness" not in vf
    vf_key = vd.build_vf(RANGES, flash_times=[1.0, 9.0])
    assert "eq=brightness" not in vf_key
    assert "zoompan" in vf_key


def test_motion_transition_warm_pulse_still_applies():
    vf = vd.build_vf(RANGES, eq_light_times=[2.0])
    assert "eq=brightness" in vf          # the SOFT warm pulse, transitions only
    assert str(config.LIGHT_OVERLAY_BRIGHTNESS) in vf


def test_zoom_expression_gets_synced_punch_at_key_moments():
    base = vd.build_zoom_expr(RANGES)
    punched = vd.build_zoom_expr(RANGES, flash_times=[2.0])
    # The key moment adds an extra gaussian punch term not in the base curve.
    assert str(config.FLASH_PUNCH_AMP) in punched
    assert punched != base


def test_light_leak_overlay_clip_is_full_frame_vertical():
    # The 16:9 asset must be cover-scaled to the full 1080x1920 frame BEFORE
    # the lumakey, so the light sweep covers the whole vertical video.
    import inspect
    src = inspect.getsource(vd.prepare_light_leak_overlay_clip)
    assert "VERTICAL_COVER" in src
    assert config.VERTICAL_COVER.startswith("scale=1080:1920")
