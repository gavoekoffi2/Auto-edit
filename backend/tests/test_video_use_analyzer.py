import json
import subprocess

from app.processing.video_use_analyzer import VideoUseAnalyzer


def test_video_use_analyzer_parses_manifest_from_cli(tmp_path, monkeypatch):
    frames_dir = tmp_path / ".video-use" / "frames" / "run123"
    frames_dir.mkdir(parents=True)
    manifest = frames_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "runHash": "run123",
                "source": "source.mp4",
                "frames": [
                    {"path": str(frames_dir / "000001.png"), "timestamp": 0.5},
                    {"path": str(frames_dir / "000002.png"), "timestamp": 3.0},
                ],
            }
        ),
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):
        assert "video-use" in " ".join(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = VideoUseAnalyzer(workdir=str(tmp_path)).extract_keyframes("source.mp4", max_frames=12)

    assert result["available"] is True
    assert result["frames_count"] == 2
    assert result["manifest_path"] == str(manifest)
    assert result["frames"][1]["timestamp"] == 3.0


def test_video_use_analyzer_parses_real_video_use_filename_and_t_fields(tmp_path, monkeypatch):
    frames_dir = tmp_path / ".video-use" / "frames" / "realrun"
    frames_dir.mkdir(parents=True)
    manifest = frames_dir / "manifest.json"
    manifest.write_text(
        json.dumps({"frames": [{"filename": "000001.png", "t": 0}, {"filename": "000002.png", "t": 1.5}]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""),
    )

    result = VideoUseAnalyzer(workdir=str(tmp_path)).extract_keyframes("source.mp4")

    assert result["frames"][0]["path"] == str((frames_dir / "000001.png").resolve())
    assert result["frames"][1]["timestamp"] == 1.5


def test_video_use_analyzer_fails_soft_when_cli_errors(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="missing yt-dlp")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = VideoUseAnalyzer(workdir=str(tmp_path)).extract_keyframes("source.mp4")

    assert result["available"] is False
    assert "missing yt-dlp" in result["error"]
