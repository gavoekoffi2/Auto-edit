"""WhiteboardRenderer — hand-drawn explanations.

Two engines, one output contract:

* **whiteboard-animator** (MIT, https://github.com/masihsultani/whiteboard-animator)
  when the package is installed. The scene is composed into an ink-on-white
  poster, described as a narration-weighted region plan, and handed to its
  `render_scene`, which traces text with CRAFT and strokes with skeletonisation
  to produce a genuine hand-drawing reveal.
* **a native reveal engine** otherwise. It traces the same vector paths with
  PIL + numpy alone, which is what keeps CutForge runnable on a small VPS
  without the 80 MB CRAFT model and the OpenCV/scikit-image/ONNX stack.

The third-party path is optional by design; see docs/THIRD_PARTY_LICENSES.md.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from .. import config
from ..assets import procedural_assets as pa
from ..schemas.render_job import RenderedIllustration
from ..schemas.scene import IllustrationScene
from ..schemas.visual import (
    R_CAPTION, R_CONNECTOR, R_ICON, R_ITEM, R_LABEL, R_NUMBER, R_SIDE_A,
    R_SIDE_B, R_TITLE, R_UNDERLINE, VisualElement, WHITEBOARD,
)
from .base import BaseRenderer, fit_font, load_font, wrap_text

INK = (17, 19, 24, 255)
PAPER = (255, 255, 255, 255)


# whiteboard-animator types its region roles as a closed Literal, so CutForge's
# own roles have to be mapped onto its vocabulary rather than passed through.
_ANIMATOR_ROLES = {
    R_TITLE: "title",
    R_ITEM: "main_concept",
    R_SIDE_A: "main_concept",
    R_SIDE_B: "main_concept",
    R_NUMBER: "main_concept",
    R_ICON: "supporting_detail",
    R_LABEL: "label",
    R_CAPTION: "annotation",
    R_CONNECTOR: "decoration",
    R_UNDERLINE: "decoration",
}


def animator_available() -> bool:
    """Is the MIT whiteboard-animator importable in this environment?"""
    if not config.USE_WHITEBOARD_ANIMATOR:
        return False
    try:
        import whiteboard_animator  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 - missing or broken install, same answer
        return False


class WhiteboardRenderer(BaseRenderer):
    name = "whiteboard"
    handles = (WHITEBOARD,)

    # ------------------------------------------------------------------ #
    # poster composition — ink on white, everything at full reveal
    # ------------------------------------------------------------------ #
    def poster(self, scene: IllustrationScene) -> Image.Image:
        canvas = Image.new("RGBA", (self.width, self.height), PAPER)
        draw = ImageDraw.Draw(canvas)
        for element in scene.ordered_elements():
            self._draw_element(draw, canvas, scene, element, 1.0)
        return canvas

    def _ink_width(self, scale: float = 1.0) -> int:
        return max(2, int(self.unit(self.style.line_width * 1.25) * scale))

    @property
    def _marker(self):
        """The single coloured marker: underlines, arrows, badges."""
        return self.style.accent

    def _draw_element(self, draw: ImageDraw.ImageDraw, canvas: Image.Image,
                      scene: IllustrationScene, element: VisualElement,
                      p: float) -> None:
        """Draw one element in ink, traced to `p` of its path length."""
        if p <= 0.0:
            return
        x1, y1, x2, y2 = self.px(element)
        width, height = x2 - x1, y2 - y1

        if element.role == R_TITLE:
            self._draw_text(draw, element.text, (x1, y1, x2, y2), p,
                            family=self.style.font_title,
                            size=self.unit(76), align="left")
            return
        if element.role == R_UNDERLINE:
            pa.underline(draw, (x1, y1, x2, y2), self._marker,
                         self._ink_width(0.9), p)
            return
        if element.role == R_NUMBER:
            text = element.text or ""
            self._draw_text(draw, text, (x1, y1, x2, y2), p,
                            family=self.style.font_number,
                            size=self.unit(260), align="center")
            return
        if element.role == R_LABEL:
            if element.shape == "bar":
                path = pa.rect_path((x1, y1, x2, y2), (y2 - y1) // 2)
                pa.draw_strokes(draw, pa.partial([path], p), INK,
                                self._ink_width(0.5))
                filled = int(width * (element.value or 0.0) * p)
                if filled > 4:
                    self._hatch(draw, (x1, y1, x1 + filled, y2), p)
            else:
                pa.underline(draw, (x1, y1, x2, y2), INK, self._ink_width(0.7), p)
            return
        if element.role == R_CONNECTOR:
            self._draw_connector(draw, scene, element, p)
            return
        if element.role == R_ICON:
            pa.draw_icon(draw, element.icon, (x1, y1, x2, y2), INK,
                         self._ink_width(0.6), p)
            return
        if element.role == R_CAPTION:
            self._draw_text(draw, element.text, (x1, y1, x2, y2), p,
                            family=self.style.font_body,
                            size=self.unit(34), align="center", max_lines=3)
            return

        # items and panels: a sketched frame, an icon, a label
        if element.shape in ("card", "node", "panel", "hub", "frame", "row",
                             "milestone"):
            path = pa.rect_path((x1, y1, x2, y2), self.unit(26))
            pa.draw_strokes(draw, pa.partial([path], min(1.0, p * 1.6)), INK,
                            self._ink_width(0.65))
        if element.value and element.shape in ("card", "node", "milestone"):
            badge = self.unit(48)
            bx, by = x1 + self.unit(18), y1 + self.unit(18)
            pa.sketch_ellipse(draw, (bx, by, bx + badge, by + badge),
                              self._marker, self._ink_width(0.5),
                              min(1.0, p * 1.8))
            if p > 0.35:
                font = load_font(self.style.font_number, int(badge * 0.60))
                label = str(int(element.value))
                tw = draw.textlength(label, font=font)
                draw.text((bx + (badge - tw) / 2, by + badge * 0.18), label,
                          font=font, fill=self._marker)
        if element.icon:
            side = max(self.unit(44), min(int(min(width, height) * 0.46),
                                          self.unit(180)))
            ix = x1 + (width - side) // 2
            iy = y1 + self.unit(34) if element.text else y1 + (height - side) // 2
            pa.draw_icon(draw, element.icon, (ix, iy, ix + side, iy + side),
                         INK, self._ink_width(0.55), min(1.0, p * 1.3))
        if element.text:
            self._draw_text(draw, element.text,
                            (x1 + self.unit(14), y2 - self.unit(86),
                             x2 - self.unit(14), y2 - self.unit(16)),
                            p, family=self.style.font_body,
                            size=self.unit(38), align="center", max_lines=2)

    def _draw_connector(self, draw: ImageDraw.ImageDraw,
                        scene: IllustrationScene, element: VisualElement,
                        p: float) -> None:
        x1, y1, x2, y2 = self.px(element)
        width = self._ink_width(0.6)
        marker = self._marker
        if element.shape == "divider":
            pa.underline(draw, (x1, y1, x2, y2), marker, width, p)
            return
        if element.shape == "axis":
            pa.underline(draw, (x1, y1, x2, y2), marker, width, p)
            return
        if element.shape == "link":
            a = scene.element(element.connects[0])
            b = scene.element(element.connects[1])
            if a and b:
                pa.curved_arrow(draw, self._edge_point(a, b),
                                self._edge_point(b, a), marker, width, progress=p)
            return
        if element.shape in ("arrow_h", "arrow_v"):
            horizontal = element.shape == "arrow_h"
        else:
            horizontal = (x2 - x1) >= (y2 - y1)
        if horizontal:
            start = (x1 + self.unit(10), (y1 + y2) / 2.0)
            end = (x2 - self.unit(10), (y1 + y2) / 2.0)
        else:
            start = ((x1 + x2) / 2.0, y1 + self.unit(10))
            end = ((x1 + x2) / 2.0, y2 - self.unit(10))
        # Hand-drawn arrows curve; that is what makes it read as a whiteboard.
        pa.curved_arrow(draw, start, end, marker, width, bend=0.12, progress=p)

    def _hatch(self, draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
               p: float) -> None:
        """Marker fill: diagonal strokes, the way a hand shades a bar."""
        x1, y1, x2, y2 = box
        step = max(6, self.unit(16))
        strokes = []
        x = x1 - (y2 - y1)
        while x < x2:
            strokes.append([(max(x1, x), y2), (min(x2, x + (y2 - y1)), y1)])
            x += step
        pa.draw_strokes(draw, pa.partial(strokes, p), INK, max(2, self.unit(5)))

    def _draw_text(self, draw: ImageDraw.ImageDraw, text: str,
                   box: Tuple[int, int, int, int], p: float, family: str,
                   size: int, align: str = "left", max_lines: int = 1) -> None:
        """Ink text, revealed character by character as it is 'written'."""
        if not text:
            return
        x1, y1, x2, y2 = box
        width = max(1, x2 - x1)
        font = fit_font(family, text, width, max(1, y2 - y1), size, self.unit(16))
        lines = wrap_text(draw, text, font, width, max_lines) if max_lines > 1 \
            else [text]
        total_chars = max(1, sum(len(line) for line in lines))
        budget = int(round(total_chars * p))
        line_h = font.getbbox("Ag")[3] + self.unit(8)
        ty = y1
        for line in lines:
            if budget <= 0:
                break
            shown = line[:budget]
            budget -= len(line)
            tw = draw.textlength(shown, font=font)
            tx = x1 if align == "left" else x1 + (width - tw) / 2
            draw.text((tx, ty), shown, font=font, fill=INK)
            ty += line_h

    # ------------------------------------------------------------------ #
    # region plan for the third-party animator
    # ------------------------------------------------------------------ #
    def region_plan(self, scene: IllustrationScene):
        """Describe the poster as narration-weighted regions.

        Returns a `SnippetRegionPlan`, or None when the package is absent.
        Boxes are converted to the animator's normalised 0..1000 space.
        """
        try:
            from whiteboard_animator.regions import Box, Region, SnippetRegionPlan
        except Exception:  # noqa: BLE001
            return None

        regions = []
        order = 0
        for element in scene.ordered_elements():
            if not (element.text or element.icon or element.shape):
                continue
            box = element.box
            ymin = int(max(0, min(1000, box.y * 1000)))
            xmin = int(max(0, min(1000, box.x * 1000)))
            ymax = int(max(ymin + 1, min(1000, (box.y + box.h) * 1000)))
            xmax = int(max(xmin + 1, min(1000, (box.x + box.w) * 1000)))
            order += 1
            reveal = "stroke"
            if element.role in (R_CAPTION,):
                reveal = "fade"
            elif element.shape in ("bar",):
                reveal = "fill"
            regions.append(Region(
                label=f"{element.role}_{order}",
                role=_ANIMATOR_ROLES.get(element.role, "supporting_detail"),
                object=element.icon or element.shape or element.role,
                reveal_order=order,
                box=Box(ymin=ymin, xmin=xmin, ymax=ymax, xmax=xmax),
                expected_visual=(element.text or element.icon or element.shape
                                 or element.role),
                annotation=element.annotation or element.text or "",
                reveal=reveal,
            ))
        if not regions:
            return None
        try:
            return SnippetRegionPlan(
                idea=(scene.title or scene.concept or "scene")[:60],
                global_style_notes=f"CutForge style {self.style.name}",
                regions=regions,
                image_size=[self.width, self.height],
            )
        except Exception as exc:  # noqa: BLE001 - validation must not kill a job
            print(f"[whiteboard] WARN region plan rejected: {exc}", file=sys.stderr)
            return None

    # ------------------------------------------------------------------ #
    # rendering
    # ------------------------------------------------------------------ #
    def render(self, scene: IllustrationScene, out_path: str) -> RenderedIllustration:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        duration = max(0.4, scene.duration)

        if animator_available() and duration <= config.WHITEBOARD_MAX_DUR:
            rendered = self._render_with_animator(scene, out_path, duration)
            if rendered is not None:
                return rendered
            print("[whiteboard] whiteboard-animator indisponible ou en échec "
                  "-> moteur de révélation natif", file=sys.stderr)

        return self._render_native(scene, out_path, duration)

    # -- third-party path ---------------------------------------------- #
    def _render_with_animator(self, scene: IllustrationScene, out_path: str,
                              duration: float) -> Optional[RenderedIllustration]:
        try:
            from whiteboard_animator import Scene as WBScene, render_scene
            from whiteboard_animator import WhiteboardAnimator
        except Exception:  # noqa: BLE001
            return None

        tmpdir = tempfile.mkdtemp(prefix="cutforge_wb_")
        poster_path = os.path.join(tmpdir, f"{scene.scene_id}.png")
        mp4_path = os.path.join(tmpdir, f"{scene.scene_id}.mp4")
        try:
            self.poster(scene).convert("RGB").save(poster_path)
            animator = WhiteboardAnimator(fade_duration=0.06)
            render_scene(
                WBScene(image=poster_path, duration=duration,
                        region_plan=self.region_plan(scene)),
                mp4_path, quality=config.WHITEBOARD_QUALITY, animator=animator)
            if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 1024:
                return None
            # The animator writes opaque MP4; the montage compositor overlays
            # ProRes, so transcode. A full-frame opaque overlay is exactly the
            # takeover this scene is meant to be.
            self._to_prores(mp4_path, out_path)
        except Exception as exc:  # noqa: BLE001 - fall back, never fail the job
            print(f"[whiteboard] WARN animator failed for {scene.scene_id}: {exc}",
                  file=sys.stderr)
            return None
        finally:
            for path in (poster_path, mp4_path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
            try:
                os.rmdir(tmpdir)
            except OSError:
                pass

        if not os.path.exists(out_path):
            return None
        return RenderedIllustration(
            scene_id=scene.scene_id, path=out_path, duration=round(duration, 3),
            renderer="whiteboard_animator", events=self.events(scene),
            has_alpha=False, width=self.width, height=self.height,
        )

    def _to_prores(self, src: str, dst: str) -> None:
        from ..timeline.encoder import ffmpeg_bin
        subprocess.run(
            [ffmpeg_bin(), "-y", "-v", "error", "-i", src,
             "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio="
                    f"decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:white",
             "-c:v", "prores_ks", "-profile:v", config.PRORES_PROFILE,
             "-pix_fmt", config.PRORES_PIX_FMT, "-an", dst],
            check=True, capture_output=True, timeout=600)

    # -- native path ---------------------------------------------------- #
    def _reveal_windows(self, scene: IllustrationScene) -> Dict[str, Tuple[float, float]]:
        """(start, end) per element, from the planned animation sequence."""
        windows: Dict[str, Tuple[float, float]] = {}
        for instruction in scene.animation_sequence:
            windows[instruction.element_id] = (
                instruction.start,
                instruction.start + max(instruction.duration, 0.18))
        return windows

    def _paper(self, scene: IllustrationScene) -> Image.Image:
        key = scene.scene_id
        if getattr(self, "_paper_key", None) != key:
            self._paper_key = key
            self._paper_plate = pa.paper_texture(
                (self.width, self.height), PAPER, seed=abs(hash(key)) % 9973)
        return self._paper_plate

    def compose_frame(self, scene: IllustrationScene, t: float) -> Image.Image:
        """Ink on paper, traced to where the narration has got to.

        Overrides the graphic-language frame so a preview shows exactly what
        the native reveal engine will render.
        """
        windows = self._reveal_windows(scene)
        canvas = self._paper(scene).copy()
        draw = ImageDraw.Draw(canvas)
        for element in scene.ordered_elements():
            start, end = windows.get(element.element_id, (0.0, scene.duration))
            if t < start:
                continue
            span = max(end - start, 0.12)
            p = max(0.0, min(1.0, (t - start) / span))
            self._draw_element(draw, canvas, scene, element, p)
        return self.apply_transition(canvas, scene, t)

    def _render_native(self, scene: IllustrationScene, out_path: str,
                       duration: float) -> RenderedIllustration:
        from ..timeline.encoder import ClipWriter

        n_frames = max(1, int(round(duration * self.fps)))
        with ClipWriter(out_path, self.width, self.height, self.fps) as writer:
            for index in range(n_frames):
                writer.write(self.compose_frame(scene, index / self.fps))
        return RenderedIllustration(
            scene_id=scene.scene_id, path=out_path, duration=round(duration, 3),
            renderer="whiteboard_native", events=self.events(scene),
            has_alpha=True, width=self.width, height=self.height,
        )

    # ------------------------------------------------------------------ #
    def events(self, scene: IllustrationScene) -> Dict[str, Any]:
        """Whiteboard scenes also carry a `draw` cue for the pencil sound."""
        base = super().events(scene)
        base["draw"] = 0.25
        return base
