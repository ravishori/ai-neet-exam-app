import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.assessment.models import Assessment, AssessmentQuestion, Attempt, AttemptAnswer
from app.modules.cms.models import ContentItem


class AssessmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def published_question_ids_for_scope(self, scope_type: str, scope_id: uuid.UUID | None) -> list[uuid.UUID]:
        query = select(ContentItem.id).where(ContentItem.content_type == "QUESTION", ContentItem.status == "PUBLISHED")

        if scope_type == "CONCEPT":
            query = query.where(ContentItem.concept_id == scope_id)
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
        # FULL: no extra filter

        result = await self.session.execute(query)
        return list(result.scalars().all())

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
