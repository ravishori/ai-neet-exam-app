import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase

# source_type: TRIAL | PURCHASE | ADMIN_GRANT
# status: ACTIVE | EXPIRED | REVOKED


class Entitlement(Base, AuditedBase):
    """The authoritative access record. can_access()/AccessService reads ONLY
    this table (plus trial state) to decide authorization — never Order/Payment
    status directly. One row per grant (trial, purchase, admin grant); a
    renewal/extension purchase updates expires_at on the existing PURCHASE-type
    row rather than creating an overlapping one (see EntitlementService)."""

    __tablename__ = "entitlements"
    __table_args__ = {"schema": "commerce"}

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commerce.products.id", ondelete="RESTRICT"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
