import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.system.models.audit_log import AuditLog
from app.modules.system.repositories.audit_repository import AuditRepository


def request_context(request: Request) -> dict:
    """Same ip/user-agent extraction as auth_router._client_meta, plus the
    per-request trace_id RequestContextMiddleware already stamps on scope.state
    (core/middleware.py) — reused here rather than duplicated per call site."""
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    trace_id = getattr(request.state, "trace_id", None)
    return {"ip_address": ip, "user_agent": user_agent, "trace_id": trace_id}


class AuditService:
    """Cross-cutting audit trail writer (PR11 Admin Portal). Every admin
    mutating action calls `.log(...)` — this service owns no business logic
    of its own, just a consistent write path into system.audit_logs."""

    def __init__(self, session: AsyncSession):
        self.repo = AuditRepository(session)

    async def log(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        action: str,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        metadata: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.repo.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                log_metadata=metadata,
                ip_address=ip_address,
                user_agent=user_agent,
                trace_id=trace_id,
            )
        )
        await self.repo.commit()
