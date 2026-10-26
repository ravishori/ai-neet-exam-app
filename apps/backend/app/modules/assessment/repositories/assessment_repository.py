import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.assessment.models import Assessment, AssessmentQuestion, Attempt, AttemptAnswer
from app.modules.cms.models import ContentItem, ContentVersion
from app.modules.cms.schemas.content_bodies import is_student_eligible


class AssessmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def published_question_ids_for_scope(self, scope_type: str, scope_id: uuid.UUID | None) -> list[uuid.UUID]:
        """Student-facing eligibility gate for every practice/mock-test
        question-selection path (generate_practice, generate_mock,
        generate_full_mock all funnel through this one method).

        PUBLISHED is necessary but never sufficient on its own -- a
        structurally-defective body, or one explicitly flagged
        ANSWER_PENDING/ANSWER_CONFLICT, can still be the current PUBLISHED
        version (nothing re-runs content.schemas.content_bodies.
        is_student_eligible at publish time beyond assert_body_publishable's
        structural check, which does not look at answer_status at all).
        This filters those out AFTER the PUBLISHED query, in Python, reusing
        the same body-validation schema the publish endpoint already uses
        (see is_student_eligible's own docstring for exactly what it does
        and deliberately does NOT require). Excluded rows remain fully
        intact and visible to authorized admins via the existing CMS
        content-item endpoints -- this never deletes or edits anything,
        only narrows what THIS method returns."""
        query = select(ContentItem.id, ContentVersion.body).where(
            ContentItem.content_type == "QUESTION",
            ContentItem.status == "PUBLISHED",
            ContentItem.deleted_at.is_(None),
        ).join(ContentVersion, ContentVersion.id == ContentItem.current_version_id)

        if scope_type == "CONCEPT":
            query = query.where(ContentItem.concept_id == scope_id)
        elif scope_type == "TOPIC":
            # Questions whose concept belongs to this topic only (no sibling-topic leakage).
            query = query.join(Concept, Concept.id == ContentItem.concept_id).where(Concept.topic_id == scope_id)
        elif scope_type == "CHAPTER":
            query = query.join(Concept, Concept.id == ContentItem.concept_id).join(Topic, Topic.id == Concept.topic_id).where(
                Topic.chapter_id == scope_id
            )
        elif scope_type == "SUBJECT":
            query = (
                query.join(Concept, Concept.id == ContentItem.concept_id)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .where(Chapter.subject_id == scope_id)
            )
        elif scope_type == "SEED_V1":
            # Server-owned frozen allowlist — never client-supplied UUIDs.
            from app.modules.assessment.seed_v1_allowlist import seed_v1_uuids

            query = query.where(ContentItem.id.in_(seed_v1_uuids()))
        elif scope_type == "SEED_V2":
            from sqlalchemy import not_
            from sqlalchemy.dialects.postgresql import array as pg_array

            from app.modules.assessment.seed_v2_allowlist import SEED_V2_SUPERSEDED_TAGS, seed_v2_uuids

            query = query.where(ContentItem.id.in_(seed_v2_uuids()))
            query = query.where(not_(ContentItem.tags.op("&&")(pg_array(list(SEED_V2_SUPERSEDED_TAGS)))))
        # FULL: no extra filter

        result = await self.session.execute(query)
        return [
            item_id
            for item_id, body in result.all()
            if is_student_eligible("QUESTION", body or {})[0]
        ]

    def add_assessment(self, assessment: Assessment) -> None:
        self.session.add(assessment)

    def add_question(self, question: AssessmentQuestion) -> None:
        self.session.add(question)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def get_assessment(self, assessment_id: uuid.UUID) -> Assessment | None:
        result = await self.session.execute(
            select(Assessment).options(selectinload(Assessment.questions)).where(Assessment.id == assessment_id)
        )
        return result.scalar_one_or_none()

    def add_attempt(self, attempt: Attempt) -> None:
        self.session.add(attempt)

    async def get_attempt(self, attempt_id: uuid.UUID) -> Attempt | None:
        result = await self.session.execute(
            select(Attempt).options(selectinload(Attempt.answers)).where(Attempt.id == attempt_id)
        )
        return result.scalar_one_or_none()

    async def list_attempts_for_user(self, user_id: uuid.UUID) -> list[Attempt]:
        result = await self.session.execute(
            select(Attempt).where(Attempt.user_id == user_id).order_by(Attempt.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_answer(self, attempt_id: uuid.UUID, content_item_id: uuid.UUID) -> AttemptAnswer | None:
        result = await self.session.execute(
            select(AttemptAnswer).where(
                AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.content_item_id == content_item_id
            )
        )
        return result.scalar_one_or_none()

    def add_answer(self, answer: AttemptAnswer) -> None:
        self.session.add(answer)

    async def get_content_items(self, ids: list[uuid.UUID]) -> list[ContentItem]:
        result = await self.session.execute(
            select(ContentItem).options(selectinload(ContentItem.versions)).where(ContentItem.id.in_(ids))
        )
        return list(result.scalars().all())

    async def answer_history_for_question(self, user_id: uuid.UUID, content_item_id: uuid.UUID) -> list[AttemptAnswer]:
        """Every past *submitted* attempt this user made at this question —
        the "Previous Attempts" panel (PR 11). Joins through Attempt since
        AttemptAnswer carries no user_id of its own."""
        result = await self.session.execute(
            select(AttemptAnswer)
            .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
            .where(
                Attempt.user_id == user_id,
                AttemptAnswer.content_item_id == content_item_id,
                Attempt.status == "SUBMITTED",
            )
            .order_by(AttemptAnswer.answered_at.desc())
        )
        return list(result.scalars().all())


def sample_question_ids(all_ids: list[uuid.UUID], count: int) -> list[uuid.UUID]:
    if count >= len(all_ids):
        ids = list(all_ids)
        random.shuffle(ids)
        return ids
    return random.sample(all_ids, count)
