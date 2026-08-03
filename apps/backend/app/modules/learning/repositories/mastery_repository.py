import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Chapter, Concept, MicroCompetency, Subject, Topic
from app.modules.assessment.models import Attempt, AttemptAnswer
from app.modules.cms.models import ContentItem
from app.modules.cms.models.content_version_knowledge_unit import ContentVersionKnowledgeUnit
from app.modules.learning.models import ConceptMastery, KnowledgeUnitMastery, MicroCompetencyMastery


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

    async def micro_competency_ids_for_content_items(self, content_item_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not content_item_ids:
            return set()
        result = await self.session.execute(
            select(ContentItem.micro_competency_id).where(
                ContentItem.id.in_(content_item_ids), ContentItem.micro_competency_id.is_not(None)
            )
        )
        return {row for row in result.scalars().all() if row is not None}

    async def aggregate_answers_for_micro_competency(
        self, user_id: uuid.UUID, micro_competency_id: uuid.UUID
    ) -> tuple[int, int, datetime | None]:
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
                ContentItem.micro_competency_id == micro_competency_id,
                AttemptAnswer.is_correct.is_not(None),
            )
        )
        attempts_count, correct_count, last_attempt_at = result.one()
        return attempts_count or 0, correct_count or 0, last_attempt_at

    async def knowledge_unit_ids_for_content_items(self, content_item_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        """Traces each content item to the Knowledge Unit(s) that grounded it
        via the existing ADR-0025 lineage table — see ADR-0028 Phase D. Only
        content items reachable from an AttemptAnswer are ever passed in
        here, and only QUESTION items are ever answered, so no content_type
        filter is needed: a CONCEPT_NOTE or FORMULA_SHEET id never appears
        in content_item_ids in practice."""
        if not content_item_ids:
            return set()
        result = await self.session.execute(
            select(ContentVersionKnowledgeUnit.knowledge_unit_id)
            .join(ContentItem, ContentItem.current_version_id == ContentVersionKnowledgeUnit.content_version_id)
            .where(ContentItem.id.in_(content_item_ids))
        )
        return set(result.scalars().all())

    async def aggregate_answers_for_knowledge_unit(
        self, user_id: uuid.UUID, knowledge_unit_id: uuid.UUID
    ) -> tuple[int, int, datetime | None]:
        result = await self.session.execute(
            select(
                func.count(AttemptAnswer.id),
                func.count(AttemptAnswer.id).filter(AttemptAnswer.is_correct.is_(True)),
                func.max(AttemptAnswer.answered_at),
            )
            .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
            .join(ContentItem, ContentItem.id == AttemptAnswer.content_item_id)
            .join(
                ContentVersionKnowledgeUnit,
                ContentVersionKnowledgeUnit.content_version_id == ContentItem.current_version_id,
            )
            .where(
                Attempt.user_id == user_id,
                ContentVersionKnowledgeUnit.knowledge_unit_id == knowledge_unit_id,
                AttemptAnswer.is_correct.is_not(None),
            )
        )
        attempts_count, correct_count, last_attempt_at = result.one()
        return attempts_count or 0, correct_count or 0, last_attempt_at

    async def get_knowledge_unit_mastery(
        self, user_id: uuid.UUID, knowledge_unit_id: uuid.UUID
    ) -> KnowledgeUnitMastery | None:
        result = await self.session.execute(
            select(KnowledgeUnitMastery).where(
                KnowledgeUnitMastery.user_id == user_id, KnowledgeUnitMastery.knowledge_unit_id == knowledge_unit_id
            )
        )
        return result.scalar_one_or_none()

    def add_knowledge_unit_mastery(self, row: KnowledgeUnitMastery) -> None:
        self.session.add(row)

    async def get_weak_knowledge_units(self, user_id: uuid.UUID, limit: int) -> list[KnowledgeUnitMastery]:
        """The Knowledge-Unit-grained analogue of get_weak_concepts below —
        see ADR-0028 Phase D / GetWeakAreas."""
        result = await self.session.execute(
            select(KnowledgeUnitMastery)
            .where(KnowledgeUnitMastery.user_id == user_id, KnowledgeUnitMastery.mastery_level == "PRACTICING")
            .order_by(KnowledgeUnitMastery.mastery_score)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_micro_competency_mastery(
        self, user_id: uuid.UUID, micro_competency_id: uuid.UUID
    ) -> MicroCompetencyMastery | None:
        result = await self.session.execute(
            select(MicroCompetencyMastery).where(
                MicroCompetencyMastery.user_id == user_id,
                MicroCompetencyMastery.micro_competency_id == micro_competency_id,
            )
        )
        return result.scalar_one_or_none()

    def add_micro_competency_mastery(self, row: MicroCompetencyMastery) -> None:
        self.session.add(row)

    async def get_micro_competencies_for_concept(self, concept_id: uuid.UUID) -> list[MicroCompetency]:
        result = await self.session.execute(
            select(MicroCompetency).where(MicroCompetency.concept_id == concept_id).order_by(MicroCompetency.display_order)
        )
        return list(result.scalars().all())

    async def get_micro_competency_mastery_for_concept(
        self, user_id: uuid.UUID, concept_id: uuid.UUID
    ) -> list[tuple[MicroCompetency, MicroCompetencyMastery | None]]:
        result = await self.session.execute(
            select(MicroCompetency, MicroCompetencyMastery)
            .outerjoin(
                MicroCompetencyMastery,
                (MicroCompetencyMastery.micro_competency_id == MicroCompetency.id)
                & (MicroCompetencyMastery.user_id == user_id),
            )
            .where(MicroCompetency.concept_id == concept_id)
            .order_by(MicroCompetency.display_order)
        )
        return list(result.all())

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

    async def get_due_for_revision(self, user_id: uuid.UUID, now: datetime, limit: int) -> list[tuple[Concept, ConceptMastery]]:
        result = await self.session.execute(
            select(Concept, ConceptMastery)
            .join(ConceptMastery, ConceptMastery.concept_id == Concept.id)
            .where(ConceptMastery.user_id == user_id, ConceptMastery.next_review_at <= now)
            .order_by(ConceptMastery.next_review_at)
            .limit(limit)
        )
        return list(result.all())

    async def get_weak_concepts(self, user_id: uuid.UUID, limit: int) -> list[tuple[Concept, ConceptMastery]]:
        result = await self.session.execute(
            select(Concept, ConceptMastery)
            .join(ConceptMastery, ConceptMastery.concept_id == Concept.id)
            .where(ConceptMastery.user_id == user_id, ConceptMastery.mastery_level == "PRACTICING")
            .order_by(ConceptMastery.mastery_score)
            .limit(limit)
        )
        return list(result.all())

    async def get_new_concepts(self, user_id: uuid.UUID, limit: int) -> list[Concept]:
        attempted = select(ConceptMastery.concept_id).where(ConceptMastery.user_id == user_id)
        result = await self.session.execute(
            select(Concept)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(Concept.id.not_in(attempted))
            .order_by(Subject.display_order, Chapter.display_order, Topic.display_order, Concept.display_order)
            .limit(limit)
        )
        return list(result.scalars().all())
