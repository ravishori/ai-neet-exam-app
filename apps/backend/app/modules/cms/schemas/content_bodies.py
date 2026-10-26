"""Body shapes per content_type — see ADR-0009 / the ECAEP spec.

Stored as JSONB on content_versions.body. Validated at the API boundary
against the schema matching the content_item's content_type; never a
dedicated column per field.

WAVE-P0-4: QUESTION bodies must meet NEET MCQ structural gates (4 options
A–D, non-empty stem/explanation, correct_option ∈ labels, unique texts).
Publish re-runs the same validation (status flip alone is not enough).
"""

from __future__ import annotations

import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.cms.schemas.question_evidence import NcertEvidence, NumericalEvidence, ProvenanceBlock

NEET_OPTION_LABELS = ("A", "B", "C", "D")

# Legitimate whitespace control characters a stem/option may contain —
# never flagged. Every other Unicode "Cc" (control) codepoint (C0 codes
# \x00-\x08, \x0B, \x0C, \x0E-\x1F, plus DEL \x7F and the C1 range
# \x80-\x9F) is a mis-segmented-extraction artifact in this corpus (see
# the 2026-10-22 PYQ integrity audit, docs/content-factory/
# PYQ_ANSWER_KEY_STATUS.md), never legitimate exam content.
_ALLOWED_CONTROL_CHARS = frozenset({"\t", "\n", "\r"})


def find_prohibited_control_characters(text: str) -> list[str]:
    """Returns the distinct prohibited control characters found in `text`,
    using Unicode category "Cc" (not an ASCII-range check) so this never
    flags ordinary printable Unicode — scientific notation (×, ⁻, ³),
    chemical formula subscripts/superscripts (₂, ₄), Greek letters (α, β,
    Δ), arrows (→, ⇌), the degree symbol (°), or any other non-control
    codepoint are all category "Ll"/"Lu"/"Sm"/"No"/etc., never "Cc", and
    are therefore always preserved untouched."""
    return sorted({ch for ch in text if unicodedata.category(ch) == "Cc" and ch not in _ALLOWED_CONTROL_CHARS})


def reject_prohibited_control_characters(text: str, *, field_label: str) -> None:
    bad = find_prohibited_control_characters(text)
    if bad:
        codepoints = ", ".join(f"U+{ord(c):04X}" for c in bad)
        raise ValueError(f"{field_label} contains prohibited control character(s): {codepoints}")


class ConceptNoteBody(BaseModel):
    ncert_ref: str | None = None
    summary: str = Field(min_length=1)
    sections: list[str] = []


class QuestionOption(BaseModel):
    label: str
    text: str = Field(min_length=1)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("option text must be non-empty")
        reject_prohibited_control_characters(cleaned, field_label="option text")
        return cleaned


AnswerStatus = Literal["ANSWER_VERIFIED", "ANSWER_PENDING"]


class QuestionBody(BaseModel):
    stem: str = Field(min_length=1)
    options: list[QuestionOption] = Field(min_length=4, max_length=4)
    correct_option: str
    explanation: str = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    bloom_level: str | None = None
    pyq_year: int | None = None
    # Explicit, admin-set answer-verification status. Never inferred/guessed
    # -- see validate_neet_mcq_shape below: ANSWER_VERIFIED additionally
    # requires real evidence (ncert_evidence beyond NOT_VERIFIED), not just
    # a correct_option being present (every QUESTION already requires that).
    answer_status: AnswerStatus | None = None
    # T6-E-FIX: optional on draft; mandatory at publish via publication_gates
    ncert_evidence: NcertEvidence | None = None
    provenance: ProvenanceBlock | None = None
    numerical_evidence: NumericalEvidence | None = None
    calculation_check: dict | None = None
    # Seed V2 factory visuals (optional). Not NCERT evidence by themselves.
    diagram_svg: str | None = None
    diagram_description: str | None = None
    visual_spec: dict | None = None

    @field_validator("stem", "explanation")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must be non-empty")
        reject_prohibited_control_characters(cleaned, field_label="stem/explanation")
        return cleaned

    @field_validator("correct_option")
    @classmethod
    def normalize_correct(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_neet_mcq_shape(self) -> QuestionBody:
        labels = [opt.label for opt in self.options]
        if sorted(labels) != sorted(NEET_OPTION_LABELS):
            raise ValueError("QUESTION must have options labeled A, B, C, D exactly once each")
        texts = [opt.text.lower() for opt in self.options]
        if len(set(texts)) != 4:
            raise ValueError("option texts must be unique")
        if self.correct_option not in labels:
            raise ValueError("correct_option must match an option label")
        if self.answer_status == "ANSWER_VERIFIED" and (
            self.ncert_evidence is None or self.ncert_evidence.verification_level == "NOT_VERIFIED"
        ):
            raise ValueError(
                "answer_status ANSWER_VERIFIED requires verified evidence "
                "(ncert_evidence with a verification_level beyond NOT_VERIFIED) -- "
                "never mark an answer verified without recording what verified it"
            )
        return self


class FlashcardBody(BaseModel):
    """Student revision card. Optional provenance/difficulty enrichments are
    additive and backward-compatible with legacy {front, back} bodies."""

    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    image_url: str | None = None
    explanation: str | None = None
    difficulty: Literal["easy", "medium", "hard"] | None = None
    source: str | None = None
    source_reference: str | None = None
    class_level: Literal["11", "12"] | None = None
    # Certification audit overlays (SEED-V1 audit) — not set by structural import alone.
    certification_status: Literal["VERIFIED", "REVIEW", "REJECTED"] | None = None
    certification_reason: str | None = None
    certification_provenance: str | None = None
    certification_flags: list[str] | None = None
    certified_at: str | None = None
    certification_batch: str | None = None
    certification_evidence_class: str | None = None
    certification_claim: str | None = None
    certification_evidence: str | None = None
    certification_prev_status: str | None = None


class DiagramBody(BaseModel):
    image_url: str = Field(min_length=1)
    labels: list[str] = []
    alt_text: str = Field(min_length=1)


class VideoRefBody(BaseModel):
    external_url: str = Field(min_length=1)
    provider: str = "youtube"
    duration_sec: int | None = None
    transcript_url: str | None = None


class FormulaSheetBody(BaseModel):
    formulas: list[str] = Field(min_length=1)


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


# Disqualifying answer_status values that must never reach a student
# practice/scored-assessment selection pool, even on a PUBLISHED item --
# "pending" or "conflicted" are "ANSWER_PENDING"/"ANSWER_CONFLICT" at the
# PYQ-staging layer (pyq.questions.state); if either value is ever copied
# into a content_item body's own answer_status (today's QuestionBody.
# AnswerStatus type only names ANSWER_VERIFIED/ANSWER_PENDING, but a raw
# DB write bypassing this schema could still carry ANSWER_CONFLICT), it
# must be excluded here too -- defensive on the raw dict value, checked
# BEFORE/independent of schema validation, not assumed impossible.
_DISQUALIFYING_ANSWER_STATUSES = frozenset({"ANSWER_PENDING", "ANSWER_CONFLICT"})


def is_student_eligible(content_type: str, body: dict) -> tuple[bool, str | None]:
    """Whether this content body may be served to a student for practice
    or a scored assessment -- publication status (PUBLISHED) alone never
    implies this; call this ON TOP OF that status check, never instead of
    it. Returns (eligible, reason) -- reason is None when eligible, else a
    short machine-readable code for audit logging.

    Deliberately does NOT require an explicit answer_status of
    "ANSWER_VERIFIED" -- most of today's real content was published
    before that field was consistently populated (see
    helpers_publishable_question.py, the test suite's own shared
    publishable-question fixture, which never sets it either), and
    requiring it retroactively would silently empty the entire existing
    practice pool rather than fixing the actual defect this gate targets.
    What this DOES exclude, unconditionally: a body that fails the same
    structural validation publish already re-checks (assert_body_
    publishable's own schema -- 4 unique-text options A-D, a correct_option
    matching one of them, non-empty stem/explanation), and a body whose
    answer_status is explicitly ANSWER_PENDING or ANSWER_CONFLICT -- i.e.
    an explicit "this isn't resolved yet" flag always wins over
    publication status, exactly as asked.

    Normalizes ``options`` via ``app.shared.question_options.normalize_options``
    before validating -- the SAME normalization every student-facing
    renderer (assessment_router._public_question/_result_question,
    editorial_review_service.review_packet, search_service) already
    applies. A production format audit (F-17) found 12,396 of 19,589
    QUESTION rows store options as a dict keyed by letter, not the list
    shape QuestionBody's own schema expects -- validating the raw,
    unnormalized body here would make this gate reject the majority of
    real, already-correctly-rendered published content as "structurally
    invalid", which is not the defect this gate exists to catch."""
    if content_type != "QUESTION":
        return True, None

    raw_status = body.get("answer_status")
    if raw_status in _DISQUALIFYING_ANSWER_STATUSES:
        return False, raw_status

    from app.shared.question_options import normalize_options

    body = {**body, "options": normalize_options(body.get("options"))}

    from pydantic import ValidationError

    try:
        validate_body(content_type, body)
    except (ValidationError, ValueError):
        return False, "STRUCTURALLY_INVALID"

    return True, None


def assert_body_publishable(content_type: str, body: dict) -> dict:
    """Re-validate body at publish time. Raises AppError on failure."""
    from pydantic import ValidationError

    from app.core.exceptions import AppError

    try:
        return validate_body(content_type, body)
    except ValidationError as exc:
        raise AppError(
            "Content body failed publishing quality gates. Fix the draft and re-approve before publishing.",
            code="INVALID_CONTENT_BODY",
            status_code=422,
        ) from exc
    except ValueError as exc:
        raise AppError(str(exc), code="INVALID_CONTENT_TYPE", status_code=400) from exc
