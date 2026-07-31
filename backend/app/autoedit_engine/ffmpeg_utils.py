"""
Shared ffmpeg / ffprobe helpers.

The spec mandates a static ffmpeg 7+ build.  We resolve the binary from the
``FFMPEG_BIN`` / ``FFPROBE_BIN`` env vars first (handy for static builds that
are not on PATH) and fall back to the names on PATH.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Optional, Sequence

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE_BIN", "ffprobe")

#: Linux refuse UN argument de plus de MAX_ARG_STRLEN (32 pages = 128 KiB) avec
#: E2BIG, quelle que soit la place restante dans l'environnement. Un filtergraph
#: de montage long (une expression de zoom par coupe, une entrée par SFX…)
#: dépasse ce seuil et faisait échouer le rendu des vidéos longues avec un
#: « Argument list too long » incompréhensible. Au-delà de ce seuil (marge de
#: sécurité volontaire), le filtre part dans un FICHIER via -filter_script.
FILTER_ARG_MAX = int(os.environ.get("FFMPEG_FILTER_ARG_MAX", "60000"))


def ensure_ffmpeg() -> None:
    """Raise a clear error if ffmpeg is not resolvable (ffprobe is optional)."""
    if shutil.which(FFMPEG) is None and not os.path.isfile(FFMPEG):
        raise RuntimeError(
            f"ffmpeg not found (looked for '{FFMPEG}'). Install a static "
            f"ffmpeg 7+ build or set FFMPEG_BIN."
        )


def _default_timeout() -> int | None:
    """Return the configured media-command timeout.

    Import lazily to keep this low-level helper usable from standalone engine
    scripts. A value <= 0 disables the subprocess timeout.
    """
    try:
        from app.config import settings
        configured = int(getattr(settings, "FFMPEG_COMMAND_TIMEOUT_SECONDS", 21600) or 0)
    except Exception:
        configured = int(os.environ.get("FFMPEG_COMMAND_TIMEOUT_SECONDS", "21600") or 0)
    return configured if configured > 0 else None


def _harden(cmd: Sequence[str]) -> list[str]:
    """Ajoute les garde-fous non-interactifs communs à tous les appels ffmpeg.

    ``-nostdin``: sans lui, ffmpeg lit stdin et un worker Celery détaché (stdin
    fermé/hérité) peut le faire tourner en boucle ou l'interrompre. ``-nostats``
    supprime la ligne de progression réécrite des milliers de fois: sur un rendu
    d'une heure, elle représentait des dizaines de Mo de stderr conservés en
    mémoire par ``capture_output``.
    """
    out = list(cmd)
    if not out:
        return out
    exe = os.path.basename(str(out[0])).lower()
    if not exe.startswith("ffmpeg"):
        return out
    flags = [f for f in ("-nostdin", "-hide_banner", "-nostats") if f not in out]
    return [out[0], *flags, *out[1:]]


def run(cmd: Sequence[str], *, timeout: int | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run an ffmpeg/ffprobe command, surfacing stderr on failure.

    The old 30-minute hardcoded timeout could kill longer AutoEdit renders in
    the middle of processing. Default to the app setting instead.
    """
    cmd = _harden(cmd)
    oversized = next((a for a in cmd if len(str(a)) > FILTER_ARG_MAX * 2), None)
    if oversized is not None:
        # Message actionnable au lieu d'un OSError E2BIG opaque du noyau.
        raise RuntimeError(
            f"argument ffmpeg trop long ({len(str(oversized))} caractères): "
            "utilise run_filter() pour passer le filtergraph par fichier."
        )
    proc = subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        timeout=_default_timeout() if timeout is None else timeout,
        start_new_session=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(map(str, cmd[:6]))} ...\n"
            f"{proc.stderr[-1500:]}"
        )
    return proc


def filter_flag(filter_str: str, *, complex_graph: bool) -> tuple[str, str, Optional[str]]:
    """Choisit comment passer *filter_str* à ffmpeg.

    Renvoie ``(flag, valeur, fichier_temporaire_ou_None)``. Tant que le filtre
    tient largement dans un argument, on garde la forme historique (``-vf`` /
    ``-filter_complex``) — lisible dans les logs. Au-delà, ffmpeg sait lire le
    graphe depuis un FICHIER (``-filter_script`` / ``-filter_complex_script``),
    ce qui supprime définitivement la limite du noyau sur la taille d'un
    argument. L'appelant est responsable de supprimer le fichier renvoyé.
    """
    long_form = "-filter_complex" if complex_graph else "-vf"
    if len(filter_str) <= FILTER_ARG_MAX:
        return long_form, filter_str, None
    script_flag = "-filter_complex_script" if complex_graph else "-filter_script"
    fd, path = tempfile.mkstemp(prefix="ffgraph_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(filter_str)
    return script_flag, path, path


def run_filter(prefix: Sequence[str], filter_str: str, suffix: Sequence[str], *,
               complex_graph: bool = False, timeout: int | None = None,
               check: bool = True) -> subprocess.CompletedProcess:
    """Exécute ffmpeg avec un filtergraph de taille arbitraire.

    ``prefix`` = ffmpeg + entrées, ``suffix`` = mappings/encodage/sortie. Le
    filtre est inséré entre les deux, en argument ou via un fichier selon sa
    taille (voir :func:`filter_flag`).
    """
    flag, value, tmp = filter_flag(filter_str, complex_graph=complex_graph)
    try:
        return run([*prefix, flag, value, *suffix], timeout=timeout, check=check)
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def probe_duration(path: str) -> float:
    """Return media duration in seconds (0.0 on failure)."""
    try:
        proc = run(
            [
                FFPROBE, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            timeout=60,
            check=False,
        )
        return float(proc.stdout.strip())
    except (ValueError, RuntimeError, FileNotFoundError, subprocess.TimeoutExpired):
        return 0.0


def probe_resolution(path: str) -> tuple[int, int]:
    """Return (width, height) of the first video stream, or (0, 0)."""
    try:
        proc = run(
            [
                FFPROBE, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                path,
            ],
            timeout=60,
            check=False,
        )
        data = json.loads(proc.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        return int(stream.get("width", 0)), int(stream.get("height", 0))
    except (ValueError, RuntimeError, KeyError, FileNotFoundError, subprocess.TimeoutExpired):
        return 0, 0


def has_audio(path: str) -> bool:
    """True if the file has at least one audio stream."""
    try:
        proc = run(
            [
                FFPROBE, "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                path,
            ],
            timeout=60,
            check=False,
        )
        return bool(proc.stdout.strip())
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
