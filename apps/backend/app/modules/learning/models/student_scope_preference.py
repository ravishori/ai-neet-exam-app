"""Student self-declared competency preference per scope.

Preference is a SIGNAL, not authoritative mastery — the mastery tables
(``concept_mastery`` etc.) remain the demonstrated-performance source of
truth. This model exists only so students can annotate a subject / topic
/ concept as STRONG, NEUTRAL, or WEAK for adaptive selection.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase


class StudentScopePreference(Base, AuditedBase):
    __tablename__ = "student_scope_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "scope_type", "scope_id", name="uq_student_scope_pref"
        ),
        {"schema": "learning"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)  # SUBJECT|TOPIC|CONCEPT
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    preference: Mapped[str] = mapped_column(String(10), nullable=False)  # STRONG|NEUTRAL|WEAK
