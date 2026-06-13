"""Disk-pressure hardening: clear pipe errors + intermediate cleanup."""
import shutil

import pytest

from app.autoedit_engine import ffmpeg_utils
from app.autoedit_engine import render_utils
from app.autoedit_engine.pipeline import cleanup_intermediates
from PIL import Image


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_prores_pipe_surfaces_real_ffmpeg_error(tmp_path, monkeypatch):
    """A dying encoder must raise a CLEAR RuntimeError, never a bare
    '[Errno 32] Broken pipe' (that was the user-facing production error)."""
    # /bin/false exits immediately: the first frame write hits a broken pipe.
    monkeypatch.setattr(ffmpeg_utils, "FFMPEG", "/bin/false")
    frame = Image.new("RGBA", (64, 64), (10, 10, 10, 255))

    with pytest.raises(RuntimeError) as exc:
        with render_utils.ProResPipe(str(tmp_path / "x.mov"), width=64, height=64) as pipe:
            for _ in range(50):
                pipe.write(frame)
    msg = str(exc.value)
    assert "ProRes" in msg
    assert "Errno 32" not in msg


def test_cleanup_intermediates_keeps_deliverables(tmp_path):
    # heavy intermediates
    (tmp_path / "clips_graded").mkdir()
    (tmp_path / "clips_graded" / "seg_0000.mp4").write_bytes(b"x" * 2048)
    (tmp_path / "motion_clips").mkdir()
    (tmp_path / "motion_clips" / "md_000.mov").write_bytes(b"x" * 4096)
    (tmp_path / "sfx").mkdir()
    (tmp_path / "sfx" / "pop.wav").write_bytes(b"x" * 512)
    for name in ("base_only.mp4", "base_dyn.mp4", "composite_nosfx.mp4",
                 "composite_withsfx.mp4", "_composite_pass0.mp4"):
        (tmp_path / name).write_bytes(b"x" * 1024)
    # light deliverables that MUST survive
    (tmp_path / "final_montage_web.mp4").write_bytes(b"final")
    (tmp_path / "edl.json").write_text("{}")
    (tmp_path / "master.ass").write_text("[Script Info]")
    (tmp_path / "broll").mkdir()
    (tmp_path / "broll" / "br_000.png").write_bytes(b"png")
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "transcripts" / "v_vu.json").write_text("{}")

    freed = cleanup_intermediates(str(tmp_path))

    assert freed > 0
    assert not (tmp_path / "clips_graded").exists()
    assert not (tmp_path / "motion_clips").exists()
    assert not (tmp_path / "sfx").exists()
    assert not (tmp_path / "base_only.mp4").exists()
    assert not (tmp_path / "_composite_pass0.mp4").exists()
    # deliverables intact
    assert (tmp_path / "final_montage_web.mp4").read_bytes() == b"final"
    assert (tmp_path / "edl.json").exists()
    assert (tmp_path / "master.ass").exists()
    assert (tmp_path / "broll" / "br_000.png").exists()
    assert (tmp_path / "transcripts" / "v_vu.json").exists()


def test_cleanup_intermediates_missing_dir_is_safe(tmp_path):
    assert cleanup_intermediates(str(tmp_path / "does-not-exist")) == 0
