import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QuestionNote(Base):
    """A student's personal note on a question (PR 11). One note per
    (user, question) — deliberately not a thread/multiple-notes system;
    re-saving replaces the note, matching how a flashcard-style "my notes"
    feature actually gets used (one running note per item, not a log)."""

    __tablename__ = "question_notes"
    __table_args__ = (
        UniqueConstraint("user_id", "content_item_id", name="uq_question_note_user_question"),
        {"schema": "learning"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="CASCADE"), nullable=False
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
