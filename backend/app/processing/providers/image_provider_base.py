"""Interface `ImageProvider` + provider Noop par défaut."""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.processing.types import GeneratedImage

logger = logging.getLogger(__name__)


@runtime_checkable
class ImageProvider(Protocol):
    """Contrat minimal d'un provider de génération d'image."""

    name: str

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        style: str | None = None,
        timeout_s: int = 60,
    ) -> GeneratedImage:
        ...


class NoopImageProvider:
    """Provider qui ne fait rien — utile pour tests + fallback hors-ligne."""

    name: str = "noop"

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        style: str | None = None,
        timeout_s: int = 60,
    ) -> GeneratedImage:
        logger.info("[noop_image_provider] (skipped) prompt='%s'", prompt[:80])
        return GeneratedImage(
            bytes=None,
            url=None,
            mime_type="image/png",
            provider=self.name,
            model="noop",
            cost_estimate_usd=0.0,
            prompt=prompt,
        )
