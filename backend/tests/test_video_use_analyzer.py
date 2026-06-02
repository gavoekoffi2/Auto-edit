import json
import subprocess

from app.processing.video_use_analyzer import VideoUseAnalyzer


def test_video_use_analyzer_parses_manifest_from_cli(tmp_path, monkeypatch):
    frames_dir = tmp_path / ".video-use" / "frames" / "abc"
    frames_dir.mkdir(parents=True)
    (frames_dir / "manifest.json").write_text(
        json.dumps({"frames": [{"filename": "000001.png", "t": 0}, {"filename": "000002.png", "t": 3.5}]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""),
    )

    result = VideoUseAnalyzer(tmp_path).extract_keyframes("source.mp4")

    assert result["available"] is True
    assert result["frames_count"] == 2
    assert result["frames"][0]["path"] == str((frames_dir / "000001.png").resolve())
    assert result["frames"][1]["timestamp"] == 3.5


def test_video_use_analyzer_uses_ffmpeg_fallback_when_cli_errors(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "npx":
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="missing tool")
        if cmd[0] == "ffprobe":
            return subprocess.CompletedProcess(cmd, 0, stdout="10.0\n", stderr="")
        if cmd[0] == "ffmpeg":
            frames_dir = tmp_path / ".video-use" / "fallback_frames"
            frames_dir.mkdir(parents=True, exist_ok=True)
            (frames_dir / "frame_0001.jpg").write_bytes(b"x")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = VideoUseAnalyzer(tmp_path).extract_keyframes("source.mp4")

    assert result["available"] is True
    assert result["tool"] == "video-use+ffmpeg-fallback"
    assert result["frames_count"] == 1
    assert "missing tool" in result["tool_error"]
