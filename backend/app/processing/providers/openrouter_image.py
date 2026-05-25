"""Provider OpenRouter — génération d'image via un modèle configurable.

OpenRouter expose plusieurs endpoints. Selon le modèle utilisé:
  - `/api/v1/images/generations`  (texte → image dédié)
  - `/api/v1/chat/completions`     (modèles multimodaux qui répondent en image,
                                    ex: gemini-2.5-flash-image-preview "Nano Banana")

On essaie d'abord `images/generations`. Si l'API renvoie 404 ou 422, on
retombe sur `chat/completions` en demandant `modalities=["image"]`.

⚠️  La clé OPENROUTER_API_KEY n'est jamais loggée ni commitée.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.config import settings
from app.processing.types import GeneratedImage

logger = logging.getLogger(__name__)


class OpenRouterError(RuntimeError):
    pass


class OpenRouterImageProvider:
    name: str = "openrouter"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        http_referer: str | None = None,
        x_title: str | None = None,
    ):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model or settings.IMAGE_GENERATION_MODEL
        self.base_url = (base_url or settings.OPENROUTER_BASE_URL).rstrip("/")
        self.http_referer = http_referer or settings.OPENROUTER_HTTP_REFERER
        self.x_title = x_title or settings.OPENROUTER_X_TITLE

    # ------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise OpenRouterError(
                "OPENROUTER_API_KEY n'est pas configuré. Voir .env.example."
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.http_referer,
            "X-Title": self.x_title,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        style: str | None = None,
        timeout_s: int = 60,
    ) -> GeneratedImage:
        size = self._size_for(aspect_ratio)

        # 1) `images/generations` (endpoint dédié)
        try:
            return self._call_images_endpoint(prompt, size, timeout_s)
        except OpenRouterError as e:
            logger.info("[openrouter] images/generations indisponible (%s), fallback chat", e)

        # 2) Fallback `chat/completions` multimodal
        return self._call_chat_endpoint(prompt, size, timeout_s)

    # ------------------------------------------------------------------
    def _call_images_endpoint(self, prompt: str, size: str, timeout_s: int) -> GeneratedImage:
        url = f"{self.base_url}/images/generations"
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(url, headers=self._headers(), json=payload)
        if resp.status_code in (404, 405, 422):
            raise OpenRouterError(f"endpoint not supported (status={resp.status_code})")
        if resp.status_code >= 400:
            raise OpenRouterError(f"openrouter images error: {resp.status_code} {resp.text[:200]}")

        data = resp.json() or {}
        items = data.get("data") or []
        if not items:
            raise OpenRouterError("openrouter returned no image data")
        first = items[0]
        b64 = first.get("b64_json")
        url_out = first.get("url")
        img_bytes = base64.b64decode(b64) if b64 else None
        return GeneratedImage(
            bytes=img_bytes,
            url=url_out,
            mime_type="image/png",
            provider=self.name,
            model=self.model,
            cost_estimate_usd=None,
            prompt=prompt,
        )

    def _call_chat_endpoint(self, prompt: str, size: str, timeout_s: int) -> GeneratedImage:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Generate a single photorealistic image, {size}, "
                                f"for the following scene. Return only the image.\n\n{prompt}"
                            ),
                        }
                    ],
                }
            ],
            # OpenRouter relaie ces hints aux modèles compatibles (Gemini image, etc.)
            "modalities": ["image"],
        }
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(url, headers=self._headers(), json=payload)
        if resp.status_code >= 400:
            raise OpenRouterError(f"openrouter chat error: {resp.status_code} {resp.text[:200]}")
        data = resp.json() or {}
        choices = data.get("choices") or []
        if not choices:
            raise OpenRouterError("openrouter chat returned no choices")

        msg = choices[0].get("message") or {}
        img_bytes, url_out = self._extract_image_from_message(msg)
        if not img_bytes and not url_out:
            raise OpenRouterError("openrouter chat returned no image content")
        return GeneratedImage(
            bytes=img_bytes,
            url=url_out,
            mime_type="image/png",
            provider=self.name,
            model=self.model,
            cost_estimate_usd=None,
            prompt=prompt,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_image_from_message(message: dict) -> tuple[bytes | None, str | None]:
        # Plusieurs formats existent côté OpenRouter selon les modèles.
        # On supporte: content list, message["images"], data URL inline.
        content = message.get("content")
        # 1) liste de parts {type, image_url, ...}
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                p_type = part.get("type")
                if p_type in ("output_image", "image", "image_url"):
                    image_url = part.get("image_url") or part.get("url")
                    if isinstance(image_url, dict):
                        image_url = image_url.get("url")
                    if isinstance(image_url, str):
                        if image_url.startswith("data:"):
                            return _decode_data_url(image_url), None
                        return None, image_url
                    b64 = part.get("b64_json") or part.get("data")
                    if isinstance(b64, str):
                        return base64.b64decode(b64), None
        # 2) message["images"]
        images = message.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict):
                url = first.get("url") or (first.get("image_url") or {}).get("url")
                if isinstance(url, str):
                    if url.startswith("data:"):
                        return _decode_data_url(url), None
                    return None, url
        return None, None

    @staticmethod
    def _size_for(aspect_ratio: str) -> str:
        mapping = {
            "9:16": "1024x1792",
            "16:9": "1792x1024",
            "1:1": "1024x1024",
            "4:5": "1024x1280",
        }
        return mapping.get(aspect_ratio, "1024x1024")


def _decode_data_url(data_url: str) -> bytes | None:
    try:
        _, b64 = data_url.split(",", 1)
        return base64.b64decode(b64)
    except Exception:
        return None
