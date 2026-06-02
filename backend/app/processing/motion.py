"""
Motion-design module.

Drives the Remotion project (../remotion) to generate professional motion
graphics — animated branded intros, end-screens, word-by-word animated caption
overlays and lower-thirds — then composites them onto the source footage with
ffmpeg.

Design goals:
  * Match the source video's resolution / fps / duration automatically.
  * Be *graceful*: if Node/Remotion/ffmpeg are unavailable or a render fails,
    log a warning and return the original video unchanged so the overall
    editing job never fails because of motion design.
"""
import os
import json
import shutil
import signal
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Defaults — overridable via the job's motion config.
DEFAULT_INTRO_SECONDS = 2.5
DEFAULT_OUTRO_SECONDS = 3.0
DEFAULT_PRIMARY = "#6366f1"
DEFAULT_ACCENT = "#ec4899"
DEFAULT_TEXT = "#ffffff"

_REMOTION_ENTRY = "src/index.ts"


# --------------------------------------------------------------------------- #
# Environment / probing helpers
# --------------------------------------------------------------------------- #
def _remotion_dir() -> Optional[str]:
    """Resolve the Remotion project directory, honoring REMOTION_DIR."""
    candidates = [
        os.environ.get("REMOTION_DIR"),
        "/app/remotion",
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "remotion")
        ),
    ]
    for c in candidates:
        if c and os.path.isdir(c) and os.path.exists(os.path.join(c, _REMOTION_ENTRY)):
            return c
    return None


def motion_available() -> bool:
    """True only if everything needed to render motion graphics is present."""
    if shutil.which("npx") is None:
        logger.warning("Motion design unavailable: 'npx' (Node.js) not found")
        return False
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        logger.warning("Motion design unavailable: ffmpeg/ffprobe not found")
        return False
    rdir = _remotion_dir()
    if rdir is None:
        logger.warning("Motion design unavailable: remotion project not found")
        return False
    if not os.path.isdir(os.path.join(rdir, "node_modules")):
        logger.warning(
            "Motion design unavailable: run 'npm install' in the remotion project"
        )
        return False
    return True


def _probe_video(video_path: str) -> dict:
    """Return width, height, fps, duration(s) and whether the file has audio."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,avg_frame_rate,codec_type",
        "-show_entries", "format=duration",
        "-of", "json", video_path,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {out.stderr}")
    data = json.loads(out.stdout)

    width = height = 0
    fps = 30.0
    has_audio = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and not width:
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            rate = stream.get("avg_frame_rate", "30/1")
            try:
                num, den = rate.split("/")
                fps = float(num) / float(den) if float(den) else 30.0
            except (ValueError, ZeroDivisionError):
                fps = 30.0
        elif stream.get("codec_type") == "audio":
            has_audio = True

    duration = float(data.get("format", {}).get("duration", 0) or 0)
    if not width or not height:
        raise RuntimeError("Could not determine video dimensions")

    # Clamp fps to a sane integer for Remotion compositions.
    fps_int = max(1, min(60, round(fps)))
    return {
        "width": width,
        "height": height,
        "fps": fps_int,
        "duration": duration,
        "has_audio": has_audio,
    }


# --------------------------------------------------------------------------- #
# Remotion render
# --------------------------------------------------------------------------- #
def _render_composition(
    comp_id: str,
    output_path: str,
    props: dict,
    work_dir: str,
    alpha: bool = False,
    timeout: int = 600,
) -> None:
    """Render a single composition with `npx remotion render`."""
    remotion_dir = _remotion_dir()
    props_file = os.path.abspath(os.path.join(work_dir, f"props_{comp_id}.json"))
    output_path = os.path.abspath(output_path)
    with open(props_file, "w", encoding="utf-8") as f:
        json.dump(props, f)

    cmd = [
        "npx", "remotion", "render",
        _REMOTION_ENTRY, comp_id, output_path,
        f"--props={props_file}",
        "--log=error",
    ]
    concurrency = os.environ.get("REMOTION_CONCURRENCY")
    if concurrency:
        cmd.append(f"--concurrency={concurrency}")

    if alpha:
        # Transparent overlay → ProRes 4444 + yuva444p10le preserves the alpha
        # channel. WITHOUT --pixel-format=yuva444p10le the render is opaque and
        # the overlay would paint a solid black frame over the whole video.
        cmd += [
            "--codec=prores",
            "--prores-profile=4444",
            "--image-format=png",
            "--pixel-format=yuva444p10le",
        ]
    else:
        cmd += ["--codec=h264"]

    logger.info("Rendering Remotion composition '%s' -> %s", comp_id, output_path)
    effective_timeout = max(timeout, 1800) if alpha else timeout
    proc = subprocess.Popen(
        cmd,
        cwd=remotion_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=effective_timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            stdout, stderr = proc.communicate()
        raise RuntimeError(
            f"Remotion render of '{comp_id}' timed out after {effective_timeout}s: {str(exc)}"
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"Remotion render of '{comp_id}' failed: {stderr[-1000:]}"
        )
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(f"Remotion produced empty output for '{comp_id}'")


# --------------------------------------------------------------------------- #
# ffmpeg compositing helpers
# --------------------------------------------------------------------------- #
def _run_ffmpeg(cmd: list, timeout: int = 1200) -> None:
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, start_new_session=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-1000:]}")


def _overlay_captions(main_path: str, overlay_path: str, output_path: str) -> None:
    """Composite a transparent caption overlay on top of the main video."""
    cmd = [
        "ffmpeg", "-y",
        "-i", main_path,
        "-i", overlay_path,
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    _run_ffmpeg(cmd)


def _concat_segments(
    intro: Optional[str],
    main: str,
    outro: Optional[str],
    meta: dict,
    output_path: str,
) -> None:
    """
    Concatenate intro + main + outro, normalizing every segment to the same
    resolution / fps / SAR and guaranteeing each has an audio track (silent for
    intro/outro and for a main video that has no audio).
    """
    w, h, fps = meta["width"], meta["height"], meta["fps"]
    inputs: list = []
    video_labels: list = []
    audio_labels: list = []
    filters: list = []
    silent_inputs: list = []  # (-f lavfi -t <dur> -i anullsrc...)
    idx = 0

    def add_clip(path: str, duration: float, real_audio: bool):
        nonlocal idx
        inputs.extend(["-i", path])
        v_in = idx
        idx += 1
        filters.append(
            f"[{v_in}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},"
            f"format=yuv420p[v{v_in}]"
        )
        video_labels.append(f"[v{v_in}]")
        if real_audio:
            audio_labels.append(f"[{v_in}:a]")
        else:
            # Reserve a silent audio input; resolved after all -i clips added.
            silent_inputs.append((v_in, duration))

    if intro:
        add_clip(intro, meta.get("intro_seconds", DEFAULT_INTRO_SECONDS), False)
    add_clip(main, meta["duration"], meta["has_audio"])
    if outro:
        add_clip(outro, meta.get("outro_seconds", DEFAULT_OUTRO_SECONDS), False)

    # Append anullsrc inputs for every clip lacking real audio.
    silent_map: dict = {}
    for v_in, dur in silent_inputs:
        inputs.extend([
            "-f", "lavfi", "-t", f"{max(0.1, dur):.3f}",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        ])
        silent_map[v_in] = idx
        idx += 1

    # Build the ordered audio label list (real or silent) per clip.
    ordered_audio: list = []
    real_iter = iter(audio_labels)
    for vlabel in video_labels:
        v_in = int(vlabel.strip("[]v"))
        if v_in in silent_map:
            ordered_audio.append(f"[{silent_map[v_in]}:a]")
        else:
            ordered_audio.append(next(real_iter))

    n = len(video_labels)
    concat_inputs = "".join(
        f"{video_labels[i]}{ordered_audio[i]}" for i in range(n)
    )
    filters.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")

    cmd = ["ffmpeg", "-y", *inputs,
           "-filter_complex", ";".join(filters),
           "-map", "[outv]", "-map", "[outa]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k",
           output_path]
    _run_ffmpeg(cmd)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def add_motion_graphics(
    video_path: str,
    output_dir: str,
    motion_config: dict,
    transcription: Optional[dict] = None,
    scenes: Optional[dict] = None,
) -> dict:
    """
    Add motion graphics to a video.

    motion_config keys (all optional):
        intro: bool | dict(title, subtitle)
        outro: bool | dict(title, call_to_action, handle)
        animated_captions: bool
        primary_color, accent_color, text_color: hex strings
        caption_position: "bottom" | "center" | "top"
        font_scale: float
        intro_seconds, outro_seconds: float

    Returns dict with output_path (the new video) and the elements applied.
    Falls back to the original video on any failure.
    """
    result: dict = {"elements": [], "output_path": video_path}

    if not motion_available():
        result["skipped"] = "motion design dependencies unavailable"
        return result

    try:
        meta = _probe_video(video_path)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Motion design skipped, probe failed: %s", e)
        result["skipped"] = f"probe failed: {e}"
        return result

    fps = meta["fps"]
    brand = {
        "primaryColor": motion_config.get("primary_color", DEFAULT_PRIMARY),
        "accentColor": motion_config.get("accent_color", DEFAULT_ACCENT),
        "textColor": motion_config.get("text_color", DEFAULT_TEXT),
    }
    dims = {"width": meta["width"], "height": meta["height"], "fps": fps}
    work = os.path.join(output_dir, "_motion")
    os.makedirs(work, exist_ok=True)

    current = video_path

    # 1) Animated captions overlay (needs transcript segments) ------------- #
    if motion_config.get("animated_captions") and transcription:
        segments = transcription.get("segments") or []
        if segments:
            try:
                overlay = os.path.join(work, "captions.mov")
                caption_props = {
                    **dims, **brand,
                    "segments": segments,
                    "position": motion_config.get("caption_position", "bottom"),
                    "fontScale": float(motion_config.get("font_scale", 1.0)),
                    "durationInFrames": max(1, round(meta["duration"] * fps)),
                }
                # Pass through caption-style, font-family, and animation
                # intensity so the Remotion compositions can render the right
                # look.
                if motion_config.get("caption_style"):
                    caption_props["captionStyle"] = motion_config["caption_style"]
                if motion_config.get("font_family"):
                    caption_props["fontFamily"] = motion_config["font_family"]
                if motion_config.get("animation_intensity"):
                    caption_props["animationIntensity"] = motion_config["animation_intensity"]

                _render_composition(
                    "Captions", overlay, caption_props,
                    work, alpha=True,
                )
                captioned = os.path.join(work, "captioned.mp4")
                _overlay_captions(current, overlay, captioned)
                current = captioned
                result["elements"].append("animated_captions")
            except Exception as e:
                logger.warning("Animated captions failed: %s", e)
                result["captions_error"] = str(e)

    # 2) Intro --------------------------------------------------------------- #
    intro_path = None
    intro_cfg = motion_config.get("intro")
    if intro_cfg:
        try:
            cfg = intro_cfg if isinstance(intro_cfg, dict) else {}
            intro_secs = float(motion_config.get("intro_seconds", DEFAULT_INTRO_SECONDS))
            intro_path = os.path.join(work, "intro.mp4")
            _render_composition(
                "Intro", intro_path,
                {
                    **dims, **brand,
                    "title": cfg.get("title", "AutoEdit"),
                    "subtitle": cfg.get("subtitle", ""),
                    "durationInFrames": max(1, round(intro_secs * fps)),
                },
                work, alpha=False,
            )
            result["elements"].append("intro")
        except Exception as e:
            logger.warning("Intro render failed: %s", e)
            result["intro_error"] = str(e)
            intro_path = None

    # 3) Outro --------------------------------------------------------------- #
    outro_path = None
    outro_cfg = motion_config.get("outro")
    if outro_cfg:
        try:
            cfg = outro_cfg if isinstance(outro_cfg, dict) else {}
            outro_secs = float(motion_config.get("outro_seconds", DEFAULT_OUTRO_SECONDS))
            outro_path = os.path.join(work, "outro.mp4")
            _render_composition(
                "Outro", outro_path,
                {
                    **dims, **brand,
                    "title": cfg.get("title", "Thanks for watching"),
                    "callToAction": cfg.get("call_to_action", "Subscribe"),
                    "handle": cfg.get("handle", ""),
                    "durationInFrames": max(1, round(outro_secs * fps)),
                },
                work, alpha=False,
            )
            result["elements"].append("outro")
        except Exception as e:
            logger.warning("Outro render failed: %s", e)
            result["outro_error"] = str(e)
            outro_path = None

    # 4) Concatenate intro + main(+captions) + outro ------------------------ #
    if intro_path or outro_path:
        try:
            final = os.path.join(output_dir, "motion_output.mp4")
            concat_meta = {
                **meta,
                "intro_seconds": float(motion_config.get("intro_seconds", DEFAULT_INTRO_SECONDS)),
                "outro_seconds": float(motion_config.get("outro_seconds", DEFAULT_OUTRO_SECONDS)),
                # main may now have audio guaranteed if it was captioned (libx264/aac)
            }
            _concat_segments(intro_path, current, outro_path, concat_meta, final)
            current = final
        except Exception as e:
            logger.warning("Motion concat failed, keeping inner video: %s", e)
            result["concat_error"] = str(e)

    # 5) Transition wipes between scenes ---------------------------------- #
    scene_list = (scenes or {}).get("scenes", []) if isinstance(scenes, dict) else (scenes or [])
    if motion_config.get("transitions") and scene_list:
        try:
            current = _insert_transition_wipes(
                current, scene_list, dims, brand, motion_config, work, fps
            )
            result["elements"].append("transition_wipes")
        except Exception as e:
            logger.warning("Transition wipes failed: %s", e)
            result["transitions_error"] = str(e)

    result["output_path"] = current
    return result


# --------------------------------------------------------------------------- #
# Transition wipes helper
# --------------------------------------------------------------------------- #
def _insert_transition_wipes(
    video_path: str,
    scenes: list[dict],
    dims: dict,
    brand: dict,
    motion_config: dict,
    work_dir: str,
    fps: int,
) -> str:
    """
    Render TransitionWipe compositions for each scene boundary and splice
    them into the video using ffmpeg.

    Each scene dict is expected to have at least a ``start_time`` (float,
    seconds) key.  The wipe is rendered as a short transparent overlay that
    is composited at each boundary.
    """
    if len(scenes) < 2:
        return video_path

    wipe_dur = float(motion_config.get("transition_duration", 0.5))
    wipe_frames = max(1, round(wipe_dur * fps))
    wipe_dir = os.path.join(work_dir, "wipes")
    os.makedirs(wipe_dir, exist_ok=True)

    wipe_path = os.path.join(wipe_dir, "wipe.mov")
    wipe_props = {
        **dims,
        **brand,
        "durationInFrames": wipe_frames,
    }
    if motion_config.get("caption_style"):
        wipe_props["captionStyle"] = motion_config["caption_style"]
    if motion_config.get("animation_intensity"):
        wipe_props["animationIntensity"] = motion_config["animation_intensity"]

    _render_composition("TransitionWipe", wipe_path, wipe_props, wipe_dir, alpha=True)

    # Overlay the wipe at each scene boundary using ffmpeg.
    current = video_path
    for idx, scene in enumerate(scenes[1:], start=1):
        ts = float(scene.get("start", 0))
        if ts <= 0:
            continue
        overlay_start = max(0, ts - wipe_dur / 2)
        out = os.path.join(wipe_dir, f"wipe_applied_{idx}.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", current,
            "-i", wipe_path,
            "-filter_complex",
            (
                f"[1:v]setpts=PTS+{overlay_start}/TB[wv];"
                f"[0:v][wv]overlay=0:0:enable='between(t,{overlay_start},{overlay_start + wipe_dur})':format=auto[v]"
            ),
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            out,
        ]
        _run_ffmpeg(cmd)
        current = out

    return current
