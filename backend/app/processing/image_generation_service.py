"""Service de génération d'images B-roll — orchestre les `BrollCue`.

Reçoit la liste de cues et:
  - choisit le provider configuré (`IMAGE_GENERATION_PROVIDER`);
  - appelle `provider.generate(prompt, aspect_ratio, ...)`;
  - persiste l'image en `broll/<index>.png`;
  - met à jour `cue.image_path`;
  - fait un fallback silencieux si l'image échoue (log + `cue.failure_reason`).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable

import httpx

from app.config import settings
from app.processing.providers import (
    ImageProvider,
    NoopImageProvider,
    OpenRouterImageProvider,
)
from app.processing.types import BrollCue, GeneratedImage

logger = logging.getLogger(__name__)


class ImageGenerationService:
    def __init__(self, provider: ImageProvider | None = None, timeout_s: int = 60):
        self.provider = provider or self._build_default_provider()
        self.timeout_s = timeout_s

    # ------------------------------------------------------------------
    @staticmethod
    def _build_default_provider() -> ImageProvider:
        name = (settings.IMAGE_GENERATION_PROVIDER or "noop").lower()
        if name == "openrouter":
            if not settings.OPENROUTER_API_KEY:
                logger.warning(
                    "IMAGE_GENERATION_PROVIDER=openrouter mais OPENROUTER_API_KEY vide. "
                    "Fallback NoopImageProvider — aucune image ne sera générée."
                )
                return NoopImageProvider()
            return OpenRouterImageProvider()
        return NoopImageProvider()

    # ------------------------------------------------------------------
    def generate_for_cues(
        self,
        cues: Iterable[BrollCue],
        broll_dir: str,
    ) -> list[BrollCue]:
        """Génère les images en place et renvoie la liste mise à jour."""
        os.makedirs(broll_dir, exist_ok=True)
        out: list[BrollCue] = []
        for idx, cue in enumerate(cues, start=1):
            target = os.path.join(broll_dir, f"{idx:04d}.png")
            try:
                image = self.provider.generate(
                    prompt=cue.prompt,
                    aspect_ratio=cue.aspect_ratio,
                    style=cue.style,
                    timeout_s=self.timeout_s,
                )
                if not self._persist(image, target):
                    cue.failure_reason = "empty_image"
                else:
                    cue.image_path = target
            except Exception as e:
                logger.warning("[image_generation_service] cue %d failed: %s", idx, e)
                cue.failure_reason = str(e)[:200]
            out.append(cue)
        successful = sum(1 for c in out if c.image_path)
        logger.info(
            "[image_generation_service] %d/%d images generated via %s",
            successful, len(out), self.provider.name,
        )
        return out

    # ------------------------------------------------------------------
    def _persist(self, image: GeneratedImage, target: str) -> bool:
        if image.bytes:
            Path(target).write_bytes(image.bytes)
            return True
        if image.url:
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    resp = client.get(image.url)
                if resp.status_code >= 400:
                    logger.warning("[image_generation_service] download %s: %s",
                                   image.url, resp.status_code)
                    return False
                Path(target).write_bytes(resp.content)
                return True
            except Exception as e:
                logger.warning("[image_generation_service] download error: %s", e)
                return False
        return False
