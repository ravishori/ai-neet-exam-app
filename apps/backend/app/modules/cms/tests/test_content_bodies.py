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
        "options": [
            {"label": "A", "text": "Ohm's Law"},
            {"label": "B", "text": "Newton's Law"},
            {"label": "C", "text": "Hooke's Law"},
            {"label": "D", "text": "Faraday's Law"},
        ],
        "correct_option": "A",
        "explanation": "Ohm's Law relates V, I, R.",
    }
    result = validate_body("QUESTION", body)
    assert result["difficulty"] == "medium"  # default applied
    assert len(result["options"]) == 4


def test_unknown_content_type_rejected():
    with pytest.raises(ValueError):
        validate_body("NOT_A_REAL_TYPE", {})


def test_all_content_types_have_a_schema():
    for content_type in CONTENT_TYPES:
        assert content_type in {"CONCEPT_NOTE", "QUESTION", "FLASHCARD", "DIAGRAM", "VIDEO_REF", "FORMULA_SHEET"}


# ---------------------------------------------------------------------------
# Control-character hardening (2026-10-22 PYQ integrity audit follow-up —
# docs/content-factory/PYQ_ANSWER_KEY_STATUS.md). The 38 real affected
# production rows all carry U+0001 (SOH) or U+0004 (EOT) inside raw_stem,
# never inside an option. Both are reproduced below verbatim, plus
# synthetic option-text cases for completeness since the shared rule
# applies to both fields identically.
# ---------------------------------------------------------------------------

_VALID_QUESTION_BASE = {
    "options": [
        {"label": "A", "text": "2.50×10⁻³ m"},
        {"label": "B", "text": "H₂SO₄ concentration"},
        {"label": "C", "text": "α and β particles, Δ energy"},
        {"label": "D", "text": "A → B ⇌ C at 25°"},
    ],
    "correct_option": "A",
    "explanation": "Reference explanation text.",
}


def test_scientific_and_chemical_notation_options_pass_unmodified():
    body = {**_VALID_QUESTION_BASE, "stem": "Evaluate the expression below."}
    result = validate_body("QUESTION", body)
    texts = [opt["text"] for opt in result["options"]]
    assert "2.50×10⁻³ m" in texts
    assert "H₂SO₄ concentration" in texts
    assert "α and β particles, Δ energy" in texts
    assert "A → B ⇌ C at 25°" in texts


def test_intentional_multiline_option_with_legitimate_whitespace_passes():
    body = {
        **_VALID_QUESTION_BASE,
        "stem": "A multi-line option is legitimate when it has no control bytes.",
        "options": [
            {"label": "A", "text": "Line one\nLine two"},
            {"label": "B", "text": "Tab\tseparated\tvalue"},
            {"label": "C", "text": "carriage\rreturn case"},
            {"label": "D", "text": "plain option"},
        ],
    }
    result = validate_body("QUESTION", body)
    assert "\n" in result["options"][0]["text"]
    assert "\t" in result["options"][1]["text"]


@pytest.mark.parametrize(
    "bad_char",
    ["\x01", "\x04", "\x00", "\x02", "\x03", "\x05", "\x06", "\x07", "\x08", "\x0b", "\x0c", "\x0e", "\x1f", "\x7f"],
)
def test_prohibited_control_character_in_stem_rejected(bad_char):
    body = {**_VALID_QUESTION_BASE, "stem": f"A vehicle travels half the distance{bad_char}at speed v."}
    with pytest.raises(ValidationError):
        validate_body("QUESTION", body)


def test_real_production_corruption_pattern_in_stem_rejected():
    # Reproduces the actual pattern found in the 38 affected ANSWER_PENDING
    # rows (e.g. staging_id f5d9003c-0d80-4d1e-89d0-d4ab265d863f): a stray
    # SOH control byte immediately preceding a damaged exponent fragment.
    corrupted_stem = (
        "A vehicle travels half the distance with speed\r\n\x01\r\n and the "
        "remaining distance with speed 2.50×10⁻³ m/s."
    )
    body = {**_VALID_QUESTION_BASE, "stem": corrupted_stem}
    with pytest.raises(ValidationError):
        validate_body("QUESTION", body)


def test_prohibited_control_character_in_option_text_rejected():
    body = {
        **_VALID_QUESTION_BASE,
        "stem": "Clean stem text.",
        "options": [
            {"label": "A", "text": "2.50\x01×10⁻³ m"},
            {"label": "B", "text": "option b"},
            {"label": "C", "text": "option c"},
            {"label": "D", "text": "option d"},
        ],
    }
    with pytest.raises(ValidationError):
        validate_body("QUESTION", body)
