import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WebhookEvent(Base):
    """Dedup record for inbound Razorpay webhook deliveries. Razorpay may
    redeliver the same event (retries, near-simultaneous duplicate
    delivery) — the unique constraint on provider_event_id is what makes a
    replay a safe no-op rather than double-processing an order."""

    __tablename__ = "webhook_events"
    __table_args__ = {"schema": "commerce"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="razorpay")
    provider_event_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
