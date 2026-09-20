"""Weekly Assessment API — admin CRUD + student list/start.

Reuses ``AssessmentService`` for the actual attempt runner; endpoints here
only own scheduling, blueprint, and materialisation.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError
from app.modules.assessment.schemas.weekly_assessment import (
    WeeklyAssessmentCreateRequest,
    WeeklyAssessmentUpdateRequest,
    WeeklyStartAttemptResponse,
)
from app.modules.assessment.services.weekly_assessment_service import (
    WeeklyAssessmentService,
    public_view_admin,
)
from app.modules.identity.dependencies import get_current_user, verify_csrf
from app.modules.identity.models.user import User
from app.shared.responses import envelope


router = APIRouter(prefix="/api/v1/weekly-assessments", tags=["weekly-assessments"])


def _require_admin(user: User) -> None:
    if not ({"ADMIN", "SUPER_ADMIN"} & set(user.role_codes)):
        raise AppError("Admin role required", code="FORBIDDEN", status_code=403)


# --------------------------------------------------------------- admin routes

@router.post("", dependencies=[Depends(verify_csrf)])
async def create_weekly(
    payload: WeeklyAssessmentCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    svc = WeeklyAssessmentService(db)
    wa = await svc.create(payload=payload, actor_id=user.id)
    return envelope(success=True, data=public_view_admin(wa), status_code=201)


@router.patch("/{weekly_id}", dependencies=[Depends(verify_csrf)])
async def update_weekly(
    weekly_id: uuid.UUID,
    payload: WeeklyAssessmentUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    svc = WeeklyAssessmentService(db)
    wa = await svc.update(weekly_id, payload=payload, actor_id=user.id)
    return envelope(success=True, data=public_view_admin(wa))


@router.post("/{weekly_id}/publish", dependencies=[Depends(verify_csrf)])
async def publish_weekly(
    weekly_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    svc = WeeklyAssessmentService(db)
    wa = await svc.publish(weekly_id, actor_id=user.id)
    return envelope(success=True, data=public_view_admin(wa))


@router.post("/{weekly_id}/unpublish", dependencies=[Depends(verify_csrf)])
async def unpublish_weekly(
    weekly_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    svc = WeeklyAssessmentService(db)
    wa = await svc.unpublish(weekly_id, actor_id=user.id)
    return envelope(success=True, data=public_view_admin(wa))


@router.get("/admin")
async def list_weekly_admin(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    svc = WeeklyAssessmentService(db)
    rows = await svc.list_admin()
    return envelope(success=True, data=[public_view_admin(w) for w in rows])


# ------------------------------------------------------------ student routes

@router.get("")
async def list_weekly_student(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = WeeklyAssessmentService(db)
    rows = await svc.list_upcoming_for_student(user_id=user.id)
    return envelope(success=True, data=rows)


@router.post("/{weekly_id}/attempts", dependencies=[Depends(verify_csrf)])
async def start_weekly_attempt(
    weekly_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = WeeklyAssessmentService(db)
    assessment, attempt, coverage = await svc.start_attempt(weekly_id=weekly_id, user_id=user.id)
    return envelope(
        success=True,
        data=WeeklyStartAttemptResponse(
            weekly_assessment_id=str(weekly_id),
            assessment_id=str(assessment.id),
            attempt_id=str(attempt.id),
            coverage=coverage,
            duration_minutes=assessment.duration_minutes or 0,
        ).model_dump(),
        status_code=201,
    )
