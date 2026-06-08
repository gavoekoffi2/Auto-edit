from pydantic import BaseModel, field_validator, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal

from app.config import VALID_JOB_TYPES, VALID_MODES, VALID_PIPELINE_VERSIONS

VALID_BROLL_DEMOGRAPHICS = {"african", "caucasian", "global"}


class JobOptions(BaseModel):
    """Toggles produit pour le pipeline v2.

    Tous optionnels — si non fournis, les valeurs par défaut viennent des
    `MODE_PRESETS` du pipeline et des feature flags d'env.
    """

    remove_silence: Optional[bool] = None
    dynamic_captions: Optional[bool] = None
    ai_broll: Optional[bool] = None
    music: Optional[bool] = None
    sfx: Optional[bool] = None
    vertical_9_16: Optional[bool] = None
    final_cta: Optional[bool] = None
    broll_style: Optional[str] = None  # ex: "african_business_premium"
    broll_demographic: Optional[str] = None  # african | caucasian | global
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
