import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    __table_args__ = {"schema": "assessment"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment.attempts.id", ondelete="CASCADE"), nullable=False
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="CASCADE"), nullable=False
    )
    selected_option: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # PR 11 — self-reported confidence (easy|medium|hard), "Mark for Review &
    # Next" (a real NEET/JEE exam UI convention), and time spent on this
    # question in this viewing. All optional/default-false: existing rows
    # and existing callers are unaffected.
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    time_spent_seconds: Mapped[int | None] = mapped_column(nullable=True)

    attempt: Mapped["Attempt"] = relationship(back_populates="answers")
