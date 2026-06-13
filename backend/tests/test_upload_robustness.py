"""Upload robustness: disk preflight, disk-full handling, partial cleanup."""
import errno
import io

import pytest
from fastapi import HTTPException

from app.services import storage


class _FakeUpload:
    """Minimal async UploadFile stand-in."""

    def __init__(self, data: bytes, filename: str = "clip.mp4", chunk: int = 1 << 16):
        self._buf = io.BytesIO(data)
        self.filename = filename
        self._chunk = chunk

    async def read(self, n: int = -1) -> bytes:
        return self._buf.read(n if n and n > 0 else self._chunk)


# A valid MP4 header so the magic-bytes check passes.
_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


@pytest.fixture()
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(storage.settings, "UPLOAD_MIN_FREE_GB", 3.0)
    return tmp_path


@pytest.mark.asyncio
async def test_upload_ok_when_disk_has_space(upload_dir, monkeypatch):
    monkeypatch.setattr(storage, "free_bytes", lambda p: 50 * 1024**3)  # 50 GB
    rel, size = await storage.save_upload(_FakeUpload(_MP4), "user1")
    assert rel.startswith("user1/")
    assert size == len(_MP4)
    assert (upload_dir / rel).exists()


@pytest.mark.asyncio
async def test_upload_refused_when_disk_low(upload_dir, monkeypatch):
    # Always low, even after emergency cleanup.
    monkeypatch.setattr(storage, "free_bytes", lambda p: 100 * 1024**2)  # 100 MB
    monkeypatch.setattr(storage, "emergency_cleanup", lambda root: 0)
    with pytest.raises(HTTPException) as exc:
        await storage.save_upload(_FakeUpload(_MP4), "user1")
    assert exc.value.status_code == 507
    # no partial file left behind
    assert list(upload_dir.glob("user1/*")) == []


@pytest.mark.asyncio
async def test_upload_recovers_after_emergency_cleanup(upload_dir, monkeypatch):
    calls = {"n": 0}

    def fake_free(_p):
        # low on the first two probes, healthy after cleanup
        calls["n"] += 1
        return 100 * 1024**2 if calls["n"] <= 1 else 50 * 1024**3

    monkeypatch.setattr(storage, "free_bytes", fake_free)
    monkeypatch.setattr(storage, "emergency_cleanup", lambda root: 5 * 1024**3)
    rel, size = await storage.save_upload(_FakeUpload(_MP4), "user1")
    assert size == len(_MP4)


@pytest.mark.asyncio
async def test_upload_disk_full_midwrite_raises_507(upload_dir, monkeypatch):
    monkeypatch.setattr(storage, "free_bytes", lambda p: 50 * 1024**3)

    class _ExplodingUpload(_FakeUpload):
        async def read(self, n: int = -1) -> bytes:
            raise OSError(errno.ENOSPC, "No space left on device")

    with pytest.raises(HTTPException) as exc:
        await storage.save_upload(_ExplodingUpload(_MP4), "user1")
    assert exc.value.status_code == 507
    assert list(upload_dir.glob("user1/*")) == []  # partial cleaned


@pytest.mark.asyncio
async def test_upload_empty_file_rejected(upload_dir, monkeypatch):
    monkeypatch.setattr(storage, "free_bytes", lambda p: 50 * 1024**3)
    with pytest.raises(HTTPException) as exc:
        await storage.save_upload(_FakeUpload(b""), "user1")
    assert exc.value.status_code == 400
    assert list(upload_dir.glob("user1/*")) == []


@pytest.mark.asyncio
async def test_upload_non_video_rejected_and_cleaned(upload_dir, monkeypatch):
    monkeypatch.setattr(storage, "free_bytes", lambda p: 50 * 1024**3)
    with pytest.raises(HTTPException) as exc:
        await storage.save_upload(_FakeUpload(b"this is plainly not a video file" * 4), "user1")
    assert exc.value.status_code == 400
    assert list(upload_dir.glob("user1/*")) == []
