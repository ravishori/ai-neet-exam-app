import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.models import Order


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

    async def has_paid_order(self, user_id: uuid.UUID) -> bool:
        """Deprecated as an authorization mechanism — payment records are
        financial history, not access records. Use
        AccessService.can_access() instead. Kept only in case admin
        reporting/reconciliation code wants "has this user ever paid" as a
        distinct question from "does this user currently have access"."""
        result = await self.session.execute(
            select(Order.id).where(Order.user_id == user_id, Order.status == "PAID").limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_for_user(self, user_id: uuid.UUID) -> list[Order]:
        result = await self.session.execute(
            select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_pending_admin(self, *, limit: int = 100) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .where(Order.status.in_(["PAYMENT_PENDING", "CREATED"]))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_all_admin(self, *, limit: int = 200) -> list[Order]:
        result = await self.session.execute(select(Order).order_by(Order.created_at.desc()).limit(limit))
        return list(result.scalars().all())
