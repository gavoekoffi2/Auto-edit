from app.processing.broll_planner import (
    BrollPlanner,
    BrollPlannerConfig,
    STYLE_SUFFIXES,
    _scene_from_text,
)
from app.autoedit_engine.content import derive_broll_ideas
from app.autoedit_engine import config as engine_config

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
        assert "Must directly illustrate this exact spoken excerpt" in c.prompt
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


def test_engine_broll_ideas_default_to_african_and_match_spoken_excerpt():
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
    ideas = derive_broll_ideas(vu, demographic="african", graphic_specs=graphics)
    assert ideas
    # Default promise: African imagery ONLY (strengthened wording).
    assert all("Black African" in idea["prompt"] for idea in ideas)
    assert all("Must directly illustrate this exact spoken excerpt" in idea["prompt"] for idea in ideas)
    assert any("mobile-money payment" in idea["prompt"] for idea in ideas)


def test_engine_broll_ideas_are_more_dense_for_shorts_even_with_graphics():
    def make_vu(duration: float, count: int):
        return {
            "duration": duration,
            "segments": [
                {
                    "start": i * (duration / count),
                    "end": (i + 1) * (duration / count),
                    "text": "marketing client paiement mobile money boutique en ligne",
                    "words": [
                        {
                            "word": w,
                            "start": i * (duration / count) + j * 0.45,
                            "end": i * (duration / count) + (j + 1) * 0.45,
                        }
                        for j, w in enumerate("marketing client paiement mobile money boutique en ligne".split())
                    ],
                }
                for i in range(count)
            ],
        }

    graphics = [{"source_start": 0.0, "source_end": 30.0}]
    short_ideas = derive_broll_ideas(make_vu(60.0, 20), demographic="african", graphic_specs=graphics)
    long_ideas = derive_broll_ideas(make_vu(180.0, 60), demographic="african", graphic_specs=graphics)

    # Cost-aware cadence: shorts stay denser than long videos, but the
    # motion-design scenes now carry part of the rhythm (API savings).
    assert len(short_ideas) >= 6
    assert len(short_ideas) <= engine_config.MAX_BROLL_IMAGES
    assert len(long_ideas) <= engine_config.MAX_BROLL_IMAGES
    assert len(short_ideas) / 60.0 > len(long_ideas) / 180.0


def test_engine_broll_keeps_image_budget_with_dense_motion():
    segments = []
    for i in range(40):
        s = i * 4.5
        text = "marketing client paiement mobile money boutique en ligne stratégie croissance livraison"
        segments.append({
            "start": s,
            "end": s + 4.0,
            "text": text,
            "words": [
                {"word": w, "start": s + j * 0.38, "end": s + (j + 1) * 0.38}
                for j, w in enumerate(text.split())
            ],
        })
    vu = {"duration": 180.0, "segments": segments}
    scenes = derive_broll_ideas.__globals__["derive_motion_scenes"](vu)
    ideas = derive_broll_ideas(
        vu,
        demographic="african",
        avoid_spans=derive_broll_ideas.__globals__["motion_scene_spans"](scenes),
    )
    assert len(scenes) > 8
    assert len(ideas) >= 6                       # motion never starves B-roll
    assert len(ideas) <= engine_config.MAX_BROLL_IMAGES


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
    assert "caucasian / white" in ideas[0]["prompt"]
