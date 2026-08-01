from datetime import date

from pydantic import BaseModel, Field


class TutorExplainRequest(BaseModel):
    concept_id: str
    question: str = Field(min_length=1, max_length=500)


class GenerateQuestionRequest(BaseModel):
    concept_id: str


class StudyPlanRequest(BaseModel):
    target_score: int = Field(ge=0, le=720)
    current_score: int = Field(ge=0, le=720)
    exam_date: date
    hours_per_day: int = Field(ge=1, le=16)
