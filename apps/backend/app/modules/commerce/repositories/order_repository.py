import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.models import Order, WebhookEvent


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, order: Order) -> None:
        self.session.add(order)

    async def commit(self) -> None:
        await self.session.commit()

    async def get(self, order_id: uuid.UUID) -> Order | None:
        result = await self.session.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()

    async def get_by_razorpay_order_id(self, razorpay_order_id: str) -> Order | None:
        result = await self.session.execute(select(Order).where(Order.razorpay_order_id == razorpay_order_id))
        return result.scalar_one_or_none()

    async def record_webhook_event(self, *, provider: str, provider_event_id: str, event_type: str) -> bool:
        """Inserts a dedup row for this webhook delivery. Returns True if
        this is a new (first-seen) delivery, False if provider_event_id was
        already recorded (a safe no-op replay) — relies on the DB-level
        unique constraint via INSERT ... ON CONFLICT DO NOTHING (not a prior
        SELECT, so two near-simultaneous deliveries of the same event can't
        both pass a check-then-insert race), and never raises/rolls back the
        caller's transaction on a duplicate — a rollback here would also
        discard any other pending work sharing this session."""
        stmt = (
            pg_insert(WebhookEvent)
            .values(
                id=uuid.uuid4(),
                provider=provider,
                provider_event_id=provider_event_id,
                event_type=event_type,
            )
            .on_conflict_do_nothing(index_elements=["provider_event_id"])
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def has_paid_order(self, user_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Order.id).where(Order.user_id == user_id, Order.status == "PAID").limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_for_user(self, user_id: uuid.UUID) -> list[Order]:
        result = await self.session.execute(
            select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
