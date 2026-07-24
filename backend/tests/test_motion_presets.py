"""Tests for the motion-design preset families + stable seed."""
from collections import Counter

from app.autoedit_engine import motion_presets as mp


def test_named_families_exist():
    names = {p.name for p in mp.PRESETS}
    assert names == {
        "clean_fintech", "neon_social", "african_premium",
        "minimal_creator", "kinetic_education",
        # Nouvelles familles en rotation (variété visuelle entre montages)
        "sunset_vibes", "electric_lime",
        # Familles des styles Captions AI (opt-in, hors rotation aléatoire)
        "editorial_paper", "sketch_notes",
    }


def test_style_only_presets_are_reachable_by_name_only():
    # Fond clair / encre sombre: jamais tirés au hasard, mais disponibles
    # quand un style de montage les demande explicitement.
    assert mp.STYLE_ONLY_PRESETS == {"editorial_paper", "sketch_notes"}
    assert mp.preset_for("sketch_notes").name == "sketch_notes"
    assert mp.preset_for("sketch_notes").ink == (20, 20, 20, 255)
    assert mp.preset_for("editorial_paper").name == "editorial_paper"


def test_style_seed_is_reproducible_and_varies():
    assert mp.style_seed("video-123") == mp.style_seed("video-123")
    assert mp.style_seed("video-123") != mp.style_seed("video-999")
    # First non-empty part wins (videoId | jobId | transcript).
    assert mp.style_seed("", None, "transcript text") == mp.style_seed(None, "transcript text")


def test_choose_preset_is_deterministic():
    a = mp.choose_preset("job-abc")
    b = mp.choose_preset("job-abc")
    assert a.name == b.name


def test_choose_preset_spreads_across_rotation_families():
    counts = Counter(mp.choose_preset(f"job-{i}").name for i in range(300))
    # Every ROTATION family should be reachable -> videos don't all look
    # identical; the light style-only families never enter the random pick.
    expected = {p.name for p in mp.PRESETS} - mp.STYLE_ONLY_PRESETS
    assert set(counts) == expected
    assert min(counts.values()) > 0


def test_palette_shape_matches_engine_tuple():
    pal = mp.palette_for_preset("neon_social")
    assert len(pal) == 4
    bg_top, bg_bottom, accent, gold = pal
    assert len(bg_top) == 3 and len(bg_bottom) == 3
    assert len(accent) == 4 and len(gold) == 4


def test_unknown_preset_falls_back_to_default():
    assert mp.preset_for("does_not_exist").name == mp.DEFAULT_PRESET
    assert mp.preset_for(None).name == mp.DEFAULT_PRESET


def test_select_palette_applies_named_preset():
    from app.autoedit_engine import motion_design as md
    name = md.select_palette("anything", preset="african_premium")
    assert name == "african_premium"
    assert md.ACCENT == mp.preset_for("african_premium").accent
