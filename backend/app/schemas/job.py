from pydantic import BaseModel, field_validator, model_validator, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal

from app.config import (
    VALID_JOB_TYPES,
    VALID_MODES,
    VALID_PIPELINE_VERSIONS,
    VALID_VISUAL_MODES,
)

VALID_BROLL_DEMOGRAPHICS = {"african", "caucasian", "global"}
VALID_MOTION_PRESETS = {
    "clean_fintech", "neon_social", "african_premium",
    "minimal_creator", "kinetic_education",
    # Nouvelles familles en rotation (variété visuelle entre montages)
    "sunset_vibes", "electric_lime",
    # Familles des styles Captions AI (réservées aux styles qui les demandent)
    "editorial_paper", "sketch_notes",
}
# Source de vérité: les templates ASS du moteur (config légère, sans PIL/ffmpeg).
from app.autoedit_engine.config import ASS_TEMPLATES as _ENGINE_ASS_TEMPLATES

VALID_SUBTITLE_TEMPLATES = set(_ENGINE_ASS_TEMPLATES)


class JobOptions(BaseModel):
    """Toggles produit pour le pipeline v2.

    Tous optionnels — si non fournis, les valeurs par défaut viennent des
    `MODE_PRESETS` du pipeline et des feature flags d'env.
    """

    remove_silence: Optional[bool] = None
    dynamic_captions: Optional[bool] = None
    ai_broll: Optional[bool] = None
    motion_design: Optional[bool] = None  # scènes illustrées animées
    music: Optional[bool] = None
    sfx: Optional[bool] = None
    vertical_9_16: Optional[bool] = None
    final_cta: Optional[bool] = None
    broll_style: Optional[str] = None  # ex: "african_business_premium"
    broll_demographic: Optional[str] = None  # african | caucasian | global
    # Stratégie visuelle: ai_broll | credit_saver | auto_fallback. Si absent,
    # le pipeline retombe sur le preset du mode puis AUTOEDIT_DEFAULT_VISUAL_MODE.
    visual_mode: Optional[str] = None
    # Famille motion design forcée (sinon choisie par seed stable de la vidéo).
    motion_preset: Optional[str] = None
    # Template de sous-titres animés (sinon déduit du mode choisi).
    subtitle_template: Optional[str] = None
    # Fonctionnalité Clips: nombre maximum de shorts extraits d'une vidéo longue.
    max_clips: Optional[int] = Field(default=None, ge=1, le=10)
    # Nettoyage IA du transcript: off | light (défaut) | balanced | aggressive.
    cleanup_level: Optional[str] = None
    # Recadrage vertical: auto (suivi de visage) | center | left | right.
    smart_crop_mode: Optional[str] = None
    # Supprime les sous-titres DÉJÀ incrustés dans la source (défaut: activé)
    # pour éviter le double sous-titrage avec les captions du montage.
    remove_source_subtitles: Optional[bool] = None
    cta_text: Optional[str] = Field(default=None, max_length=120)
    logo_text: Optional[str] = Field(default=None, max_length=60)

    @field_validator("broll_demographic")
    @classmethod
    def validate_broll_demographic(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_BROLL_DEMOGRAPHICS:
            raise ValueError(
                f"broll_demographic must be one of: {', '.join(sorted(VALID_BROLL_DEMOGRAPHICS))}"
            )
        return v

    @field_validator("visual_mode")
    @classmethod
    def validate_visual_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_VISUAL_MODES:
            raise ValueError(
                f"visual_mode must be one of: {', '.join(sorted(VALID_VISUAL_MODES))}"
            )
        return v

    @field_validator("motion_preset")
    @classmethod
    def validate_motion_preset(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_MOTION_PRESETS:
            raise ValueError(
                f"motion_preset must be one of: {', '.join(sorted(VALID_MOTION_PRESETS))}"
            )
        return v

    @field_validator("smart_crop_mode")
    @classmethod
    def validate_smart_crop_mode(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"auto", "center", "left", "right"}
        if v is not None and v not in allowed:
            raise ValueError(f"smart_crop_mode must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("cleanup_level")
    @classmethod
    def validate_cleanup_level(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"off", "light", "balanced", "aggressive"}
        if v is not None and v not in allowed:
            raise ValueError(f"cleanup_level must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("subtitle_template")
    @classmethod
    def validate_subtitle_template(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SUBTITLE_TEMPLATES:
            raise ValueError(
                f"subtitle_template must be one of: {', '.join(sorted(VALID_SUBTITLE_TEMPLATES))}"
            )
        return v


class JobCreate(BaseModel):
    video_id: UUID
    job_type: str = "pipeline"
    mode: Optional[str] = None
    params: Optional[dict] = None
    pipeline_version: Optional[str] = None  # "v1" ou "v2" ; défaut = settings.PIPELINE_VERSION
    options: Optional[JobOptions] = None

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        # Frontend/product wording uses "auto_edit" for the main full pipeline.
        # Internally the backend worker dispatches that same operation as "pipeline".
        aliases = {"auto_edit": "pipeline"}
        normalized = aliases.get(v, v)
        if normalized not in VALID_JOB_TYPES:
            allowed = sorted(set(VALID_JOB_TYPES) | set(aliases))
            raise ValueError(f"job_type must be one of: {', '.join(allowed)}")
        return normalized

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(VALID_MODES))}")
        return v

    @field_validator("pipeline_version")
    @classmethod
    def validate_pipeline_version(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PIPELINE_VERSIONS:
            raise ValueError(
                f"pipeline_version must be one of: {', '.join(sorted(VALID_PIPELINE_VERSIONS))}"
            )
        return v


class ClipsCreate(BaseModel):
    """Création d'un job « Clips »: vidéo longue -> shorts viraux.

    La source est SOIT une URL publique (YouTube, TikTok…), SOIT une vidéo
    déjà uploadée sur la plateforme.
    """

    source_url: Optional[str] = Field(default=None, max_length=2048)
    video_id: Optional[UUID] = None
    mode: Optional[str] = None            # style de montage appliqué aux clips
    options: Optional[JobOptions] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(VALID_MODES))}")
        return v

    @model_validator(mode="after")
    def validate_one_source(self):
        if self.video_id is None and not self.source_url:
            raise ValueError("Provide either source_url or video_id")
        if self.video_id is not None and self.source_url:
            raise ValueError("Provide only one of source_url or video_id")
        return self


class ClipSelection(BaseModel):
    """Un extrait sélectionné (bornes ajustées + titre éventuellement modifié)."""

    start: float = Field(ge=0)
    end: float = Field(gt=0)
    title: Optional[str] = Field(default=None, max_length=120)
    hook: Optional[str] = Field(default=None, max_length=200)
    reason: Optional[str] = Field(default=None, max_length=300)
    score: Optional[int] = Field(default=None, ge=0, le=100)


class ClipsRenderRequest(BaseModel):
    """Étape 2 de Clips: rendu des extraits sélectionnés par l'utilisateur."""

    clips: list[ClipSelection] = Field(min_length=1, max_length=15)
    mode: Optional[str] = None
    options: Optional[JobOptions] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(VALID_MODES))}")
        return v


class JobResponse(BaseModel):
    id: UUID
    video_id: UUID
    job_type: str
    mode: Optional[str]
    status: str
    progress: int
    pipeline_version: Optional[str] = None
    result: Optional[dict]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
