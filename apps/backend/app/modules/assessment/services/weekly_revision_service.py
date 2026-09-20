"""Student-driven Weekly Revision recommender.

Design:
- Idempotent per (user_id, ISO year, ISO week) — reading the "current
  week" recommendation twice returns the same plan (same DB row).
- Never generates or modifies question content. Only selects from
  PUBLISHED + non-deleted questions in the existing pool.
- Blueprint composition (subject quotas + recent/previous split) is
  chosen once and stored; materialisation re-uses the same blueprint so
  question selection is fresh but the recommendation is stable.
- If any subject can't fulfil its quota, we mark the recommendation
  ``UNAVAILABLE`` with a specific reason — we never ship a short paper.

Subjects: Physics + Chemistry + Biology (Biology = Botany ∪ Zoology).

Defaults (from product brief):
    Physics 15, Chemistry 15, Biology 30, total 60. ~75/25 recent/previous.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.assessment.models import (
    Assessment,
    AssessmentQuestion,
    Attempt,
    AttemptAnswer,
    WeeklyRevisionRecommendation,
)
from app.modules.assessment.repositories.assessment_repository import sample_question_ids
from app.modules.cms.models import ContentItem
from app.modules.learning.models.concept_mastery import ConceptMastery

logger = get_logger("weekly_revision")


# --------------------------------------------------------------------- config

@dataclass(frozen=True)
class SubjectQuota:
    matcher: tuple[str, ...]  # subject.name candidates that fold into this bucket
    quota: int
    label: str


SUBJECT_QUOTAS: tuple[SubjectQuota, ...] = (
    SubjectQuota(matcher=("Physics",), quota=15, label="Physics"),
    SubjectQuota(matcher=("Chemistry",), quota=15, label="Chemistry"),
    SubjectQuota(matcher=("Biology", "Botany", "Zoology"), quota=30, label="Biology"),
)

RECENT_WINDOW_DAYS = 14                    # "recent" = attempted anywhere in the last 2 weeks
RECENT_SPLIT_PCT = 75                      # ~75% recent / ~25% previous
WEAK_MASTERY_THRESHOLD = 40                # concept mastery_score below this = weak
DEFAULT_DURATION_MINUTES = 60
MIN_RECENT_CHAPTER_TOUCH = 3               # >=3 attempted questions before a chapter counts as "recent"


def current_iso_week(now: datetime | None = None) -> tuple[int, int]:
    now = now or datetime.now(UTC)
    iso = now.isocalendar()
    return int(iso.year), int(iso.week)


class WeeklyRevisionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------- public API

    async def get_or_generate_current(
        self, *, user_id: uuid.UUID, now: datetime | None = None
    ) -> WeeklyRevisionRecommendation:
        now = now or datetime.now(UTC)
        year, week = current_iso_week(now)
        existing = await self._get_by_week(user_id=user_id, year=year, week=week)
        if existing is not None:
            return existing
        return await self._generate(user_id=user_id, year=year, week=week, now=now)

    async def start_attempt(
        self, *, user_id: uuid.UUID, now: datetime | None = None
    ) -> tuple[WeeklyRevisionRecommendation, Assessment, Attempt]:
        now = now or datetime.now(UTC)
        rec = await self.get_or_generate_current(user_id=user_id, now=now)

        if rec.status == "UNAVAILABLE":
            raise AppError(
                "Not enough published questions are available for this week's revision. "
                "Try again once more material has been published.",
                code="WEEKLY_REVISION_UNAVAILABLE",
                status_code=422,
            )
        if rec.status == "COMPLETED":
            raise AppError(
                "You have already completed this week's revision.",
                code="WEEKLY_REVISION_ALREADY_COMPLETED",
                status_code=409,
            )
        # Resume in-progress attempt if it exists — never create a duplicate.
        in_progress = await self._latest_attempt_for_recommendation(rec.id, user_id)
        if in_progress and in_progress.status == "IN_PROGRESS":
            assessment = (
                await self.session.execute(select(Assessment).where(Assessment.id == in_progress.assessment_id))
            ).scalar_one()
            return rec, assessment, in_progress

        selected_ids = await self._materialise_from_blueprint(rec)
        if selected_ids is None:
            # Pool shifted between generate and start — flip to UNAVAILABLE and refuse.
            rec.status = "UNAVAILABLE"
            rec.updated_by = user_id
            await self.session.commit()
            raise AppError(
                "The question pool changed since this recommendation was generated. "
                "Please refresh your dashboard to see this week's status.",
                code="WEEKLY_REVISION_POOL_DRIFT",
                status_code=409,
            )

        assessment = Assessment(
            assessment_type="MOCK",
            scope_type="FULL",
            scope_id=None,
            title=f"Weekly Revision · Week {rec.iso_week}",
            duration_minutes=rec.estimated_duration_minutes,
            marks_per_question=rec.marks_per_question,
            negative_marks_per_question=rec.negative_marks_per_question,
            question_count=len(selected_ids),
            weekly_revision_id=rec.id,
            created_by=user_id,
            updated_by=user_id,
        )
        self.session.add(assessment)
        await self.session.flush()

        for order_no, cid in enumerate(selected_ids):
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

        rec.status = "IN_PROGRESS"
        rec.updated_by = user_id
        await self.session.commit()

        logger.info(
            "weekly_revision_attempt_started",
            recommendation_id=str(rec.id),
            user_id=str(user_id),
            iso_year=rec.iso_year,
            iso_week=rec.iso_week,
            question_count=len(selected_ids),
        )
        return rec, assessment, attempt

    async def sync_completed_state(self, *, user_id: uuid.UUID) -> None:
        """Flip the current-week recommendation to COMPLETED once any linked
        attempt is submitted. Called from the attempt-submit path."""
        year, week = current_iso_week()
        rec = await self._get_by_week(user_id=user_id, year=year, week=week)
        if rec is None or rec.status == "COMPLETED":
            return
        submitted = (
            await self.session.execute(
                select(func.count(Attempt.id))
                .join(Assessment, Assessment.id == Attempt.assessment_id)
                .where(
                    Assessment.weekly_revision_id == rec.id,
                    Attempt.user_id == user_id,
                    Attempt.status == "SUBMITTED",
                )
            )
        ).scalar_one()
        if submitted:
            rec.status = "COMPLETED"
            rec.updated_by = user_id
            await self.session.commit()

    # -------------------------------------------------------------- helpers

    async def _get_by_week(
        self, *, user_id: uuid.UUID, year: int, week: int
    ) -> WeeklyRevisionRecommendation | None:
        return (
            await self.session.execute(
                select(WeeklyRevisionRecommendation).where(
                    WeeklyRevisionRecommendation.user_id == user_id,
                    WeeklyRevisionRecommendation.iso_year == year,
                    WeeklyRevisionRecommendation.iso_week == week,
                    WeeklyRevisionRecommendation.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    async def _latest_attempt_for_recommendation(
        self, recommendation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Attempt | None:
        return (
            await self.session.execute(
                select(Attempt)
                .join(Assessment, Assessment.id == Attempt.assessment_id)
                .where(
                    Assessment.weekly_revision_id == recommendation_id,
                    Attempt.user_id == user_id,
                )
                .order_by(Attempt.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _generate(
        self, *, user_id: uuid.UUID, year: int, week: int, now: datetime
    ) -> WeeklyRevisionRecommendation:
        subjects = await self._subjects_by_bucket()
        recent_cutoff = now - timedelta(days=RECENT_WINDOW_DAYS)

        blueprint: list[dict] = []
        reason: dict = {"cold_start": False, "recent_chapters": [], "weak_topics": [], "buckets": []}
        unavailable_reasons: list[str] = []

        for quota in SUBJECT_QUOTAS:
            subject_ids = [s.id for s in subjects if s.name in quota.matcher]
            if not subject_ids:
                unavailable_reasons.append(f"{quota.label}: no subject seeded")
                continue

            plan = await self._plan_bucket(
                user_id=user_id,
                subject_ids=subject_ids,
                quota_total=quota.quota,
                recent_cutoff=recent_cutoff,
            )
            if plan is None:
                unavailable_reasons.append(
                    f"{quota.label}: only {await self._pool_size_for_subjects(subject_ids)} "
                    f"published questions available, need {quota.quota}"
                )
                continue

            blueprint.append(
                {
                    "label": quota.label,
                    "subject_ids": [str(s) for s in subject_ids],
                    "quota": quota.quota,
                    "recent_quota": plan["recent_quota"],
                    "previous_quota": plan["previous_quota"],
                    "recent_chapter_ids": [str(c) for c in plan["recent_chapter_ids"]],
                    "previous_chapter_ids": [str(c) for c in plan["previous_chapter_ids"]],
                    "weak_chapter_ids": [str(c) for c in plan["weak_chapter_ids"]],
                    "used_cold_start": plan["used_cold_start"],
                }
            )
            reason["buckets"].append(
                {
                    "label": quota.label,
                    "recent_chapter_count": len(plan["recent_chapter_ids"]),
                    "previous_chapter_count": len(plan["previous_chapter_ids"]),
                    "weak_chapter_count": len(plan["weak_chapter_ids"]),
                    "cold_start": plan["used_cold_start"],
                }
            )
            if plan["used_cold_start"]:
                reason["cold_start"] = True

        status = "RECOMMENDED" if not unavailable_reasons and blueprint else "UNAVAILABLE"
        if unavailable_reasons:
            reason["unavailable_reasons"] = unavailable_reasons

        rec = WeeklyRevisionRecommendation(
            user_id=user_id,
            iso_year=year,
            iso_week=week,
            blueprint=blueprint,
            reason=reason,
            status=status,
            estimated_duration_minutes=DEFAULT_DURATION_MINUTES,
            marks_per_question=4,
            negative_marks_per_question=1,
            attempt_limit=1,
            generated_at=now,
            created_by=user_id,
            updated_by=user_id,
        )
        self.session.add(rec)
        await self.session.commit()

        logger.info(
            "weekly_revision_generated",
            user_id=str(user_id),
            iso_year=year,
            iso_week=week,
            status=status,
            buckets=len(blueprint),
        )
        return rec

    async def _subjects_by_bucket(self) -> list[Subject]:
        return list(
            (await self.session.execute(select(Subject).order_by(Subject.name))).scalars().all()
        )

    async def _pool_size_for_subjects(self, subject_ids: list[uuid.UUID]) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count(ContentItem.id))
                    .select_from(ContentItem)
                    .join(Concept, Concept.id == ContentItem.concept_id)
                    .join(Topic, Topic.id == Concept.topic_id)
                    .join(Chapter, Chapter.id == Topic.chapter_id)
                    .where(
                        ContentItem.content_type == "QUESTION",
                        ContentItem.status == "PUBLISHED",
                        ContentItem.deleted_at.is_(None),
                        Chapter.subject_id.in_(subject_ids),
                    )
                )
            ).scalar_one()
            or 0
        )

    async def _plan_bucket(
        self,
        *,
        user_id: uuid.UUID,
        subject_ids: list[uuid.UUID],
        quota_total: int,
        recent_cutoff: datetime,
    ) -> dict | None:
        pool_size = await self._pool_size_for_subjects(subject_ids)
        if pool_size < quota_total:
            return None

        recent_qty = round(quota_total * RECENT_SPLIT_PCT / 100)
        previous_qty = quota_total - recent_qty

        recent_chapters = await self._chapters_recently_attempted(
            user_id=user_id, subject_ids=subject_ids, since=recent_cutoff
        )
        previous_chapters = await self._chapters_previously_attempted(
            user_id=user_id,
            subject_ids=subject_ids,
            recent_cutoff=recent_cutoff,
            exclude=set(recent_chapters),
        )
        used_cold_start = False
        if not recent_chapters:
            # Cold start — no attempts in the last 2 weeks. Recommend across
            # every chapter in the subject that has enough pool coverage.
            recent_chapters = await self._chapters_with_pool(subject_ids)
            used_cold_start = True

        # If either side has no chapters, the "split" collapses into the
        # other side rather than emitting UNAVAILABLE.
        if not previous_chapters:
            recent_qty, previous_qty = quota_total, 0
        elif not recent_chapters:
            recent_qty, previous_qty = 0, quota_total

        weak = await self._weak_chapters_for_user(user_id=user_id, chapter_ids=recent_chapters | previous_chapters)

        return {
            "recent_quota": recent_qty,
            "previous_quota": previous_qty,
            "recent_chapter_ids": sorted(recent_chapters),
            "previous_chapter_ids": sorted(previous_chapters),
            "weak_chapter_ids": sorted(weak),
            "used_cold_start": used_cold_start,
        }

    async def _chapters_recently_attempted(
        self, *, user_id: uuid.UUID, subject_ids: list[uuid.UUID], since: datetime
    ) -> set[uuid.UUID]:
        rows = (
            await self.session.execute(
                select(Chapter.id)
                .join(Topic, Topic.chapter_id == Chapter.id)
                .join(Concept, Concept.topic_id == Topic.id)
                .join(ContentItem, ContentItem.concept_id == Concept.id)
                .join(AttemptAnswer, AttemptAnswer.content_item_id == ContentItem.id)
                .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
                .where(
                    Attempt.user_id == user_id,
                    Attempt.started_at >= since,
                    Chapter.subject_id.in_(subject_ids),
                )
                .group_by(Chapter.id)
                .having(func.count(AttemptAnswer.id) >= MIN_RECENT_CHAPTER_TOUCH)
            )
        ).scalars().all()
        return set(rows)

    async def _chapters_previously_attempted(
        self,
        *,
        user_id: uuid.UUID,
        subject_ids: list[uuid.UUID],
        recent_cutoff: datetime,
        exclude: set[uuid.UUID],
    ) -> set[uuid.UUID]:
        rows = (
            await self.session.execute(
                select(Chapter.id)
                .join(Topic, Topic.chapter_id == Chapter.id)
                .join(Concept, Concept.topic_id == Topic.id)
                .join(ContentItem, ContentItem.concept_id == Concept.id)
                .join(AttemptAnswer, AttemptAnswer.content_item_id == ContentItem.id)
                .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
                .where(
                    Attempt.user_id == user_id,
                    Attempt.started_at < recent_cutoff,
                    Chapter.subject_id.in_(subject_ids),
                )
                .group_by(Chapter.id)
            )
        ).scalars().all()
        return {r for r in rows if r not in exclude}

    async def _chapters_with_pool(self, subject_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        rows = (
            await self.session.execute(
                select(Chapter.id)
                .join(Topic, Topic.chapter_id == Chapter.id)
                .join(Concept, Concept.topic_id == Topic.id)
                .join(ContentItem, ContentItem.concept_id == Concept.id)
                .where(
                    ContentItem.content_type == "QUESTION",
                    ContentItem.status == "PUBLISHED",
                    ContentItem.deleted_at.is_(None),
                    Chapter.subject_id.in_(subject_ids),
                )
                .group_by(Chapter.id)
            )
        ).scalars().all()
        return set(rows)

    async def _weak_chapters_for_user(
        self, *, user_id: uuid.UUID, chapter_ids: set[uuid.UUID]
    ) -> set[uuid.UUID]:
        if not chapter_ids:
            return set()
        rows = (
            await self.session.execute(
                select(
                    Chapter.id,
                    func.avg(func.coalesce(ConceptMastery.mastery_score, 0)).label("avg_score"),
                )
                .select_from(Chapter)
                .join(Topic, Topic.chapter_id == Chapter.id)
                .join(Concept, Concept.topic_id == Topic.id)
                .join(
                    ConceptMastery,
                    and_(ConceptMastery.concept_id == Concept.id, ConceptMastery.user_id == user_id),
                    isouter=True,
                )
                .where(Chapter.id.in_(chapter_ids))
                .group_by(Chapter.id)
            )
        ).all()
        return {r[0] for r in rows if float(r[1] or 0) < WEAK_MASTERY_THRESHOLD}

    # ------------------------------------------------------- materialisation

    async def _materialise_from_blueprint(
        self, rec: WeeklyRevisionRecommendation
    ) -> list[uuid.UUID] | None:
        rng = random.Random(f"{rec.user_id}:{rec.iso_year}:{rec.iso_week}")
        picked: set[uuid.UUID] = set()
        ordered: list[uuid.UUID] = []

        for bucket in rec.blueprint:
            subject_ids = [uuid.UUID(s) for s in bucket["subject_ids"]]
            recent_chapter_ids = [uuid.UUID(c) for c in bucket["recent_chapter_ids"]]
            previous_chapter_ids = [uuid.UUID(c) for c in bucket["previous_chapter_ids"]]
            weak_chapter_ids = {uuid.UUID(c) for c in bucket["weak_chapter_ids"]}
            recent_qty = int(bucket["recent_quota"])
            previous_qty = int(bucket["previous_quota"])

            recent_picked = await self._pick_from_chapters(
                subject_ids=subject_ids,
                chapter_ids=recent_chapter_ids or list(recent_chapter_ids),
                want=recent_qty,
                already=picked,
                weak_chapter_ids=weak_chapter_ids,
                rng=rng,
                subject_fallback=recent_qty and not recent_chapter_ids,
            )
            previous_picked = await self._pick_from_chapters(
                subject_ids=subject_ids,
                chapter_ids=previous_chapter_ids or list(previous_chapter_ids),
                want=previous_qty,
                already=picked,
                weak_chapter_ids=weak_chapter_ids,
                rng=rng,
                subject_fallback=previous_qty and not previous_chapter_ids,
            )
            bucket_ids = recent_picked + previous_picked
            if len(bucket_ids) < bucket["quota"]:
                # Fall back to whole-subject pool to fill remaining slots.
                remainder = bucket["quota"] - len(bucket_ids)
                filler = await self._pick_from_chapters(
                    subject_ids=subject_ids,
                    chapter_ids=[],
                    want=remainder,
                    already=picked | set(bucket_ids),
                    weak_chapter_ids=weak_chapter_ids,
                    rng=rng,
                    subject_fallback=True,
                )
                bucket_ids += filler
            if len(bucket_ids) < bucket["quota"]:
                return None
            for cid in bucket_ids:
                if cid in picked:
                    # Should not happen — final dedup guard.
                    continue
                picked.add(cid)
                ordered.append(cid)
        return ordered

    async def _pick_from_chapters(
        self,
        *,
        subject_ids: list[uuid.UUID],
        chapter_ids: list[uuid.UUID],
        want: int,
        already: set[uuid.UUID],
        weak_chapter_ids: set[uuid.UUID],
        rng: random.Random,
        subject_fallback: bool,
    ) -> list[uuid.UUID]:
        if want <= 0:
            return []
        query = (
            select(ContentItem.id, Chapter.id.label("chapter_id"))
            .join(Concept, Concept.id == ContentItem.concept_id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.status == "PUBLISHED",
                ContentItem.deleted_at.is_(None),
            )
        )
        if chapter_ids:
            query = query.where(Chapter.id.in_(chapter_ids))
        elif subject_fallback:
            query = query.where(Chapter.subject_id.in_(subject_ids))
        else:
            return []
        rows = (await self.session.execute(query)).all()
        weak_pool = [r[0] for r in rows if r[1] in weak_chapter_ids and r[0] not in already]
        rest_pool = [r[0] for r in rows if r[1] not in weak_chapter_ids and r[0] not in already]
        rng.shuffle(weak_pool)
        rng.shuffle(rest_pool)
        # Bias toward weak chapters (~60% when both pools exist), but always
        # fill `want` when the combined pool can — never short-fill because
        # of the mix ratio. This matters for cold-start users where every
        # chapter shows as "weak" (no mastery rows -> avg = 0 < threshold),
        # which previously drove weak_pool to hold everything and left
        # rest_pool empty, tripping WEEKLY_REVISION_POOL_DRIFT.
        if not weak_pool:
            return rest_pool[:want]
        if not rest_pool:
            return weak_pool[:want]
        weak_target = min(len(weak_pool), max(1, int(round(want * 0.6))))
        tail_target = want - weak_target
        if tail_target > len(rest_pool):
            # Backfill from weak so we don't short-fill purely because rest is small.
            weak_target = min(len(weak_pool), weak_target + (tail_target - len(rest_pool)))
            tail_target = want - weak_target
        head = weak_pool[:weak_target]
        tail = rest_pool[:tail_target]
        return head + tail


def public_view(rec: WeeklyRevisionRecommendation, *, subject_labels: dict[str, str] | None = None) -> dict:
    total_questions = sum(int(b["quota"]) for b in rec.blueprint) if rec.blueprint else 0
    return {
        "id": str(rec.id),
        "iso_year": rec.iso_year,
        "iso_week": rec.iso_week,
        "status": rec.status,
        "estimated_duration_minutes": rec.estimated_duration_minutes,
        "marks_per_question": float(rec.marks_per_question),
        "negative_marks_per_question": float(rec.negative_marks_per_question),
        "attempt_limit": rec.attempt_limit,
        "total_questions": total_questions,
        "generated_at": (
            rec.generated_at.astimezone(UTC) if rec.generated_at.tzinfo else rec.generated_at.replace(tzinfo=UTC)
        ).isoformat(),
        "blueprint": [
            {
                "label": b["label"],
                "quota": int(b["quota"]),
                "recent_quota": int(b["recent_quota"]),
                "previous_quota": int(b["previous_quota"]),
                "recent_chapter_count": len(b.get("recent_chapter_ids") or []),
                "previous_chapter_count": len(b.get("previous_chapter_ids") or []),
                "weak_chapter_count": len(b.get("weak_chapter_ids") or []),
                "used_cold_start": bool(b.get("used_cold_start")),
            }
            for b in (rec.blueprint or [])
        ],
        "reason": rec.reason,
    }
