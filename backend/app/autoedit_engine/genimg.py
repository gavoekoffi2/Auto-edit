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


# Canonical reasons the paid image step can be skipped / fall back. Used by the
# pipeline to populate the job summary's `fallbackReason`.
FALLBACK_REASONS = {
    "insufficient_credits", "quota_exceeded", "payment_required",
    "rate_limited", "timeout", "provider_unavailable", "missing_api_key",
    "image_generation_failed", "disabled", "no_ideas",
}


def classify_image_error(exc: object) -> str:
    """Map an image-generation failure to a canonical fallback reason.

    Recognises the common provider failure modes (insufficient credits, quota,
    402/429, timeouts, provider down, missing key) so the pipeline can keep
    rendering in credit-saver mode and report WHY the AI images were skipped —
    never turning any of these into a hard render failure.
    """
    msg = str(exc).lower()
    if "openrouter_api_key" in msg or "api key" in msg or "api_key" in msg or "missing key" in msg:
        return "missing_api_key"
    if "insufficient" in msg and ("credit" in msg or "fund" in msg or "balance" in msg):
        return "insufficient_credits"
    if "credit" in msg and ("exhaust" in msg or "no " in msg or "out of" in msg):
        return "insufficient_credits"
    if "402" in msg or "payment required" in msg:
        return "payment_required"
    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return "rate_limited"
    if "quota" in msg or "limit exceeded" in msg or "exceeded your" in msg:
        return "quota_exceeded"
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if ("unavailable" in msg or "503" in msg or "502" in msg or "500" in msg
            or "connection" in msg or "could not connect" in msg):
        return "provider_unavailable"
    return "image_generation_failed"


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
                   retries: int = 3, style_prefix: Optional[str] = None) -> str:
    """Generate one image for *prompt* and save it to *out_path*."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    prefix = config.BROLL_STYLE_PREFIX if style_prefix is None else style_prefix
    body = {
        "model": config.OPENROUTER_IMAGE_MODEL,
        "messages": [{"role": "user", "content": prefix + prompt}],
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


# --------------------------------------------------------------------------- #
# prompt precision — a cheap text model turns each spoken excerpt into a
# LITERAL visual scene before image generation, so the picture shows exactly
# what is being said at that timestamp (heuristic prompt kept as fallback).
# --------------------------------------------------------------------------- #
def refine_prompts(items: List[dict], api_key: str, *,
                   kind: str = "photo") -> List[dict]:
    if not config.PROMPT_REFINER_ENABLED or not items:
        return items
    style = ("realistic editorial photograph" if kind == "photo"
             else "cinema-quality 3D rendered scene (CGI animation still), "
                  "no text in the image")
    numbered = "\n".join(
        f'{i}. "{it.get("excerpt") or it["prompt"][:180]}"' for i, it in enumerate(items)
    )
    instruction = (
        "You write image-generation scene descriptions for a video editor.\n"
        f"For EACH spoken excerpt below (French), describe ONE {style} that shows "
        "LITERALLY and CONCRETELY what the speaker is saying at that moment — the "
        "exact objects, actions and people mentioned, never a generic stock scene. "
        "One line per item, 25-45 English words, no camera jargon, no quotes.\n"
        "Answer ONLY with a JSON array of strings, same order and count as the "
        f"{len(items)} items.\n\nExcerpts:\n{numbered}"
    )
    try:
        resp = requests.post(
            config.OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": config.PROMPT_REFINER_MODEL,
                  "messages": [{"role": "user", "content": instruction}]},
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"refiner {resp.status_code}")
        text = resp.json()["choices"][0]["message"]["content"] or ""
        start, end = text.find("["), text.rfind("]")
        scenes = json.loads(text[start:end + 1])
        if not isinstance(scenes, list) or len(scenes) != len(items):
            raise RuntimeError("refiner shape mismatch")
        refined: List[dict] = []
        for it, scene in zip(items, scenes):
            if isinstance(scene, str) and len(scene.split()) >= 8:
                suffix = it["prompt"].split("Visual direction:")[-1] if "Visual direction:" in it["prompt"] else ""
                new_prompt = scene.strip().rstrip(".") + "."
                if suffix:
                    new_prompt += f" Visual direction: {suffix.strip()}"
                refined.append({**it, "prompt": new_prompt, "prompt_refined": True})
            else:
                refined.append(it)
        n_ok = sum(1 for r in refined if r.get("prompt_refined"))
        print(f"[genimg] prompt refiner: {n_ok}/{len(items)} prompts upgraded "
              f"({config.PROMPT_REFINER_MODEL})")
        return refined
    except Exception as exc:  # noqa: BLE001 - heuristic prompts still work
        print(f"[genimg] WARN prompt refiner skipped: {exc}", file=sys.stderr)
        return items


def generate_brolls(ideas: List[dict], outdir: str, api_key: Optional[str] = None) -> List[dict]:
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for image generation")
    os.makedirs(outdir, exist_ok=True)

    ideas = ideas[: config.MAX_BROLL_IMAGES]      # hard API budget cap
    ideas = refine_prompts(ideas, api_key, kind="photo")

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


def select_3d_style_prefix(style_seed_text: Optional[str]) -> str:
    """Pick the 3D illustration style template for THIS video.

    Seeded by the transcript/job id so a given render is reproducible while
    different videos rotate across the MOTION_STYLE_3D_PREFIXES templates —
    the montages never share the same motion-design illustration style.
    """
    prefixes = config.MOTION_STYLE_3D_PREFIXES
    if not style_seed_text:
        return prefixes[0]
    import hashlib
    h = int(hashlib.md5(style_seed_text.encode("utf-8")).hexdigest(), 16)
    return prefixes[h % len(prefixes)]


def pick_motion_3d_style(seed_text: Optional[str]) -> dict:
    """Retourne la vue nommée du style choisi par le nouveau sélecteur.

    Cette API de compatibilité réutilise exactement la même sélection, afin
    qu'une seed donnée conserve le même rendu dans les anciens appels.
    """
    prefix = select_3d_style_prefix(seed_text)
    index = config.MOTION_STYLE_3D_PREFIXES.index(prefix)
    return config.MOTION_3D_STYLES[index]


def generate_illustrations(scenes: List[dict], outdir: str,
                           api_key: Optional[str] = None,
                           style_seed_text: Optional[str] = None) -> List[dict]:
    """Generate 3D-rendered illustrations for the TOP-priority motion scenes.

    The visual style is a REAL 3D animation look (no more flat 2D cartoon):
    one of several 3D style templates is chosen per video via
    *style_seed_text* so consecutive montages don't look alike.

    API budget: only the MOTION_AI_ILLUSTRATIONS_MAX most important beats get
    an AI image — every other scene uses the free procedural line-art drawing.
    A failed generation simply leaves the scene without an ``image`` key, so
    the montage never loses its illustrated beats.
    """
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key or config.MOTION_AI_ILLUSTRATIONS_MAX <= 0:
        return scenes
    os.makedirs(outdir, exist_ok=True)
    style_prefix = select_3d_style_prefix(style_seed_text)

    ranked = sorted(scenes, key=lambda s: float(s.get("priority", 0.0)), reverse=True)
    chosen = {s["id"] for s in ranked[: config.MOTION_AI_ILLUSTRATIONS_MAX]}
    to_generate = [s for s in scenes if s["id"] in chosen]
    refined = {s["id"]: s for s in refine_prompts(to_generate, api_key, kind="illustration")}

    out: List[dict] = []
    for scene in scenes:
        if scene["id"] not in chosen:
            out.append(dict(scene))
            continue
        scene = refined.get(scene["id"], scene)
        png = os.path.join(outdir, f"{scene['id']}.png")
        try:
            generate_image(scene["prompt"], png, api_key,
                           style_prefix=style_prefix)
            out.append({**scene, "image": png})
            print(f"[genimg] illustration {scene['id']} -> {png}")
        except Exception as exc:  # noqa: BLE001 - procedural fallback takes over
            print(f"[genimg] WARN illustration {scene['id']} failed "
                  f"(procedural fallback): {exc}", file=sys.stderr)
            out.append(dict(scene))
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
