"""Pydantic schemas for the Weekly Assessment API surface."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

# Same 100-question ceiling as the rest of the assessment engine.
MAX_TOTAL_QUESTIONS = 200
MAX_BLUEPRINT_ROWS = 10


class WeeklyBlueprintRow(BaseModel):
    subject_id: str
    question_count: int = Field(ge=1, le=100)
    chapter_ids: list[str] | None = None
    topic_ids: list[str] | None = None


class WeeklyAssessmentCreateRequest(BaseModel):
    assessment_key: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=3, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int = Field(ge=1, le=600)
    marks_per_question: float = Field(default=4, ge=0, le=10)
    negative_marks_per_question: float = Field(default=1, ge=0, le=10)
    attempt_limit: int = Field(default=1, ge=1, le=10)
    cumulative_weight: dict | None = None
    difficulty_distribution: dict | None = None
    blueprint: list[WeeklyBlueprintRow] = Field(min_length=1, max_length=MAX_BLUEPRINT_ROWS)

    @model_validator(mode="after")
    def _validate(self) -> "WeeklyAssessmentCreateRequest":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        total = sum(row.question_count for row in self.blueprint)
        if total > MAX_TOTAL_QUESTIONS:
            raise ValueError(f"Total question_count across blueprint must be <= {MAX_TOTAL_QUESTIONS}")
        subjects = [row.subject_id for row in self.blueprint]
        if len(set(subjects)) != len(subjects):
            raise ValueError("blueprint has duplicate subject_id entries")
        if self.cumulative_weight is not None:
            keys = set(self.cumulative_weight.keys())
            allowed = {"current_syllabus_pct", "previous_syllabus_pct"}
            if not keys.issubset(allowed):
                raise ValueError(f"cumulative_weight allows only {sorted(allowed)}")
            total_pct = sum(float(v) for v in self.cumulative_weight.values())
            if not (99.0 <= total_pct <= 101.0):
                raise ValueError("cumulative_weight percentages must sum to ~100")
        return self


class WeeklyAssessmentUpdateRequest(BaseModel):
    """PATCH — every field optional. Blueprint replacement is all-or-nothing."""

    title: str | None = Field(default=None, min_length=3, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    marks_per_question: float | None = Field(default=None, ge=0, le=10)
    negative_marks_per_question: float | None = Field(default=None, ge=0, le=10)
    attempt_limit: int | None = Field(default=None, ge=1, le=10)
    cumulative_weight: dict | None = None
    difficulty_distribution: dict | None = None
    blueprint: list[WeeklyBlueprintRow] | None = Field(default=None, max_length=MAX_BLUEPRINT_ROWS)


class WeeklyStartAttemptResponse(BaseModel):
    weekly_assessment_id: str
    assessment_id: str
    attempt_id: str
    coverage: list[dict]
    duration_minutes: int
