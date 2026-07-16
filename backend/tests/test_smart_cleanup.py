"""Tests du nettoyage IA du transcript (répétitions / hésitations / faux départs)."""
import json

from app.autoedit_engine import smart_cleanup as sc


def _vu(repeat: int = 5):
    """Transcript synthétique assez LONG pour dépasser les zones protégées
    (head/tail 4 s) et donner un budget de retrait non nul."""
    base = ["bonjour", "à", "tous", "euh", "euh", "donc", "je", "voulais",
            "dire", "je", "voulais", "vous", "dire", "merci", "beaucoup"]
    words = []
    t = 0.0
    for w in base * repeat:
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
        {"start": 4.5, "end": 5.2, "reason": "hesitation"},       # ok (hors zones protégées)
        {"start": 6.0, "end": 6.1},                               # trop court
        {"start": "x", "end": 6.0},                               # invalide
        "junk",                                                   # invalide
        {"start": 0.0, "end": 999.0, "reason": "incoherent"},     # > budget du niveau
    ]
    spans = sc._validate_spans(raw, vu, level="light")
    assert spans == [{"start": 4.5, "end": 5.2, "reason": "hesitation"}]


def test_validate_spans_protects_hook_and_cta():
    """Jamais de coupe IA dans le hook d'ouverture ni la conclusion."""
    vu = _vu()
    speech_end = vu["segments"][-1]["end"]
    raw = [
        {"start": 0.0, "end": 2.0, "reason": "hesitation"},               # hook
        {"start": speech_end - 2.0, "end": speech_end, "reason": "x"},    # CTA
    ]
    assert sc._validate_spans(raw, vu, level="aggressive") == []


def test_cleanup_levels_budget():
    """off = rien; le budget croît avec le niveau."""
    assert sc.CLEANUP_LEVELS["off"] == 0.0
    assert (sc.CLEANUP_LEVELS["light"] < sc.CLEANUP_LEVELS["balanced"]
            < sc.CLEANUP_LEVELS["aggressive"])
    assert sc.resolve_level(None) in sc.CLEANUP_LEVELS
    assert sc.resolve_level("nonsense") == "light"   # inconnu => prudent
    vu = _vu()
    raw = [{"start": 4.5, "end": 5.2, "reason": "hesitation"}]
    assert sc._validate_spans(raw, vu, level="off") == []


def test_apply_spans_drops_words_and_rebuilds_text():
    vu = _vu(repeat=1)
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
        lambda vu, api_key=None, model=None, **kw: [
            {"start": 4.5, "end": 5.2, "reason": "hesitation"}],
    )
    path, report = sc.clean_vu(str(vu_path), str(out))
    assert path == str(out)
    assert report["llm_cleanup_spans"] == 1
    assert report["llm_cleanup_removed_s"] > 0
    # Traçabilité: les passages retirés sont listés dans le report du job.
    assert report["llm_cleanup_removed_spans"][0]["reason"] == "hesitation"
    assert report["llm_cleanup_level"] in sc.CLEANUP_LEVELS
    cleaned = json.loads(out.read_text(encoding="utf-8"))
    # La répétition "je voulais" à 4.5-5.2 s a été retirée (un "je" de moins).
    before = _vu()["segments"][0]["text"].split().count("je")
    assert cleaned["segments"][0]["text"].split().count("je") == before - 1
