"""Pydantic schemas for Content Factory planning (FACTORY-P2)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.cms.models.content_factory_planning import (
    DIFFICULTIES,
    LEARNING_LEVELS,
    PROVENANCE_TIERS,
    QUESTION_FORMATS,
)


class LearningObjectiveCreateRequest(BaseModel):
    objective_key: str = Field(min_length=3, max_length=120)
    concept_id: uuid.UUID
    title: str = Field(min_length=8, max_length=300)
    description: str | None = None
    learning_level: str = "apply"

    @field_validator("objective_key")
    @classmethod
    def strip_key(cls, v: str) -> str:
        return v.strip()

    @field_validator("learning_level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        lower = v.strip().lower()
        if lower not in LEARNING_LEVELS:
            raise ValueError(f"learning_level must be one of {LEARNING_LEVELS}")
        return lower

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        title = v.strip()
        if len(title) < 8:
            raise ValueError("title is too vague — provide a specific capability statement")
        return title


class QuestionFamilyCreateRequest(BaseModel):
    family_key: str = Field(min_length=3, max_length=120)
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    applicable_subject_codes: list[str] = Field(min_length=1)
    cognitive_intent: str = Field(min_length=3, max_length=200)
    difficulty_min: str = "easy"
    difficulty_max: str = "hard"
    question_format: str = "MCQ_4"

    @field_validator("family_key")
    @classmethod
    def strip_key(cls, v: str) -> str:
        return v.strip()

    @field_validator("applicable_subject_codes")
    @classmethod
    def normalize_subjects(cls, v: list[str]) -> list[str]:
        codes = sorted({c.strip().upper() for c in v if c.strip()})
        if not codes:
            raise ValueError("applicable_subject_codes required")
        return codes

    @field_validator("difficulty_min", "difficulty_max")
    @classmethod
    def validate_diff(cls, v: str) -> str:
        lower = v.strip().lower()
        if lower not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {DIFFICULTIES}")
        return lower

    @field_validator("question_format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in QUESTION_FORMATS:
            raise ValueError(f"question_format must be one of {QUESTION_FORMATS}")
        return upper

    @model_validator(mode="after")
    def check_difficulty_range(self) -> QuestionFamilyCreateRequest:
        from app.modules.cms.models.content_factory_planning import DIFFICULTY_RANK

        if DIFFICULTY_RANK[self.difficulty_min] > DIFFICULTY_RANK[self.difficulty_max]:
            raise ValueError("difficulty_min cannot exceed difficulty_max")
        return self


class QuestionBlueprintCreateRequest(BaseModel):
    blueprint_key: str = Field(min_length=3, max_length=120)
    subject_id: uuid.UUID
    chapter_id: uuid.UUID
    topic_id: uuid.UUID
    concept_id: uuid.UUID
    learning_objective_id: uuid.UUID
    question_family_id: uuid.UUID
    difficulty: str
    target_count: int = Field(ge=0, le=10_000, default=0)
    constraints: dict[str, Any] = Field(default_factory=dict)
    provenance_tier: str
    # If true and key exists, create next version and supersede prior ACTIVE/DRAFT.
    new_version: bool = False

    @field_validator("blueprint_key")
    @classmethod
    def strip_key(cls, v: str) -> str:
        return v.strip()

    @field_validator("difficulty")
    @classmethod
    def validate_diff(cls, v: str) -> str:
        lower = v.strip().lower()
        if lower not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {DIFFICULTIES}")
        return lower

    @field_validator("provenance_tier")
    @classmethod
    def validate_prov(cls, v: str) -> str:
        lower = v.strip().lower()
        # Reject false official claims
        if lower in {"official", "official_source", "nta", "ncert_official"}:
            raise ValueError(
                "provenance_tier must not claim official NTA/NCERT; use authoritative|licensed|human|ai|derived"
            )
        if lower not in PROVENANCE_TIERS:
            raise ValueError(f"provenance_tier must be one of {PROVENANCE_TIERS}")
        return lower


class CoverageSliceCreateRequest(BaseModel):
    slice_key: str = Field(min_length=3, max_length=160)
    subject_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    concept_id: uuid.UUID | None = None
    difficulty: str | None = None
    question_family_id: uuid.UUID | None = None
    target_count: int = Field(ge=0, le=100_000, default=0)

    @field_validator("slice_key")
    @classmethod
    def strip_key(cls, v: str) -> str:
        return v.strip()

    @field_validator("difficulty")
    @classmethod
    def validate_diff(cls, v: str | None) -> str | None:
        if v is None:
            return None
        lower = v.strip().lower()
        if lower not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {DIFFICULTIES}")
        return lower


class BatchBlueprintAttachRequest(BaseModel):
    blueprint_id: uuid.UUID
    requested_count: int | None = Field(default=None, ge=0, le=10_000)


class GenerationJobWithBlueprintRequest(BaseModel):
    """Optional P2 fields when creating a job that targets a blueprint (no execution)."""

    job_key: str = Field(min_length=3, max_length=120)
    job_type: str = "GENERATE"
    requested_count: int = Field(ge=0, le=100_000, default=0)
    max_retries: int = Field(ge=0, le=10, default=3)
    blueprint_id: uuid.UUID | None = None


class FactoryGenerateRequest(BaseModel):
    """FACTORY-P3: generate up to target_count valid unique DRAFT questions from a blueprint."""

    blueprint_id: uuid.UUID
    target_count: int = Field(ge=1, le=100, default=10)
    job_key: str | None = Field(default=None, min_length=3, max_length=120)


class FactoryQARequest(BaseModel):
    """FACTORY-P4: run automated QA on CREATED candidates in a batch."""

    force_new: bool = False
    run_id: uuid.UUID | None = None
    job_key: str | None = Field(default=None, min_length=3, max_length=120)


class FactorySampleRequest(BaseModel):
    """FACTORY-P4: reproducible stratified sampling eligibility draw."""

    seed: int | None = None
    sample_key: str | None = Field(default=None, min_length=3, max_length=120)
    green_size: int | None = Field(default=None, ge=0, le=10_000)


class FactoryReviewDecisionRequest(BaseModel):
    """FACTORY-P5 human decision — does not mutate ECAEP status."""

    decision: str = Field(description="ACCEPT | CORRECTION_REQUIRED | REJECT")
    checklist: dict[str, bool] | None = None
    failure_reasons: list[str] | None = None
    reviewer_note: str | None = Field(default=None, max_length=4000)

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in {"ACCEPT", "CORRECTION_REQUIRED", "REJECT"}:
            raise ValueError("decision must be ACCEPT, CORRECTION_REQUIRED, or REJECT")
        return upper

