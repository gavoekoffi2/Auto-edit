"""The montage-type catalog: new default + legacy modes preserved."""
from app.api.v1 import modes
from app.config import VALID_MODES, VALID_VISUAL_MODES


def test_default_mode_is_credit_saver_creator_edit():
    assert modes.DEFAULT_MODE == "credit_saver_creator_edit"


def test_default_mode_is_first_and_flagged():
    first = modes.MODE_DEFINITIONS[0]
    assert first["id"] == "credit_saver_creator_edit"
    assert first.get("default") is True
    assert first["defaults"].get("visual_mode") == "credit_saver"
    # MVP default must NOT require AI images.
    assert first["defaults"].get("ai_broll") is False


def test_legacy_ai_broll_mode_is_preserved_and_selectable():
    by_id = {m["id"]: m for m in modes.MODE_DEFINITIONS}
    assert "business_premium_african" in by_id
    ai = by_id["business_premium_african"]
    assert ai["defaults"].get("visual_mode") == "ai_broll"
    assert ai["defaults"].get("ai_broll") is True


def test_auto_fallback_option_exists():
    visual_modes = {m["defaults"].get("visual_mode") for m in modes.MODE_DEFINITIONS}
    assert "auto_fallback" in visual_modes
    assert "credit_saver" in visual_modes
    assert "ai_broll" in visual_modes


def test_exactly_one_default_mode():
    flagged = [m for m in modes.MODE_DEFINITIONS if m.get("default")]
    assert len(flagged) == 1


def test_all_v2_mode_ids_are_valid():
    for m in modes.MODE_DEFINITIONS:
        if m["pipeline"] == "v2":
            assert m["id"] in VALID_MODES, m["id"]


def test_all_visual_modes_are_valid():
    for m in modes.MODE_DEFINITIONS:
        vm = m["defaults"].get("visual_mode")
        if vm is not None:
            assert vm in VALID_VISUAL_MODES, vm


def test_legacy_v1_modes_still_listed():
    ids = {m["id"] for m in modes.MODE_DEFINITIONS}
    # Old pipeline-v1 modes must remain available (not removed/renamed).
    assert {"tiktok", "youtube", "podcast"} <= ids
