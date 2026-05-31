"""Tests de la detection MIME video par magic bytes."""
from app.services.storage import _looks_like_video


def test_detects_mp4_ftyp():
    # bytes 4-8 = "ftyp" → MP4/MOV
    head = b"\x00\x00\x00\x18" + b"ftyp" + b"isom" + b"\x00\x00\x00\x00"
    assert _looks_like_video(head) is True


def test_detects_webm_matroska():
    head = b"\x1a\x45\xdf\xa3" + b"\x00" * 8
    assert _looks_like_video(head) is True


def test_detects_avi():
    head = b"RIFF" + b"\x00\x00\x00\x00" + b"AVI "
    assert _looks_like_video(head) is True


def test_detects_mpeg_transport_stream():
    head = b"\x47" + b"\x00" * 31
    assert _looks_like_video(head) is True


def test_rejects_plain_text():
    assert _looks_like_video(b"Hello world this is plain text and not a video") is False


def test_rejects_empty():
    assert _looks_like_video(b"") is False
    assert _looks_like_video(b"abc") is False


def test_rejects_jpeg_image():
    head = b"\xff\xd8\xff\xe0" + b"\x00" * 8
    assert _looks_like_video(head) is False


def test_rejects_pdf():
    head = b"%PDF-1.4" + b"\x00" * 4
    assert _looks_like_video(head) is False
