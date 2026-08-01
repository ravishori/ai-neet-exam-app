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
        result = await self.session.execute(
            select(Order.id).where(Order.user_id == user_id, Order.status == "PAID").limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_for_user(self, user_id: uuid.UUID) -> list[Order]:
        result = await self.session.execute(
            select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
