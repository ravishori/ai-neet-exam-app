"""Weekly Assessment service — schedule + blueprint envelope over the
existing assessment engine.

Design commitments:
- Never re-implement scoring / attempt / question-selection. Delegate to
  ``AssessmentService`` and ``AssessmentRepository``.
- Only PUBLISHED questions can be selected (the repo query enforces this).
- No duplicate questions within a materialised assessment (a set-tracked
  per-subject sample + a final assert).
- Insufficient pool fails fast with a specific code — never silently
  ships a short paper.
- Enforce the scheduling window, attempt limit and publication state
  server-side.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.assessment.models import (
    Assessment,
    Attempt,
    WeeklyAssessment,
    WeeklyAssessmentBlueprint,
)
from app.modules.assessment.repositories.assessment_repository import (
    AssessmentRepository,
    sample_question_ids,
)
from app.modules.cms.models import ContentItem

logger = get_logger("weekly_assessment")


class WeeklyAssessmentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.assessment_repo = AssessmentRepository(session)

    # ---------------------------------------------------------------------- admin

    async def create(self, *, payload, actor_id: uuid.UUID) -> WeeklyAssessment:
        # Uniqueness on assessment_key — surface a friendly conflict error.
        existing = (
            await self.session.execute(
                select(WeeklyAssessment).where(WeeklyAssessment.assessment_key == payload.assessment_key)
            )
        ).scalar_one_or_none()
        if existing:
            raise AppError(
                "A weekly assessment with this key already exists",
                code="WEEKLY_KEY_TAKEN",
                status_code=409,
            )

        await self._assert_subjects_exist([uuid.UUID(row.subject_id) for row in payload.blueprint])

        wa = WeeklyAssessment(
            assessment_key=payload.assessment_key,
            title=payload.title,
            description=payload.description,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            duration_minutes=payload.duration_minutes,
            marks_per_question=payload.marks_per_question,
            negative_marks_per_question=payload.negative_marks_per_question,
            attempt_limit=payload.attempt_limit,
            cumulative_weight=payload.cumulative_weight,
            difficulty_distribution=payload.difficulty_distribution,
            published=False,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.session.add(wa)
        await self.session.flush()

        for order_no, row in enumerate(payload.blueprint):
            self.session.add(
                WeeklyAssessmentBlueprint(
                    weekly_assessment_id=wa.id,
                    subject_id=uuid.UUID(row.subject_id),
                    question_count=row.question_count,
                    chapter_ids=row.chapter_ids,
                    topic_ids=row.topic_ids,
                    order_no=order_no,
                )
            )
        await self.session.commit()
        return await self.get(wa.id)

    async def update(self, weekly_id: uuid.UUID, *, payload, actor_id: uuid.UUID) -> WeeklyAssessment:
        wa = await self.get(weekly_id, required=True)
        if wa.published and payload.blueprint is not None:
            raise AppError(
                "Cannot change the blueprint of a published weekly assessment; unpublish first",
                code="WEEKLY_PUBLISHED_LOCKED",
                status_code=409,
            )

        updatable = (
            "title",
            "description",
            "starts_at",
            "ends_at",
            "duration_minutes",
            "marks_per_question",
            "negative_marks_per_question",
            "attempt_limit",
            "cumulative_weight",
            "difficulty_distribution",
        )
        for attr in updatable:
            val = getattr(payload, attr)
            if val is not None:
                setattr(wa, attr, val)
        if wa.ends_at <= wa.starts_at:
            raise AppError("ends_at must be after starts_at", code="WEEKLY_WINDOW_INVALID", status_code=400)
        wa.updated_by = actor_id

        if payload.blueprint is not None:
            await self._assert_subjects_exist([uuid.UUID(row.subject_id) for row in payload.blueprint])
            # Blow away existing blueprint rows and re-create in order.
            for row in list(wa.blueprints):
                await self.session.delete(row)
            await self.session.flush()
            for order_no, row in enumerate(payload.blueprint):
                self.session.add(
                    WeeklyAssessmentBlueprint(
                        weekly_assessment_id=wa.id,
                        subject_id=uuid.UUID(row.subject_id),
                        question_count=row.question_count,
                        chapter_ids=row.chapter_ids,
                        topic_ids=row.topic_ids,
                        order_no=order_no,
                    )
                )
        await self.session.commit()
        return await self.get(weekly_id)

    async def publish(self, weekly_id: uuid.UUID, *, actor_id: uuid.UUID) -> WeeklyAssessment:
        wa = await self.get(weekly_id, required=True)
        # Refuse to publish a paper that cannot be materialised — do the
        # exact same availability check the runtime will use.
        for bp in wa.blueprints:
            pool = await self._published_pool_for_blueprint(bp)
            if len(pool) < bp.question_count:
                raise AppError(
                    f"Blueprint row for subject {bp.subject_id} needs {bp.question_count} "
                    f"published questions but only {len(pool)} are available",
                    code="WEEKLY_POOL_INSUFFICIENT",
                    status_code=422,
                )
        wa.published = True
        wa.updated_by = actor_id
        await self.session.commit()
        return wa

    async def unpublish(self, weekly_id: uuid.UUID, *, actor_id: uuid.UUID) -> WeeklyAssessment:
        wa = await self.get(weekly_id, required=True)
        wa.published = False
        wa.updated_by = actor_id
        await self.session.commit()
        return wa

    # ------------------------------------------------------------------- reads

    async def get(self, weekly_id: uuid.UUID, *, required: bool = False) -> WeeklyAssessment | None:
        row = (
            await self.session.execute(
                select(WeeklyAssessment)
                .where(WeeklyAssessment.id == weekly_id, WeeklyAssessment.deleted_at.is_(None))
                .options(selectinload(WeeklyAssessment.blueprints))
            )
        ).scalar_one_or_none()
        if row is None and required:
            raise AppError("Weekly assessment not found", code="NOT_FOUND", status_code=404)
        return row

    async def list_admin(self) -> list[WeeklyAssessment]:
        rows = (
            await self.session.execute(
                select(WeeklyAssessment)
                .where(WeeklyAssessment.deleted_at.is_(None))
                .order_by(WeeklyAssessment.starts_at.desc())
                .options(selectinload(WeeklyAssessment.blueprints))
            )
        ).scalars().all()
        return list(rows)

    async def list_upcoming_for_student(self, *, user_id: uuid.UUID, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(UTC)
        rows = (
            await self.session.execute(
                select(WeeklyAssessment)
                .where(
                    WeeklyAssessment.deleted_at.is_(None),
                    WeeklyAssessment.published.is_(True),
                    WeeklyAssessment.ends_at >= now,
                )
                .order_by(WeeklyAssessment.starts_at.asc())
                .options(selectinload(WeeklyAssessment.blueprints))
            )
        ).scalars().all()
        out: list[dict] = []
        for wa in rows:
            attempts_used = await self._attempts_used(user_id=user_id, weekly_id=wa.id)
            out.append(self._public_view(wa, attempts_used=attempts_used, now=now))
        return out

    # -------------------------------------------------------------- materialise

    async def start_attempt(
        self, *, weekly_id: uuid.UUID, user_id: uuid.UUID, now: datetime | None = None
    ) -> tuple[Assessment, Attempt, list[dict]]:
        now = now or datetime.now(UTC)
        wa = await self.get(weekly_id, required=True)
        if not wa.published:
            raise AppError("This weekly assessment is not yet published", code="WEEKLY_NOT_PUBLISHED", status_code=409)
        if now < _aware(wa.starts_at):
            raise AppError("This weekly assessment has not started yet", code="WEEKLY_NOT_OPEN", status_code=409)
        if now > _aware(wa.ends_at):
            raise AppError("The window for this weekly assessment has closed", code="WEEKLY_CLOSED", status_code=409)

        used = await self._attempts_used(user_id=user_id, weekly_id=wa.id)
        if used >= wa.attempt_limit:
            raise AppError(
                f"You have already used your {wa.attempt_limit} attempt(s) for this weekly assessment",
                code="WEEKLY_ATTEMPT_LIMIT_REACHED",
                status_code=409,
            )

        # Select without duplicates by tracking a set across blueprint rows.
        already_picked: set[uuid.UUID] = set()
        selected_ordered: list[uuid.UUID] = []
        coverage: list[dict] = []
        subject_names = await self._subject_names_by_id([bp.subject_id for bp in wa.blueprints])
        for bp in wa.blueprints:
            pool = await self._published_pool_for_blueprint(bp)
            pool_dedup = [pid for pid in pool if pid not in already_picked]
            if len(pool_dedup) < bp.question_count:
                raise AppError(
                    f"Not enough published questions for {subject_names.get(bp.subject_id, 'subject')}: "
                    f"need {bp.question_count}, have {len(pool_dedup)}",
                    code="WEEKLY_POOL_INSUFFICIENT",
                    status_code=422,
                )
            picked = sample_question_ids(pool_dedup, bp.question_count)
            for pid in picked:
                if pid in already_picked:
                    raise AppError("Internal duplicate detected in weekly selection", code="WEEKLY_INTERNAL", status_code=500)
                already_picked.add(pid)
            selected_ordered.extend(picked)
            coverage.append(
                {
                    "subject_id": str(bp.subject_id),
                    "subject_name": subject_names.get(bp.subject_id, ""),
                    "quota": bp.question_count,
                    "available": len(pool),
                    "selected": len(picked),
                }
            )

        assessment = Assessment(
            assessment_type="MOCK",
            scope_type="FULL",
            scope_id=None,
            title=f"{wa.title} · attempt",
            duration_minutes=wa.duration_minutes,
            marks_per_question=wa.marks_per_question,
            negative_marks_per_question=wa.negative_marks_per_question,
            question_count=len(selected_ordered),
            weekly_assessment_id=wa.id,
            created_by=user_id,
            updated_by=user_id,
        )
        self.session.add(assessment)
        await self.session.flush()

        from app.modules.assessment.models import AssessmentQuestion

        for order_no, cid in enumerate(selected_ordered):
            self.session.add(
                AssessmentQuestion(assessment_id=assessment.id, content_item_id=cid, order_no=order_no)
            )

        attempt = Attempt(
            assessment_id=assessment.id,
            user_id=user_id,
            status="IN_PROGRESS",
            started_at=now,
            created_by=user_id,
            updated_by=user_id,
        )
        self.session.add(attempt)
        await self.session.commit()

        logger.info(
            "weekly_attempt_started",
            weekly_assessment_id=str(wa.id),
            assessment_id=str(assessment.id),
            attempt_id=str(attempt.id),
            user_id=str(user_id),
            question_count=len(selected_ordered),
        )
        return assessment, attempt, coverage

    # ------------------------------------------------------------------- internals

    async def _published_pool_for_blueprint(self, bp: WeeklyAssessmentBlueprint) -> list[uuid.UUID]:
        """Only PUBLISHED, non-deleted questions in the subject; optionally
        narrowed by explicit chapter/topic ids from the blueprint row."""
        query = (
            select(ContentItem.id)
            .join(Concept, Concept.id == ContentItem.concept_id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.status == "PUBLISHED",
                ContentItem.deleted_at.is_(None),
                Chapter.subject_id == bp.subject_id,
            )
        )
        if bp.chapter_ids:
            query = query.where(Chapter.id.in_([uuid.UUID(x) for x in bp.chapter_ids]))
        if bp.topic_ids:
            query = query.where(Topic.id.in_([uuid.UUID(x) for x in bp.topic_ids]))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def _assert_subjects_exist(self, subject_ids: list[uuid.UUID]) -> None:
        found = (
            await self.session.execute(select(Subject.id).where(Subject.id.in_(subject_ids)))
        ).scalars().all()
        missing = set(subject_ids) - set(found)
        if missing:
            raise AppError(
                f"Unknown subject_id(s): {sorted(str(m) for m in missing)}",
                code="SUBJECT_NOT_FOUND",
                status_code=422,
            )

    async def _subject_names_by_id(self, subject_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        rows = (
            await self.session.execute(
                select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
            )
        ).all()
        return {r[0]: r[1] for r in rows}

    async def _attempts_used(self, *, user_id: uuid.UUID, weekly_id: uuid.UUID) -> int:
        q = (
            select(func.count(Attempt.id))
            .join(Assessment, Assessment.id == Attempt.assessment_id)
            .where(
                Assessment.weekly_assessment_id == weekly_id,
                Attempt.user_id == user_id,
            )
        )
        return int((await self.session.execute(q)).scalar_one() or 0)

    def _public_view(self, wa: WeeklyAssessment, *, attempts_used: int, now: datetime) -> dict:
        starts = _aware(wa.starts_at)
        ends = _aware(wa.ends_at)
        state = "UPCOMING"
        if now >= starts and now <= ends:
            state = "OPEN"
        elif now > ends:
            state = "CLOSED"
        return {
            "id": str(wa.id),
            "assessment_key": wa.assessment_key,
            "title": wa.title,
            "description": wa.description,
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "duration_minutes": wa.duration_minutes,
            "marks_per_question": float(wa.marks_per_question),
            "negative_marks_per_question": float(wa.negative_marks_per_question),
            "attempt_limit": wa.attempt_limit,
            "attempts_used": attempts_used,
            "cumulative_weight": wa.cumulative_weight,
            "difficulty_distribution": wa.difficulty_distribution,
            "blueprint": [
                {
                    "subject_id": str(bp.subject_id),
                    "question_count": bp.question_count,
                    "chapter_ids": bp.chapter_ids or [],
                    "topic_ids": bp.topic_ids or [],
                    "order_no": bp.order_no,
                }
                for bp in wa.blueprints
            ],
            "state": state,
            "seconds_until_start": max(0, int((starts - now).total_seconds())) if state == "UPCOMING" else 0,
        }


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def public_view_admin(wa: WeeklyAssessment) -> dict[str, Any]:
    """Admin listing view — includes published flag."""
    return {
        "id": str(wa.id),
        "assessment_key": wa.assessment_key,
        "title": wa.title,
        "description": wa.description,
        "starts_at": _aware(wa.starts_at).isoformat(),
        "ends_at": _aware(wa.ends_at).isoformat(),
        "duration_minutes": wa.duration_minutes,
        "marks_per_question": float(wa.marks_per_question),
        "negative_marks_per_question": float(wa.negative_marks_per_question),
        "attempt_limit": wa.attempt_limit,
        "cumulative_weight": wa.cumulative_weight,
        "difficulty_distribution": wa.difficulty_distribution,
        "published": wa.published,
        "blueprint": [
            {
                "id": str(bp.id),
                "subject_id": str(bp.subject_id),
                "question_count": bp.question_count,
                "chapter_ids": bp.chapter_ids or [],
                "topic_ids": bp.topic_ids or [],
                "order_no": bp.order_no,
            }
            for bp in wa.blueprints
        ],
    }
