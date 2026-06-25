from pydantic import BaseModel, field_validator, Field
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
}


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
