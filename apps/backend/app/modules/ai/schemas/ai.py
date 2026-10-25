from datetime import date

from pydantic import BaseModel, Field, field_validator


class TutorExplainRequest(BaseModel):
    concept_id: str
    question: str = Field(min_length=1, max_length=500)


class ExplainQuestionRequest(BaseModel):
    question_id: str


class GenerateQuestionRequest(BaseModel):
    concept_id: str


class StudyPlanRequest(BaseModel):
    target_score: int = Field(ge=0, le=720)
    current_score: int = Field(ge=0, le=720)
    exam_date: date
    hours_per_day: int = Field(ge=1, le=16)


class StudyPlanDayShape(BaseModel):
    """One daily_schedule entry — strict shape, not just "valid JSON".
    `extra="forbid"` is deliberate: an AI response that invents extra
    fields is a sign it didn't follow the prompt's contract and should be
    treated the same as a missing/malformed one (reject, fall back to the
    deterministic plan), not silently accepted with the extras dropped."""

    model_config = {"extra": "forbid"}

    day: int = Field(ge=1, le=60)
    focus: str = Field(min_length=1, max_length=300)
    duration_minutes: int = Field(ge=1, le=960)  # 16h/day cap, matches StudyPlanRequest.hours_per_day


class StudyPlanShape(BaseModel):
    """Strict schema an AI-generated plan must satisfy before
    StudyPlannerService will use it in place of the deterministic
    baseline — see study_planner.SYSTEM_PROMPT for the contract this
    mirrors. Deliberately independent of StudyPlanDeterministic's own
    dict-building (that one is never validated against this — it's
    already correct by construction, being pure Python, not a model's
    output)."""

    model_config = {"extra": "forbid"}

    summary: str = Field(min_length=1, max_length=2000)
    weekly_focus: list[str] = Field(min_length=1, max_length=20)
    daily_schedule: list[StudyPlanDayShape] = Field(min_length=1, max_length=60)

    @field_validator("weekly_focus")
    @classmethod
    def _no_blank_focus_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("weekly_focus entries must be non-empty")
        return value
