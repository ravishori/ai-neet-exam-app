import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase


class Concept(Base, AuditedBase):
    __tablename__ = "concepts"
    __table_args__ = {"schema": "academic"}

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.topics.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    # Free-text book/chapter/section reference — see ADR-0012.
    ncert_reference: Mapped[str | None] = mapped_column(String(300))
    difficulty: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    topic: Mapped["Topic"] = relationship(back_populates="concepts")
