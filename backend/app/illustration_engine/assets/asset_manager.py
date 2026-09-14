"""AssetManager — the strict priority chain of the mission.

    1. procedural SVG      (always available, zero cost)
    2. vector shapes       (cards, arrows, bars — drawn by the renderers)
    3. local icon library  (42 icons, resolution independent)
    4. bundled local assets
    5. existing images already in the job workdir
    6. image generation    (optional, paid, never required)

The manager never raises: each tier falls through to the next, and tier 1 can
always satisfy a request, so a scene is never blocked on an asset.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw

from . import icon_library, image_assets, procedural_assets, svg_assets

TIER_PROCEDURAL = "procedural"
TIER_ICON = "icon"
TIER_LOCAL = "local"
TIER_WORKDIR = "workdir"
TIER_GENERATED = "generated"


@dataclass
class Asset:
    """What the renderer got, and where it came from."""
    tier: str
    icon: str = ""
    path: str = ""
    image: Optional[Image.Image] = None

    @property
    def is_vector(self) -> bool:
        return self.tier in (TIER_PROCEDURAL, TIER_ICON)


class AssetManager:
    def __init__(self, workdir: str = "", allow_generation: bool = False,
                 style_hint: str = ""):
        self.workdir = workdir or ""
        self.allow_generation = bool(allow_generation)
        self.style_hint = style_hint
        self.stats = {TIER_PROCEDURAL: 0, TIER_ICON: 0, TIER_LOCAL: 0,
                      TIER_WORKDIR: 0, TIER_GENERATED: 0}

    # ------------------------------------------------------------------ #
    def for_element(self, element, prompt: str = "") -> Asset:
        """Resolve the visual for one element, cheapest tier first."""
        if element.icon and element.icon in icon_library.ICONS:
            self.stats[TIER_ICON] += 1
            return Asset(TIER_ICON, icon=element.icon)

        name = element.text or element.annotation or prompt
        local = image_assets.find_local(name)
        if local:
            image = image_assets.load(local)
            if image is not None:
                self.stats[TIER_LOCAL] += 1
                return Asset(TIER_LOCAL, path=local, image=image)

        if self.workdir:
            candidate = os.path.join(self.workdir, f"{element.element_id}.png")
            if os.path.exists(candidate):
                image = image_assets.load(candidate)
                if image is not None:
                    self.stats[TIER_WORKDIR] += 1
                    return Asset(TIER_WORKDIR, path=candidate, image=image)

        if self.allow_generation and prompt:
            out = os.path.join(self.workdir or ".", f"{element.element_id}.png")
            generated = image_assets.generate(prompt, out, self.style_hint)
            if generated:
                image = image_assets.load(generated)
                if image is not None:
                    self.stats[TIER_GENERATED] += 1
                    return Asset(TIER_GENERATED, path=generated, image=image)

        # Tier 1: always succeeds.
        self.stats[TIER_PROCEDURAL] += 1
        return Asset(TIER_PROCEDURAL,
                     icon=icon_library.icon_for(name or "idea"))

    # ------------------------------------------------------------------ #
    def icon_svg(self, name: str, size: int = 200, color=(17, 19, 24, 255)) -> str:
        return svg_assets.icon_to_svg(name, size=size, color=color)

    def icon_image(self, name: str, size: int, color, width: int = 6,
                   progress: float = 1.0) -> Image.Image:
        """Render an icon to a standalone RGBA tile."""
        tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tile)
        procedural_assets.draw_icon(draw, name, (0, 0, size, size), color,
                                    width=width, progress=progress)
        return tile

    def report(self) -> dict:
        """Which tiers actually served this job — surfaced in the job report."""
        return {k: v for k, v in self.stats.items() if v}
