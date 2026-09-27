import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# status: CREATED | PAYMENT_PENDING | PAID | FAILED | CANCELLED | EXPIRED | REFUNDED
#
# amount_inr (Numeric, rupees) is the ORIGINAL column, kept for backward
# compatibility with any pre-existing rows — see migration
# a8f3c9d2e1b4_commerce_pricing_entitlements.py for why it was not dropped
# (2 CREATED, never-paid rows existed in production at migration time; no
# PAID/historical-revenue rows exist, so no monetary value was ever rewritten).
# amount_paise (Integer) is the new AUTHORITATIVE field for all orders created
# from this point forward — see CommerceService.create_order. Never derive an
# order's price from the current PricingPlan; it is locked at creation.


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": "commerce"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
    )
    order_number: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    pricing_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commerce.pricing_plans.id", ondelete="RESTRICT"), nullable=True
    )
    amount_inr: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    amount_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="CREATED", nullable=False, index=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    razorpay_signature: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
