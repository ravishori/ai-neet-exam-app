import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Concept
from app.modules.assessment.models import Attempt, AttemptAnswer
from app.modules.cms.models import ContentItem
from app.modules.learning.models import ConceptMastery


class MasteryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def concept_ids_for_content_items(self, content_item_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not content_item_ids:
            return set()
        result = await self.session.execute(
            select(ContentItem.concept_id).where(
                ContentItem.id.in_(content_item_ids), ContentItem.concept_id.is_not(None)
            )
        )
        return {row for row in result.scalars().all() if row is not None}

    async def aggregate_answers(self, user_id: uuid.UUID, concept_id: uuid.UUID) -> tuple[int, int, datetime | None]:
        result = await self.session.execute(
            select(
                func.count(AttemptAnswer.id),
                func.count(AttemptAnswer.id).filter(AttemptAnswer.is_correct.is_(True)),
                func.max(AttemptAnswer.answered_at),
            )
            .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
            .join(ContentItem, ContentItem.id == AttemptAnswer.content_item_id)
            .where(
                Attempt.user_id == user_id,
                ContentItem.concept_id == concept_id,
                AttemptAnswer.is_correct.is_not(None),
            )
        )
        attempts_count, correct_count, last_attempt_at = result.one()
        return attempts_count or 0, correct_count or 0, last_attempt_at

    async def get(self, user_id: uuid.UUID, concept_id: uuid.UUID) -> ConceptMastery | None:
        result = await self.session.execute(
            select(ConceptMastery).where(ConceptMastery.user_id == user_id, ConceptMastery.concept_id == concept_id)
        )
        return result.scalar_one_or_none()

    def add(self, row: ConceptMastery) -> None:
        self.session.add(row)

    async def commit(self) -> None:
        await self.session.commit()

    async def get_for_topic(self, user_id: uuid.UUID, topic_id: uuid.UUID) -> list[tuple[Concept, ConceptMastery | None]]:
        result = await self.session.execute(
            select(Concept, ConceptMastery)
            .outerjoin(
                ConceptMastery, (ConceptMastery.concept_id == Concept.id) & (ConceptMastery.user_id == user_id)
            )
            .where(Concept.topic_id == topic_id)
            .order_by(Concept.display_order)
        )
        return list(result.all())

    async def get_overview(self, user_id: uuid.UUID) -> list[dict]:
        from app.modules.academic.models import Chapter, Subject, Topic

        result = await self.session.execute(
            select(
                Subject.id,
                Subject.name,
                func.count(Concept.id),
                func.count(ConceptMastery.id),
                func.coalesce(func.avg(ConceptMastery.mastery_score), 0),
                func.count(ConceptMastery.id).filter(ConceptMastery.mastery_level == "MASTERED"),
            )
            .select_from(Subject)
            .join(Chapter, Chapter.subject_id == Subject.id)
            .join(Topic, Topic.chapter_id == Chapter.id)
            .join(Concept, Concept.topic_id == Topic.id)
            .outerjoin(
                ConceptMastery, (ConceptMastery.concept_id == Concept.id) & (ConceptMastery.user_id == user_id)
            )
            .group_by(Subject.id, Subject.name)
            .order_by(Subject.display_order)
        )
        return [
            {
                "subject_id": str(row[0]),
                "subject_name": row[1],
                "concepts_total": row[2],
                "concepts_attempted": row[3],
                "average_score": round(float(row[4]), 1),
                "mastered_count": row[5],
            }
            for row in result.all()
        ]
