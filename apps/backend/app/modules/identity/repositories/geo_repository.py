"""Read-only accessors for the states / cities master tables."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.identity.models.geo import City, State


class GeoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active_states(self) -> list[State]:
        result = await self.session.execute(
            select(State).where(State.is_active.is_(True)).order_by(State.name.asc())
        )
        return list(result.scalars().all())

    async def get_state_by_code(self, code: str) -> State | None:
        if not code:
            return None
        result = await self.session.execute(
            select(State).where(func.upper(State.code) == code.strip().upper())
        )
        return result.scalar_one_or_none()

    async def get_state_by_id(self, state_id: uuid.UUID) -> State | None:
        return await self.session.get(State, state_id)

    async def list_active_cities_for(self, state_id: uuid.UUID) -> list[City]:
        result = await self.session.execute(
            select(City)
            .where(City.state_id == state_id, City.is_active.is_(True))
            .order_by(City.name.asc())
        )
        return list(result.scalars().all())

    async def find_city(self, *, state_id: uuid.UUID, name: str) -> City | None:
        """Case-insensitive lookup used by profile validators. State scope
        keeps ambiguous names (Aurangabad in Bihar vs Maharashtra) unambiguous."""
        if not name:
            return None
        result = await self.session.execute(
            select(City)
            .options(selectinload(City.state))
            .where(
                City.state_id == state_id,
                func.lower(City.name) == name.strip().lower(),
            )
        )
        return result.scalar_one_or_none()

    async def count_states_and_cities(self) -> tuple[int, int]:
        s = (await self.session.execute(select(func.count()).select_from(State))).scalar_one()
        c = (await self.session.execute(select(func.count()).select_from(City))).scalar_one()
        return int(s), int(c)
