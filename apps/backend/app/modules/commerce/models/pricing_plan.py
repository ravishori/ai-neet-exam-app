import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase


class PricingPlan(Base, AuditedBase):
    """A priced offer for a Product. `max_purchases` + `purchase_count` are the
    authoritative founding-offer allocation counter — see
    FoundingAllocationService for the concurrency-safe increment logic.
    `purchase_count` counts RESERVED (order-created) allocations, released on
    expiry of an unpaid order — see FoundingAllocationService docstring for
    the exact rule and why."""

    __tablename__ = "pricing_plans"
    __table_args__ = {"schema": "commerce"}

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commerce.products.id", ondelete="RESTRICT"), nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    max_purchases: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
