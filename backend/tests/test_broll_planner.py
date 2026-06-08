from app.processing.broll_planner import (
    BrollPlanner,
    BrollPlannerConfig,
    STYLE_SUFFIXES,
    _scene_from_text,
)
from app.autoedit_engine.content import derive_broll_ideas

from app.processing.types import (
    Cut,
    EditDecisionList,
    Transcript,
    TranscriptSegment,
    Word,
)


def _seg(start, end, text, words):
    return TranscriptSegment(
        start=start,
        end=end,
        text=text,
        words=[Word(text=t, start=s, end=e) for (t, s, e) in words],
    )


def test_scene_rules_match_african_topics():
    assert "mobile money" in _scene_from_text("on parle de mobile money").lower()
    assert "e-commerce" in _scene_from_text("lance ton e-commerce") or "shop" in _scene_from_text("lance ton e-commerce").lower()
    assert "real estate" in _scene_from_text("immobilier à Dakar").lower() or "African" in _scene_from_text("immobilier à Dakar")
    assert "African" in _scene_from_text("aucun mot clé spécifique")  # fallback africain


def test_planner_produces_prompts_with_african_style():
    transcript = Transcript(
        language="fr",
        text="",
        segments=[
            _seg(0.0, 4.0, "je vais te parler de mobile money", [
                ("je", 0.0, 0.2), ("vais", 0.2, 0.5), ("te", 0.5, 0.7),
                ("parler", 0.7, 1.2), ("de", 1.2, 1.4),
                ("mobile", 1.4, 1.9), ("money", 1.9, 2.5),
            ]),
            _seg(4.0, 9.0, "et de e-commerce africain", [
                ("et", 4.0, 4.2), ("de", 4.2, 4.4),
                ("e-commerce", 4.4, 5.5), ("africain", 5.5, 6.5),
            ]),
        ],
    )
    edl = EditDecisionList(
        source_path="/tmp/x.mp4",
        cuts=[Cut(0.0, 9.0, keep=True, reason="keep")],
        total_kept_duration=9.0,
    )
    cues = BrollPlanner(BrollPlannerConfig(min_segment_duration=2.0, max_cues=5)).plan(transcript, edl)
    assert len(cues) >= 1
    style_suffix = STYLE_SUFFIXES["african_business_premium"]
    for c in cues:
        assert style_suffix.split(",")[0] in c.prompt  # début du style appliqué
        assert c.aspect_ratio in ("9:16", "16:9", "1:1", "4:5")
        assert c.style == "african_business_premium"


def test_planner_respects_max_cues():
    words = []
    segments = []
    for i in range(20):
        s = i * 3.0
        e = s + 3.0
        ws = [(f"mot{i}_{j}", s + j * 0.3, s + (j + 1) * 0.3) for j in range(8)]
        segments.append(_seg(s, e, " ".join(w[0] for w in ws), ws))
    transcript = Transcript(language="fr", text="", segments=segments)
    edl = EditDecisionList(
        source_path="/tmp/x.mp4",
        cuts=[Cut(0.0, 60.0, keep=True, reason="keep")],
        total_kept_duration=60.0,
    )
    cues = BrollPlanner(BrollPlannerConfig(min_segment_duration=2.0, max_cues=5)).plan(transcript, edl)
    assert len(cues) <= 5


def test_engine_broll_ideas_default_to_african_and_reduce_when_graphics_exist():
    vu = {
        "duration": 36.0,
        "segments": [
            {
                "start": i * 3.0,
                "end": (i + 1) * 3.0,
                "text": "business client mobile money strategie croissance",
                "words": [
                    {"word": w, "start": i * 3.0 + j * 0.4, "end": i * 3.0 + (j + 1) * 0.4}
                    for j, w in enumerate("business client mobile money strategie croissance".split())
                ],
            }
            for i in range(12)
        ],
    }
    graphics = [{"source_start": 0.0, "source_end": 8.0}, {"source_start": 18.0, "source_end": 26.0}]
    plain = derive_broll_ideas(vu)
    mixed = derive_broll_ideas(vu, demographic="african", graphic_specs=graphics)
    assert len(mixed) < len(plain)
    assert mixed
    assert all("modern African people" in idea["prompt"] for idea in mixed)


def test_engine_broll_ideas_can_target_caucasian_casting():
    vu = {
        "duration": 10.0,
        "segments": [{
            "start": 0.0, "end": 10.0, "text": "marketing finance client",
            "words": [
                {"word": "marketing", "start": 0.0, "end": 0.5},
                {"word": "finance", "start": 1.0, "end": 1.5},
                {"word": "client", "start": 2.0, "end": 2.5},
            ],
        }],
    }
    ideas = derive_broll_ideas(vu, n=1, demographic="caucasian")
    assert "caucasian / white people" in ideas[0]["prompt"]
