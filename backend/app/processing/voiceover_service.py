"""Optional text-to-speech service for brief-generated advertisements."""
from __future__ import annotations

from pathlib import Path

import httpx

from app.config import settings


class VoiceoverError(RuntimeError):
    pass


class VoiceoverService:
    def __init__(self, timeout_s: int = 90):
        self.timeout_s = timeout_s

    def synthesize(self, text: str, target_path: str, voice_id: str | None = None) -> str:
        if not text.strip():
            raise VoiceoverError("Le texte de voix off est vide.")
        if (settings.TTS_PROVIDER or "none").lower() == "none":
            raise VoiceoverError("TTS_PROVIDER=none : configure un fournisseur de voix off avant le rendu.")
        if (settings.TTS_PROVIDER or "").lower() != "elevenlabs":
            raise VoiceoverError(f"Fournisseur TTS inconnu : {settings.TTS_PROVIDER}")
        if not settings.ELEVENLABS_API_KEY:
            raise VoiceoverError("ELEVENLABS_API_KEY est requis pour générer la voix off.")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id or settings.TTS_VOICE_ID}"
        payload = {
            "text": text,
            "model_id": settings.TTS_MODEL,
            "voice_settings": {"stability": 0.48, "similarity_boost": 0.78},
        }
        headers = {
            "xi-api-key": settings.ELEVENLABS_API_KEY,
            "accept": "audio/mpeg",
            "content-type": "application/json",
        }
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=self.timeout_s)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VoiceoverError(f"La génération TTS a échoué : {exc}") from exc

        destination = Path(target_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        return str(destination)
