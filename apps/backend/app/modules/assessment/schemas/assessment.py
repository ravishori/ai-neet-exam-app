from pydantic import BaseModel, Field, model_validator

# FULL / SEED_V1 / taxonomy scopes stay capped at 90. SEED_V2 may request 91–100.
MAX_GENERIC_PRACTICE_COUNT = 90
MAX_SEED_V2_PRACTICE_COUNT = 100


class GenerateRequest(BaseModel):
    scope_type: str  # CONCEPT | TOPIC | CHAPTER | SUBJECT | FULL | SEED_V1 | SEED_V2
    scope_id: str | None = None
    question_count: int | None = Field(default=None, ge=1, le=MAX_SEED_V2_PRACTICE_COUNT)

    @model_validator(mode="after")
    def cap_non_seed_v2_counts(self) -> "GenerateRequest":
        if self.question_count is None:
            return self
        if self.scope_type == "SEED_V2":
            return self
        if self.question_count > MAX_GENERIC_PRACTICE_COUNT:
            raise ValueError(
                f"question_count must be <= {MAX_GENERIC_PRACTICE_COUNT} unless scope_type is SEED_V2"
            )
        return self


class AnswerRequest(BaseModel):
    content_item_id: str
    selected_option: str | None = None  # null clears the answer (mark as skipped)
    confidence: str | None = None  # easy | medium | hard
    marked_for_review: bool = False
    time_spent_seconds: int | None = Field(default=None, ge=0)
