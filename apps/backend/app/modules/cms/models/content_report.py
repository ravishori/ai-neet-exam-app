import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# reason: WRONG_ANSWER | UNCLEAR | TYPO | OFFENSIVE | OTHER
# status: OPEN | RESOLVED | DISMISSED — no admin UI exists yet to change this
# from OPEN (PR 11 scope is student-facing submission only); flagged as a
# real follow-up in the sprint report, not built here.


class ContentReport(Base):
    """A student-submitted content-quality flag (PR 11) — "Report Issue" on
    a question. Independent of ContentReview (the editorial approve/reject
    workflow): a report is a signal from a consumer, a review is an
    editorial decision. Nullable content_version_id captures which version
    the student actually saw, since content can be re-edited later."""

    __tablename__ = "content_reports"
    __table_args__ = {"schema": "cms"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="CASCADE"), nullable=False
    )
    content_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_versions.id", ondelete="SET NULL")
    )
    reported_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
