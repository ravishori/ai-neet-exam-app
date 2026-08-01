import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase


class Topic(Base, AuditedBase):
    __tablename__ = "topics"
    __table_args__ = {"schema": "academic"}

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.chapters.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    chapter: Mapped["Chapter"] = relationship(back_populates="topics")
    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="topic", order_by="Concept.display_order", cascade="all, delete-orphan"
    )
