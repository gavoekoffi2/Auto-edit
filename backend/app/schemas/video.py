from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class VideoResponse(BaseModel):
    id: UUID
    title: str
    duration_s: Optional[float]
    size_bytes: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    videos: list[VideoResponse]
    total: int
