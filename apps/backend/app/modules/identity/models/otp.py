from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase


class OtpChallenge(Base, AuditedBase):
    __tablename__ = "otp_challenges"
    __table_args__ = {"schema": "identity"}

    destination: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # email | sms
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OtpAbuseCounter(Base, AuditedBase):
    """Tracks failed OTP verification attempts across ALL challenges for
    one (destination, purpose) pair, independent of any single
    OtpChallenge row -- a per-challenge `attempts` counter alone resets
    to 0 every time a new code is requested, letting an attacker who
    exhausts one challenge's 5 attempts simply request a fresh code for
    another 5. This counter is never reset by requesting a new code;
    only a successful verification or the rolling window (ABUSE_WINDOW_
    MINUTES in otp_service.py) clears it."""

    __tablename__ = "otp_abuse_counters"
    __table_args__ = {"schema": "identity"}

    destination: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TotpRecoveryCode(Base, AuditedBase):
    __tablename__ = "totp_recovery_codes"
    __table_args__ = {"schema": "identity"}

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
