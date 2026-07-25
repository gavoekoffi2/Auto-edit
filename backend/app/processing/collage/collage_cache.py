"""Cache disque content-addressed du moteur Collage Premium (ÉTAPE 10).

Deux usages, une seule mécanique:

  * ``JsonCache``   — concepts sémantiques (petits, lisibles, debuggables);
  * ``BinaryCache`` — images générées (le poste de coût dominant).

La clé est TOUJOURS un hash du contenu qui a produit l'entrée (texte + version
du verrou de style + modèle). Conséquence: deux vidéos qui disent la même chose
ne paient qu'une fois, et faire évoluer le style invalide le cache tout seul —
sans purge manuelle, sans risque de servir un asset « ancien style ».

Le cache est best-effort: la moindre erreur d'I/O est avalée (on régénère).
Sûr en multi-worker: écriture dans un fichier temporaire + ``os.replace``
atomique, donc jamais de fichier à moitié écrit lu par un autre worker.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from . import collage_config as ccfg

logger = logging.getLogger(__name__)


def make_key(*parts: object) -> str:
    """Clé stable à partir de n'importe quels fragments sérialisables."""
    blob = "~".join(str(p) for p in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


class _BaseCache:
    def __init__(self, namespace: str, enabled: Optional[bool] = None,
                 root: Optional[str] = None):
        self.namespace = namespace
        self.enabled = ccfg.CACHE_ENABLED if enabled is None else bool(enabled)
        self.root = Path(root or ccfg.CACHE_DIR) / namespace

    # ------------------------------------------------------------------ #
    def _path(self, key: str, suffix: str) -> Path:
        # Deux niveaux de fanout: quelques milliers d'entrées par dossier max.
        return self.root / key[:2] / f"{key}{suffix}"

    def _fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        if ccfg.CACHE_TTL_DAYS <= 0:
            return True
        age_days = (time.time() - path.stat().st_mtime) / 86400.0
        return age_days <= ccfg.CACHE_TTL_DAYS

    def _write_atomic(self, path: Path, payload: bytes) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
            tmp.write_bytes(payload)
            os.replace(tmp, path)
            return True
        except OSError as exc:
            logger.debug("[collage_cache] write skipped (%s): %s", path, exc)
            return False


class JsonCache(_BaseCache):
    """Cache de petits objets JSON (concepts, plans, rapports)."""

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        path = self._path(key, ".json")
        if not self._fresh(path):
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def set(self, key: str, value: Any) -> bool:
        if not self.enabled:
            return False
        try:
            payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError):
            return False
        return self._write_atomic(self._path(key, ".json"), payload)


class BinaryCache(_BaseCache):
    """Cache de blobs (images générées)."""

    def __init__(self, namespace: str, suffix: str = ".png", **kw):
        super().__init__(namespace, **kw)
        self.suffix = suffix

    def path_for(self, key: str) -> Path:
        return self._path(key, self.suffix)

    def get_bytes(self, key: str) -> Optional[bytes]:
        if not self.enabled:
            return None
        path = self.path_for(key)
        if not self._fresh(path):
            return None
        try:
            data = path.read_bytes()
            return data or None
        except OSError:
            return None

    def set_bytes(self, key: str, data: bytes) -> bool:
        if not self.enabled or not data:
            return False
        return self._write_atomic(self.path_for(key), data)


def purge_expired(root: Optional[str] = None) -> int:
    """Supprime les entrées périmées; renvoie le nombre de fichiers retirés.

    Appelée par la purge de rétention existante — jamais dans le chemin chaud
    d'un rendu (un job ne doit pas payer le balayage du cache).
    """
    base = Path(root or ccfg.CACHE_DIR)
    if not base.is_dir() or ccfg.CACHE_TTL_DAYS <= 0:
        return 0
    cutoff = time.time() - ccfg.CACHE_TTL_DAYS * 86400.0
    removed = 0
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info("[collage_cache] %d entrée(s) périmée(s) purgée(s)", removed)
    return removed
