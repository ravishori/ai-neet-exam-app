import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase


class WhatsAppLinkCode(Base, AuditedBase):
    """A one-time code binding a specific, already-authenticated
    ``identity.users`` row to a future WhatsApp identity.

    Deliberately a dedicated table, not a reuse of ``identity.OtpChallenge``
    — the semantics differ (bound to a user_id at generation time, resolved
    to a whatsapp_identity_id only at consumption, and consumption performs
    a cross-module link rather than just proving mailbox/phone control).
    The security *pattern* (hashed code, expiry, attempt-limited,
    single-use) is deliberately copied from OtpChallenge.

    Never stores the plaintext code — only ``code_hash``. See
    docs/whatsapp/WHATSAPP_M2A_ACCOUNT_LINKING.md for the full flow and
    security properties.
    """

    __tablename__ = "link_codes"
    __table_args__ = {"schema": "whatsapp"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set only on successful consumption — records which WhatsApp identity
    # redeemed this code, independent of whatsapp.identities.user_id (which
    # this consumption is what sets).
    whatsapp_identity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("whatsapp.identities.id", ondelete="SET NULL"), nullable=True
    )
