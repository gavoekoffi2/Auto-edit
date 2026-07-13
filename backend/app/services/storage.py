import os
import uuid
import errno
import shutil
import aiofiles
import subprocess
import logging
from pathlib import Path
from fastapi import UploadFile, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


def _min_free_bytes() -> int:
    """Marge disque exigée avant d'accepter un upload (source: settings).

    Le rendu écrit ensuite des Go d'intermédiaires, donc on garde du mou.
    """
    return int(float(getattr(settings, "UPLOAD_MIN_FREE_GB", 3.0)) * 1024**3)


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
    # MP4/MOV/M4V/3GP/MTS: bytes 4-8 sont souvent "ftyp".
    # Certains fichiers mobiles/fragmentés peuvent démarrer par moov/mdat/free/skip.
    if head[4:8] in (b"ftyp", b"moov", b"mdat", b"free", b"skip"):
        return True
    # MPEG transport streams (.mts/.m2ts): sync byte 0x47 toutes les 188 bytes
    if head[0:1] == b"\x47" or (len(head) > 4 and head[4:5] == b"\x47"):
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


def free_bytes(path: str) -> int:
    """Octets libres sur le système de fichiers de *path* (0 si introuvable)."""
    try:
        target = path
        while target and not os.path.exists(target):
            target = os.path.dirname(target)
        return shutil.disk_usage(target or "/").free
    except OSError:
        return 0


def emergency_cleanup(upload_root: str) -> int:
    """Purge en urgence les intermédiaires de rendu de TOUS les jobs.

    Appelé quand le disque est presque plein avant d'accepter un upload. Ne
    touche QUE les fichiers intermédiaires connus — jamais les vidéos sources
    ni les montages finaux.
    """
    try:
        from app.autoedit_engine.pipeline import cleanup_intermediates
    except Exception:  # pragma: no cover - engine import guard
        return 0
    freed = 0
    root = Path(upload_root)
    if not root.exists():
        return 0
    # uploads/<user>/output/<job>/
    for output_dir in root.glob("*/output/*"):
        if output_dir.is_dir():
            try:
                freed += cleanup_intermediates(str(output_dir))
            except Exception as exc:  # noqa: BLE001 - best effort
                logger.warning("emergency_cleanup skipped %s: %s", output_dir, exc)
    if freed:
        logger.info("emergency_cleanup freed %.0f MB", freed / 1e6)
    return freed


async def save_upload(
    file: UploadFile, user_id: str, max_size_mb: int = None,
    expected_size: int | None = None,
) -> tuple[str, int]:
    """Save uploaded file with size + disk validation. Returns (relative_path, size_bytes)."""
    max_size = (max_size_mb or settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024

    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    upload_dir = Path(settings.UPLOAD_DIR) / user_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # --- préflight disque ----------------------------------------------------
    # Sans place, l'écriture échouait en plein milieu avec un OSError générique
    # (l'upload "s'arrête en chemin"). On refuse TÔT avec un message clair, après
    # avoir tenté de récupérer de l'espace en purgeant les intermédiaires.
    needed = (expected_size or 0) + _min_free_bytes()
    if free_bytes(str(upload_dir)) < needed:
        freed = emergency_cleanup(upload_root)
        logger.warning("Low disk before upload (user=%s): freed %.0f MB", user_id, freed / 1e6)
    if free_bytes(str(upload_dir)) < needed:
        free_gb = free_bytes(str(upload_dir)) / 1e9
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=(
                f"Espace disque serveur insuffisant ({free_gb:.1f} Go libres). "
                "Réessaie dans quelques minutes, le temps que le serveur se libère."
            ),
        )

    ext = Path(file.filename).suffix.lower() if file.filename else ".mp4"
    filename = f"{uuid.uuid4()}{ext}"
    file_path = upload_dir / filename

    size = 0
    first_chunk: bytes = b""
    try:
        async with aiofiles.open(file_path, "wb") as f:
            chunk_size = 8 * 1024 * 1024  # 8MB chunks: fewer syscalls for large mobile uploads
            while chunk := await file.read(chunk_size):
                if not first_chunk:
                    first_chunk = chunk[:32]
                size += len(chunk)
                if size > max_size:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Fichier trop lourd. Maximum: {settings.MAX_UPLOAD_SIZE_MB}MB",
                    )
                await f.write(chunk)
    except HTTPException:
        _safe_unlink(file_path)
        raise
    except OSError as exc:
        _safe_unlink(file_path)
        if exc.errno == errno.ENOSPC:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail=(
                    "Le serveur n'a plus d'espace disque pendant l'envoi. "
                    "Réessaie dans quelques minutes."
                ),
            ) from exc
        logger.error("Disk write failed during upload (user=%s): %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Échec d'écriture du fichier sur le serveur. Réessaie.",
        ) from exc
    except Exception:
        _safe_unlink(file_path)
        raise

    # Fichier vide (connexion coupée tout de suite) -> message clair.
    if size == 0:
        _safe_unlink(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fichier vide reçu (connexion interrompue ?). Réessaie.",
        )

    # Validation magic bytes: l'extension ne suffit pas en sécurité.
    if not _looks_like_video(first_chunk):
        _safe_unlink(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier ne ressemble pas à une vidéo valide.",
        )

    relative_path = f"{user_id}/{filename}"
    return relative_path, size


def _safe_unlink(path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def get_absolute_path(relative_path: str) -> str:
    """Get absolute file path from relative storage path. Validates against traversal."""
    _validate_path(relative_path)
    abs_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, relative_path))

    # Ensure path is within UPLOAD_DIR. Comparaison par SEGMENT de chemin:
    # un simple startswith laisserait passer un sibling ("/data/uploads_evil"
    # matche "/data/uploads").
    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    if abs_path != upload_root and not abs_path.startswith(upload_root + os.sep):
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
