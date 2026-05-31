import os
import secrets
import logging
from typing import Optional, List

from pydantic_settings import BaseSettings
from pydantic import field_validator

logger = logging.getLogger(__name__)

VALID_WHISPER_MODELS = {"tiny", "base", "small", "medium", "large"}
VALID_JOB_TYPES = {"pipeline", "transcribe", "silence_removal", "scene_detect", "effects", "export"}
VALID_MODES = {"tiktok", "youtube", "podcast"}


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

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        is_production = (
            os.environ.get("PRODUCTION") == "1"
            or os.environ.get("ENV") == "production"
        )
        if not v or v == "dev-secret-key-change-in-production":
            if is_production:
                raise ValueError(
                    "SECRET_KEY must be explicitly set in production. "
                    "Set the SECRET_KEY environment variable to a secure value "
                    "(at least 32 characters)."
                )
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
