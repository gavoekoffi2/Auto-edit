"""Professional SFX design (v4.2): new sounds, variation, per-visual pools."""
import json

import numpy as np
import pytest

from app.autoedit_engine import config as engine_config
from app.autoedit_engine import sfx_lib
from app.autoedit_engine.mix_sfx import _build_filter


def test_every_named_sfx_has_a_generator():
    for name in engine_config.SFX_NAMES:
        assert name in sfx_lib.GENERATORS, name
        assert name in engine_config.SFX_GAINS, name


def test_new_professional_sounds_render_non_silent():
    for name in ("shutter_burst", "camera_focus", "pen_scribble", "tape_stop",
                 "bubble", "snap", "cinematic_hit", "data_tick"):
        samples = sfx_lib.GENERATORS[name]()
        assert len(samples) > 1000, name
        assert float(np.max(np.abs(samples))) > 0.05, f"{name} is silent"


def test_broll_pool_is_camera_centric_and_never_repeats_consecutively():
    pool = engine_config.BROLL_SFX_POOL
    camera = {"camera_flash", "shutter", "shutter_burst", "camera_focus"}
    assert sum(1 for s in pool if s in camera) >= len(pool) // 2
    for a, b in zip(pool, pool[1:]):
        assert a != b


def test_pools_are_distinct_per_visual_type():
    # Motion-design accents and B-roll photo sounds must not be the same set —
    # that sameness is exactly what made the previous mix feel static.
    assert set(engine_config.MOTION_ELEMENT_SFX) != set(engine_config.BROLL_SFX_POOL)
    assert set(engine_config.GRAPHIC_SFX) != set(engine_config.BROLL_SFX_POOL)
    for name in engine_config.POPUP_SFX_POOL + [engine_config.MOTION_DRAW_SFX]:
        assert name in engine_config.SFX_NAMES


def test_mix_filter_varies_pitch_and_gain_on_repeats():
    cues = [
        {"sfx": "camera_flash", "t": 1.0},
        {"sfx": "camera_flash", "t": 4.0},
        {"sfx": "camera_flash", "t": 8.0},
    ]
    index = {"camera_flash": "sfx/camera_flash.wav"}
    filt, inputs = _build_filter(cues, index)
    assert len(inputs) == 3
    # first occurrence at designed pitch, later ones humanised via asetrate
    chains = [p for p in filt.split(";") if p.startswith("[")][:3]
    assert "asetrate" not in chains[0]
    assert "asetrate" in chains[1]
    assert "asetrate" in chains[2]
    # gains differ between occurrences
    import re
    gains = re.findall(r"volume=([0-9.]+)", filt)
    assert len(set(gains[:3])) >= 2


def test_build_library_writes_all_sounds(tmp_path):
    paths = sfx_lib.build_library(str(tmp_path))
    assert set(paths) == set(engine_config.SFX_NAMES)
    for p in paths.values():
        assert (tmp_path / p.split("/")[-1]).stat().st_size > 1000
