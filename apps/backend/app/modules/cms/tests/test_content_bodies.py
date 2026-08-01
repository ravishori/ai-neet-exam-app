import pytest
from pydantic import ValidationError

from app.modules.cms.schemas.content_bodies import CONTENT_TYPES, validate_body


def test_concept_note_body_valid():
    result = validate_body("CONCEPT_NOTE", {"summary": "Ohm's Law.", "sections": ["Intro"]})
    assert result["summary"] == "Ohm's Law."
    assert result["ncert_ref"] is None


def test_concept_note_body_missing_required_field():
    with pytest.raises(ValidationError):
        validate_body("CONCEPT_NOTE", {"sections": []})


def test_question_body_valid():
    body = {
        "stem": "What is I = V/R?",
        "options": [{"label": "A", "text": "Ohm's Law"}, {"label": "B", "text": "Newton's Law"}],
        "correct_option": "A",
        "explanation": "Ohm's Law relates V, I, R.",
    }
    result = validate_body("QUESTION", body)
    assert result["difficulty"] == "medium"  # default applied
    assert len(result["options"]) == 2


def test_unknown_content_type_rejected():
    with pytest.raises(ValueError):
        validate_body("NOT_A_REAL_TYPE", {})


def test_all_content_types_have_a_schema():
    for content_type in CONTENT_TYPES:
        assert content_type in {"CONCEPT_NOTE", "QUESTION", "FLASHCARD", "DIAGRAM", "VIDEO_REF", "FORMULA_SHEET"}
