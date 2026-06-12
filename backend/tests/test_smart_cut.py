"""Smart cut — retakes, repeated sentences, markers, stutters (engine v4.2)."""
import pytest

from app.autoedit_engine import config as engine_config
from app.autoedit_engine.build_edl import (
    build_ranges,
    drop_false_starts,
    split_stutters,
    trim_trailing_marker,
)


def _words(spec, start=0.0, word_dur=0.32, word_gap=0.08):
    """Build word dicts from a string; '|' inserts a big silence (cut)."""
    out = []
    t = start
    for token in spec.split():
        if token == "|":
            t += engine_config.GAP_CUT + 0.2
            continue
        out.append({"word": token, "start": round(t, 3), "end": round(t + word_dur, 3)})
        t += word_dur + word_gap
    return out


def _vu(spec: str, duration=None):
    words = _words(spec)
    return {
        "duration": duration or (words[-1]["end"] + 1.0 if words else 0.0),
        "segments": [{
            "start": words[0]["start"] if words else 0.0,
            "end": words[-1]["end"] if words else 0.0,
            "text": " ".join(w["word"] for w in words),
            "words": words,
        }],
    }


def _kept_text(vu, ranges):
    kept = []
    for w in vu["segments"][0]["words"]:
        mid = (w["start"] + w["end"]) / 2
        if any(r["start"] <= mid <= r["end"] for r in ranges):
            kept.append(w["word"])
    return " ".join(kept)


# --------------------------------------------------------------------------- #
# false starts & repeated sentences
# --------------------------------------------------------------------------- #
def test_false_start_dropped_keeps_last_take():
    vu = _vu("aujourd'hui je vais | aujourd'hui je vais vous montrer la méthode complète")
    ranges = build_ranges(vu)
    text = _kept_text(vu, ranges)
    assert text.count("aujourd'hui") == 1
    assert "montrer la méthode complète" in text


def test_repeated_sentence_keeps_one_take():
    vu = _vu("la stratégie marketing est essentielle | la stratégie marketing est essentielle "
             "| et maintenant la suite du contenu")
    ranges = build_ranges(vu)
    text = _kept_text(vu, ranges)
    assert text.count("stratégie") == 1
    assert "la suite du contenu" in text


def test_chained_false_starts_collapse_to_final_take():
    runs = [
        _words("je vais"),
        _words("je vais vous", start=10.0),
        _words("je vais vous montrer la méthode", start=20.0),
    ]
    kept = drop_false_starts(runs)
    assert len(kept) == 1
    assert " ".join(w["word"] for w in kept[0]).endswith("la méthode")


def test_different_sentences_are_never_dropped():
    runs = [
        _words("voici la première idée importante"),
        _words("et maintenant un point totalement différent", start=10.0),
    ]
    assert len(drop_false_starts(runs)) == 2


# --------------------------------------------------------------------------- #
# retake markers
# --------------------------------------------------------------------------- #
def test_trailing_retake_marker_is_trimmed():
    run = _words("la formule du succès est non je reprends")
    trimmed = trim_trailing_marker(run)
    text = " ".join(w["word"] for w in trimmed)
    assert "reprends" not in text
    assert text.startswith("la formule")


def test_marker_in_middle_is_left_alone():
    run = _words("je reprends souvent les bonnes habitudes chaque matin au travail")
    assert trim_trailing_marker(run) == run


# --------------------------------------------------------------------------- #
# stutters
# --------------------------------------------------------------------------- #
def test_bigram_stutter_removed_word_safely():
    # "il faut il faut" -> the first occurrence goes away (span 0.8 s >= min)
    run = _words("donc il faut il faut travailler dur")
    pieces = split_stutters(run)
    kept = [w["word"] for piece, _, _ in pieces for w in piece]
    assert kept == ["donc", "il", "faut", "travailler", "dur"]
    # the cut boundaries are flagged tight (micro pads)
    assert pieces[0][2] is True      # first piece ends at a micro cut
    assert pieces[1][1] is True      # second piece starts at a micro cut


def test_tiny_stutter_left_alone():
    # "je je" spans ~0.4 s < STUTTER_MIN_SPAN: cutting it would be eaten by pads
    run = _words("je je travaille", word_dur=0.18, word_gap=0.04)
    pieces = split_stutters(run)
    kept = [w["word"] for piece, _, _ in pieces for w in piece]
    assert kept == ["je", "je", "travaille"]


def test_stutter_cut_ranges_never_overlap_and_stay_on_word_edges():
    vu = _vu("donc il faut il faut travailler dur pour réussir vraiment")
    ranges = build_ranges(vu)
    for a, b in zip(ranges, ranges[1:]):
        assert a["end"] <= b["start"]
    text = _kept_text(vu, ranges)
    assert text.count("il faut") == 1
    # no word is chopped: every kept word lies fully inside a range
    for w in vu["segments"][0]["words"]:
        mid = (w["start"] + w["end"]) / 2
        inside = [r for r in ranges if r["start"] <= mid <= r["end"]]
        if inside:
            assert inside[0]["start"] <= w["start"] and w["end"] <= inside[0]["end"]


def test_remove_retakes_flag_can_disable_smart_cut(monkeypatch):
    monkeypatch.setattr(engine_config, "REMOVE_RETAKES", False)
    vu = _vu("aujourd'hui je vais | aujourd'hui je vais vous montrer la méthode complète")
    text = _kept_text(vu, build_ranges(vu))
    assert text.count("aujourd'hui") == 2
