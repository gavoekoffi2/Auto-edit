"""Local and generated raster assets — the last resort of the asset chain.

The engine must be able to produce every scene without a single API call, so
everything here is optional and every failure is non-fatal.
"""
from __future__ import annotations

import glob
import os
import sys
from functools import lru_cache
from typing import List, Optional

from PIL import Image

# Repository-local asset roots, searched in order.
_ROOTS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "assets_data", "images"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "autoedit_engine", "assets"),
]

_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


@lru_cache(maxsize=256)
def find_local(name: str) -> Optional[str]:
    """A bundled image whose filename matches *name*, if one exists."""
    if not name:
        return None
    needle = str(name).strip().lower().replace(" ", "_")
    for root in _ROOTS:
        if not os.path.isdir(root):
            continue
        for ext in _EXTENSIONS:
            matches = glob.glob(os.path.join(root, "**", f"*{needle}*{ext}"),
                                recursive=True)
            if matches:
                return sorted(matches)[0]
    return None


def load(path: str, max_side: int = 1600) -> Optional[Image.Image]:
    """Open an image as RGBA, downscaled to a sane working size."""
    if not path or not os.path.exists(path):
        return None
    try:
        with Image.open(path) as raw:
            image = raw.convert("RGBA")
    except (OSError, ValueError) as exc:
        print(f"[illustration_engine] WARN cannot read image {path}: {exc}",
              file=sys.stderr)
        return None
    if max(image.size) > max_side:
        ratio = max_side / float(max(image.size))
        image = image.resize((max(1, int(image.width * ratio)),
                              max(1, int(image.height * ratio))),
                             Image.LANCZOS)
    return image


def cover(image: Image.Image, width: int, height: int) -> Image.Image:
    """Scale-and-crop to exactly fill a box, without distortion."""
    if image.width <= 0 or image.height <= 0:
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ratio = max(width / image.width, height / image.height)
    resized = image.resize((max(1, int(image.width * ratio)),
                            max(1, int(image.height * ratio))), Image.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def generate(prompt: str, out_path: str, style_hint: str = "") -> Optional[str]:
    """Optional AI illustration. Returns None whenever generation is not
    available — which is the normal case in offline mode.

    It reuses CutForge's existing image provider rather than adding a second
    integration, so quota accounting and error classification stay in one place.
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        return None
    try:
        from ...autoedit_engine import genimg
    except Exception:  # noqa: BLE001 - engine must not hard-depend on this
        return None
    generator = getattr(genimg, "generate_image", None)
    if not callable(generator):
        return None
    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        result = generator(f"{style_hint} {prompt}".strip(), out_path)
    except Exception as exc:  # noqa: BLE001 - never fail a render over an image
        print(f"[illustration_engine] WARN image generation failed: {exc}",
              file=sys.stderr)
        return None
    path = result if isinstance(result, str) else out_path
    return path if path and os.path.exists(path) else None
