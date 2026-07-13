"""Tests du nettoyage IA du transcript (répétitions / hésitations / faux départs)."""
import json

from app.autoedit_engine import smart_cleanup as sc


def _vu():
    words = []
    t = 0.0
    for w in ["bonjour", "à", "tous", "euh", "euh", "donc", "je", "voulais",
              "dire", "je", "voulais", "vous", "dire", "merci", "beaucoup"]:
        words.append({"word": w, "start": round(t, 2), "end": round(t + 0.4, 2)})
        t += 0.5
    return {
        "language": "fr",
        "duration": round(t, 2),
        "segments": [{
            "text": " ".join(w["word"] for w in words),
            "start": words[0]["start"], "end": words[-1]["end"],
            "words": words,
        }],
    }


def test_validate_spans_filters_garbage_and_caps_removal():
    vu = _vu()
    raw = [
        {"start": 1.5, "end": 2.5, "reason": "hesitation"},      # ok
        {"start": 3.0, "end": 3.1},                               # trop court
        {"start": "x", "end": 4.0},                               # invalide
        "junk",                                                   # invalide
        {"start": 0.0, "end": 999.0, "reason": "incoherent"},     # > budget 30%
    ]
    spans = sc._validate_spans(raw, vu)
    assert spans == [{"start": 1.5, "end": 2.5, "reason": "hesitation"}]


def test_apply_spans_drops_words_and_rebuilds_text():
    vu = _vu()
    spans = [{"start": 1.5, "end": 2.5, "reason": "hesitation"}]  # les 2 "euh"
    cleaned, removed = sc.apply_spans(vu, spans)
    text = cleaned["segments"][0]["text"]
    assert "euh" not in text
    assert removed > 0
    assert cleaned["duration"] == vu["duration"]  # temps SOURCE inchangé


def test_apply_spans_noop_without_spans():
    vu = _vu()
    cleaned, removed = sc.apply_spans(vu, [])
    assert cleaned is vu and removed == 0.0


def test_clean_vu_returns_original_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    vu_path = tmp_path / "vid_vu.json"
    vu_path.write_text(json.dumps(_vu()), encoding="utf-8")
    out = tmp_path / "vid_vu_clean.json"
    path, report = sc.clean_vu(str(vu_path), str(out))
    assert path == str(vu_path)          # pas de clé => transcript inchangé
    assert report["llm_cleanup_spans"] == 0
    assert not out.exists()


def test_clean_vu_writes_cleaned_transcript(tmp_path, monkeypatch):
    vu_path = tmp_path / "vid_vu.json"
    vu_path.write_text(json.dumps(_vu()), encoding="utf-8")
    out = tmp_path / "vid_vu_clean.json"
    monkeypatch.setattr(
        sc, "llm_cleanup_spans",
        lambda vu, api_key=None, model=None: [
            {"start": 1.5, "end": 2.5, "reason": "hesitation"}],
    )
    path, report = sc.clean_vu(str(vu_path), str(out))
    assert path == str(out)
    assert report["llm_cleanup_spans"] == 1
    assert report["llm_cleanup_removed_s"] > 0
    cleaned = json.loads(out.read_text(encoding="utf-8"))
    assert "euh" not in cleaned["segments"][0]["text"]
