"""ÉTAPE 4 — `CollageImageService`: génération d'images, provider-agnostique.

Règle produit: **aucun fournisseur n'est codé en dur**. Le service parle à une
abstraction (`CollageImageProvider`) et résout l'implémentation par un
REGISTRE + la configuration:

    COLLAGE_IMAGE_PROVIDER=openrouter | google_ai_studio | maxfusion | noop

Ajouter un fournisseur = écrire une classe avec `.generate(...)` et appeler
`register_provider("mon_provider", factory)` — zéro modification du pipeline.

Réutilisation: le provider OpenRouter existant (`app.processing.providers`)
n'est pas réécrit, il est simplement adapté au contrat collage (qui ajoute un
`negative_prompt`). Le type de retour reste le `GeneratedImage` du pipeline V2.
"""
from __future__ import annotations

import base64
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence, runtime_checkable

import httpx

from app.processing.types import GeneratedImage

from . import collage_config as ccfg
from .collage_cache import BinaryCache
from .collage_types import CollageAsset, CollageConcept, CollagePrompts

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Contrat
# --------------------------------------------------------------------------- #
@runtime_checkable
class CollageImageProvider(Protocol):
    """Contrat minimal d'un fournisseur d'images pour le collage."""

    name: str

    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "9:16",
        negative_prompt: str = "",
        timeout_s: int = 180,
    ) -> GeneratedImage:
        ...


ProviderFactory = Callable[[], CollageImageProvider]
PROVIDERS: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Enregistre (ou remplace) un fournisseur dans le registre."""
    PROVIDERS[name.strip().lower()] = factory


def available_providers() -> list[str]:
    return sorted(PROVIDERS)


class ImageProviderError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Implémentations livrées
# --------------------------------------------------------------------------- #
class NoopCollageImageProvider:
    """Ne génère rien — utilisé hors-ligne, en test et en repli sans clé."""

    name = "noop"

    def generate(self, prompt: str, *, aspect_ratio: str = "9:16",
                 negative_prompt: str = "", timeout_s: int = 180) -> GeneratedImage:
        logger.info("[collage_image] noop provider — prompt='%s…'", prompt[:70])
        return GeneratedImage(bytes=None, url=None, mime_type="image/png",
                              provider=self.name, model="noop",
                              cost_estimate_usd=0.0, prompt=prompt)


class OpenRouterCollageProvider:
    """Adaptateur sur le provider OpenRouter EXISTANT du pipeline V2.

    OpenRouter n'expose pas de champ `negative_prompt` générique: on le replie
    dans le prompt (le verrou de style le répète déjà en positif).
    """

    name = "openrouter"

    def __init__(self, model: Optional[str] = None):
        from app.processing.providers import OpenRouterImageProvider
        self._inner = OpenRouterImageProvider(model=model or ccfg.IMAGE_MODEL or None)

    def generate(self, prompt: str, *, aspect_ratio: str = "9:16",
                 negative_prompt: str = "", timeout_s: int = 180) -> GeneratedImage:
        full = prompt if not negative_prompt else f"{prompt} Avoid: {negative_prompt}."
        return self._inner.generate(prompt=full, aspect_ratio=aspect_ratio,
                                    style="collage_premium", timeout_s=timeout_s)


class GoogleAIStudioImageProvider:
    """Google AI Studio (Gemini image) — `:generateContent` avec modalité IMAGE."""

    name = "google_ai_studio"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_AI_STUDIO_API_KEY", "")
        self.model = model or ccfg.IMAGE_MODEL or ccfg.GOOGLE_AI_STUDIO_MODEL
        self.base_url = (base_url or ccfg.GOOGLE_AI_STUDIO_BASE_URL).rstrip("/")

    def generate(self, prompt: str, *, aspect_ratio: str = "9:16",
                 negative_prompt: str = "", timeout_s: int = 180) -> GeneratedImage:
        if not self.api_key:
            raise ImageProviderError("GOOGLE_AI_STUDIO_API_KEY manquante")
        text = prompt if not negative_prompt else f"{prompt} Avoid: {negative_prompt}."
        url = f"{self.base_url}/models/{self.model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(url, headers={"x-goog-api-key": self.api_key,
                                             "Content-Type": "application/json"},
                               json=payload)
        if resp.status_code >= 400:
            raise ImageProviderError(
                f"google_ai_studio {resp.status_code}: {resp.text[:180]}")
        data = resp.json() or {}
        for candidate in data.get("candidates") or []:
            for part in (candidate.get("content") or {}).get("parts") or []:
                inline = part.get("inlineData") or part.get("inline_data") or {}
                blob = inline.get("data")
                if blob:
                    return GeneratedImage(
                        bytes=base64.b64decode(blob), url=None,
                        mime_type=inline.get("mimeType") or "image/png",
                        provider=self.name, model=self.model,
                        cost_estimate_usd=None, prompt=prompt)
        raise ImageProviderError("google_ai_studio: aucune image dans la réponse")


class MaxFusionImageProvider:
    """MaxFusion — endpoint images de style OpenAI, entièrement configurable.

    `MAXFUSION_BASE_URL` / `MAXFUSION_IMAGE_MODEL` permettent de pointer
    n'importe quelle passerelle compatible sans toucher au code.
    """

    name = "maxfusion"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("MAXFUSION_API_KEY", "")
        self.model = model or ccfg.IMAGE_MODEL or ccfg.MAXFUSION_IMAGE_MODEL
        self.base_url = (base_url or ccfg.MAXFUSION_BASE_URL).rstrip("/")

    def generate(self, prompt: str, *, aspect_ratio: str = "9:16",
                 negative_prompt: str = "", timeout_s: int = 180) -> GeneratedImage:
        if not self.api_key:
            raise ImageProviderError("MAXFUSION_API_KEY manquante")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "size": _size_for(aspect_ratio),
            "aspect_ratio": aspect_ratio,
            "n": 1,
        }
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(f"{self.base_url}/images/generations",
                               headers={"Authorization": f"Bearer {self.api_key}",
                                        "Content-Type": "application/json"},
                               json=payload)
        if resp.status_code >= 400:
            raise ImageProviderError(f"maxfusion {resp.status_code}: {resp.text[:180]}")
        items = (resp.json() or {}).get("data") or []
        if not items:
            raise ImageProviderError("maxfusion: réponse sans image")
        first = items[0] if isinstance(items[0], dict) else {}
        b64 = first.get("b64_json") or first.get("image")
        return GeneratedImage(
            bytes=base64.b64decode(b64) if b64 else None,
            url=first.get("url"),
            mime_type="image/png", provider=self.name, model=self.model,
            cost_estimate_usd=None, prompt=prompt)


register_provider("noop", NoopCollageImageProvider)
register_provider("openrouter", OpenRouterCollageProvider)
register_provider("google_ai_studio", GoogleAIStudioImageProvider)
register_provider("maxfusion", MaxFusionImageProvider)


# --------------------------------------------------------------------------- #
def resolve_provider_name(explicit: Optional[str] = None) -> str:
    """Provider effectif: argument > COLLAGE_IMAGE_PROVIDER > réglage global."""
    for candidate in (explicit, ccfg.IMAGE_PROVIDER):
        name = (candidate or "").strip().lower()
        if name in PROVIDERS:
            return name
    # Repli sur le réglage global du produit (pipeline V2), puis noop.
    try:
        from app.config import settings
        name = (settings.IMAGE_GENERATION_PROVIDER or "").strip().lower()
    except Exception:  # noqa: BLE001 - settings indisponibles (tests isolés)
        name = os.environ.get("IMAGE_GENERATION_PROVIDER", "").strip().lower()
    return name if name in PROVIDERS else "noop"


def build_provider(name: Optional[str] = None) -> CollageImageProvider:
    """Instancie le provider configuré; retombe sur `noop` si indisponible."""
    resolved = resolve_provider_name(name)
    try:
        return PROVIDERS[resolved]()
    except Exception as exc:  # noqa: BLE001 - jamais bloquant
        logger.warning("[collage_image] provider '%s' indisponible (%s) — noop",
                       resolved, str(exc)[:140])
        return NoopCollageImageProvider()


# --------------------------------------------------------------------------- #
class CollageImageService:
    """Orchestre la génération d'images de collage (cache + parallélisme)."""

    def __init__(self, provider: Optional[CollageImageProvider] = None,
                 timeout_s: Optional[int] = None,
                 cache: Optional[BinaryCache] = None,
                 max_workers: Optional[int] = None):
        self.provider = provider or build_provider()
        self.timeout_s = timeout_s or ccfg.IMAGE_TIMEOUT_S
        self.cache = cache if cache is not None else BinaryCache("images", suffix=".png")
        self.max_workers = max(1, int(max_workers or ccfg.IO_WORKERS))

    # ------------------------------------------------------------------ #
    def generate(self, concept: CollageConcept, prompts: CollagePrompts,
                 out_dir: str, attempt: int = 1) -> CollageAsset:
        """Génère (ou récupère en cache) l'image d'UNE scène."""
        os.makedirs(out_dir, exist_ok=True)
        target = os.path.join(out_dir, f"{concept.id}_a{attempt}.png")
        asset = CollageAsset(concept_id=concept.id, provider=self.provider.name,
                             attempts=attempt)

        # Le cache est indexé par le PROMPT (donc par style + concept + retry):
        # une correction de retry ne peut pas servir l'image fautive.
        cache_key = prompts.cache_key()
        cached = self.cache.get_bytes(cache_key)
        if cached:
            try:
                Path(target).write_bytes(cached)
                asset.image_path = target
                asset.from_cache = True
                asset.cost_estimate_usd = 0.0
                return asset
            except OSError as exc:
                logger.debug("[collage_image] cache illisible: %s", exc)

        try:
            image = self.provider.generate(
                prompts.image_prompt,
                aspect_ratio=prompts.aspect_ratio,
                negative_prompt=prompts.negative_prompt,
                timeout_s=self.timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 - jamais bloquant
            asset.failure_reason = _classify(exc)
            logger.warning("[collage_image] %s: génération échouée (%s)",
                           concept.id, str(exc)[:160])
            return asset

        data = self._materialize(image)
        if not data:
            asset.failure_reason = "empty_image"
            return asset
        try:
            Path(target).write_bytes(data)
        except OSError as exc:
            asset.failure_reason = f"write_failed:{exc}"[:120]
            return asset
        self.cache.set_bytes(cache_key, data)
        asset.image_path = target
        asset.model = image.model
        asset.provider = image.provider
        asset.cost_estimate_usd = image.cost_estimate_usd
        return asset

    # ------------------------------------------------------------------ #
    def generate_many(self, items: Sequence[tuple[CollageConcept, CollagePrompts]],
                      out_dir: str, attempt: int = 1) -> list[CollageAsset]:
        """Génère N images en parallèle (I/O bound → threads)."""
        if not items:
            return []
        if len(items) == 1 or self.max_workers == 1:
            return [self.generate(c, p, out_dir, attempt) for c, p in items]
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(items))) as pool:
            futures = [pool.submit(self.generate, c, p, out_dir, attempt)
                       for c, p in items]
            return [f.result() for f in futures]

    # ------------------------------------------------------------------ #
    def _materialize(self, image: GeneratedImage) -> Optional[bytes]:
        if image.bytes:
            return image.bytes
        if not image.url:
            return None
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.get(image.url)
            if resp.status_code >= 400:
                logger.warning("[collage_image] download %s", resp.status_code)
                return None
            return resp.content or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("[collage_image] download error: %s", str(exc)[:140])
            return None


# --------------------------------------------------------------------------- #
def _size_for(aspect_ratio: str) -> str:
    return {"9:16": "1024x1792", "16:9": "1792x1024",
            "1:1": "1024x1024", "4:5": "1024x1280"}.get(aspect_ratio, "1024x1024")


def _classify(exc: object) -> str:
    """Raison canonique d'échec — aligne le vocabulaire sur `genimg`."""
    try:
        from app.autoedit_engine.genimg import classify_image_error
        return classify_image_error(exc)
    except Exception:  # noqa: BLE001
        return "image_generation_failed"
