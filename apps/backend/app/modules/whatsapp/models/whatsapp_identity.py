import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase


class WhatsAppIdentity(Base, AuditedBase):
    """Maps an external WhatsApp identity (via whichever provider delivered
    it) to a Trinetra user. Provider-neutral — see
    docs/decisions/ADR-WHATSAPP-PROVIDER-ABSTRACTION.md. Never auto-linked
    to a user; linking is a separate, explicit, one-time-code flow (M2)."""

    __tablename__ = "identities"
    __table_args__ = {"schema": "whatsapp"}

    # Nullable: an identity may message in before ever completing the
    # (M2) linking flow.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="SET NULL"), nullable=True
    )

    # "twilio" today; a discriminator, never assumed elsewhere.
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    # The provider's own identifier for this WhatsApp user, where the
    # provider exposes one distinct from the phone number. Nullable —
    # Twilio's WhatsApp messages are identified by phone number, not a
    # separate opaque user id.
    external_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # The actual WhatsApp number. Provider-independent.
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
