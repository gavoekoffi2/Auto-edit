import os
import secrets
import logging
from typing import Optional, List

from pydantic_settings import BaseSettings
from pydantic import field_validator

logger = logging.getLogger(__name__)

VALID_WHISPER_MODELS = {"tiny", "base", "small", "medium", "large"}
VALID_JOB_TYPES = {"pipeline", "transcribe", "silence_removal", "scene_detect", "effects", "export"}
VALID_MODES = {
    # Legacy modes (v1)
    "tiktok",
    "youtube",
    "podcast",
    # Nouveaux modes orientés Afrique francophone (v2)
    "tiktok_viral",
    "business_premium_african",
    "publicite_locale",
    "podcast_propre",
    "formation_educative",
}
VALID_PIPELINE_VERSIONS = {"v1", "v2"}
VALID_IMAGE_PROVIDERS = {"openrouter", "replicate", "stability", "noop"}
VALID_RENDERERS = {"ffmpeg", "hyperframes", "remotion"}


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://autoedit:autoedit@localhost:5432/autoedit"
    DATABASE_URL_SYNC: str = "postgresql://autoedit:autoedit@localhost:5432/autoedit"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost"

    # Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_VIDEO_DURATION_FREE: int = 300  # 5 min in seconds
    MAX_VIDEO_DURATION_PRO: int = 1800  # 30 min
    MAX_VIDEOS_PER_MONTH_FREE: int = 2

    # FedaPay
    FEDAPAY_SECRET_KEY: Optional[str] = None
    FEDAPAY_PUBLIC_KEY: Optional[str] = None
    FEDAPAY_ENV: str = "sandbox"

    # Whisper
    WHISPER_MODEL: str = "base"

    # Rate limiting
    LOGIN_RATE_LIMIT: int = 5  # max attempts per window
    LOGIN_RATE_WINDOW: int = 900  # 15 minutes in seconds

    # =====================================================================
    # Pipeline V2 — B-roll IA / templates / renderers
    # Aucune de ces variables n'est requise pour le pipeline v1 actuel.
    # =====================================================================
    PIPELINE_VERSION: str = "v1"

    # Image generation (B-roll IA africain)
    IMAGE_GENERATION_PROVIDER: str = "openrouter"
    IMAGE_GENERATION_MODEL: str = "google/gemini-2.5-flash-image-preview"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_HTTP_REFERER: str = "https://autoedit.app"
    OPENROUTER_X_TITLE: str = "AutoEdit"

    # B-roll style & planning
    BROLL_STYLE: str = "african_business_premium"
    BROLL_DEFAULT_ASPECT_RATIO: str = "9:16"
    BROLL_MAX_CUES_PER_VIDEO: int = 12
    BROLL_MIN_SEGMENT_DURATION: float = 2.5
    BROLL_MAX_SEGMENT_DURATION: float = 8.0

    # Renderer abstrait
    VIDEO_RENDERER: str = "ffmpeg"

    # Feature flags produit
    ENABLE_AI_BROLL: bool = True
    ENABLE_DYNAMIC_CAPTIONS: bool = True
    ENABLE_SFX: bool = True
    ENABLE_MUSIC: bool = True

    @field_validator("PIPELINE_VERSION")
    @classmethod
    def validate_pipeline_version(cls, v: str) -> str:
        if v not in VALID_PIPELINE_VERSIONS:
            raise ValueError(f"PIPELINE_VERSION must be one of: {VALID_PIPELINE_VERSIONS}")
        return v

    @field_validator("IMAGE_GENERATION_PROVIDER")
    @classmethod
    def validate_image_provider(cls, v: str) -> str:
        if v not in VALID_IMAGE_PROVIDERS:
            raise ValueError(f"IMAGE_GENERATION_PROVIDER must be one of: {VALID_IMAGE_PROVIDERS}")
        return v

    @field_validator("VIDEO_RENDERER")
    @classmethod
    def validate_video_renderer(cls, v: str) -> str:
        if v not in VALID_RENDERERS:
            raise ValueError(f"VIDEO_RENDERER must be one of: {VALID_RENDERERS}")
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or v == "dev-secret-key-change-in-production":
            generated = secrets.token_urlsafe(32)
            logger.warning(
                "SECRET_KEY not set or insecure. Generating random key for this session. "
                "Set SECRET_KEY environment variable for production!"
            )
            return generated
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("WHISPER_MODEL")
    @classmethod
    def validate_whisper_model(cls, v: str) -> str:
        if v not in VALID_WHISPER_MODELS:
            raise ValueError(f"WHISPER_MODEL must be one of: {VALID_WHISPER_MODELS}")
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
