from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    scope_type: str  # CONCEPT | CHAPTER | SUBJECT | FULL
    scope_id: str | None = None
    question_count: int | None = Field(default=None, ge=1, le=90)


class AnswerRequest(BaseModel):
    content_item_id: str
    selected_option: str | None = None  # null clears the answer (mark as skipped)
    confidence: str | None = None  # easy | medium | hard
    marked_for_review: bool = False
    time_spent_seconds: int | None = Field(default=None, ge=0)
