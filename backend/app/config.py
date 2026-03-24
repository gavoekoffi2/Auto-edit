from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://autoedit:autoedit@localhost:5432/autoedit"
    DATABASE_URL_SYNC: str = "postgresql://autoedit:autoedit@localhost:5432/autoedit"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 500

    # FedaPay
    FEDAPAY_SECRET_KEY: Optional[str] = None
    FEDAPAY_PUBLIC_KEY: Optional[str] = None
    FEDAPAY_ENV: str = "sandbox"

    # Whisper
    WHISPER_MODEL: str = "base"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
