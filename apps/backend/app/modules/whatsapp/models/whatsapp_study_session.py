import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase


class WhatsAppStudySession(Base, AuditedBase):
    """Short-lived WhatsApp learning state — persistence boundary only for
    M1. No quiz/tutor/flashcard/revision state machine is implemented on
    top of this table yet (that's M2+); this model exists so those later
    phases have somewhere to persist state without a schema change.
    assessment_id/attempt_id/current_question_id are nullable FKs into the
    existing assessment/CMS tables — WhatsApp never owns its own copies of
    those (see ADR-WHATSAPP-PROVIDER-ABSTRACTION.md's "Do NOT create"
    list)."""

    __tablename__ = "study_sessions"
    __table_args__ = {"schema": "whatsapp"}

    whatsapp_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("whatsapp.identities.id", ondelete="CASCADE"), nullable=False
    )

    session_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment.assessments.id", ondelete="SET NULL"), nullable=True
    )
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment.attempts.id", ondelete="SET NULL"), nullable=True
    )
    current_question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms.content_items.id", ondelete="SET NULL"), nullable=True
    )
    current_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
