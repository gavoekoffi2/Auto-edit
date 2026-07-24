"""The montage-type catalog: new default + legacy modes preserved."""
from app.api.v1 import modes
from app.config import VALID_MODES, VALID_VISUAL_MODES


def test_default_mode_is_signature_3d():
    """Décision produit: le défaut est le style vedette AVEC images IA 3D —
    jamais le mode économique sans images, ni un style manuscrit."""
    assert modes.DEFAULT_MODE == "signature_3d"


def test_default_mode_is_first_and_flagged():
    first = modes.MODE_DEFINITIONS[0]
    assert first["id"] == "signature_3d"
    assert first.get("default") is True
    # Le défaut tente les images IA mais ne bloque jamais (fallback propre).
    assert first["defaults"].get("visual_mode") == "auto_fallback"
    assert first["defaults"].get("ai_broll") is True
    # Le défaut n'utilise JAMAIS les sous-titres manuscrits.
    assert first["defaults"].get("subtitle_template") != "handwritten_note"


def test_credit_saver_mode_still_selectable_but_not_default():
    by_id = {m["id"]: m for m in modes.MODE_DEFINITIONS}
    eco = by_id["credit_saver_creator_edit"]
    assert eco.get("default") is not True
    assert eco["defaults"].get("visual_mode") == "credit_saver"
    assert eco["defaults"].get("ai_broll") is False


def test_new_viral_styles_are_listed():
    by_id = {m["id"]: m for m in modes.MODE_DEFINITIONS}
    for style, tpl in (("beast_impact", "beast_impact"),
                       ("mint_wave", "mint_wave"),
                       ("bangers_comic", "bangers_fun")):
        assert style in by_id, style
        d = by_id[style]["defaults"]
        assert d.get("subtitle_template") == tpl
        assert d.get("visual_mode") == "auto_fallback"


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
