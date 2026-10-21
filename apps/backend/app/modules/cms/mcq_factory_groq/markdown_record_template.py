"""MCQ-FACTORY-5000-DELIVERY-001 — per-question Markdown record template.

Produces the full per-question Markdown record this project's 5,000-question
delivery plan commits to for EVERY future generated question — one Markdown
block per question, organized by subject / class / chapter, carrying the
complete field set: question content, classification, evidence/provenance,
validation, duplicate-check result, and reviewer status.

This module is PURE FORMATTING — it never calls a model, never touches a
database, and never invents data. ``render_question_markdown_record`` takes
a plain ``QuestionMarkdownRecord`` dataclass (every field already computed
elsewhere — by the orchestrator once real generation exists) and turns it
into one Markdown block. Any field not yet available is rendered as the
literal string ``"NOT_YET_GENERATED"`` — never a fabricated value — so a
template demonstration run against fact-level-only data (no question exists
yet) stays honest about what is and is not real.

See ``docs/quality/neet_mcq_factory_5000_delivery.md`` §6 for the
demonstration run of this module against the existing validated 100-fact
pilot pack (``data/generated_mcqs/mcq_factory_pilot/fact_pack.json``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

NOT_YET_GENERATED = "NOT_YET_GENERATED"


@dataclass
class QuestionMarkdownRecordOption:
    label: str
    text: str = NOT_YET_GENERATED
    is_correct: bool = False
    distractor_rationale: str | None = None  # why this wrong option is plausible-but-wrong; None if not applicable/correct


@dataclass
class QuestionMarkdownRecord:
    """Every field the project's record spec requires, one row per future
    generated question. Construct this from a real ``CandidateAuditRecord``
    + its ``FactSpec`` once generation actually runs; for a template
    demonstration (no generation has happened), construct it from fact-pack
    data alone and leave question-content fields at their ``NOT_YET_GENERATED``
    default — never fill them with invented text."""

    # Identity / provenance
    stable_id: str = NOT_YET_GENERATED  # (batch_id, fact_id, attempt_number) composite today
    batch_id: str = NOT_YET_GENERATED
    fact_id: str = NOT_YET_GENERATED
    attempt_number: int = 1

    # Classification
    question_type: str = "MCQ"
    question_format: str = "single_correct_mcq"
    difficulty: str = NOT_YET_GENERATED
    difficulty_rationale: str | None = None

    # Taxonomy placement
    subject: str = NOT_YET_GENERATED
    subdivision: str | None = None  # BOTANY / ZOOLOGY under Biology, if applicable
    class_level: str = NOT_YET_GENERATED
    chapter: str = NOT_YET_GENERATED
    topic: str | None = None
    concept: str | None = None
    subject_id: str | None = None
    chapter_id: str | None = None
    topic_id: str | None = None
    concept_id: str | None = None
    learning_objective: str | None = None
    syllabus_mapping: str | None = None

    # Question content
    stem: str = NOT_YET_GENERATED
    options: list[QuestionMarkdownRecordOption] = field(default_factory=list)
    correct_option: str = NOT_YET_GENERATED
    explanation: str = NOT_YET_GENERATED

    # Source / evidence
    source_book: str = NOT_YET_GENERATED
    source_edition: str | None = None
    source_page: int | str = NOT_YET_GENERATED
    source_pdf_page: int | str = NOT_YET_GENERATED
    extracted_passage: str = NOT_YET_GENERATED
    source_file: str = NOT_YET_GENERATED
    source_file_hash: str | None = None
    extraction_method: str | None = None

    # Model / run metadata
    generation_model: str | None = None
    generation_provider: str | None = None
    verification_model: str | None = None
    verification_provider: str | None = None
    generated_at: str | None = None

    # Validation / status
    validation_classification: str = NOT_YET_GENERATED  # GREEN/YELLOW/RED
    validation_gate_results: list[dict[str, Any]] = field(default_factory=list)
    publication_content_ready: bool | str = NOT_YET_GENERATED
    duplicate_check_result: str = NOT_YET_GENERATED  # "NONE" | "POSSIBLE_DUPLICATE:<source>" | NOT_YET_GENERATED
    verification_status: str = NOT_YET_GENERATED  # ACCEPTED / REVIEW_REQUIRED / REJECTED
    reviewer_notes: str | None = None
    rejection_reasons: list[str] = field(default_factory=list)
    correction_history: list[str] = field(default_factory=list)


def _fmt(value: Any) -> str:
    if value is None:
        return "_(not applicable)_"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def render_question_markdown_record(record: QuestionMarkdownRecord) -> str:
    """Render ONE question as a self-contained Markdown block. Never raises
    on missing optional data — every field has an explicit, honest
    placeholder rather than a silently-omitted section."""
    lines: list[str] = []
    heading_bits = [record.subject]
    if record.subdivision:
        heading_bits.append(record.subdivision)
    heading_bits += [f"Class {record.class_level}", record.chapter]
    lines.append(f"#### {record.stable_id} — {' / '.join(heading_bits)}")
    lines.append("")
    lines.append(f"- **Topic / Concept:** {_fmt(record.topic)} / {_fmt(record.concept)}")
    lines.append(
        f"- **Taxonomy IDs:** subject={_fmt(record.subject_id)}, chapter={_fmt(record.chapter_id)}, "
        f"topic={_fmt(record.topic_id)}, concept={_fmt(record.concept_id)}"
    )
    lines.append(f"- **Learning objective:** {_fmt(record.learning_objective)}")
    lines.append(f"- **Syllabus mapping:** {_fmt(record.syllabus_mapping)}")
    lines.append(
        f"- **Question type / format:** {record.question_type} / {record.question_format}"
    )
    lines.append(f"- **Difficulty:** {record.difficulty} — _{_fmt(record.difficulty_rationale)}_")
    lines.append("")
    lines.append(f"**Stem:** {record.stem}")
    lines.append("")
    for opt in record.options:
        marker = "✅" if opt.is_correct else "—"
        lines.append(f"- **{opt.label}.** {opt.text} {marker}")
        if not opt.is_correct and opt.distractor_rationale:
            lines.append(f"  - _Distractor rationale:_ {opt.distractor_rationale}")
    if not record.options:
        lines.append(f"_(options: {NOT_YET_GENERATED})_")
    lines.append("")
    lines.append(f"**Correct answer:** {record.correct_option}")
    lines.append("")
    lines.append(f"**Explanation:** {record.explanation}")
    lines.append("")
    lines.append("**Source / evidence**")
    lines.append(
        f"- Book: {record.source_book}" + (f" (edition: {record.source_edition})" if record.source_edition else " (edition: _not tracked_)")
    )
    lines.append(f"- Page / PDF page: {record.source_page} / {record.source_pdf_page}")
    lines.append(f"- Source file: {record.source_file}" + (f" (sha256: {record.source_file_hash})" if record.source_file_hash else ""))
    lines.append(f"- Extraction method: {_fmt(record.extraction_method)}")
    lines.append(f"- Extracted passage: _{record.extracted_passage}_")
    lines.append("")
    lines.append("**Model / run metadata**")
    lines.append(
        f"- Generation: {_fmt(record.generation_provider)}:{_fmt(record.generation_model)} | "
        f"Verification: {_fmt(record.verification_provider)}:{_fmt(record.verification_model)}"
    )
    lines.append(f"- Batch: {record.batch_id} | Fact: {record.fact_id} | Attempt: {record.attempt_number} | Generated at: {_fmt(record.generated_at)}")
    lines.append("")
    lines.append("**Validation / status**")
    lines.append(f"- Classification: {record.validation_classification} | Publication content_ready: {_fmt(record.publication_content_ready)}")
    if record.validation_gate_results:
        for g in record.validation_gate_results:
            lines.append(f"  - `{g.get('code')}`: passed={g.get('passed')} severity={g.get('severity')}")
    else:
        lines.append(f"  - _(gate results: {NOT_YET_GENERATED})_")
    lines.append(f"- Duplicate-check result: {record.duplicate_check_result}")
    lines.append(f"- Final status: **{record.verification_status}**")
    if record.rejection_reasons:
        lines.append(f"- Rejection reasons: {'; '.join(record.rejection_reasons)}")
    if record.reviewer_notes:
        lines.append(f"- Reviewer notes: {record.reviewer_notes}")
    if record.correction_history:
        lines.append(f"- Correction history: {' -> '.join(record.correction_history)}")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


def record_from_fact_spec_dict(fact: dict[str, Any], *, batch_id: str) -> QuestionMarkdownRecord:
    """Build a template-demonstration record from ONE raw fact-pack entry
    (``fact_pack.json``'s per-fact dict shape) — fact/taxonomy fields are
    real; every question-content/model/validation field is left at its
    honest ``NOT_YET_GENERATED`` default because no question has actually
    been generated for this fact. Used only to prove the template renders
    correctly against real fact data, never presented as a real question."""
    taxonomy = fact.get("taxonomy") or {}
    subject_raw = str(fact.get("subject", NOT_YET_GENERATED))
    subdivision = None
    if subject_raw == "BIOLOGY":
        # The real academic DB taxonomy (seed.py) has no single "BIOLOGY"
        # subject row — it is split into BOTANY/ZOOLOGY subject rows. The
        # pilot fact pack's "BIOLOGY" label predates that split; surfacing
        # it here (rather than silently renaming it) is itself a template-
        # demonstration finding, not a defect in this rendering function.
        subdivision = "BOTANY_OR_ZOOLOGY (fact pack predates the BOTANY/ZOOLOGY taxonomy split — not resolved here)"
    return QuestionMarkdownRecord(
        stable_id=f"{batch_id}:{fact.get('fact_id', NOT_YET_GENERATED)}:1",
        batch_id=batch_id,
        fact_id=str(fact.get("fact_id", NOT_YET_GENERATED)),
        subject=subject_raw,
        subdivision=subdivision,
        class_level=str(fact.get("class_level", NOT_YET_GENERATED)),
        chapter=str(fact.get("chapter", NOT_YET_GENERATED)),
        topic=fact.get("topic"),
        concept=fact.get("concept"),
        subject_id=taxonomy.get("subject_id"),
        chapter_id=taxonomy.get("chapter_id"),
        topic_id=taxonomy.get("topic_id"),
        concept_id=taxonomy.get("concept_id"),
        verification_status="NOT_YET_GENERATED",
        validation_classification=NOT_YET_GENERATED,
        duplicate_check_result=NOT_YET_GENERATED,
        source_book=f"NCERT Class {fact.get('class_level', '?')} {subject_raw}",
        publication_content_ready=NOT_YET_GENERATED,
    )


__all__ = [
    "NOT_YET_GENERATED",
    "QuestionMarkdownRecordOption",
    "QuestionMarkdownRecord",
    "render_question_markdown_record",
    "record_from_fact_spec_dict",
]
