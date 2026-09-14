"""RendererRouter — pick the renderer for a scene, and recover when it fails.

The mission's fallback chain is enforced here:

    WhiteboardRenderer -> MotionGraphicsRenderer -> procedural SVG renderer

Every renderer in the chain writes the same contract, so a fallback is
invisible downstream apart from the `fallback_from` field in the report.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Sequence

from .. import config
from ..assets.asset_manager import AssetManager
from ..schemas.render_job import RenderedIllustration
from ..schemas.scene import IllustrationScene
from ..styles import Style, get_style
from .base import BaseRenderer
from .diagram_renderer import DiagramRenderer
from .infographic_renderer import InfographicRenderer
from .kinetic_text_renderer import KineticTextRenderer
from .motion_graphics_renderer import MotionGraphicsRenderer
from .whiteboard_renderer import WhiteboardRenderer


class RendererRouter:
    def __init__(self, style: str | Style = "professional",
                 width: int = 1920, height: int = 1080, fps: int = 30,
                 assets: Optional[AssetManager] = None, preview: bool = False):
        self.style = style if isinstance(style, Style) else get_style(style)
        kwargs = dict(style=self.style, width=width, height=height, fps=fps,
                      assets=assets or AssetManager(), preview=preview)
        self.whiteboard = WhiteboardRenderer(**kwargs)
        self.motion = MotionGraphicsRenderer(**kwargs)
        self.infographic = InfographicRenderer(**kwargs)
        self.diagram = DiagramRenderer(**kwargs)
        self.kinetic = KineticTextRenderer(**kwargs)
        # Order matters: the first renderer that claims the type wins.
        self.renderers: List[BaseRenderer] = [
            self.whiteboard, self.infographic, self.diagram, self.kinetic,
            self.motion,
        ]

    # ------------------------------------------------------------------ #
    def select(self, scene: IllustrationScene) -> BaseRenderer:
        for renderer in self.renderers:
            if renderer.supports(scene):
                return renderer
        return self.motion

    def chain(self, scene: IllustrationScene) -> List[BaseRenderer]:
        """The renderer plus its fallbacks, in the order they will be tried."""
        primary = self.select(scene)
        chain = [primary]
        if primary is not self.motion:
            chain.append(self.motion)
        if primary is not self.kinetic and self.motion is not self.kinetic:
            # Last resort: pure vector typography always renders.
            chain.append(self.kinetic)
        return chain

    # ------------------------------------------------------------------ #
    def render(self, scene: IllustrationScene, out_path: str
               ) -> Optional[RenderedIllustration]:
        """Render `scene`, walking the fallback chain on failure.

        Returns None only when every renderer failed — the caller then drops
        the scene and the montage continues, exactly as the legacy engine did.
        """
        failures: List[str] = []
        for renderer in self.chain(scene):
            try:
                rendered = renderer.render(scene, out_path)
            except Exception as exc:  # noqa: BLE001 - one bad scene is not fatal
                failures.append(f"{renderer.name}: {exc}")
                print(f"[illustration_engine] WARN {scene.scene_id} "
                      f"{renderer.name} a échoué: {exc}", file=sys.stderr)
                continue
            if not os.path.exists(rendered.path) or os.path.getsize(rendered.path) < 512:
                failures.append(f"{renderer.name}: sortie vide")
                continue
            scene.renderer = rendered.renderer
            if failures:
                rendered.fallback_from = failures[0].split(":")[0]
            return rendered
        print(f"[illustration_engine] ERREUR {scene.scene_id} abandonnée "
              f"({'; '.join(failures)})", file=sys.stderr)
        return None
