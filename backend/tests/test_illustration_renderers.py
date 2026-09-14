"""Renderers: do the scenes actually draw, and does every failure recover?"""
from __future__ import annotations

import os

import pytest
from PIL import Image

from app.illustration_engine import config
from app.illustration_engine.assets import icon_library, procedural_assets as pa
from app.illustration_engine.assets.asset_manager import (
    AssetManager, TIER_ICON, TIER_PROCEDURAL)
from app.illustration_engine.assets.svg_assets import icon_to_svg, scene_to_svg
from app.illustration_engine.planner import ScenePlanner
from app.illustration_engine.renderers import (
    DiagramRenderer, InfographicRenderer, KineticTextRenderer,
    MotionGraphicsRenderer, RendererRouter, WhiteboardRenderer,
)
from app.illustration_engine.schemas.visual import (
    DIAGRAM, INFOGRAPHIC, KINETIC_TYPOGRAPHY, MOTION_GRAPHICS, P_LIST,
    STATISTICS, VISUAL_TYPES, VisualOpportunity, WHITEBOARD,
)
from app.illustration_engine.renderers import animator_available
from tests.illustration_fixtures import has_ffmpeg

W, H = 960, 540


def make_scene(visual_type=INFOGRAPHIC, style="professional", aspect="16:9"):
    opportunity = VisualOpportunity(
        10.0, 16.0, "le produit, le trafic et la livraison", P_LIST, 0.88, 0.7,
        concepts=["produit", "trafic", "livraison"],
        items=["Produit", "Trafic", "Livraison"],
        numbers=[("87%", 87.0)], sides=("Avant", "Après"))
    return ScenePlanner(style, aspect).plan(
        opportunity, visual_type, "s1", 10.0, 16.0,
        title="PRODUIT TRAFIC", subtitle="À RETENIR")


# --------------------------------------------------------------------------- #
# vector assets
# --------------------------------------------------------------------------- #
def test_every_icon_is_drawable_and_normalised():
    assert len(icon_library.names()) >= 40
    for name in icon_library.names():
        strokes = icon_library.get(name)
        assert strokes, name
        for stroke in strokes:
            assert len(stroke) >= 2, name
            for x, y in stroke:
                assert -0.1 <= x <= 1.1 and -0.1 <= y <= 1.1, name


def test_icons_cover_the_african_commerce_vocabulary():
    for phrase, expected in [
        ("le mobile money", "mobile_money"),
        ("la livraison du colis", "truck"),
        ("ma boutique en ligne", "shop"),
        ("le client", "customer"),
        ("l'intelligence artificielle", "ai"),
        ("l'agriculture et la récolte", "plant"),
    ]:
        assert icon_library.icon_for(phrase) == expected, phrase


def test_icon_choice_avoids_repeats_when_an_alternative_exists():
    phrase = "le client paie par mobile money"
    first = icon_library.icon_for(phrase)
    second = icon_library.icon_for(phrase, exclude=[first])
    assert second != first
    assert {first, second} == {"customer", "mobile_money"}


def test_icon_choice_keeps_the_right_icon_over_forced_variety():
    """With one honest match, a correct repeat beats a wrong alternative."""
    only_match = icon_library.icon_for("la livraison")
    assert only_match == "truck"
    assert icon_library.icon_for("la livraison", exclude=[only_match]) == "truck"


def test_partial_stroke_is_a_real_fraction_of_the_path():
    icon = icon_library.get("cart")
    full = pa.total_length(icon)
    half = pa.total_length(pa.partial(icon, 0.5))
    assert 0.35 * full <= half <= 0.65 * full
    assert pa.partial(icon, 0.0) == []
    assert pa.total_length(pa.partial(icon, 1.0)) == pytest.approx(full)


def test_svg_export_is_well_formed():
    svg = icon_to_svg("rocket", size=120)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "polyline" in svg and 'width="120"' in svg


def test_scene_svg_preview_contains_the_labels():
    svg = scene_to_svg(make_scene(), 800, 450)
    assert "Produit" in svg and "Livraison" in svg


# --------------------------------------------------------------------------- #
# asset manager priority chain
# --------------------------------------------------------------------------- #
def test_asset_manager_prefers_vectors_and_never_fails():
    manager = AssetManager(allow_generation=False)
    scene = make_scene()
    for element in scene.elements:
        asset = manager.for_element(element)
        assert asset.tier in (TIER_ICON, TIER_PROCEDURAL)
        assert asset.is_vector
    assert manager.report()


def test_asset_manager_makes_no_paid_call_when_generation_is_off(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("image generation must not be called")
    monkeypatch.setattr(
        "app.illustration_engine.assets.image_assets.generate", _boom)
    manager = AssetManager(allow_generation=False)
    asset = manager.for_element(make_scene().elements[0], prompt="anything")
    assert asset.is_vector


# --------------------------------------------------------------------------- #
# frame composition
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("visual_type", VISUAL_TYPES)
def test_every_type_composes_a_non_empty_frame(visual_type):
    scene = make_scene(visual_type)
    renderer = RendererRouter("professional", W, H, 30).select(scene)
    frame = renderer.compose_frame(scene, scene.duration * 0.85)
    assert frame.size == (W, H)
    assert frame.mode == "RGBA"
    # Something was actually painted.
    assert frame.getbbox() is not None
    assert max(frame.split()[3].getextrema()) > 0


def test_frames_progress_over_time():
    """A scene that looks identical at 10% and 90% is not an animation."""
    scene = make_scene(INFOGRAPHIC)
    renderer = MotionGraphicsRenderer("professional", W, H, 30)
    early = renderer.compose_frame(scene, scene.duration * 0.10)
    late = renderer.compose_frame(scene, scene.duration * 0.90)
    assert early.tobytes() != late.tobytes()


def test_scene_fades_in_and_out():
    scene = make_scene(INFOGRAPHIC)
    renderer = MotionGraphicsRenderer("professional", W, H, 30)
    assert renderer.scene_alpha(scene, 0.0) == 0.0
    assert renderer.scene_alpha(scene, scene.duration * 0.5) == 1.0
    assert renderer.scene_alpha(scene, scene.duration) == pytest.approx(0.0, abs=0.02)


@pytest.mark.parametrize("aspect,size", [("16:9", (960, 540)),
                                         ("9:16", (540, 960)),
                                         ("1:1", (600, 600))])
def test_rendering_works_in_every_aspect(aspect, size):
    scene = make_scene(INFOGRAPHIC, aspect=aspect)
    renderer = RendererRouter("professional", size[0], size[1], 30).select(scene)
    frame = renderer.compose_frame(scene, scene.duration * 0.8)
    assert frame.size == size
    assert frame.getbbox() is not None


def test_router_maps_types_to_their_renderer():
    router = RendererRouter("professional", W, H, 30)
    assert isinstance(router.select(make_scene(WHITEBOARD)), WhiteboardRenderer)
    assert isinstance(router.select(make_scene(STATISTICS)), InfographicRenderer)
    assert isinstance(router.select(make_scene(DIAGRAM)), DiagramRenderer)
    assert isinstance(router.select(make_scene(KINETIC_TYPOGRAPHY)), KineticTextRenderer)
    assert isinstance(router.select(make_scene(MOTION_GRAPHICS)), MotionGraphicsRenderer)


def test_fallback_chain_always_ends_on_a_general_renderer():
    router = RendererRouter("professional", W, H, 30)
    chain = router.chain(make_scene(WHITEBOARD))
    assert isinstance(chain[0], WhiteboardRenderer)
    assert any(isinstance(r, MotionGraphicsRenderer) for r in chain[1:])


def test_router_recovers_when_the_primary_renderer_fails(tmp_path, monkeypatch):
    """WhiteboardRenderer -> MotionGraphicsRenderer, per the fallback spec."""
    scene = make_scene(WHITEBOARD)
    router = RendererRouter("professional", W, H, 30)

    def _fail(self, scene, out_path):
        raise RuntimeError("simulated whiteboard failure")

    monkeypatch.setattr(WhiteboardRenderer, "render", _fail)

    produced = {}

    def _fake_motion_render(self, scene, out_path):
        from app.illustration_engine.schemas.render_job import RenderedIllustration
        with open(out_path, "wb") as handle:
            handle.write(b"0" * 4096)
        produced["renderer"] = self.name
        return RenderedIllustration(
            scene_id=scene.scene_id, path=out_path, duration=scene.duration,
            renderer=self.name, events={}, width=W, height=H)

    monkeypatch.setattr(MotionGraphicsRenderer, "render", _fake_motion_render)
    result = router.render(scene, str(tmp_path / "out.mov"))
    assert result is not None
    assert produced["renderer"] == "motion_graphics"
    assert result.fallback_from == "whiteboard"


def test_router_returns_none_when_everything_fails(tmp_path, monkeypatch):
    from app.illustration_engine.renderers.base import BaseRenderer

    def _fail(self, scene, out_path):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(BaseRenderer, "render", _fail)
    monkeypatch.setattr(WhiteboardRenderer, "render", _fail)
    router = RendererRouter("professional", W, H, 30)
    assert router.render(make_scene(INFOGRAPHIC), str(tmp_path / "x.mov")) is None


# --------------------------------------------------------------------------- #
# whiteboard specifics
# --------------------------------------------------------------------------- #
def test_whiteboard_poster_is_ink_on_white():
    scene = make_scene(WHITEBOARD, style="whiteboard")
    poster = WhiteboardRenderer("whiteboard", W, H, 30).poster(scene)
    assert poster.size == (W, H)
    corner = poster.convert("RGB").getpixel((2, 2))
    assert min(corner) > 230, "the page must stay paper-white"
    # And there must be actual ink somewhere.
    greys = poster.convert("L").getextrema()
    assert greys[0] < 120


def test_whiteboard_preview_matches_its_reveal_engine():
    """compose_frame must use the ink path, not the graphic one."""
    scene = make_scene(WHITEBOARD, style="whiteboard")
    renderer = WhiteboardRenderer("whiteboard", W, H, 30)
    early = renderer.compose_frame(scene, scene.duration * 0.15)
    late = renderer.compose_frame(scene, scene.duration * 0.9)
    assert early.tobytes() != late.tobytes()
    # Ink grows over time: the later frame is darker overall.
    def _ink(image):
        grey = image.convert("L")
        return sum(1 for px in grey.getdata() if px < 128)
    assert _ink(late) > _ink(early)


def test_whiteboard_region_plan_is_skipped_without_the_package():
    scene = make_scene(WHITEBOARD, style="whiteboard")
    plan = WhiteboardRenderer("whiteboard", W, H, 30).region_plan(scene)
    if not animator_available():
        assert plan is None
    else:
        assert plan is not None and plan.regions


@pytest.mark.skipif(not animator_available(),
                    reason="whiteboard-animator not installed")
def test_region_plan_speaks_the_animators_vocabulary():
    """Its roles are a closed Literal: ours must be mapped, not passed through."""
    from whiteboard_animator.regions import RegionRole
    from typing import get_args

    allowed = set(get_args(RegionRole))
    scene = make_scene(WHITEBOARD, style="whiteboard")
    plan = WhiteboardRenderer("whiteboard", W, H, 30).region_plan(scene)
    assert plan is not None
    for region in plan.regions:
        assert region.role in allowed, region.role
        assert region.reveal in ("stroke", "fill", "fade")
        assert 0 <= region.box.xmin < region.box.xmax <= 1000
        assert 0 <= region.box.ymin < region.box.ymax <= 1000
    orders = [r.reveal_order for r in plan.regions]
    assert orders == sorted(orders) and len(set(orders)) == len(orders)


@pytest.mark.skipif(not animator_available() or not has_ffmpeg(),
                    reason="needs whiteboard-animator and ffmpeg")
def test_whiteboard_really_uses_the_third_party_animator(tmp_path):
    scene = make_scene(WHITEBOARD, style="whiteboard")
    renderer = WhiteboardRenderer("whiteboard", 480, 270, 12)
    rendered = renderer.render(scene, str(tmp_path / "wb.mov"))
    assert rendered.renderer == "whiteboard_animator"
    assert os.path.getsize(rendered.path) > 1024


def test_whiteboard_events_carry_a_pencil_cue():
    scene = make_scene(WHITEBOARD, style="whiteboard")
    events = WhiteboardRenderer("whiteboard", W, H, 30).events(scene)
    assert "draw" in events
    assert events["exit"] <= scene.duration


# --------------------------------------------------------------------------- #
# encoding (needs ffmpeg)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not has_ffmpeg(), reason="ffmpeg not available")
def test_render_produces_a_playable_clip(tmp_path):
    scene = make_scene(INFOGRAPHIC)
    renderer = MotionGraphicsRenderer("professional", 480, 270, 12)
    out = str(tmp_path / "scene.mov")
    rendered = renderer.render(scene, out)
    assert os.path.exists(out) and os.path.getsize(out) > 1024
    assert rendered.duration == pytest.approx(scene.duration, abs=0.05)
    assert rendered.has_alpha
