"""FACTORY-P3 generation candidate lineage (not question bodies)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase

CANDIDATE_STATUSES = (
    "CREATED",
    "REJECTED_VALIDATION",
    "REJECTED_DUPLICATE",
    "FAILED_PROVIDER",
    "FAILED_PARSE",
    "FAILED_BUDGET",
)


class GenerationCandidate(Base, AuditedBase):
    __tablename__ = "generation_candidates"
    __table_args__ = (
        UniqueConstraint("run_id", "attempt_no", name="uq_cms_gen_candidates_run_attempt"),
        Index("ix_cms_gen_candidates_job_id", "job_id"),
        Index("ix_cms_gen_candidates_run_id", "run_id"),
        Index("ix_cms_gen_candidates_stem_hash", "stem_hash"),
        Index("ix_cms_gen_candidates_status", "status"),
        {"schema": "cms"},
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_batches.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.generation_jobs.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.generation_runs.id", ondelete="CASCADE"), nullable=False
    )
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.question_blueprints.id", ondelete="RESTRICT"), nullable=False
    )
    blueprint_version: Mapped[int] = mapped_column(Integer, nullable=False)
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.concepts.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    stem_hash: Mapped[str | None] = mapped_column(String(64))
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="SET NULL"), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_summary: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    cost_usd: Mapped[float | None] = mapped_column(Float)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # FACTORY-P3.1 provider lineage
    provider: Mapped[str | None] = mapped_column(String(40))
    routing_policy: Mapped[str | None] = mapped_column(String(120))
    provider_attempt_no: Mapped[int | None] = mapped_column(Integer)
    cost_status: Mapped[str | None] = mapped_column(String(20))
    provider_request_id: Mapped[str | None] = mapped_column(String(120))
    generator_version: Mapped[str | None] = mapped_column(String(80))
    # FACTORY-P4 — factory QA state (≠ ECAEP ContentItem.status)
    qa_classification: Mapped[str | None] = mapped_column(String(10))
    qa_quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    latest_qa_result_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    option_stem_hash: Mapped[str | None] = mapped_column(String(64))
    # FACTORY-P5 — factory human review status (≠ ECAEP)
    factory_review_status: Mapped[str | None] = mapped_column(String(30))
    latest_factory_review_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
