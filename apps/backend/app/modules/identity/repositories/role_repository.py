import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.role import Permission, Role, RolePermission, UserRole


class RoleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code(self, code: str) -> Role | None:
        result = await self.session.execute(select(Role).where(Role.code == code))
        return result.scalar_one_or_none()

    async def replace_roles(self, user_id: uuid.UUID, role_codes: list[str]) -> None:
        """Full diff-and-sync: the user ends up with exactly these roles, nothing more."""
        await self.session.execute(delete(UserRole).where(UserRole.user_id == user_id))
        if not role_codes:
            return
        result = await self.session.execute(select(Role).where(Role.code.in_(role_codes)))
        for role in result.scalars().all():
            self.session.add(UserRole(user_id=user_id, role_id=role.id))

    # NOTE: named `list` (shadowing the builtin) — any method added after this one
    # must not use a bare `list[...]` annotation, or it will resolve to this method
    # instead of the builtin during class-body evaluation. Keep new list[...]-typed
    # methods above this line, or annotate with `List` from typing instead.
    async def list(self) -> list[Role]:
        result = await self.session.execute(select(Role).order_by(Role.name))
        return list(result.scalars().all())

    async def get_permission_codes_for_roles(self, role_ids: list) -> set[str]:
        if not role_ids:
            return set()
        result = await self.session.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id.in_(role_ids))
        )
        return set(result.scalars().all())

    def assign_role(self, user_id, role_id) -> UserRole:
        link = UserRole(user_id=user_id, role_id=role_id)
        self.session.add(link)
        return link
