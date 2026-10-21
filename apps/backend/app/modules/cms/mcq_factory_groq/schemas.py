"""Pydantic output contract for one Groq-generated practice-MCQ candidate.

Mirrors the shape/strictness conventions of
``app.modules.cms.schemas.content_bodies.QuestionBody`` (4 labeled options,
unique texts, correct_option must match a label) and
``app.modules.cms.schemas.question_evidence`` (never claim a verification
level stronger than what was actually checked), but adds the two fields
this generation pipeline specifically requires: a re-verifiable
``source_evidence`` citation and real academic-taxonomy ids.

``TaxonomyIds`` carries real ``app.modules.academic.models``
Subject/Chapter/Topic/Concept row ids (UUID strings) — the same
id-plus-name convention already established by
``app.modules.cms.services.fact_quality_gate.TaxonomyBinding``. No new
taxonomy vocabulary is invented here; ``validators.py`` rejects any id
that does not resolve to a real row.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

OPTION_LABELS = ("A", "B", "C", "D")


class CandidateOption(BaseModel):
    label: str
    text: str = Field(min_length=1)

    @field_validator("label")
    @classmethod
    def _normalize_label(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("option text must be non-empty")
        return cleaned


class SourceEvidenceRef(BaseModel):
    """Self-reported citation — NEVER trusted at face value.

    ``validators.verify_source_evidence_relocatable`` independently
    re-locates ``quoted_snippet`` inside the actually-extracted PDF text at
    ``(doc_id, page)``; a candidate whose snippet cannot be re-found is
    rejected as a fabricated citation regardless of how confident the
    model's own output looked.
    """

    doc_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    quoted_snippet: str = Field(min_length=10)


class TaxonomyIds(BaseModel):
    """Real academic-taxonomy row ids. ``concept_id`` stays optional,
    matching the existing project-wide convention that a missing
    concept_id is metadata-incomplete, not a publication blocker (see
    ``publication_gates.py`` / ``docs/PRODUCTION_READINESS.md``:
    "concept_id NULL must not block publication")."""

    subject_id: str = Field(min_length=1)
    chapter_id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    concept_id: str | None = None


class GeneratedMcqCandidate(BaseModel):
    stem: str = Field(min_length=1)
    options: list[CandidateOption] = Field(min_length=4, max_length=4)
    correct_option: str
    explanation: str = Field(min_length=1)
    source_evidence: SourceEvidenceRef
    taxonomy: TaxonomyIds
    difficulty: Literal["easy", "medium", "hard"] = "medium"

    # --- NEET-MCQ-FACTORY-5000-DELIVERY-001 schema-readiness additions ---
    # Additive, optional fields only (no existing required field touched, no
    # existing caller broken by their absence). These are NOT yet populated
    # by GENERATION_SYSTEM_PROMPT / GENERATION_USER_PROMPT_TEMPLATE
    # (prompt_templates.py is intentionally left unmodified by this task —
    # changing what the validated generation prompt asks the model for is a
    # live-prompt-behavior change, out of scope for schema-readiness work)
    # — they exist so the record SHAPE is ready to carry this data the
    # moment a future prompt revision starts populating it, without a
    # second schema migration. Until then they stay None/default and are
    # surfaced as explicit gaps in neet_mcq_factory_5000_validation.csv,
    # never fabricated.
    difficulty_rationale: str | None = None
    distractor_rationale: dict[str, str] | None = None  # {option_label: why_this_wrong_option_is_plausible_but_wrong}
    question_format: Literal["single_correct_mcq", "assertion_reason", "numerical", "multi_correct"] = (
        "single_correct_mcq"  # matches the only format the current prompt/validators actually support
    )
    learning_objective: str | None = None

    @field_validator("stem", "explanation")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must be non-empty")
        return cleaned

    @field_validator("correct_option")
    @classmethod
    def _normalize_correct(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def _validate_shape(self) -> "GeneratedMcqCandidate":
        labels = [opt.label for opt in self.options]
        if sorted(labels) != sorted(OPTION_LABELS):
            raise ValueError("options must be labeled A, B, C, D exactly once each")
        texts = [opt.text.strip().lower() for opt in self.options]
        if len(set(texts)) != 4:
            raise ValueError("option texts must be unique")
        if self.correct_option not in labels:
            raise ValueError("correct_option must match an option label")
        return self

    def option_text(self, label: str) -> str | None:
        for opt in self.options:
            if opt.label == label.strip().upper():
                return opt.text
        return None

    def to_question_body_dict(self) -> dict:
        """Adapt to the shape the existing deterministic gates
        (``factory_qa_gates.gate_a_structure`` et al.) and
        ``factory_v2_answer_ambiguity`` already know how to validate."""
        return {
            "stem": self.stem,
            "options": [{"label": o.label, "text": o.text} for o in self.options],
            "correct_option": self.correct_option,
            "explanation": self.explanation,
            "difficulty": self.difficulty,
        }


__all__ = [
    "OPTION_LABELS",
    "CandidateOption",
    "SourceEvidenceRef",
    "TaxonomyIds",
    "GeneratedMcqCandidate",
]
