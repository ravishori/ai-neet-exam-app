import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase


class Chapter(Base, AuditedBase):
    __tablename__ = "chapters"
    __table_args__ = {"schema": "academic"}

    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.subjects.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # NEET-specific: roughly how much of the exam this chapter accounts for.
    neet_weightage_percent: Mapped[float | None] = mapped_column(Numeric(4, 1))

    subject: Mapped["Subject"] = relationship(back_populates="chapters")
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="chapter", order_by="Topic.display_order", cascade="all, delete-orphan"
    )
