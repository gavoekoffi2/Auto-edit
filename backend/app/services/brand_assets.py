"""Éléments de marque importés par l'utilisateur (logo du client pour le Studio)."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings

MAX_LOGO_BYTES = 5 * 1024 * 1024
LOGO_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
_ID = re.compile(r"^[0-9a-f]{32}$")
_UID = re.compile(r"^[0-9a-fA-F-]{8,40}$")


def brand_dir(user_id: str) -> Path:
    if not _UID.match(user_id or ""):
        raise ValueError("identifiant utilisateur invalide")
    d = Path(settings.UPLOAD_DIR) / user_id / "brand"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_logo(user_id: str, data: bytes, content_type: str) -> str:
    """Enregistre le logo (vérifié par Pillow) et renvoie son identifiant."""
    from io import BytesIO

    from PIL import Image

    if len(data) > MAX_LOGO_BYTES:
        raise ValueError("Logo trop lourd (5 Mo maximum).")
    if content_type not in LOGO_TYPES:
        raise ValueError("Format de logo non supporté (PNG, JPG ou WEBP).")
    try:
        im = Image.open(BytesIO(data))
        im.verify()
    except Exception as e:  # noqa: BLE001
        raise ValueError("Image illisible.") from e
    aid = uuid.uuid4().hex
    (brand_dir(user_id) / f"logo_{aid}{LOGO_TYPES[content_type]}").write_bytes(data)
    return aid


def logo_path_for(user_id: str, asset_id: str) -> Optional[str]:
    if not _ID.match(asset_id or "") or not _UID.match(user_id or ""):
        return None
    d = Path(settings.UPLOAD_DIR) / user_id / "brand"
    for ext in LOGO_TYPES.values():
        p = d / f"logo_{asset_id}{ext}"
        if p.exists():
            return str(p)
    return None


def latest_logo(user_id: str) -> Optional[str]:
    """Identifiant du dernier logo importé (réutilisé d'une vidéo à l'autre)."""
    try:
        d = brand_dir(user_id)
    except ValueError:
        return None
    files = sorted(d.glob("logo_*"), key=os.path.getmtime, reverse=True)
    return files[0].stem.replace("logo_", "") if files else None
