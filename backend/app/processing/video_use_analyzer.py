"""video-use integration for AutoEdit.

`video-use` is an npm MCP/CLI that extracts visual keyframes with timestamps.
AutoEdit uses it fail-soft: if the CLI is unavailable or fails, the render still
continues and records the error in pipeline results.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


class VideoUseAnalyzer:
    def __init__(self, workdir: str | os.PathLike[str]):
        self.workdir = Path(workdir)

    def extract_keyframes(self, video_path: str, max_frames: int = 48) -> dict[str, Any]:
        out_root = self.workdir / ".video-use"
        out_root.mkdir(parents=True, exist_ok=True)
        cmd = [
            "npx",
            "-y",
            "video-use",
            "frames",
            video_path,
            "--out-root",
            str(out_root),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except Exception as exc:
            return self._fallback_ffmpeg_keyframes(video_path, max_frames=max_frames, reason=str(exc))
        if result.returncode != 0:
            return self._fallback_ffmpeg_keyframes(
                video_path,
                max_frames=max_frames,
                reason=(result.stderr or result.stdout or "video-use failed")[:1000],
            )

        manifest_path = self._find_latest_manifest(out_root)
        if not manifest_path:
            return self._fallback_ffmpeg_keyframes(video_path, max_frames=max_frames, reason="video-use manifest not found")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"available": False, "error": f"manifest parse failed: {exc}", "frames_count": 0, "frames": []}

        frames = self._normalize_frames(manifest, manifest_path)[:max_frames]
        return {
            "available": True,
            "tool": "video-use",
            "manifest_path": str(manifest_path),
            "frames_count": len(frames),
            "frames": frames,
            "stats": manifest.get("stats", {}),
        }

    def _fallback_ffmpeg_keyframes(self, video_path: str, max_frames: int, reason: str) -> dict[str, Any]:
        """Fallback keyframe extraction when the external video-use CLI changes output format.

        The result remains marked as available because AutoEdit still has timestamped
        visual frames to feed downstream analysis. `tool_error` preserves the original
        video-use issue for diagnostics.
        """
        frames_dir = self.workdir / ".video-use" / "fallback_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        fps = max(1, min(max_frames, 48)) / max(self._probe_duration(video_path), 1.0)
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            video_path,
            "-vf",
            f"fps={fps:.6f},scale=360:-1",
            "-frames:v",
            str(max_frames),
            str(frames_dir / "frame_%04d.jpg"),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=True)
        except Exception as exc:
            return {"available": False, "error": f"{reason}; ffmpeg fallback failed: {exc}", "frames_count": 0, "frames": []}

        files = sorted(frames_dir.glob("frame_*.jpg"))[:max_frames]
        duration = self._probe_duration(video_path)
        step = duration / max(len(files), 1)
        frames = [
            {"path": str(path.resolve()), "timestamp": round(i * step, 3), "index": i}
            for i, path in enumerate(files)
        ]
        manifest_path = frames_dir / "manifest.json"
        manifest_path.write_text(json.dumps({"frames": frames, "tool_error": reason}, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "available": True,
            "tool": "video-use+ffmpeg-fallback",
            "tool_error": reason,
            "manifest_path": str(manifest_path),
            "frames_count": len(frames),
            "frames": frames,
            "stats": {"duration": duration},
        }

    def _probe_duration(self, video_path: str) -> float:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            return float(result.stdout.strip())
        except Exception:
            return 1.0

    def _find_latest_manifest(self, out_root: Path) -> Path | None:
        manifests = sorted(out_root.glob("frames/*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return manifests[0] if manifests else None

    def _normalize_frames(self, manifest: dict[str, Any], manifest_path: Path) -> list[dict[str, Any]]:
        base = manifest_path.parent
        frames = []
        for i, frame in enumerate(manifest.get("frames") or manifest.get("keyframes") or []):
            if isinstance(frame, str):
                path = frame
                ts = None
            else:
                path = frame.get("path") or frame.get("file") or frame.get("filename")
                ts = frame.get("timestamp") or frame.get("time") or frame.get("timeSec") or frame.get("seconds") or frame.get("t")
            if path and not os.path.isabs(str(path)):
                path = str((base / str(path)).resolve())
            try:
                ts = float(ts) if ts is not None else None
            except (TypeError, ValueError):
                ts = None
            frames.append({"path": path, "timestamp": ts, "index": i})
        return frames
