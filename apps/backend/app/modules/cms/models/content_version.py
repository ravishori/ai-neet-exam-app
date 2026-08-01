import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContentVersion(Base):
    __tablename__ = "content_versions"
    __table_args__ = {"schema": "cms"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    workflow_state: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    ai_check_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text)
    authored_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    content_item: Mapped["ContentItem"] = relationship(
        back_populates="versions", foreign_keys=[content_item_id]
    )
    reviews: Mapped[list["ContentReview"]] = relationship(back_populates="content_version", cascade="all, delete-orphan")
