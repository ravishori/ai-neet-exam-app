"""Weekly Assessment models.

A ``WeeklyAssessment`` is a schedule + blueprint envelope on top of the
existing PRACTICE/MOCK exam engine. It does NOT introduce a second
scoring/attempt engine — attempts are still ``assessment.attempts`` rows
whose ``assessment_id`` points at a materialised ``Assessment`` and whose
``Assessment.weekly_assessment_id`` links back to this row.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase


class WeeklyAssessment(Base, AuditedBase):
    __tablename__ = "weekly_assessments"
    __table_args__ = {"schema": "assessment"}

    assessment_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    marks_per_question: Mapped[float] = mapped_column(Numeric(5, 2), default=4, nullable=False)
    negative_marks_per_question: Mapped[float] = mapped_column(Numeric(5, 2), default=1, nullable=False)
    attempt_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cumulative_weight: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    difficulty_distribution: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    blueprints: Mapped[list[WeeklyAssessmentBlueprint]] = relationship(
        back_populates="weekly_assessment",
        order_by="WeeklyAssessmentBlueprint.order_no",
        cascade="all, delete-orphan",
    )


class WeeklyAssessmentBlueprint(Base):
    __tablename__ = "weekly_assessment_blueprints"
    __table_args__ = {"schema": "assessment"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    weekly_assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment.weekly_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic.subjects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    topic_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)

    weekly_assessment: Mapped[WeeklyAssessment] = relationship(back_populates="blueprints")
