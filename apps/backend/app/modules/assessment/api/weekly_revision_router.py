"""Student-driven Weekly Revision recommendation API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.assessment.services.weekly_revision_service import (
    WeeklyRevisionService,
    public_view,
)
from app.modules.identity.dependencies import get_current_user, require_active_access, verify_csrf
from app.modules.identity.models.user import User
from app.shared.responses import envelope

# Premium: entirely student-facing (no admin routes in this router) —
# active trial OR active entitlement required for both routes.
router = APIRouter(
    prefix="/api/v1/weekly-revisions",
    tags=["weekly-revisions"],
    dependencies=[Depends(require_active_access())],
)


@router.get("/current")
async def get_current(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    svc = WeeklyRevisionService(db)
    rec = await svc.get_or_generate_current(user_id=user.id)
    return envelope(success=True, data=public_view(rec))


@router.post("/current/attempts", dependencies=[Depends(verify_csrf)])
async def start_current(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    svc = WeeklyRevisionService(db)
    rec, assessment, attempt = await svc.start_attempt(user_id=user.id)
    return envelope(
        success=True,
        data={
            "recommendation_id": str(rec.id),
            "assessment_id": str(assessment.id),
            "attempt_id": str(attempt.id),
            "duration_minutes": assessment.duration_minutes or 0,
            "total_questions": assessment.question_count,
            "status": rec.status,
        },
        status_code=201,
    )
