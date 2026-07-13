"""Téléchargement de vidéos sources depuis une URL (YouTube, TikTok, etc.).

Utilisé par la fonctionnalité « Clips » : l'utilisateur colle l'URL d'une vidéo
longue, on la télécharge via yt-dlp puis on en extrait des shorts viraux.

Sécurité:
  * schéma http/https uniquement, URL bornée en longueur;
  * refus des hôtes privés/loopback/link-local (anti-SSRF) — l'API ne doit pas
    servir de proxy vers le réseau interne;
  * durée et taille de la source plafonnées AVANT téléchargement.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import socket
from typing import Callable, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MAX_URL_LENGTH = 2048
MAX_SOURCE_DURATION_S = 3 * 3600          # 3 h de vidéo source max
MAX_SOURCE_FILESIZE = 4 * 1024 ** 3       # 4 Go max
_DOWNLOAD_HEIGHT_CAP = 1080               # inutile de télécharger de la 4K


class SourceURLError(ValueError):
    """URL source invalide ou interdite (message montrable à l'utilisateur)."""


def validate_source_url(url: str) -> str:
    """Validate and normalise a user-provided source URL.

    Raises SourceURLError with a user-friendly (French) message.
    """
    url = (url or "").strip()
    if not url:
        raise SourceURLError("URL manquante.")
    if len(url) > MAX_URL_LENGTH:
        raise SourceURLError("URL trop longue.")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SourceURLError("Seules les URLs http(s) sont acceptées.")
    host = parsed.hostname
    if not host:
        raise SourceURLError("URL invalide (hôte manquant).")

    # Anti-SSRF: refuse loopback / réseaux privés / link-local, que l'hôte
    # soit une IP littérale ou un nom qui y résout.
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        raise SourceURLError("Impossible de résoudre l'hôte de cette URL.")
    for addr in addrs:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise SourceURLError("Cette URL pointe vers un réseau interdit.")
    return url


def probe_source(url: str) -> dict:
    """Fetch metadata (title/duration) WITHOUT downloading. Raises SourceURLError."""
    import yt_dlp

    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "skip_download": True, "socket_timeout": 30,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001 - yt-dlp raises many types
        logger.warning("probe_source failed for %s: %s", url, exc)
        raise SourceURLError(
            "Impossible de lire cette URL. Vérifie que la vidéo est publique."
        )
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if not entries:
            raise SourceURLError("Cette URL ne contient aucune vidéo.")
        info = entries[0]
    duration = float(info.get("duration") or 0.0)
    if duration and duration > MAX_SOURCE_DURATION_S:
        raise SourceURLError(
            f"Vidéo trop longue ({duration / 60:.0f} min). "
            f"Maximum: {MAX_SOURCE_DURATION_S // 3600} h."
        )
    return {
        "title": (info.get("title") or "video")[:500],
        "duration": duration,
        "extractor": info.get("extractor_key") or info.get("extractor") or "",
        "webpage_url": info.get("webpage_url") or url,
    }


def download_source(
    url: str,
    dest_path: str,
    progress: Optional[Callable[[float], None]] = None,
) -> Tuple[str, dict]:
    """Download *url* to *dest_path* (mp4). Returns (path, info).

    *progress* receives a 0..1 fraction when known. Raises SourceURLError on
    user-addressable failures.
    """
    import yt_dlp

    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    base, _ = os.path.splitext(dest_path)

    def _hook(d: dict) -> None:
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes")
            if total and done:
                progress(min(1.0, float(done) / float(total)))

    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "outtmpl": base + ".%(ext)s",
        "format": (
            f"bv*[height<={_DOWNLOAD_HEIGHT_CAP}]+ba/"
            f"b[height<={_DOWNLOAD_HEIGHT_CAP}]/b"
        ),
        "merge_output_format": "mp4",
        "max_filesize": MAX_SOURCE_FILESIZE,
        "socket_timeout": 30,
        "retries": 3,
        "progress_hooks": [_hook],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("download_source failed for %s: %s", url, exc)
        raise SourceURLError(
            "Le téléchargement de la vidéo a échoué. Vérifie l'URL et réessaie."
        )

    final_path = base + ".mp4"
    if not os.path.exists(final_path):
        # yt-dlp peut produire un autre conteneur si le merge mp4 est impossible.
        candidates = [base + ext for ext in (".mkv", ".webm", ".mov")]
        final_path = next((c for c in candidates if os.path.exists(c)), final_path)
    if not os.path.exists(final_path) or os.path.getsize(final_path) == 0:
        raise SourceURLError("Le téléchargement n'a produit aucun fichier vidéo.")

    return final_path, {
        "title": (info.get("title") or "video")[:500],
        "duration": float(info.get("duration") or 0.0),
        "extractor": info.get("extractor_key") or "",
    }
