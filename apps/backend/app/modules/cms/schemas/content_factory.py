"""Pydantic schemas for Content Factory orchestration (FACTORY-P1)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.cms.models.content_factory import (
    BATCH_STATUSES,
    JOB_TYPES,
    SOURCE_TIERS,
    SOURCE_TYPES,
)


class ContentBatchCreateRequest(BaseModel):
    batch_key: str = Field(min_length=3, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    subject_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    concept_id: uuid.UUID | None = None
    source_type: str = "HUMAN"
    source_tier: str = "human"
    target_count: int = Field(ge=0, le=100_000, default=0)
    # Optional initial job created in the same transaction.
    initial_job: "InitialJobRequest | None" = None

    @field_validator("batch_key")
    @classmethod
    def normalize_batch_key(cls, v: str) -> str:
        key = v.strip()
        if not key:
            raise ValueError("batch_key is required")
        return key

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {SOURCE_TYPES}")
        return upper

    @field_validator("source_tier")
    @classmethod
    def validate_source_tier(cls, v: str) -> str:
        lower = v.strip().lower()
        if lower not in SOURCE_TIERS:
            raise ValueError(f"source_tier must be one of {SOURCE_TIERS}")
        return lower


class InitialJobRequest(BaseModel):
    job_key: str = Field(min_length=3, max_length=120)
    job_type: str = "GENERATE"
    requested_count: int = Field(ge=0, le=100_000, default=0)
    max_retries: int = Field(ge=0, le=10, default=3)

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in JOB_TYPES:
            raise ValueError(f"job_type must be one of {JOB_TYPES}")
        return upper


class GenerationJobCreateRequest(BaseModel):
    job_key: str = Field(min_length=3, max_length=120)
    job_type: str = "GENERATE"
    requested_count: int = Field(ge=0, le=100_000, default=0)
    max_retries: int = Field(ge=0, le=10, default=3)
    # FACTORY-P2: optional blueprint target (no execution in P1/P2).
    blueprint_id: uuid.UUID | None = None

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in JOB_TYPES:
            raise ValueError(f"job_type must be one of {JOB_TYPES}")
        return upper


class BatchStatusTransitionRequest(BaseModel):
    to_status: str

    @field_validator("to_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in BATCH_STATUSES:
            raise ValueError(f"to_status must be one of {BATCH_STATUSES}")
        return upper


class JobStatusTransitionRequest(BaseModel):
    to_status: Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]


class GenerationRunCreateRequest(BaseModel):
    """Request a new attempt for a job (bounded retry). Does not generate content."""

    execution_metadata: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=500)


class GenerationRunCompleteRequest(BaseModel):
    """Mark a run finished without performing generation (orchestration bookkeeping only)."""

    status: Literal["SUCCEEDED", "FAILED"]
    processed_count: int = Field(ge=0, default=0)
    success_count: int = Field(ge=0, default=0)
    failure_count: int = Field(ge=0, default=0)
    error_summary: str | None = Field(default=None, max_length=2000)
    error_code: str | None = Field(default=None, max_length=80)
    execution_metadata: dict[str, Any] | None = None


# Rebuild forward refs
ContentBatchCreateRequest.model_rebuild()
