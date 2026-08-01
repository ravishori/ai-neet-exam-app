import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Mirrors ConceptMastery's exact shape — see ADR-0021. mastery_level:
# NOT_STARTED | LEARNING | PRACTICING | MASTERED


class MicroCompetencyMastery(Base):
    __tablename__ = "micro_competency_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "micro_competency_id", name="uq_micro_competency_mastery_user_mc"),
        {"schema": "learning"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
    )
    micro_competency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic.micro_competencies.id", ondelete="CASCADE"), nullable=False
    )
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_level: Mapped[str] = mapped_column(String(20), default="NOT_STARTED", nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
