import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase


class WhatsAppMessage(Base, AuditedBase):
    """Inbound/outbound message metadata. (provider, provider_message_id)
    is the durable idempotency guarantee — see ADR-WHATSAPP-PROVIDER-
    ABSTRACTION.md. Never a provider-specific column name (no
    twilio_message_sid) — provider_message_id is generic and holds
    Twilio's MessageSid today."""

    __tablename__ = "messages"
    __table_args__ = {"schema": "whatsapp"}

    whatsapp_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("whatsapp.identities.id", ondelete="CASCADE"), nullable=False
    )

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String(120), nullable=False)

    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # inbound | outbound
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(20), nullable=False, default="received")
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
