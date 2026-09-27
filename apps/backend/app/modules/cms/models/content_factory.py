"""Content Factory orchestration entities (FACTORY-P1).

Batch CERTIFIED/RELEASED ≠ question APPROVED/PUBLISHED.
Student visibility remains ECAEP ContentItem.status == PUBLISHED only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase

if TYPE_CHECKING:
    pass

# Batch orchestration lifecycle — orthogonal to ECAEP DRAFT→…→PUBLISHED.
BATCH_STATUSES = (
    "CREATED",
    "GENERATING",
    "QA",
    "SAMPLING",
    "CERTIFIED",
    "RELEASE_CANDIDATE",
    "RELEASED",
    "QUARANTINED",
    "FAILED",
)

BATCH_TRANSITIONS: dict[str, frozenset[str]] = {
    "CREATED": frozenset({"GENERATING", "FAILED", "QUARANTINED"}),
    "GENERATING": frozenset({"QA", "FAILED", "QUARANTINED"}),
    "QA": frozenset({"SAMPLING", "FAILED", "QUARANTINED"}),
    "SAMPLING": frozenset({"CERTIFIED", "FAILED", "QUARANTINED"}),
    "CERTIFIED": frozenset({"RELEASE_CANDIDATE", "FAILED", "QUARANTINED"}),
    "RELEASE_CANDIDATE": frozenset({"RELEASED", "FAILED", "QUARANTINED"}),
    "RELEASED": frozenset({"QUARANTINED"}),
    "QUARANTINED": frozenset({"QA", "FAILED"}),
    "FAILED": frozenset({"GENERATING", "QUARANTINED"}),
}

SOURCE_TIERS = ("authoritative", "licensed", "human", "ai", "derived")
SOURCE_TYPES = ("HUMAN", "AI", "LICENSED", "AUTHORITATIVE", "DERIVED", "MIXED")

JOB_TYPES = ("GENERATE", "VALIDATE", "DEDUPE", "SAMPLE", "IMPORT")
JOB_STATUSES = ("PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED")
JOB_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"RUNNING", "CANCELLED", "FAILED"}),
    "RUNNING": frozenset({"SUCCEEDED", "FAILED", "CANCELLED"}),
    "FAILED": frozenset({"PENDING", "CANCELLED"}),  # retry resets to PENDING then new run
    "SUCCEEDED": frozenset(),
    "CANCELLED": frozenset(),
}

RUN_STATUSES = ("PENDING", "RUNNING", "SUCCEEDED", "FAILED")
RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"RUNNING", "FAILED"}),
    "RUNNING": frozenset({"SUCCEEDED", "FAILED"}),
    "SUCCEEDED": frozenset(),
    "FAILED": frozenset(),
}

DEFAULT_MAX_RETRIES = 3


class ContentBatch(Base, AuditedBase):
    __tablename__ = "content_batches"
    __table_args__ = (
        UniqueConstraint("batch_key", name="uq_cms_content_batches_batch_key"),
        Index("ix_cms_content_batches_status", "status"),
        Index("ix_cms_content_batches_subject_id", "subject_id"),
        Index("ix_cms_content_batches_created_at", "created_at"),
        {"schema": "cms"},
    )

    batch_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.subjects.id", ondelete="RESTRICT"), nullable=False
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.chapters.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.topics.id", ondelete="SET NULL"), nullable=True
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.concepts.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="HUMAN")
    source_tier: Mapped[str] = mapped_column(String(30), nullable=False, default="human")
    target_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qa_pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="CREATED")

    jobs: Mapped[list[GenerationJob]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="GenerationJob.created_at",
    )


class GenerationJob(Base, AuditedBase):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        UniqueConstraint("batch_id", "job_key", name="uq_cms_generation_jobs_batch_job_key"),
        Index("ix_cms_generation_jobs_batch_id", "batch_id"),
        Index("ix_cms_generation_jobs_status", "status"),
        Index("ix_cms_generation_jobs_blueprint_id", "blueprint_id"),
        {"schema": "cms"},
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_batches.id", ondelete="CASCADE"), nullable=False
    )
    job_key: Mapped[str] = mapped_column(String(120), nullable=False)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=DEFAULT_MAX_RETRIES)
    error_code: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # FACTORY-P2: optional blueprint target for P3 generation (nullable; unused until P3).
    blueprint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cms.question_blueprints.id", ondelete="SET NULL"),
        nullable=True,
    )
    blueprint_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    batch: Mapped[ContentBatch] = relationship(back_populates="jobs")
    runs: Mapped[list[GenerationRun]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="GenerationRun.attempt_number",
    )


class GenerationRun(Base, AuditedBase):
    __tablename__ = "generation_runs"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_cms_generation_runs_job_attempt"),
        Index("ix_cms_generation_runs_job_id", "job_id"),
        Index("ix_cms_generation_runs_status", "status"),
        {"schema": "cms"},
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.generation_jobs.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    # Safe operational metadata only — never store secrets or full prompts.
    execution_metadata: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[GenerationJob] = relationship(back_populates="runs")
