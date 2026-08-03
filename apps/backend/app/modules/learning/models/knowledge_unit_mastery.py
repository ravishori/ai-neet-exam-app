import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Mirrors ConceptMastery's exact, real, populated shape — see ADR-0028.
# Deliberately does NOT include confidence_score / average_response_time /
# difficulty_level / revision_count / retention_score: nothing in this
# codebase computes any of those today, and a column nothing ever writes to
# is precisely the placeholder ADR-0024 already ruled out for KnowledgeUnit
# itself ("would itself be exactly the kind of placeholder the frozen
# architecture bans"). Add them in the same future work that actually
# starts computing them, not speculatively ahead of it.
# mastery_level: NOT_STARTED | LEARNING | PRACTICING | MASTERED


class KnowledgeUnitMastery(Base):
    __tablename__ = "knowledge_unit_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_unit_id", name="uq_knowledge_unit_mastery_user_unit"),
        # The unique constraint above already indexes (user_id,
        # knowledge_unit_id) — sufficient for "this user's mastery rows."
        # A separate index on knowledge_unit_id alone is added for the
        # reverse query ("which users are weak on this unit," the
        # aggregate direction GetWeakAreas / a future analytics view needs)
        # since the composite index's leftmost-prefix rule doesn't serve it.
        Index("ix_knowledge_unit_mastery_knowledge_unit", "knowledge_unit_id"),
        {"schema": "learning"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge.knowledge_units.id", ondelete="CASCADE"), nullable=False
    )
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_level: Mapped[str] = mapped_column(String(20), default="NOT_STARTED", nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
