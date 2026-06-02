"""Détecteur de silences pour le pipeline V2.

Deux stratégies:
  1. `auto-editor` (wrapping CLI déjà fait dans `silence.py` v1) — rend
     directement une vidéo nettoyée mais ne renvoie pas les ranges.
  2. Analyse via FFmpeg `silencedetect` — renvoie une liste de `SilenceRange`
     précises pour construire l'EDL.

Le pipeline V2 utilise la 2e stratégie pour avoir un plan explicite, puis
appliquera les coupes via FFmpeg directement (pas via auto-editor).
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
from typing import Optional

from app.processing.types import SilenceRange

logger = logging.getLogger(__name__)


_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.\-]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.\-]+)")


class SilenceDetector:
    def __init__(
        self,
        noise_db: float = -30.0,
        min_silence_duration: float = 0.4,
        timeout_s: int = 600,
    ):
        self.noise_db = noise_db
        self.min_silence_duration = min_silence_duration
        self.timeout_s = timeout_s

    def detect(self, video_path: str) -> list[SilenceRange]:
        """Retourne la liste des plages silencieuses détectées par FFmpeg.

        Fail-soft: si ffmpeg manque ou parse échoue → retourne `[]`, le
        pipeline pourra continuer sans suppression des silences.
        """
        if not shutil.which("ffmpeg"):
            logger.warning("ffmpeg introuvable, aucune détection de silence")
            return []

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            video_path,
            "-af",
            f"silencedetect=noise={self.noise_db}dB:d={self.min_silence_duration}",
            "-f",
            "null",
            "-",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error("[silence_detector] FFmpeg silencedetect timeout")
            return []

        ranges: list[SilenceRange] = []
        current_start: Optional[float] = None
        # FFmpeg écrit silencedetect sur stderr
        for line in (proc.stderr or "").splitlines():
            m_start = _SILENCE_START_RE.search(line)
            if m_start:
                try:
                    current_start = float(m_start.group(1))
                except ValueError:
                    current_start = None
                continue
            m_end = _SILENCE_END_RE.search(line)
            if m_end and current_start is not None:
                try:
                    end = float(m_end.group(1))
                    if end > current_start:
                        ranges.append(
                            SilenceRange(
                                start=max(0.0, current_start),
                                end=end,
                                reason="silence",
                            )
                        )
                except ValueError:
                    pass
                current_start = None

        logger.info(f"[silence_detector] {len(ranges)} silence ranges detected")
        return ranges
