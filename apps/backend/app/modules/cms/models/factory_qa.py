"""FACTORY-P4 automated QA results + sampling preparation.

Factory QA classification is orthogonal to ECAEP ContentItem.status.
GREEN ≠ approved ≠ publishable. RED ≠ ARCHIVED — quarantine is factory-level.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase

QA_VERSION_V1 = "factory_qa_v1"
SAMPLING_POLICY_V1 = "factory_sample_v1"

QA_CLASSIFICATIONS = ("GREEN", "YELLOW", "RED")
DUPLICATE_CLASSES = (
    "UNIQUE",
    "EXACT_DUPLICATE",
    "NORMALIZED_DUPLICATE",
    "POSSIBLE_DUPLICATE",
    "SEMANTIC_UNCHECKED",
)

GATE_CODES = ("A_STRUCTURE", "B_BLUEPRINT", "C_HIERARCHY", "D_PROVENANCE", "E_ANSWER", "F_DUPLICATE", "G_SAFETY")


class QAResult(Base, AuditedBase):
    """Immutable-ish evaluation evidence. Re-runs create new evaluation_no rows."""

    __tablename__ = "qa_results"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "qa_version",
            "evaluation_no",
            name="uq_cms_qa_results_candidate_version_eval",
        ),
        Index("ix_cms_qa_results_batch_id", "batch_id"),
        Index("ix_cms_qa_results_candidate_id", "candidate_id"),
        Index("ix_cms_qa_results_classification", "classification"),
        Index("ix_cms_qa_results_qa_version", "qa_version"),
        Index(
            "uq_cms_qa_results_latest",
            "candidate_id",
            "qa_version",
            unique=True,
            postgresql_where=text("is_latest IS TRUE AND deleted_at IS NULL"),
        ),
        {"schema": "cms"},
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.generation_candidates.id", ondelete="CASCADE"), nullable=False
    )
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="SET NULL"), nullable=True
    )
    content_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_versions.id", ondelete="SET NULL"), nullable=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_batches.id", ondelete="CASCADE"), nullable=False
    )
    qa_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.generation_jobs.id", ondelete="SET NULL"), nullable=True
    )
    qa_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.generation_runs.id", ondelete="SET NULL"), nullable=True
    )
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.generation_runs.id", ondelete="SET NULL"), nullable=True
    )
    blueprint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.question_blueprints.id", ondelete="SET NULL"), nullable=True
    )
    blueprint_version: Mapped[int | None] = mapped_column(Integer)

    qa_version: Mapped[str] = mapped_column(String(40), nullable=False, default=QA_VERSION_V1)
    evaluation_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    classification: Mapped[str] = mapped_column(String(10), nullable=False)
    gate_results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    failed_checks: Mapped[list] = mapped_column(ARRAY(String(80)), nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(ARRAY(String(80)), nullable=False, default=list)

    duplicate_class: Mapped[str] = mapped_column(String(40), nullable=False, default="SEMANTIC_UNCHECKED")
    duplicate_of_item_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    duplicate_of_candidate_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))

    sampling_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quarantine: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Explicit: automated QA is NEVER scientific certification.
    scientific_certification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disclaimer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="AUTOMATED_QA_ONLY — not scientifically certified; not approved; not publishable",
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class QuestionFingerprint(Base, AuditedBase):
    """DB-backed stem/option hashes for scalable dedupe (not semantic)."""

    __tablename__ = "question_fingerprints"
    __table_args__ = (
        UniqueConstraint("content_item_id", name="uq_cms_question_fingerprints_item"),
        Index("ix_cms_question_fingerprints_stem_hash", "stem_hash"),
        Index("ix_cms_question_fingerprints_option_stem_hash", "option_stem_hash"),
        Index("ix_cms_question_fingerprints_concept_stem", "concept_id", "stem_hash"),
        {"schema": "cms"},
    )

    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="CASCADE"), nullable=False
    )
    content_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_versions.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.concepts.id", ondelete="SET NULL"), nullable=True
    )
    stem_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    option_stem_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ReviewSample(Base, AuditedBase):
    """FACTORY-P4 sampling preparation — eligibility draw, not certification."""

    __tablename__ = "review_samples"
    __table_args__ = (
        UniqueConstraint("sample_key", name="uq_cms_review_samples_sample_key"),
        Index("ix_cms_review_samples_batch_id", "batch_id"),
        {"schema": "cms"},
    )

    sample_key: Mapped[str] = mapped_column(String(120), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_batches.id", ondelete="CASCADE"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False, default=SAMPLING_POLICY_V1)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    green_sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_candidate_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    yellow_candidate_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    red_candidate_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    selection_reasons: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    strata_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Sampling eligibility only — does not approve, publish, or scientifically certify",
    )

# FACTORY-P5 — factory human review (≠ ECAEP ContentItem.status)
FACTORY_REVIEW_STATUSES = (
    "SELECTED",
    "IN_REVIEW",
    "ACCEPTED",
    "CORRECTION_REQUIRED",
    "REJECTED",
)
FACTORY_REVIEW_DECISIONS = ("ACCEPT", "CORRECTION_REQUIRED", "REJECT")
FACTORY_SELECTION_CLASSES = ("GREEN_SAMPLE", "YELLOW", "RED")
FACTORY_FAILURE_REASONS = (
    "SCIENTIFIC_ERROR",
    "WRONG_ANSWER",
    "AMBIGUOUS",
    "BAD_DISTRACTOR",
    "WRONG_DIFFICULTY",
    "WRONG_MAPPING",
    "POOR_EXPLANATION",
    "LANGUAGE_PROBLEM",
    "DUPLICATE",
    "PROVENANCE_PROBLEM",
    "NEET_UNSUITABLE",
)

FACTORY_HUMAN_CHECKLIST = (
    {"id": "scientific_correctness", "category": "A. Scientific correctness", "prompt": "Is the question scientifically correct?"},
    {"id": "correct_answer", "category": "B. Correct answer", "prompt": "Is exactly one answer defensibly correct?"},
    {"id": "distractors", "category": "C. Distractors", "prompt": "Are distractors plausible and educationally useful?"},
    {"id": "neet_suitability", "category": "D. NEET suitability", "prompt": "Is the question appropriate for NEET level and style?"},
    {"id": "explanation", "category": "E. Explanation", "prompt": "Is the explanation correct, clear, and sufficient?"},
    {"id": "academic_mapping", "category": "F. Academic mapping", "prompt": "Does the question assess the mapped concept/objective?"},
    {"id": "difficulty", "category": "G. Difficulty", "prompt": "Is the difficulty appropriate?"},
    {"id": "language", "category": "H. Language", "prompt": "Is the wording clear and unambiguous?"},
    {"id": "provenance", "category": "I. Provenance", "prompt": "Does the provenance accurately describe the origin?"},
)


class FactoryReviewItem(Base, AuditedBase):
    """Per-candidate factory sample membership + human decision evidence.

    Factory review status is orthogonal to ECAEP DRAFT→…→PUBLISHED.
    ACCEPT ≠ approve ≠ publish.
    """

    __tablename__ = "factory_review_items"
    __table_args__ = (
        UniqueConstraint("sample_id", "candidate_id", name="uq_cms_factory_review_items_sample_candidate"),
        Index("ix_cms_factory_review_items_batch_id", "batch_id"),
        Index("ix_cms_factory_review_items_status", "review_status"),
        Index("ix_cms_factory_review_items_selection_class", "selection_class"),
        Index("ix_cms_factory_review_items_content_item_id", "content_item_id"),
        Index("ix_cms_factory_review_items_candidate_id", "candidate_id"),
        {"schema": "cms"},
    )

    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.review_samples.id", ondelete="CASCADE"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_batches.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.generation_candidates.id", ondelete="CASCADE"), nullable=False
    )
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="SET NULL"), nullable=True
    )
    qa_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.qa_results.id", ondelete="SET NULL"), nullable=True
    )
    qa_version: Mapped[str | None] = mapped_column(String(40))
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False, default=SAMPLING_POLICY_V1)
    selection_class: Mapped[str] = mapped_column(String(20), nullable=False)
    selection_reason: Mapped[str | None] = mapped_column(String(120))
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="SELECTED")
    decision: Mapped[str | None] = mapped_column(String(30))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    checklist: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    failure_reasons: Mapped[list] = mapped_column(ARRAY(String(40)), nullable=False, default=list)
    ecaep_submit_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disclaimer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Factory human review ≠ ECAEP approval ≠ publication ≠ scientific certification of the full batch",
    )
