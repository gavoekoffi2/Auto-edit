import os
import uuid
import aiofiles
from pathlib import Path
from fastapi import UploadFile

from app.config import settings


async def save_upload(file: UploadFile, user_id: str) -> tuple[str, int]:
    """Save uploaded file and return (relative_path, size_bytes)."""
    upload_dir = Path(settings.UPLOAD_DIR) / user_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix if file.filename else ".mp4"
    filename = f"{uuid.uuid4()}{ext}"
    file_path = upload_dir / filename

    size = 0
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await f.write(chunk)
            size += len(chunk)

    relative_path = f"{user_id}/{filename}"
    return relative_path, size


def get_absolute_path(relative_path: str) -> str:
    """Get absolute file path from relative storage path."""
    return str(Path(settings.UPLOAD_DIR) / relative_path)


def get_output_dir(user_id: str, job_id: str) -> str:
    """Get output directory for a processing job."""
    output_dir = Path(settings.UPLOAD_DIR) / user_id / "output" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return str(output_dir)
