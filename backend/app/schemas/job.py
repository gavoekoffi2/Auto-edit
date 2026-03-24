from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class JobCreate(BaseModel):
    video_id: UUID
    job_type: str = "pipeline"  # pipeline, transcribe, silence_removal, scene_detect, effects, export
    mode: Optional[str] = None  # tiktok, youtube, podcast
    params: Optional[dict] = None


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
