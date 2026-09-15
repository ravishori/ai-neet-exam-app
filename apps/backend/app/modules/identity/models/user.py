import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase


class User(Base, AuditedBase):
    __tablename__ = "users"
    __table_args__ = {"schema": "identity"}

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    display_name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(20))
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    # Mobile-OTP login + address (added by identity_profile_mobile_state_city migration).
    # `mobile_e164` is the canonical E.164 representation ("+91XXXXXXXXXX"); the
    # legacy `phone` column above is not repurposed. Nullable so existing rows
    # migrate safely; new registrations enforce non-null at the service layer.
    mobile_e164: Mapped[str | None] = mapped_column(String(20))
    # `state_code` / `city_name` are DENORMALIZED views of state_id / city_id
    # — populated automatically by the profile validator from the master
    # tables. Kept for API compatibility and cheap read paths.
    state_code: Mapped[str | None] = mapped_column(String(64))
    city_name: Mapped[str | None] = mapped_column(String(120))
    # Master-data FKs — added by identity_geo_master_tables migration.
    state_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity.states.id", ondelete="RESTRICT"),
        nullable=True,
    )
    city_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity.cities.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # True until the user has changed the auto-issued initial credential.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    preferred_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Single-use, short-lived tokens — see ADR-0011 for why these live on
    # the user row instead of their own tables.
    email_verification_token_hash: Mapped[str | None] = mapped_column(String(64))
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(64))
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def role_codes(self) -> list[str]:
        return [ur.role.code for ur in self.roles]
