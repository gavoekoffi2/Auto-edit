"""Tests for the keyMomentPlanner (credit-saver creator edit).

Pure-Python: no ffmpeg, no API, no credits — proves the heuristics, the
minimum flash spacing and the premium cadence.
"""
import pytest

from app.autoedit_engine import key_moments as km


def _seg(start: float, end: float, text: str) -> dict:
    toks = text.split()
    step = (end - start) / max(1, len(toks))
    words = [
        {"word": tok, "start": round(start + i * step, 3),
         "end": round(start + (i + 1) * step, 3)}
        for i, tok in enumerate(toks)
    ]
    return {"start": start, "end": end, "text": text, "words": words}


@pytest.fixture()
def rich_vu() -> dict:
    return {
        "language": "fr",
        "duration": 78.0,
        "segments": [
            _seg(0.0, 6.0, "bonjour à tous aujourd hui je vais vous montrer comment lancer votre business"),
            _seg(7.0, 15.0, "premièrement vous créez votre boutique ensuite vous ajoutez vos produits enfin le paiement mobile money"),
            _seg(16.5, 24.0, "retenez ce chiffre important 80% des clients abandonnent leur panier avant de payer"),
            _seg(25.5, 33.0, "le secret c est la stratégie marketing sur whatsapp et tiktok pour vos clients"),
            _seg(34.5, 42.0, "avec cette méthode simple vous allez doubler vos ventes et faire grandir votre business"),
            _seg(43.5, 52.0, "beaucoup de gens font l erreur de vendre sans connaître leurs clients et leur marché"),
            _seg(53.5, 62.0, "la formation complète vous montre chaque étape pour réussir votre boutique"),
            _seg(63.5, 72.0, "alors abonnez vous maintenant cliquez sur le lien et commencez à vendre"),
        ],
    }


def test_hook_is_first_strong_cue(rich_vu):
    cues = km.plan_key_moments(rich_vu)
    assert cues, "should produce cues"
    hooks = [c for c in cues if c.reason == "hook"]
    assert hooks, "the first beat must be a hook cue"
    assert hooks[0].start == pytest.approx(0.0, abs=0.5)
    assert hooks[0].intensity == "high"
    assert "flash" in hooks[0].effects and "shutter_sfx" in hooks[0].effects


def test_number_percentage_detected(rich_vu):
    cues = km.plan_key_moments(rich_vu)
    numbers = [c for c in cues if c.reason == "number"]
    assert numbers, "the 80% figure must produce a number cue"
    assert any(c.intensity == "high" for c in numbers)


def test_cta_detected_near_end(rich_vu):
    cues = km.plan_key_moments(rich_vu)
    ctas = [c for c in cues if c.reason == "cta"]
    assert ctas, "abonnez/cliquez/lien near the end must produce a CTA cue"
    assert ctas[0].start > rich_vu["duration"] * 0.6
    assert ctas[0].intensity == "high"


def test_reasons_are_varied(rich_vu):
    cues = km.plan_key_moments(rich_vu)
    reasons = {c.reason for c in cues}
    # hook + at least two other families => not a monotonous single-trigger edit
    assert "hook" in reasons
    assert len(reasons) >= 3


def test_minimum_flash_spacing(rich_vu):
    cues = km.plan_key_moments(rich_vu)
    flashes = km.flash_times(cues)
    gaps = [b - a for a, b in zip(flashes, flashes[1:])]
    assert all(g >= km.FLASH_MIN_GAP - 1e-6 for g in gaps), (
        f"two flashes closer than {km.FLASH_MIN_GAP}s: {gaps}")


def test_custom_min_gap_is_honoured(rich_vu):
    cues = km.plan_key_moments(rich_vu, min_gap=6.0)
    flashes = km.flash_times(cues)
    gaps = [b - a for a, b in zip(flashes, flashes[1:])]
    assert all(g >= 6.0 - 1e-6 for g in gaps)


@pytest.mark.parametrize("duration,lo,hi", [
    (20.0, 3, 6),
    (45.0, 5, 10),
    (120.0, 10, 22),
])
def test_cadence_bounds(duration, lo, hi):
    assert km.target_cue_count(duration) >= lo
    assert km.target_cue_count(duration) <= hi


def test_cadence_caps_long_video(rich_vu):
    # A long video must stay premium: never an effect every second.
    long_vu = {"language": "fr", "duration": 170.0, "segments": []}
    base = 0.0
    segs = []
    # 170s of dense speech with numbers + emotional words everywhere.
    for i in range(28):
        segs.append(_seg(base, base + 6.0,
                         f"attention chiffre {i} important secret resultat {i}0% maintenant gratuit"))
        base += 6.0
    long_vu["segments"] = segs
    cues = km.plan_key_moments(long_vu)
    assert len(cues) <= 22, f"too many cues for a premium long edit: {len(cues)}"
    flashes = km.flash_times(cues)
    gaps = [b - a for a, b in zip(flashes, flashes[1:])]
    assert all(g >= km.FLASH_MIN_GAP - 1e-6 for g in gaps)


def test_empty_transcript_is_safe():
    assert km.plan_key_moments({"segments": [], "duration": 0.0}) == []
    assert km.plan_key_moments({}) == []


def test_cue_serialisation_shape(rich_vu):
    cue = km.plan_key_moments(rich_vu)[0]
    d = cue.to_dict()
    assert set(d) == {"start", "end", "intensity", "reason", "textExcerpt", "effects"}
    assert isinstance(d["effects"], list)
