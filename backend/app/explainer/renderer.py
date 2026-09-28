"""Rendu Chromium (Node) de la page: repères SFX, images fixes, vidéo en tranches parallèles."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

RENDER_JS = str(Path(__file__).resolve().parent / "web" / "render.js")


def _node_env() -> dict[str, str]:
    env = dict(os.environ)
    paths = [p for p in [os.environ.get("EXPLAINER_NODE_PATH"), "/app/templates/hyperframes/node_modules",
                         str(Path(__file__).resolve().parents[3] / "templates" / "hyperframes" / "node_modules")]
             if p and os.path.isdir(p)]
    if paths:
        env["NODE_PATH"] = os.pathsep.join(paths + [env.get("NODE_PATH", "")]).strip(os.pathsep)
    return env


def _run(args: list[str], timeout: int = 3600) -> None:
    r = subprocess.run(["node", RENDER_JS, *args], env=_node_env(), capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"render.js a échoué: {r.stderr[-800:]}")


def events(page: str, out_json: str) -> dict:
    _run([page, "--events", out_json], timeout=300)
    return json.loads(Path(out_json).read_text())


def stills(page: str, times: list[float], outdir: str, alpha: bool = False) -> list[str]:
    _run([page, "--stills", ",".join(f"{t:.2f}" for t in times), "--outdir", outdir] + (["--alpha", "1"] if alpha else []), timeout=600)
    return sorted(str(p) for p in Path(outdir).glob("still_*.png"))


def video(page: str, duration: float, out_mp4: str, *, fps: int = 30, sub: int = 3, workers: Optional[int] = None,
          progress: Optional[Callable[[float], None]] = None) -> str:
    total = int(round(duration * fps))
    workers = max(1, min(workers or (os.cpu_count() or 2), 8, total // 60 or 1))
    step = -(-total // workers)
    tmp = tempfile.mkdtemp(prefix="expl_")
    parts, progs = [], []
    jobs = []
    for i in range(workers):
        f0, f1 = i * step, min(total, (i + 1) * step)
        if f0 >= f1:
            continue
        part = os.path.join(tmp, f"part{i:02d}.mp4"); prog = os.path.join(tmp, f"p{i}.txt")
        parts.append(part); progs.append(prog)
        jobs.append([page, "--video", part, "--from", str(f0), "--to", str(f1), "--fps", str(fps), "--sub", str(sub), "--progress", prog])

    stop = False
    last = [-1.0]

    def watch():
        import time
        while not stop:
            vals = []
            for p in progs:
                try:
                    vals.append(float(Path(p).read_text() or 0))
                except Exception:
                    vals.append(0.0)
            if progress and vals:
                f = sum(vals) / len(vals)
                if f - last[0] >= 0.02:
                    last[0] = f
                    progress(f)
            time.sleep(2)

    with ThreadPoolExecutor(max_workers=len(jobs) + 1) as ex:
        w = ex.submit(watch)
        futs = [ex.submit(_run, j) for j in jobs]
        try:
            for f in futs:
                f.result()
        finally:
            stop = True
            w.result()
    lst = os.path.join(tmp, "list.txt")
    Path(lst).write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_mp4], check=True)
    return out_mp4


def mux(video_mp4: str, audio_wav: str, out_mp4: str) -> str:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video_mp4, "-i", audio_wav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-crf", "21", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_mp4], check=True)
    return out_mp4


def contact_sheet(pngs: list[str], out_png: str, cols: int = 6) -> str:
    rows = -(-len(pngs) // cols)
    with tempfile.TemporaryDirectory() as d:
        for i, p in enumerate(pngs):
            os.symlink(os.path.abspath(p), os.path.join(d, f"s{i:03d}.png"))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(d, "s%03d.png"), "-vf",
                        f"scale=270:-1,tile={cols}x{rows}:padding=4:color=white", "-frames:v", "1", out_png], check=True)
    return out_png
