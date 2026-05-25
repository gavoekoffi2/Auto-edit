import os
import uuid
import aiofiles
import subprocess
import logging
from pathlib import Path
from fastapi import UploadFile, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


# Magic bytes des conteneurs video supportes. La detection se fait en lisant
# les premiers octets du fichier upload, en complement de la verification
# d'extension dans l'endpoint.
_VIDEO_SIGNATURES: dict[str, list[bytes]] = {
    "mp4":  [b"ftyp"],          # offset 4
    "mov":  [b"moov", b"ftyp"], # offset 4 (mov est un container similaire mp4)
    "webm": [b"\x1a\x45\xdf\xa3"],
    "mkv":  [b"\x1a\x45\xdf\xa3"],
    "avi":  [b"RIFF"],
    "flv":  [b"FLV"],
    "wmv":  [b"\x30\x26\xb2\x75"],
}


def _looks_like_video(head: bytes) -> bool:
    if not head or len(head) < 12:
        return False
    # MP4/MOV/3GP: bytes 4-8 sont "ftyp"
    if head[4:8] in (b"ftyp", b"moov", b"mdat", b"free", b"skip"):
        return True
    # Matroska / WebM
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return True
    # AVI
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return True
    # FLV
    if head[:3] == b"FLV":
        return True
    # WMV / ASF
    if head[:4] == b"\x30\x26\xb2\x75":
        return True
    return False


def _validate_path(relative_path: str) -> None:
    """Validate path to prevent directory traversal attacks."""
    normalized = os.path.normpath(relative_path)
    if ".." in normalized or normalized.startswith("/"):
        raise ValueError("Invalid file path")


async def save_upload(
    file: UploadFile, user_id: str, max_size_mb: int = None
) -> tuple[str, int]:
    """Save uploaded file with size validation. Returns (relative_path, size_bytes)."""
    max_size = (max_size_mb or settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024

    upload_dir = Path(settings.UPLOAD_DIR) / user_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix.lower() if file.filename else ".mp4"
    filename = f"{uuid.uuid4()}{ext}"
    file_path = upload_dir / filename

    size = 0
    first_chunk: bytes = b""
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            if not first_chunk:
                first_chunk = chunk[:32]
            size += len(chunk)
            if size > max_size:
                # Clean up partial file
                await f.close()
                os.unlink(file_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB",
                )
            await f.write(chunk)

    # Validation magic bytes: l'extension ne suffit pas en sécurité.
    if not _looks_like_video(first_chunk):
        try:
            os.unlink(file_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File does not look like a valid video (magic bytes check failed).",
        )

    relative_path = f"{user_id}/{filename}"
    return relative_path, size


def get_absolute_path(relative_path: str) -> str:
    """Get absolute file path from relative storage path. Validates against traversal."""
    _validate_path(relative_path)
    abs_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, relative_path))

    # Ensure path is within UPLOAD_DIR
    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    if not abs_path.startswith(upload_root):
        raise ValueError("Path traversal detected")

    return abs_path


def get_output_dir(user_id: str, job_id: str) -> str:
    """Get output directory for a processing job."""
    _validate_path(user_id)
    _validate_path(job_id)
    output_dir = Path(settings.UPLOAD_DIR) / user_id / "output" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return str(output_dir)


def get_video_duration(file_path: str) -> float | None:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return None


def cleanup_directory(dir_path: str, keep_files: set[str] = None) -> None:
    """Clean up intermediate files in a directory, keeping specified files.

    Itère uniquement les fichiers au premier niveau — les sous-dossiers
    (`broll/`, `overlays/`) sont préservés intacts.
    """
    keep = keep_files or {
        # v1
        "final_output.mp4",
        "subtitles.srt",
        "transcript.json",
        "scenes.csv",
        # v2
        "words.json",
        "edl.json",
        "concat.txt",
    }
    try:
        for f in Path(dir_path).iterdir():
            if f.is_file() and f.name not in keep:
                f.unlink()
                logger.debug(f"Cleaned up: {f}")
    except Exception as e:
        logger.warning(f"Cleanup failed for {dir_path}: {e}")
