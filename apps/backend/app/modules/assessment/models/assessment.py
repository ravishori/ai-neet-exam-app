import uuid

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase

# assessment_type: PRACTICE | MOCK
# scope_type: CONCEPT | CHAPTER | SUBJECT | FULL


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

    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        back_populates="assessment", order_by="AssessmentQuestion.order_no", cascade="all, delete-orphan"
    )
