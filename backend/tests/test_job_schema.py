import pytest
from pydantic import ValidationError
from uuid import uuid4

from app.schemas.job import JobCreate


def test_auto_edit_job_type_aliases_to_pipeline():
    job = JobCreate(video_id=uuid4(), job_type="auto_edit")

    assert job.job_type == "pipeline"


def test_invalid_job_type_lists_auto_edit_alias():
    with pytest.raises(ValidationError) as exc_info:
        JobCreate(video_id=uuid4(), job_type="not_real")

    assert "auto_edit" in str(exc_info.value)
    assert "pipeline" in str(exc_info.value)
