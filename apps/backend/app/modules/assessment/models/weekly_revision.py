"""Student-driven Weekly Revision recommendation.

Idempotent per (user, ISO year, ISO week). Materialised assessments link
back via ``assessment.assessments.weekly_revision_id``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase


class WeeklyRevisionRecommendation(Base, AuditedBase):
    __tablename__ = "weekly_revision_recommendations"
    __table_args__ = (
        UniqueConstraint("user_id", "iso_year", "iso_week", name="uq_weekly_revision_per_week"),
        {"schema": "assessment"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    iso_year: Mapped[int] = mapped_column(Integer, nullable=False)
    iso_week: Mapped[int] = mapped_column(Integer, nullable=False)
    blueprint: Mapped[list] = mapped_column(JSONB, nullable=False)
    reason: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="RECOMMENDED", nullable=False)
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    marks_per_question: Mapped[float] = mapped_column(Numeric(5, 2), default=4, nullable=False)
    negative_marks_per_question: Mapped[float] = mapped_column(Numeric(5, 2), default=1, nullable=False)
    attempt_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
