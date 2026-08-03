"""Admin Portal (PR11) — cross-cutting admin endpoints that don't belong to
any single existing module: dashboard aggregation and the audit log reader.
Each of the 9 modules' domain-specific endpoints live in their own module's
router; this one is genuinely cross-cutting."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.identity.dependencies import require_permission
from app.modules.system.services.dashboard_service import DashboardService
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/dashboard", dependencies=[Depends(require_permission("analytics.view"))])
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    service = DashboardService(db)
    return envelope(success=True, data=await service.get_overview())


@router.get("/audit-logs", dependencies=[Depends(require_permission("audit.view"))])
async def list_audit_logs(
    actor_user_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from app.modules.identity.models.user import User
    from app.modules.system.repositories.audit_repository import AuditRepository

    repo = AuditRepository(db)
    entries, total = await repo.list(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    actor_ids = {e.actor_user_id for e in entries if e.actor_user_id}
    emails: dict[uuid.UUID, str] = {}
    if actor_ids:
        result = await db.execute(select(User.id, User.email).where(User.id.in_(actor_ids)))
        emails = dict(result.all())

    return envelope(
        success=True,
        data=[
            {
                "id": str(e.id),
                "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
                "actor_email": emails.get(e.actor_user_id) if e.actor_user_id else None,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": str(e.entity_id) if e.entity_id else None,
                "metadata": e.log_metadata,
                "ip_address": e.ip_address,
                "created_at": e.created_at,
            }
            for e in entries
        ],
        meta={"total": total, "limit": limit, "offset": offset},
    )
