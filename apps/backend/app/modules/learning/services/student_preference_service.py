"""Student preference service — thin, no cross-cutting side effects.

Persists STRONG/NEUTRAL/WEAK per (user, scope_type, scope_id). Validates
scope_id against the existing academic hierarchy. Never mutates mastery
tables.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.academic.models import Concept, Subject, Topic
from app.modules.learning.models import StudentScopePreference

ALLOWED_SCOPES = frozenset({"SUBJECT", "TOPIC", "CONCEPT"})
ALLOWED_PREFERENCES = frozenset({"STRONG", "NEUTRAL", "WEAK"})

_SCOPE_MODELS = {"SUBJECT": Subject, "TOPIC": Topic, "CONCEPT": Concept}


def _validate(scope_type: str, preference: str) -> None:
    if scope_type not in ALLOWED_SCOPES:
        raise AppError(
            f"scope_type must be one of {sorted(ALLOWED_SCOPES)}",
            code="PREFERENCE_SCOPE_INVALID",
            status_code=422,
        )
    if preference not in ALLOWED_PREFERENCES:
        raise AppError(
            f"preference must be one of {sorted(ALLOWED_PREFERENCES)}",
            code="PREFERENCE_VALUE_INVALID",
            status_code=422,
        )


class StudentPreferenceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _assert_scope_exists(self, scope_type: str, scope_id: uuid.UUID) -> None:
        model = _SCOPE_MODELS[scope_type]
        row = (
            await self.session.execute(select(model.id).where(model.id == scope_id))
        ).scalar_one_or_none()
        if row is None:
            raise AppError(
                f"{scope_type.lower()} not found",
                code="PREFERENCE_SCOPE_NOT_FOUND",
                status_code=404,
            )

    async def list_for_user(self, user_id: uuid.UUID) -> list[StudentScopePreference]:
        rows = (
            await self.session.execute(
                select(StudentScopePreference)
                .where(
                    StudentScopePreference.user_id == user_id,
                    StudentScopePreference.deleted_at.is_(None),
                )
                .order_by(StudentScopePreference.scope_type, StudentScopePreference.created_at)
            )
        ).scalars().all()
        return list(rows)

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        scope_type: str,
        scope_id: uuid.UUID,
        preference: str,
    ) -> StudentScopePreference:
        _validate(scope_type, preference)
        await self._assert_scope_exists(scope_type, scope_id)

        existing_id = (
            await self.session.execute(
                select(StudentScopePreference.id).where(
                    StudentScopePreference.user_id == user_id,
                    StudentScopePreference.scope_type == scope_type,
                    StudentScopePreference.scope_id == scope_id,
                    StudentScopePreference.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if existing_id is not None:
            # Explicit UPDATE avoids the greenlet trap that ORM-attr mutation
            # on an audited row can hit inside async sessions.
            await self.session.execute(
                update(StudentScopePreference)
                .where(StudentScopePreference.id == existing_id)
                .values(preference=preference, updated_by=user_id)
            )
            await self.session.commit()
            reloaded = (
                await self.session.execute(
                    select(StudentScopePreference).where(StudentScopePreference.id == existing_id)
                )
            ).scalar_one()
            return reloaded

        row = StudentScopePreference(
            user_id=user_id,
            scope_type=scope_type,
            scope_id=scope_id,
            preference=preference,
            created_by=user_id,
            updated_by=user_id,
        )
        self.session.add(row)
        await self.session.commit()
        return row

    async def reset_one(
        self, *, user_id: uuid.UUID, scope_type: str, scope_id: uuid.UUID
    ) -> bool:
        if scope_type not in ALLOWED_SCOPES:
            raise AppError(
                f"scope_type must be one of {sorted(ALLOWED_SCOPES)}",
                code="PREFERENCE_SCOPE_INVALID",
                status_code=422,
            )
        result = await self.session.execute(
            delete(StudentScopePreference).where(
                StudentScopePreference.user_id == user_id,
                StudentScopePreference.scope_type == scope_type,
                StudentScopePreference.scope_id == scope_id,
            )
        )
        await self.session.commit()
        return (result.rowcount or 0) > 0

    async def reset_all(self, *, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            delete(StudentScopePreference).where(
                StudentScopePreference.user_id == user_id
            )
        )
        await self.session.commit()
        return result.rowcount or 0
