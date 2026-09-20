"""Content Factory planning entities (FACTORY-P2).

Defines WHAT to generate. Does not generate questions or mutate ECAEP content.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.cms.models.content_factory import SOURCE_TIERS
from app.shared.mixins import AuditedBase

DIFFICULTIES = ("easy", "medium", "hard")
DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}

LEARNING_LEVELS = ("recall", "understand", "apply", "analyze", "evaluate")

BLUEPRINT_STATUSES = ("DRAFT", "ACTIVE", "SUPERSEDED", "ARCHIVED")

# Reuse P1 provenance vocabulary; "official_source" is rejected as a claim label —
# use authoritative/licensed/human/ai/derived explicitly.
PROVENANCE_TIERS = SOURCE_TIERS

QUESTION_FORMATS = ("MCQ_4",)


class LearningObjective(Base, AuditedBase):
    __tablename__ = "learning_objectives"
    __table_args__ = (
        UniqueConstraint("objective_key", name="uq_cms_learning_objectives_key"),
        Index("ix_cms_learning_objectives_concept_id", "concept_id"),
        Index("ix_cms_learning_objectives_is_active", "is_active"),
        {"schema": "cms"},
    )

    objective_key: Mapped[str] = mapped_column(String(120), nullable=False)
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.concepts.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    learning_level: Mapped[str] = mapped_column(String(30), nullable=False, default="apply")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class QuestionFamily(Base, AuditedBase):
    __tablename__ = "question_families"
    __table_args__ = (
        UniqueConstraint("family_key", name="uq_cms_question_families_key"),
        Index("ix_cms_question_families_is_active", "is_active"),
        {"schema": "cms"},
    )

    family_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Subject codes e.g. PHYSICS, CHEMISTRY, BOTANY, ZOOLOGY — not free-form prose.
    applicable_subject_codes: Mapped[list[str]] = mapped_column(ARRAY(String(30)), nullable=False)
    cognitive_intent: Mapped[str] = mapped_column(String(200), nullable=False)
    difficulty_min: Mapped[str] = mapped_column(String(20), nullable=False, default="easy")
    difficulty_max: Mapped[str] = mapped_column(String(20), nullable=False, default="hard")
    question_format: Mapped[str] = mapped_column(String(30), nullable=False, default="MCQ_4")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class QuestionBlueprint(Base, AuditedBase):
    """Generation contract for FACTORY-P3. Never stores question bodies."""

    __tablename__ = "question_blueprints"
    __table_args__ = (
        UniqueConstraint("blueprint_key", "blueprint_version", name="uq_cms_blueprints_key_version"),
        Index("ix_cms_question_blueprints_concept_id", "concept_id"),
        Index("ix_cms_question_blueprints_status", "status"),
        Index("ix_cms_question_blueprints_family_id", "question_family_id"),
        Index("ix_cms_question_blueprints_objective_id", "learning_objective_id"),
        Index("ix_cms_question_blueprints_eligible", "generation_eligible"),
        {"schema": "cms"},
    )

    blueprint_key: Mapped[str] = mapped_column(String(120), nullable=False)
    blueprint_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.subjects.id", ondelete="RESTRICT"), nullable=False
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.chapters.id", ondelete="RESTRICT"), nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.topics.id", ondelete="RESTRICT"), nullable=False
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.concepts.id", ondelete="RESTRICT"), nullable=False
    )
    learning_objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.learning_objectives.id", ondelete="RESTRICT"), nullable=False
    )
    question_family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.question_families.id", ondelete="RESTRICT"), nullable=False
    )
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Constraints / reasoning / distractors / explanation — never question stems.
    constraints: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    provenance_tier: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    generation_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Explains last validate() outcome (deterministic planning checks).
    last_validation: Mapped[dict | None] = mapped_column(JSONB)

    learning_objective: Mapped[LearningObjective] = relationship()
    question_family: Mapped[QuestionFamily] = relationship()


class CoverageSlice(Base, AuditedBase):
    """Demand-driven coverage plan cell. Counts are computed at read time."""

    __tablename__ = "coverage_slices"
    __table_args__ = (
        UniqueConstraint("slice_key", name="uq_cms_coverage_slices_key"),
        Index("ix_cms_coverage_slices_subject_id", "subject_id"),
        Index("ix_cms_coverage_slices_concept_id", "concept_id"),
        Index("ix_cms_coverage_slices_family_id", "question_family_id"),
        {"schema": "cms"},
    )

    slice_key: Mapped[str] = mapped_column(String(160), nullable=False)
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
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    question_family_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.question_families.id", ondelete="SET NULL"), nullable=True
    )
    target_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ContentBatchBlueprint(Base, AuditedBase):
    """Batch ↔ blueprint association for P3 job targeting."""

    __tablename__ = "content_batch_blueprints"
    __table_args__ = (
        UniqueConstraint("batch_id", "blueprint_id", name="uq_cms_batch_blueprint"),
        Index("ix_cms_batch_blueprints_batch_id", "batch_id"),
        Index("ix_cms_batch_blueprints_blueprint_id", "blueprint_id"),
        {"schema": "cms"},
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_batches.id", ondelete="CASCADE"), nullable=False
    )
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.question_blueprints.id", ondelete="RESTRICT"), nullable=False
    )
    # Optional override; NULL means use blueprint.target_count.
    requested_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
