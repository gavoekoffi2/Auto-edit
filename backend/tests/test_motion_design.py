"""Tests for the illustrated motion-design system (engine v4.1).

Pure-Python by default (scene derivation, icon mapping, stroke math, event
timelines). The actual ProRes render smoke test only runs when ffmpeg is
available on the machine.
"""
import json
import shutil

import pytest

from app.autoedit_engine import config as engine_config
from app.autoedit_engine import content
from app.autoedit_engine import motion_design


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
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
    """A 78 s talking-head transcript with enumerations, numbers and emphasis."""
    return {
        "language": "fr",
        "duration": 78.0,
        "segments": [
            _seg(0.0, 6.0, "bonjour à tous aujourd'hui je vais vous montrer comment lancer votre business en ligne"),
            _seg(7.0, 15.0, "premièrement vous créez votre boutique, ensuite vous ajoutez vos produits, enfin vous configurez le paiement mobile money"),
            _seg(16.5, 24.0, "retenez ce chiffre important 80% des clients abandonnent leur panier avant de payer"),
            _seg(25.5, 33.0, "le secret c'est la stratégie marketing sur whatsapp et tiktok pour toucher vos clients directement"),
            _seg(34.5, 42.0, "avec cette méthode simple vous allez doubler vos ventes et faire grandir votre business rapidement"),
            _seg(43.5, 52.0, "beaucoup de gens font l'erreur de vendre sans connaître leurs clients et leur marché"),
            _seg(53.5, 62.0, "la formation complète vous montre chaque étape pour réussir votre boutique en ligne"),
            _seg(63.5, 72.0, "alors lancez-vous maintenant créez votre business et commencez à vendre vos produits"),
        ],
    }


# --------------------------------------------------------------------------- #
# scene derivation
# --------------------------------------------------------------------------- #
def test_derive_motion_scenes_picks_key_beats(rich_vu):
    scenes = content.derive_motion_scenes(rich_vu)

    assert 1 <= len(scenes) <= engine_config.MOTION_MAX_SCENES
    # chronological + spaced
    starts = [s["source_start"] for s in scenes]
    assert starts == sorted(starts)
    for a, b in zip(starts, starts[1:]):
        assert b - a >= engine_config.MOTION_MIN_SPACING
    # never the very first seconds
    assert all(s["source_start"] >= engine_config.MOTION_MIN_START for s in scenes)
    # every scene illustrates real speech
    for s in scenes:
        assert s["headline"]
        assert s["excerpt"]
        assert s["excerpt"][:25].lower() in s["prompt"].lower()
        assert s["icon"] in motion_design.ICONS
        assert s["kind"] in {"idea", "steps", "number"}


def test_derive_motion_scenes_detects_steps_and_numbers(rich_vu):
    scenes = content.derive_motion_scenes(rich_vu)
    kinds = {s["kind"] for s in scenes}
    assert "steps" in kinds or "number" in kinds

    by_kind = {s["kind"]: s for s in scenes}
    if "steps" in by_kind:
        assert len(by_kind["steps"]["steps"]) >= 2
        # duration tracks the spoken span, clamped to [floor, MAX]
        assert (engine_config.MOTION_SCENE_DUR_STEPS - 0.01
                <= by_kind["steps"]["duration"]
                <= engine_config.MOTION_SCENE_MAX_DUR + 0.01)
    if "number" in by_kind:
        assert by_kind["number"]["value"] == 80.0
        assert "%" in by_kind["number"]["raw"]


def test_motion_scenes_avoid_repeated_headlines_and_icons():
    """Same dominant word must NOT headline every scene (no CONFIANCE x6)."""
    def _seg2(s, e, t):
        toks = t.split(); step = (e - s) / max(1, len(toks))
        return {"start": s, "end": e, "text": t,
                "words": [{"word": w, "start": round(s + i * step, 3),
                           "end": round(s + (i + 1) * step, 3)} for i, w in enumerate(toks)]}
    vu = {"language": "fr", "duration": 90.0, "segments": [
        _seg2(3, 11, "la confiance est la base de toute vente en ligne réussie"),
        _seg2(13, 21, "sans confiance le client ne va jamais acheter ton produit"),
        _seg2(23, 31, "pour créer la confiance tu dois livrer rapidement tes commandes"),
        _seg2(33, 41, "la confiance se gagne avec un bon service client au téléphone"),
        _seg2(43, 51, "le paiement mobile money rassure et renforce la confiance"),
        _seg2(53, 61, "enfin la confiance fidélise et fait grandir ton chiffre"),
    ]}
    scenes = content.derive_motion_scenes(vu)
    headlines = [s["headline"] for s in scenes]
    assert len(set(headlines)) == len(headlines), f"duplicate headlines: {headlines}"
    # consecutive scenes never share the same icon
    icons = [s["icon"] for s in scenes]
    for a, b in zip(icons, icons[1:]):
        assert a != b, f"consecutive identical icon: {icons}"


def test_derive_motion_scenes_short_video_returns_empty():
    vu = {"duration": 8.0, "segments": [_seg(0.0, 8.0, "très court extrait sans grand contenu")]}
    assert content.derive_motion_scenes(vu) == []


def test_broll_ideas_avoid_motion_spans(rich_vu):
    scenes = content.derive_motion_scenes(rich_vu)
    spans = content.motion_scene_spans(scenes)
    assert spans, "expected at least one motion span"

    ideas = content.derive_broll_ideas(rich_vu, avoid_spans=spans)
    for idea in ideas:
        s, e = idea["source_start"], idea["source_end"]
        for ms, me in spans:
            assert not (s < me and e > ms), (
                f"B-roll {idea['id']} ({s}-{e}) overlaps motion span ({ms}-{me})"
            )


def test_icon_mapping_matches_concepts():
    assert content.icon_for_text("le client paie en mobile money") == "money"
    assert content.icon_for_text("notre croissance va doubler") == "growth"
    assert content.icon_for_text("envoie un message whatsapp") == "phone"
    assert content.icon_for_text("phrase neutre sans concept") == content.DEFAULT_ICON
    # every mapped icon exists in the drawing library
    for _, icon in content.ICON_RULES:
        assert icon in motion_design.ICONS


# --------------------------------------------------------------------------- #
# stroke math + event timeline
# --------------------------------------------------------------------------- #
def test_partial_strokes_progressive_reveal():
    strokes = [[(0.0, 0.0), (1.0, 0.0)], [(0.0, 1.0), (1.0, 1.0)]]  # 2 px-units
    assert motion_design._partial_strokes(strokes, 0.0) == []
    full = motion_design._partial_strokes(strokes, 1.0)
    assert full == strokes

    half = motion_design._partial_strokes(strokes, 0.5)
    assert len(half) == 1
    total = motion_design._strokes_total_len(half)
    assert abs(total - 1.0) < 1e-6


def test_scene_events_timeline():
    scene = {"kind": "steps", "duration": engine_config.MOTION_SCENE_DUR_STEPS,
             "steps": ["UN", "DEUX", "TROIS"]}
    ev = motion_design.scene_events(scene)
    assert ev["entrance"] == 0.0
    assert len(ev["elements"]) == 3
    assert ev["elements"] == sorted(ev["elements"])
    assert all(0 < t < scene["duration"] for t in ev["elements"])
    assert ev["exit"] == pytest.approx(scene["duration"] - motion_design.EXIT_FADE)

    idea = motion_design.scene_events({"kind": "idea", "duration": 4.6})
    assert idea["elements"]  # headline + arrows


def test_every_icon_has_drawable_strokes():
    for name, strokes in motion_design.ICONS.items():
        assert strokes, name
        assert motion_design._strokes_total_len(strokes) > 0.5, name
        for stroke in strokes:
            assert len(stroke) >= 2, name


# --------------------------------------------------------------------------- #
# render smoke (needs ffmpeg)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_scene_procedural_fallback(tmp_path):
    scene = {
        "id": "md_test", "kind": "idea", "duration": 0.5,
        "headline": "MOBILE MONEY", "kicker": "À RETENIR",
        "icon": "money", "steps": [], "value": None, "raw": "",
        "source_start": 5.0, "source_end": 9.0,
    }
    out = tmp_path / "md_test.mov"
    rendered = motion_design.render_scene(scene, str(out))

    assert out.exists() and out.stat().st_size > 0
    assert rendered["illustrated"] is False          # no AI image -> drawing
    assert rendered["events"]["entrance"] == 0.0
    assert rendered["mov"] == str(out)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_all_writes_manifest(tmp_path, rich_vu):
    scenes = content.derive_motion_scenes(rich_vu)[:1]
    scenes[0]["duration"] = 0.4                      # keep the test fast
    rendered = motion_design.render_all(scenes, str(tmp_path))
    assert len(rendered) == 1
    manifest = {**rendered[0]}
    assert manifest["events"]["exit"] > 0
    json.dumps(rendered)                             # manifest is serialisable


def test_motion_scenes_guaranteed_on_long_videos(rich_vu, monkeypatch):
    # Même si le scoring ne trouve AUCUN beat fort, une vidéo assez longue
    # doit toujours recevoir au moins une scène motion design (promesse produit).
    monkeypatch.setattr(content, "_beat_score", lambda text, counts: 0.0)
    scenes = content.derive_motion_scenes(rich_vu)
    assert len(scenes) >= 1
    assert all(s["source_start"] >= engine_config.MOTION_MIN_START for s in scenes)


def test_overlays_are_light_and_capped(rich_vu):
    """Overlays must be few, brief and live BELOW the face zone (never cover it)."""
    specs = content.derive_motion_scenes  # noqa: ensure module imported
    overlays = content.derive_overlay_specs(rich_vu)
    assert len(overlays) <= engine_config.OVERLAY_MAX_PER_VIDEO
    for o in overlays:
        assert o["duration"] <= engine_config.OVERLAY_MAX_DUR + 0.01
        assert o["type"] in {"stat", "progress", "lower_third"}  # no invasive lists
    # spacing between overlays
    starts = sorted(o["source_start"] for o in overlays)
    for a, b in zip(starts, starts[1:]):
        assert b - a >= engine_config.OVERLAY_MIN_GAP - 0.01


def test_motion_scene_duration_tracks_spoken_span(rich_vu):
    for s in content.derive_motion_scenes(rich_vu):
        assert engine_config.MOTION_SCENE_MIN_DUR <= s["duration"] <= engine_config.MOTION_SCENE_MAX_DUR + 0.01
        # scene window equals start + duration (leaves when the point ends)
        assert abs((s["source_end"] - s["source_start"]) - s["duration"]) < 0.05


def test_motion_transitions_are_consistent_not_random():
    # Product rule: one coherent slide, never random left/right directions.
    assert engine_config.MOTION_ENTRANCES == ["slide_up"]
    assert engine_config.MOTION_EXITS == ["slide_down"]
