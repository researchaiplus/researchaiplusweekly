"""Pydantic models for the FastAPI layer."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, Field, ConfigDict


class TaskStatus(str, Enum):
    """Lifecycle states for a newsletter generation task."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskProgress(BaseModel):
    """Represents the progress of a background task."""

    total_urls: int = Field(ge=0, default=0)
    processed: int = Field(ge=0, default=0)
    failed: int = Field(ge=0, default=0)


class GenerationOptions(BaseModel):
    """Customisation flags for newsletter generation."""

    include_subtopics: bool | None = Field(default=None)
    max_recommendation_length: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="allow")


class GenerateRequest(BaseModel):
    """Payload submitted to trigger newsletter generation."""

    urls: list[AnyHttpUrl] = Field(..., description="List of URLs to process.", min_length=1)
    options: GenerationOptions | None = Field(default=None)


class GenerateResponse(BaseModel):
    """Response returned after enqueueing a newsletter task."""

    task_id: str
    status: TaskStatus


class StatusProgress(BaseModel):
    """Progress payload included in status responses."""

    total_urls: int
    processed: int
    failed: int


class StatusResponse(BaseModel):
    """API response describing the current state of a task."""

    task_id: str
    status: TaskStatus
    progress: StatusProgress
    estimated_completion: datetime | None = None
    error: str | None = None


class ResultMetadata(BaseModel):
    """Additional metadata about a completed task."""

    generated_at: datetime
    total_processed: int
    topics: list[str]


class ResultResponse(BaseModel):
    """Result payload containing rendered Markdown output."""

    task_id: str
    status: TaskStatus
    markdown_content: str
    metadata: ResultMetadata


class UploadResponse(BaseModel):
    """Response payload returned after parsing an uploaded manifest."""

    urls: list[AnyHttpUrl]
    invalid_urls: list[str]


class TaskRecord(BaseModel):
    """Internal record of a task stored in the repository."""

    task_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    progress: TaskProgress = Field(default_factory=TaskProgress)
    markdown_content: str | None = None
    metadata: ResultMetadata | None = None
    error: str | None = None
    original_payload: dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


__all__ = [
    "GenerateRequest",
    "GenerateResponse",
    "ResultMetadata",
    "ResultResponse",
    "StatusProgress",
    "StatusResponse",
    "TaskProgress",
    "TaskRecord",
    "TaskStatus",
    "UploadResponse",
]
