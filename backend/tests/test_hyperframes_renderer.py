import json
import os
import subprocess

from app.processing.template_renderer import TemplateRenderer
from app.processing.types import OverlayClip


def test_hyperframes_renderer_invokes_node_wrapper_and_writes_overlay(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text, timeout):
        calls.append(cmd)
        out_path = cmd[cmd.index("--out") + 1]
        with open(out_path, "wb") as f:
            f.write(b"fake mp4")
        return subprocess.CompletedProcess(cmd, 0, stdout='{"ok":true}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/node" if name == "node" else "/usr/bin/ffmpeg")

    ov = OverlayClip(
        kind="explain_card",
        start=1.25,
        end=3.75,
        props={"title": "LOCALISER", "subtitle": "Google Maps", "step": "2"},
    )

    target = tmp_path / "overlay.mp4"
    rendered = TemplateRenderer(backend="hyperframes")._render_one(ov, str(target), "9:16")

    assert rendered == str(target)
    assert target.read_bytes() == b"fake mp4"
    assert calls, "node wrapper was not called"
    cmd = calls[0]
    assert os.path.basename(cmd[0]) == "node"
    assert "render.js" in cmd[1]
    assert cmd[cmd.index("--out") + 1] == str(target)
    assert cmd[cmd.index("--aspect") + 1] == "9:16"
    assert cmd[cmd.index("--duration") + 1] == "2.500"
    props = json.loads(cmd[cmd.index("--props") + 1])
    assert props["kind"] == "explain_card"
    assert props["title"] == "LOCALISER"
    assert props["subtitle"] == "Google Maps"
    assert props["step"] == "2"
