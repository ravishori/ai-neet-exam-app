"""Isolated review_sandbox schema — never writes to production MCQ tables."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReviewSandboxSession(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "review_sandbox"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reviewed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    partial_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_check_status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    protected_checksums: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    questions: Mapped[list[ReviewSandboxQuestion]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ReviewSandboxUpload(Base):
    __tablename__ = "uploads"
    __table_args__ = {"schema": "review_sandbox"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("review_sandbox.sessions.id", ondelete="SET NULL"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    validation_report: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class ReviewSandboxQuestion(Base):
    __tablename__ = "questions"
    __table_args__ = {"schema": "review_sandbox"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("review_sandbox.sessions.id", ondelete="CASCADE"))
    source_question_id: Mapped[str] = mapped_column(String(80), nullable=False)
    subject: Mapped[str] = mapped_column(String(40), nullable=False)
    class_level: Mapped[str | None] = mapped_column(String(10))
    chapter: Mapped[str | None] = mapped_column(String(40))
    topic: Mapped[str | None] = mapped_column(String(200))
    provider: Mapped[str | None] = mapped_column(String(40))
    difficulty: Mapped[str | None] = mapped_column(String(20))
    question_type: Mapped[str | None] = mapped_column(String(40))
    original_question: Mapped[str] = mapped_column(Text, nullable=False)
    original_option_a: Mapped[str] = mapped_column(Text, nullable=False)
    original_option_b: Mapped[str] = mapped_column(Text, nullable=False)
    original_option_c: Mapped[str] = mapped_column(Text, nullable=False)
    original_option_d: Mapped[str] = mapped_column(Text, nullable=False)
    original_proposed_answer: Mapped[str] = mapped_column(String(10), nullable=False)
    original_ncert_source: Mapped[str | None] = mapped_column(Text)
    original_validator_verdict: Mapped[str | None] = mapped_column(String(40))
    original_validation_status_before_r1: Mapped[str | None] = mapped_column(String(40))
    original_validation_status_after_r1: Mapped[str | None] = mapped_column(String(40))
    original_r1_validator_provider: Mapped[str | None] = mapped_column(String(40))
    preaudit_priority: Mapped[str | None] = mapped_column(String(20))
    preaudit_verdict: Mapped[str | None] = mapped_column(String(40))
    preaudit_reason: Mapped[str | None] = mapped_column(Text)
    preaudit_recommended_action: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    session: Mapped[ReviewSandboxSession] = relationship(back_populates="questions")
    human_review: Mapped[ReviewSandboxHumanReview | None] = relationship(back_populates="question", uselist=False, cascade="all, delete-orphan")
    ai_review: Mapped[ReviewSandboxAiReview | None] = relationship(back_populates="question", uselist=False, cascade="all, delete-orphan")


class ReviewSandboxHumanReview(Base):
    __tablename__ = "human_reviews"
    __table_args__ = {"schema": "review_sandbox"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("review_sandbox.questions.id", ondelete="CASCADE"), unique=True)
    human_stem: Mapped[str | None] = mapped_column(Text)
    human_option_a: Mapped[str | None] = mapped_column(Text)
    human_option_b: Mapped[str | None] = mapped_column(Text)
    human_option_c: Mapped[str | None] = mapped_column(Text)
    human_option_d: Mapped[str | None] = mapped_column(Text)
    human_answer: Mapped[str | None] = mapped_column(String(10))
    human_explanation: Mapped[str | None] = mapped_column(Text)
    human_ncert_support: Mapped[str | None] = mapped_column(String(40))
    human_ambiguity: Mapped[str | None] = mapped_column(String(20))
    human_duplicate: Mapped[str | None] = mapped_column(String(30))
    human_difficulty: Mapped[str | None] = mapped_column(String(20))
    human_neet_suitability: Mapped[str | None] = mapped_column(String(40))
    human_overall: Mapped[str | None] = mapped_column(String(20))
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    question: Mapped[ReviewSandboxQuestion] = relationship(back_populates="human_review")


class ReviewSandboxAiReview(Base):
    __tablename__ = "ai_reviews"
    __table_args__ = {"schema": "review_sandbox"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("review_sandbox.questions.id", ondelete="CASCADE"), unique=True)
    ai_answer_check: Mapped[str | None] = mapped_column(String(30))
    ai_answer_confidence: Mapped[float | None] = mapped_column(Float)
    ai_calculation_check: Mapped[str | None] = mapped_column(String(30))
    ai_calculated_answer: Mapped[str | None] = mapped_column(String(10))
    ai_stem_check: Mapped[str | None] = mapped_column(Text)
    ai_option_quality: Mapped[str | None] = mapped_column(String(20))
    ai_distractor_analysis: Mapped[str | None] = mapped_column(Text)
    ai_ncert_support: Mapped[str | None] = mapped_column(String(40))
    ai_ncert_evidence: Mapped[str | None] = mapped_column(Text)
    ai_scientific_check: Mapped[str | None] = mapped_column(Text)
    ai_assertion_reason_check: Mapped[str | None] = mapped_column(Text)
    ai_duplicate_check: Mapped[str | None] = mapped_column(String(40))
    ai_question_type_check: Mapped[str | None] = mapped_column(String(40))
    ai_difficulty: Mapped[str | None] = mapped_column(String(20))
    ai_neet_suitability: Mapped[str | None] = mapped_column(String(40))
    ai_overall: Mapped[str | None] = mapped_column(String(30))
    ai_reason: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    check_status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped[ReviewSandboxQuestion] = relationship(back_populates="ai_review")


class ReviewSandboxAuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = {"schema": "review_sandbox"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("review_sandbox.sessions.id", ondelete="CASCADE"))
    question_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("review_sandbox.questions.id", ondelete="SET NULL"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
