import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.system.models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, entry: AuditLog) -> None:
        self.session.add(entry)

    async def commit(self) -> None:
        await self.session.commit()

    async def list(
        self,
        *,
        actor_user_id: uuid.UUID | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        base = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        if actor_user_id:
            base = base.where(AuditLog.actor_user_id == actor_user_id)
            count_query = count_query.where(AuditLog.actor_user_id == actor_user_id)
        if action:
            base = base.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        if entity_type:
            base = base.where(AuditLog.entity_type == entity_type)
            count_query = count_query.where(AuditLog.entity_type == entity_type)
        if since:
            base = base.where(AuditLog.created_at >= since)
            count_query = count_query.where(AuditLog.created_at >= since)
        if until:
            base = base.where(AuditLog.created_at <= until)
            count_query = count_query.where(AuditLog.created_at <= until)

        total = (await self.session.execute(count_query)).scalar_one()
        base = base.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(base)
        return list(result.scalars().all()), total
