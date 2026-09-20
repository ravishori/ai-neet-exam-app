"""HR-1 review queue foundation — reviewer sessions and per-question claims.

Orthogonal to ECAEP ContentItem.status: a claim/session never changes
status, approves, or publishes anything. They only coordinate which human
reviewer is currently looking at which IN_REVIEW question, so two reviewers
don't duplicate work.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

REVIEW_SESSION_STATUSES = ("ACTIVE", "COMPLETED", "ABANDONED")
REVIEW_CLAIM_STATUSES = ("ACTIVE", "RELEASED", "EXPIRED", "COMPLETED")
DEFAULT_SESSION_SIZE = 25


class ReviewSession(Base):
    __tablename__ = "review_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','COMPLETED','ABANDONED')", name="ck_review_sessions_status"),
        {"schema": "cms"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
    )
    session_size: Mapped[int] = mapped_column(Integer, nullable=False, default=DEFAULT_SESSION_SIZE)
    item_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReviewClaim(Base):
    __tablename__ = "review_claims"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','RELEASED','EXPIRED','COMPLETED')", name="ck_review_claims_status"),
        {"schema": "cms"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.review_sessions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
