"""Student preference API — thin CRUD over StudentPreferenceService."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.identity.dependencies import get_current_user, verify_csrf
from app.modules.identity.models.user import User
from app.modules.learning.models import StudentScopePreference
from app.modules.learning.services.student_preference_service import (
    ALLOWED_PREFERENCES,
    ALLOWED_SCOPES,
    StudentPreferenceService,
)
from app.shared.responses import envelope


router = APIRouter(prefix="/api/v1/preferences", tags=["preferences"])


class PreferenceUpsertRequest(BaseModel):
    scope_type: str = Field(min_length=1, max_length=20)
    scope_id: str
    preference: str = Field(min_length=1, max_length=10)


def _view(row: StudentScopePreference) -> dict:
    return {
        "id": str(row.id),
        "scope_type": row.scope_type,
        "scope_id": str(row.scope_id),
        "preference": row.preference,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("")
async def list_preferences(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = await StudentPreferenceService(db).list_for_user(user.id)
    return envelope(
        success=True,
        data=[_view(r) for r in rows],
        meta={"allowed_scopes": sorted(ALLOWED_SCOPES), "allowed_preferences": sorted(ALLOWED_PREFERENCES)},
    )


@router.put("", dependencies=[Depends(verify_csrf)])
async def upsert_preference(
    payload: PreferenceUpsertRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await StudentPreferenceService(db).upsert(
        user_id=user.id,
        scope_type=payload.scope_type,
        scope_id=uuid.UUID(payload.scope_id),
        preference=payload.preference,
    )
    return envelope(success=True, data=_view(row), status_code=200)


@router.delete("/{scope_type}/{scope_id}", dependencies=[Depends(verify_csrf)])
async def reset_one_preference(
    scope_type: str,
    scope_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await StudentPreferenceService(db).reset_one(
        user_id=user.id, scope_type=scope_type, scope_id=scope_id
    )
    return envelope(success=True, data={"deleted": deleted})


@router.post("/reset", dependencies=[Depends(verify_csrf)])
async def reset_all_preferences(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    deleted = await StudentPreferenceService(db).reset_all(user_id=user.id)
    return envelope(success=True, data={"deleted": deleted})
