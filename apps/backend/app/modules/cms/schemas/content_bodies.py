"""Body shapes per content_type — see ADR-0009 / the ECAEP spec.

Stored as JSONB on content_versions.body. Validated at the API boundary
against the schema matching the content_item's content_type; never a
dedicated column per field.
"""

from pydantic import BaseModel


class ConceptNoteBody(BaseModel):
    ncert_ref: str | None = None
    summary: str
    sections: list[str] = []


class QuestionOption(BaseModel):
    label: str
    text: str


class QuestionBody(BaseModel):
    stem: str
    options: list[QuestionOption]
    correct_option: str
    explanation: str
    difficulty: str = "medium"
    bloom_level: str | None = None
    pyq_year: int | None = None


class FlashcardBody(BaseModel):
    front: str
    back: str
    image_url: str | None = None


class DiagramBody(BaseModel):
    image_url: str
    labels: list[str] = []
    alt_text: str


class VideoRefBody(BaseModel):
    external_url: str
    provider: str = "youtube"
    duration_sec: int | None = None
    transcript_url: str | None = None


class FormulaSheetBody(BaseModel):
    formulas: list[str]


BODY_SCHEMA_BY_TYPE: dict[str, type[BaseModel]] = {
    "CONCEPT_NOTE": ConceptNoteBody,
    "QUESTION": QuestionBody,
    "FLASHCARD": FlashcardBody,
    "DIAGRAM": DiagramBody,
    "VIDEO_REF": VideoRefBody,
    "FORMULA_SHEET": FormulaSheetBody,
}

CONTENT_TYPES = list(BODY_SCHEMA_BY_TYPE.keys())


def validate_body(content_type: str, body: dict) -> dict:
    schema = BODY_SCHEMA_BY_TYPE.get(content_type)
    if not schema:
        raise ValueError(f"Unknown content_type: {content_type}")
    return schema.model_validate(body).model_dump()
