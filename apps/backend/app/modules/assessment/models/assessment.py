import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase

# assessment_type: PRACTICE | MOCK
# scope_type: CONCEPT | TOPIC | CHAPTER | SUBJECT | FULL | SEED_V1 | SEED_V2


class Assessment(Base, AuditedBase):
    __tablename__ = "assessments"
    __table_args__ = {"schema": "assessment"}

    assessment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    marks_per_question: Mapped[float] = mapped_column(Numeric(5, 2), default=4, nullable=False)
    negative_marks_per_question: Mapped[float] = mapped_column(Numeric(5, 2), default=1, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Back-link when this assessment was materialised for a WeeklyAssessment.
    # Null for plain PRACTICE / MOCK generation.
    weekly_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment.weekly_assessments.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Back-link when this assessment was materialised for a student-driven
    # WeeklyRevisionRecommendation. Mutually exclusive with the field above.
    weekly_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment.weekly_revision_recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )

    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        back_populates="assessment", order_by="AssessmentQuestion.order_no", cascade="all, delete-orphan"
    )
