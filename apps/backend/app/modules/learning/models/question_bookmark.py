import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QuestionBookmark(Base):
    """A student's saved-for-later flag on a question (PR 11). One row per
    (user, question) — bookmarking twice is a no-op, not a second row."""

    __tablename__ = "question_bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "content_item_id", name="uq_question_bookmark_user_question"),
        {"schema": "learning"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
