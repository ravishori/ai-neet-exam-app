import uuid
from typing import List, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.identity.models.role import Role, UserRole
from app.modules.identity.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[User]:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_paginated(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        role_code: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[User], int]:
        """Admin Portal (PR11) Module 9 — the pre-existing list() had no
        filters and no total count, so the admin UI could never paginate
        past the first page or search by email/status/role. Kept as a
        separate method since list() is also used by users_router.py's
        plain GET /users, which callers may depend on returning a bare list."""
        base = select(User).where(User.deleted_at.is_(None))
        count_query = select(func.count(func.distinct(User.id))).where(User.deleted_at.is_(None))

        if search:
            base = base.where(User.email.ilike(f"%{search}%"))
            count_query = count_query.where(User.email.ilike(f"%{search}%"))
        if status:
            base = base.where(User.status == status)
            count_query = count_query.where(User.status == status)
        if role_code:
            base = base.join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id).where(Role.code == role_code)
            count_query = count_query.join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id).where(
                Role.code == role_code
            )

        total = (await self.session.execute(count_query)).scalar_one()
        base = (
            base.options(selectinload(User.roles).selectinload(UserRole.role))
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(base)
        return list(result.scalars().unique().all()), total

    def add(self, user: User) -> None:
        self.session.add(user)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
