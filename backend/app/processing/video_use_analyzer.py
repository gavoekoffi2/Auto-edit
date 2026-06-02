"""video-use integration for AutoEdit.

The upstream `video-use` package is an MCP/CLI focused on extracting key frames
with timestamps so agents can analyze the visual content of a video. AutoEdit
uses it as an optional analysis layer: when available, it writes a manifest of
representative frames that can be used for future visual scoring, B-roll timing,
and QA. It intentionally fails soft so a missing npm binary never blocks a paid
render.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VideoUseAnalyzer:
    def __init__(self, workdir: str, timeout_s: int = 240):
        self.workdir = Path(workdir)
        self.timeout_s = timeout_s

    def extract_keyframes(self, video_path: str, max_frames: int = 48) -> dict[str, Any]:
        """Run `video-use extract` and return a compact manifest summary.

        `video-use` versions differ slightly in flags, so the integration uses
        the stable command shape from the official README and then discovers the
        latest `.video-use/frames/*/manifest.json` produced under `workdir`.
        """
        self.workdir.mkdir(parents=True, exist_ok=True)
        cmd = self._command(video_path, max_frames=max_frames)
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("[video_use] extract failed: %s", exc)
            return {"available": False, "error": str(exc), "frames_count": 0, "frames": []}

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "video-use failed").strip()[-1000:]
            logger.warning("[video_use] CLI returned %s: %s", proc.returncode, err)
            return {"available": False, "error": err, "frames_count": 0, "frames": []}

        manifest_path = self._latest_manifest()
        if not manifest_path:
            return {
                "available": False,
                "error": "video-use completed but no manifest.json was found",
                "frames_count": 0,
                "frames": [],
            }

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"available": False, "error": f"manifest parse failed: {exc}", "frames_count": 0, "frames": []}

        frames = self._normalize_frames(manifest, manifest_path=manifest_path)[:max_frames]
        return {
            "available": True,
            "tool": "video-use",
            "manifest_path": str(manifest_path),
            "frames_count": len(frames),
            "frames": frames,
        }

    def _command(self, video_path: str, max_frames: int) -> list[str]:
        local_bin = self.workdir / "node_modules" / ".bin" / "video-use"
        if local_bin.exists():
            return [str(local_bin), "extract", video_path]
        if shutil.which("video-use"):
            return ["video-use", "extract", video_path]
        # npx keeps deployment simple. --yes avoids an interactive prompt.
        return ["npx", "--yes", "video-use", "extract", video_path]

    def _latest_manifest(self) -> Path | None:
        base = self.workdir / ".video-use" / "frames"
        if not base.exists():
            return None
        manifests = sorted(
            base.glob("*/manifest.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return manifests[0] if manifests else None

    def _normalize_frames(self, manifest: dict[str, Any], manifest_path: Path | None = None) -> list[dict[str, Any]]:
        raw_frames = manifest.get("frames") or manifest.get("keyframes") or []
        frame_base = manifest_path.parent if manifest_path else self.workdir
        frames: list[dict[str, Any]] = []
        for i, frame in enumerate(raw_frames):
            if isinstance(frame, str):
                frames.append({"path": frame, "timestamp": None, "index": i})
                continue
            if not isinstance(frame, dict):
                continue
            ts = (
                frame.get("timestamp")
                or frame.get("time")
                or frame.get("timeSec")
                or frame.get("seconds")
                or frame.get("t")
            )
            try:
                ts = float(ts) if ts is not None else None
            except (TypeError, ValueError):
                ts = None
            path = frame.get("path") or frame.get("file") or frame.get("filename")
            if path and not os.path.isabs(str(path)):
                path = str((frame_base / str(path)).resolve())
            frames.append({"path": path, "timestamp": ts, "index": i})
        return frames
