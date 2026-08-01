from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase


class Exam(Base, AuditedBase):
    __tablename__ = "exams"
    __table_args__ = {"schema": "academic"}

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    subjects: Mapped[list["Subject"]] = relationship(back_populates="exam", order_by="Subject.display_order")
