"""Renderer abstrait pour overlays animés (cards, lower thirds, CTA…).

Trois backends prévus:
  - `ffmpeg`      : drawtext / drawbox / fade (MVP, déjà disponible).
  - `hyperframes` : rend HTML/CSS/JS → MP4 via le projet HyperFrames de HeyGen
                    (à brancher en Phase 2 via une image Docker Node).
  - `remotion`    : compositions React rendues via `npx remotion render`
                    (à brancher en Phase 2).

L'API publique est figée pour que le pipeline ne change pas quand on activera
les backends avancés.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable

from app.config import settings
from app.processing.types import OverlayClip

logger = logging.getLogger(__name__)


@dataclass
class RendererCapabilities:
    intro_card: bool
    lower_third: bool
    cta: bool
    custom_template: bool


class TemplateRenderer:
    def __init__(self, backend: str | None = None, ffmpeg_bin: str = "ffmpeg"):
        chosen = (backend or settings.VIDEO_RENDERER or "ffmpeg").lower()
        if chosen not in ("ffmpeg", "hyperframes", "remotion"):
            logger.warning("Unknown renderer '%s', fallback ffmpeg", chosen)
            chosen = "ffmpeg"
        self.backend = chosen
        self.ffmpeg_bin = ffmpeg_bin

    # ------------------------------------------------------------------
    def capabilities(self) -> RendererCapabilities:
        if self.backend == "ffmpeg":
            return RendererCapabilities(True, True, True, custom_template=False)
        # HyperFrames / Remotion: tout supporté en théorie une fois branchés.
        return RendererCapabilities(True, True, True, custom_template=True)

    # ------------------------------------------------------------------
    def render_overlays(self, overlays: Iterable[OverlayClip], out_dir: str,
                        aspect_ratio: str = "9:16") -> list[OverlayClip]:
        os.makedirs(out_dir, exist_ok=True)
        out: list[OverlayClip] = []
        for idx, ov in enumerate(overlays, start=1):
            target = os.path.join(out_dir, f"{ov.kind}_{idx:02d}.mp4")
            try:
                rendered = self._render_one(ov, target, aspect_ratio)
                ov.clip_path = rendered
            except Exception as e:
                logger.warning("[template_renderer] %s failed: %s", ov.kind, e)
            out.append(ov)
        return out

    # ------------------------------------------------------------------
    def _render_one(self, ov: OverlayClip, target: str, aspect_ratio: str) -> str:
        if self.backend == "ffmpeg":
            return self._ffmpeg_overlay(ov, target, aspect_ratio)
        if self.backend == "hyperframes":
            return self._hyperframes_overlay(ov, target, aspect_ratio)
        if self.backend == "remotion":
            return self._remotion_overlay(ov, target, aspect_ratio)
        raise RuntimeError(f"unknown renderer backend: {self.backend}")

    # ------------------------------------------------------------------
    def _ffmpeg_overlay(self, ov: OverlayClip, target: str, aspect_ratio: str) -> str:
        """Génère un overlay vidéo simple avec FFmpeg drawtext + fond noir transparent."""
        if not shutil.which(self.ffmpeg_bin):
            raise RuntimeError("ffmpeg not available")

        duration = max(0.5, ov.end - ov.start)
        if aspect_ratio == "9:16":
            w, h = 1080, 1920
        elif aspect_ratio == "16:9":
            w, h = 1920, 1080
        else:
            w, h = 1080, 1080

        title = _escape_drawtext(str(ov.props.get("title") or ov.props.get("text") or ""))
        subtitle = _escape_drawtext(str(ov.props.get("subtitle") or ov.props.get("role") or ""))

        # On rend un fond noir transparent (alpha) avec texte en overlay.
        # Format yuva420p pour permettre l'overlay alpha plus tard.
        size = f"{w}x{h}"
        vf_parts = [
            f"drawtext=text='{title}':fontcolor=white:fontsize={int(h*0.06)}:"
            f"x=(w-text_w)/2:y=h*0.45:box=1:boxcolor=black@0.55:boxborderw=24"
        ]
        if subtitle:
            vf_parts.append(
                f"drawtext=text='{subtitle}':fontcolor=white:fontsize={int(h*0.035)}:"
                f"x=(w-text_w)/2:y=h*0.55:box=1:boxcolor=black@0.45:boxborderw=18"
            )
        vf_parts.append("fade=t=in:st=0:d=0.3")
        vf_parts.append(f"fade=t=out:st={max(0.0, duration-0.3):.3f}:d=0.3")
        vf = ",".join(vf_parts)

        cmd = [
            self.ffmpeg_bin,
            "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi",
            "-i", f"color=c=black@0.0:s={size}:d={duration}:r=30",
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuva420p",
            "-t", f"{duration:.3f}",
            target,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            # fallback: réessaye en yuv420p (sans alpha) pour les FFmpeg sans yuva
            cmd_alt = list(cmd)
            cmd_alt[cmd_alt.index("yuva420p")] = "yuv420p"
            cmd_alt[cmd_alt.index(f"color=c=black@0.0:s={size}:d={duration}:r=30")] = (
                f"color=c=black:s={size}:d={duration}:r=30"
            )
            proc = subprocess.run(cmd_alt, capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr[:200])
        if not os.path.exists(target) or os.path.getsize(target) == 0:
            raise RuntimeError("empty overlay output")
        return target

    # ------------------------------------------------------------------
    def _hyperframes_overlay(self, ov: OverlayClip, target: str, aspect_ratio: str) -> str:
        # Placeholder — Phase 2. On documente l'invocation attendue.
        # Exemple (sera fait dans un container Node séparé):
        #   docker run --rm -v ...:/work autoedit/hyperframes \
        #       node render.js --template lower_third --props '{"name":"..."}' \
        #       --out /work/out.mp4 --aspect 9:16
        raise NotImplementedError(
            "HyperFrames renderer non encore branché — voir docs/VIDEO_PIPELINE_ARCHITECTURE.md §7."
        )

    def _remotion_overlay(self, ov: OverlayClip, target: str, aspect_ratio: str) -> str:
        # Placeholder — Phase 2.
        # Exemple:
        #   npx remotion render src/index.tsx LowerThird out.mp4 \
        #     --props='{"name":"..."}'
        raise NotImplementedError(
            "Remotion renderer non encore branché — voir docs/VIDEO_PIPELINE_ARCHITECTURE.md §7."
        )


def _escape_drawtext(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("%", r"\%")
    )
