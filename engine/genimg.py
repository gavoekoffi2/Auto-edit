"""
STEP 6 (a) — AI B-roll image generation (OpenRouter / gemini-2.5-flash-image).

Number of illustrations is DYNAMIC, never fixed: ~1 image per 5 s of speech
(n ~= output_duration / 5).  One image = one strong idea; long topics get
several.  A strong theme is never left without an illustration.

    POST https://openrouter.ai/api/v1/chat/completions
    body: {"model": "google/gemini-2.5-flash-image",
           "messages": [{"role":"user","content": STYLE + prompt}],
           "modalities": ["image","text"]}
    reply: choices[0].message.images[0].image_url.url  (base64 data URI)

Usage:
    python -m engine.genimg --from-vu transcripts/v_vu.json --outdir broll
    python -m engine.genimg ideas.json --outdir broll
    (requires OPENROUTER_API_KEY)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from typing import List, Optional

import requests

from . import config
from . import content


def _decode_image_payload(url: str) -> bytes:
    """Decode a base64 data URI, or download an http(s) URL."""
    if url.startswith("data:"):
        b64 = url.split(",", 1)[1]
        return base64.b64decode(b64)
    if url.startswith("http"):
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        return resp.content
    raise RuntimeError(f"unrecognised image url: {url[:40]}...")


def _extract_image_url(data: dict) -> str:
    """Pull the image URL out of the (slightly variable) OpenRouter reply."""
    msg = data["choices"][0]["message"]
    images = msg.get("images") or []
    if images:
        img = images[0]
        if isinstance(img, dict):
            return img.get("image_url", {}).get("url") or img.get("url")
        return img
    # Some models inline a data URI in the text content.
    content_field = msg.get("content")
    if isinstance(content_field, str) and "data:image" in content_field:
        start = content_field.index("data:image")
        return content_field[start:].split(")")[0].split('"')[0].strip()
    raise RuntimeError("no image found in OpenRouter response")


def generate_image(prompt: str, out_path: str, api_key: str,
                   retries: int = 3) -> str:
    """Generate one image for *prompt* and save it to *out_path*."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": config.OPENROUTER_IMAGE_MODEL,
        "messages": [{"role": "user", "content": config.BROLL_STYLE_PREFIX + prompt}],
        "modalities": ["image", "text"],
    }

    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = requests.post(config.OPENROUTER_URL, headers=headers,
                                 json=body, timeout=180)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:300]}")
            url = _extract_image_url(resp.json())
            raw = _decode_image_payload(url)
            with open(out_path, "wb") as fh:
                fh.write(raw)
            return out_path
        except Exception as exc:  # noqa: BLE001 - retry with backoff
            last_err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"image generation failed for '{prompt[:40]}': {last_err}")


def generate_brolls(ideas: List[dict], outdir: str, api_key: Optional[str] = None) -> List[dict]:
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for image generation")
    os.makedirs(outdir, exist_ok=True)

    out: List[dict] = []
    for idea in ideas:
        png = os.path.join(outdir, f"{idea['id']}.png")
        try:
            generate_image(idea["prompt"], png, api_key)
            out.append({**idea, "image": png})
            print(f"[genimg] {idea['id']} '{idea['prompt'][:40]}' -> {png}")
        except Exception as exc:  # noqa: BLE001 - skip a failed idea, keep going
            print(f"[genimg] WARN {idea['id']} failed: {exc}", file=sys.stderr)
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Generate AI B-roll images (OpenRouter)")
    ap.add_argument("ideas", nargs="?", help="JSON list of {id,prompt} ideas")
    ap.add_argument("--from-vu", help="derive ideas from a transcript _vu.json")
    ap.add_argument("--n", type=int, help="force number of images (default: duration/5)")
    ap.add_argument("--outdir", default="broll")
    ap.add_argument("--dump-ideas", help="write derived ideas and exit (no API calls)")
    args = ap.parse_args(argv)

    if args.from_vu:
        vu = json.load(open(args.from_vu, encoding="utf-8"))
        ideas = content.derive_broll_ideas(vu, n=args.n)
    elif args.ideas:
        ideas = json.load(open(args.ideas, encoding="utf-8"))
    else:
        ap.error("provide ideas.json or --from-vu")

    if args.dump_ideas:
        json.dump(ideas, open(args.dump_ideas, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[genimg] {len(ideas)} ideas -> {args.dump_ideas}")
        return 0

    rendered = generate_brolls(ideas, args.outdir)
    json.dump(rendered, open(os.path.join(args.outdir, "_broll_images.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"[genimg] {len(rendered)}/{len(ideas)} images generated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
