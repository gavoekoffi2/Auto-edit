import os
import secrets
import logging
from typing import Optional, List

from pydantic_settings import BaseSettings
from pydantic import field_validator

logger = logging.getLogger(__name__)

VALID_APP_ENVS = {"development", "staging", "production"}
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
    # Mode économie crédits (montage créateur sans dépendre des images IA) —
    # nouveau défaut MVP. `creator_economy_mode` est un alias historique accepté.
    "credit_saver_creator_edit",
    "creator_economy_mode",
    # Styles de montage inspirés des montages Captions AI (réfs TikTok du
    # produit): pilule éditoriale / néon hype / notes manuscrites.
    "pill_editorial",
    "neon_hype",
    "handwritten_note",
}
VALID_PIPELINE_VERSIONS = {"v1", "v2"}
VALID_IMAGE_PROVIDERS = {"openrouter", "replicate", "stability", "noop"}
VALID_RENDERERS = {"ffmpeg", "hyperframes", "remotion"}

# Visual strategy for a render:
#   ai_broll      -> existing behaviour, generate AI B-roll images when possible.
#   credit_saver  -> never call the paid image API; rely on source video +
#                    captions + motion design + camera flashes + SFX.
#   auto_fallback -> try AI images when configured, but continue in credit_saver
#                    if generation fails / credits are exhausted / disabled.
VALID_VISUAL_MODES = {"ai_broll", "credit_saver", "auto_fallback"}


class Settings(BaseSettings):
    # Environnement (development | staging | production)
    APP_ENV: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://autoedit:autoedit@localhost:5432/autoedit"
    DATABASE_URL_SYNC: str = "postgresql://autoedit:autoedit@localhost:5432/autoedit"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost"

    # Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 5120
    # Marge disque exigée avant d'accepter un upload (le rendu écrit des Go
    # d'intermédiaires ensuite). Le proxy Caddy doit accepter un body >= ceci.
    UPLOAD_MIN_FREE_GB: float = 3.0
    MAX_VIDEO_DURATION_FREE: int = 900  # 15 min in seconds
    MAX_VIDEO_DURATION_PRO: int = 3600  # 60 min
    MAX_VIDEOS_PER_MONTH_FREE: int = 2

    # Long video processing
    # A 3-4 minute mobile video can take far longer than its playback duration
    # once Whisper, generated visuals, FFmpeg compositing and SFX are chained.
    # Keep these configurable and generous so jobs do not die mid-render because
    # of a fixed worker/subprocess timeout. Set to 0 to disable the Celery limit.
    CELERY_TASK_TIME_LIMIT_SECONDS: int = 0
    CELERY_TASK_SOFT_TIME_LIMIT_SECONDS: int = 0
    FFMPEG_COMMAND_TIMEOUT_SECONDS: int = 21600  # 6h per heavy command

    # FedaPay
    FEDAPAY_SECRET_KEY: Optional[str] = None
    FEDAPAY_PUBLIC_KEY: Optional[str] = None
    FEDAPAY_ENV: str = "sandbox"

    # Transcription
    # Provider: auto (ElevenLabs Scribe si clé dispo, sinon Whisper) | elevenlabs | whisper.
    # Scribe = plus rapide (déchargé du VPS) + plus précis + timestamps natifs.
    TRANSCRIPTION_PROVIDER: str = "auto"
    TRANSCRIPTION_LANGUAGE: str = "fr"   # code langue (Scribe + Whisper). "" = auto-détection
    ELEVENLABS_API_KEY: Optional[str] = None

    # Whisper (repli local) — "small" plus précis que "base" en français.
    WHISPER_MODEL: str = "small"

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
    # Cheapest Nano Banana image model currently visible on OpenRouter.
    IMAGE_GENERATION_MODEL: str = "google/gemini-2.5-flash-image"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_HTTP_REFERER: str = "https://cutforge.app"
    OPENROUTER_X_TITLE: str = "CutForge"

    # B-roll style & planning
    BROLL_STYLE: str = "african_business_premium"
    BROLL_DEFAULT_ASPECT_RATIO: str = "9:16"
    # Cost-aware default: motion-design cards cover part of the video, so the
    # engine does not need to generate a new image every few seconds.
    BROLL_MAX_CUES_PER_VIDEO: int = 14
    BROLL_SHORTS_MAX_DURATION_SECONDS: float = 90.0
    BROLL_SHORTS_MAX_CUES_PER_VIDEO: int = 18
    BROLL_MIN_SEGMENT_DURATION: float = 2.5
    BROLL_MAX_SEGMENT_DURATION: float = 8.0

    # Renderer abstrait
    VIDEO_RENDERER: str = "hyperframes"

    # Feature flags produit
    ENABLE_AI_BROLL: bool = True
    # Scènes motion design illustrées (dessins animés qui illustrent le
    # discours). Fonctionne même sans clé API (dessins procéduraux).
    ENABLE_MOTION_DESIGN: bool = True
    ENABLE_DYNAMIC_CAPTIONS: bool = True
    ENABLE_SFX: bool = True
    ENABLE_MUSIC: bool = True

    # ---------------------------------------------------------------------
    # Mode économie crédits (montage créateur sans images IA obligatoires)
    # ---------------------------------------------------------------------
    # Stratégie visuelle par défaut quand le job n'en fournit pas une.
    #   credit_saver  -> jamais d'image payante (MVP rapide, non bloquant)
    #   auto_fallback -> tente l'IA, retombe en credit_saver si échec/crédits
    #   ai_broll      -> ancien comportement (images IA quand possible)
    AUTOEDIT_DEFAULT_VISUAL_MODE: str = "auto_fallback"
    # Coupe-circuit global: si True, AUCUNE génération d'image payante n'est
    # appelée, quel que soit le mode demandé (utile quand les crédits sont à 0
    # ou pour garantir des tests sans coût).
    AUTOEDIT_DISABLE_PAID_IMAGE_GENERATION: bool = False

    # ---------------------------------------------------------------------
    # Email transactionnel — optionnel en dev, requis en prod si tu veux
    # le reset password fonctionnel.
    # ---------------------------------------------------------------------
    EMAIL_PROVIDER: str = "console"  # console | smtp | sendgrid
    EMAIL_FROM: str = "CutForge <noreply@cutforge.app>"
    EMAIL_SMTP_HOST: Optional[str] = None
    EMAIL_SMTP_PORT: int = 587
    EMAIL_SMTP_USER: Optional[str] = None
    EMAIL_SMTP_PASSWORD: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None
    PUBLIC_APP_URL: str = "http://localhost"

    # ---------------------------------------------------------------------
    # Observabilite (Sentry) — optionnel
    # ---------------------------------------------------------------------
    SENTRY_DSN: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # ---------------------------------------------------------------------
    # Compte ops
    # ---------------------------------------------------------------------
    SUPPORT_EMAIL: str = "support@cutforge.app"
    ADMIN_EMAILS: str = ""

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

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

    @field_validator("AUTOEDIT_DEFAULT_VISUAL_MODE")
    @classmethod
    def validate_default_visual_mode(cls, v: str) -> str:
        if v not in VALID_VISUAL_MODES:
            raise ValueError(
                f"AUTOEDIT_DEFAULT_VISUAL_MODE must be one of: {VALID_VISUAL_MODES}"
            )
        return v

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        if v not in VALID_APP_ENVS:
            raise ValueError(f"APP_ENV must be one of: {VALID_APP_ENVS}")
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        env = info.data.get("APP_ENV", "development") if info and info.data else "development"
        is_dev_placeholder = (
            not v
            or v == "dev-secret-key-change-in-production"
            or v.startswith("replace-me")
        )
        if is_dev_placeholder:
            if env != "development":
                raise ValueError(
                    "SECRET_KEY is required for staging/production. "
                    "Generate one with `openssl rand -hex 32` and set it in your environment."
                )
            generated = secrets.token_urlsafe(32)
            logger.warning(
                "[dev only] SECRET_KEY not set. A random key was generated for this process. "
                "All JWT tokens will be invalidated on restart. Set SECRET_KEY in .env."
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

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
