import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase


class Subject(Base, AuditedBase):
    __tablename__ = "subjects"
    __table_args__ = {"schema": "academic"}

    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.exams.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # NEET blueprint weightage in percent. Mirrors the identically-named
    # column on ``academic.chapters`` — nullable for legacy rows, populated
    # for the seeded NEET subjects by migration d4e5f7a8b9c0.
    neet_weightage_percent: Mapped[float | None] = mapped_column(Numeric(4, 1))

    exam: Mapped["Exam"] = relationship(back_populates="subjects")
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="subject", order_by="Chapter.display_order", cascade="all, delete-orphan"
    )
