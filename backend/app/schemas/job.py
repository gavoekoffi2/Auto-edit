from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.config import VALID_JOB_TYPES, VALID_MODES


class JobCreate(BaseModel):
    video_id: UUID
    job_type: str = "pipeline"
    mode: Optional[str] = None
    params: Optional[dict] = None

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        if v not in VALID_JOB_TYPES:
            raise ValueError(f"job_type must be one of: {', '.join(VALID_JOB_TYPES)}")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_MODES:
            raise ValueError(f"mode must be one of: {', '.join(VALID_MODES)}")
        return v


class JobResponse(BaseModel):
    id: UUID
    video_id: UUID
    job_type: str
    mode: Optional[str]
    status: str
    progress: int
    result: Optional[dict]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
