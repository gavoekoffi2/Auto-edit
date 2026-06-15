import json

from app.autoedit_engine import keyword_popup


def _seg(start, end, text):
    toks = text.split()
    step = (end - start) / max(1, len(toks))
    return {
        "start": start,
        "end": end,
        "text": text,
        "words": [
            {"word": tok, "start": round(start + i * step, 3), "end": round(start + (i + 1) * step, 3)}
            for i, tok in enumerate(toks)
        ],
    }


def test_popup_keywords_reject_weak_words_and_clean_apostrophes():
    assert not keyword_popup._is_strong_keyword("dire")
    assert not keyword_popup._is_strong_keyword("tellement")
    assert keyword_popup._is_strong_keyword("l'intelligence")
    assert keyword_popup._display_keyword("l'intelligence") == "intelligence"


def test_build_popups_uses_only_professional_keywords(tmp_path, monkeypatch):
    vu = {
        "duration": 34.0,
        "segments": [
            _seg(0, 8, "dire tellement l'intelligence artificielle modèle gouvernement"),
            _seg(9, 17, "dire tellement l'intelligence artificielle modèle gouvernement"),
            _seg(18, 26, "dire tellement l'intelligence artificielle modèle gouvernement"),
            _seg(27, 34, "dire tellement l'intelligence artificielle modèle gouvernement"),
        ],
    }
    vu_path = tmp_path / "vu.json"
    vu_path.write_text(json.dumps(vu), encoding="utf-8")
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps({
        "transcripts_vu": str(vu_path),
        "ranges": [{"start": 0, "end": 34}],
        "overlays": [],
    }), encoding="utf-8")
    (tmp_path / "sfx_cues.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr(keyword_popup, "render_popup", lambda text, out_path: str(out_path))
    result = keyword_popup.build_popups(str(edl_path), str(tmp_path))

    assert "dire" not in result["keywords"]
    assert "tellement" not in result["keywords"]
    assert "l'intelligence" in result["keywords"]
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    assert all("dire" not in o["id"] and "tellement" not in o["id"] for o in edl["overlays"])
