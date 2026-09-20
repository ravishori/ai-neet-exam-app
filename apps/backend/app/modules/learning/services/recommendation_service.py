import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Concept
from app.modules.learning.models import ConceptMastery
from app.modules.learning.repositories.mastery_repository import MasteryRepository

DEFAULT_REVISION_LIMIT = 10
DEFAULT_RECOMMENDATION_LIMIT = 5


class RecommendationService:
    def __init__(self, session: AsyncSession):
        self.repo = MasteryRepository(session)

    async def get_due_for_revision(self, user_id: uuid.UUID, limit: int = DEFAULT_REVISION_LIMIT) -> list[dict]:
        pairs = await self.repo.get_due_for_revision(user_id, datetime.now(UTC), limit)
        counts = await self.repo.published_question_counts([concept.id for concept, _ in pairs])
        return [_revision_item(concept, row, counts.get(concept.id, 0)) for concept, row in pairs]

    async def get_recommendations(self, user_id: uuid.UUID, limit: int = DEFAULT_RECOMMENDATION_LIMIT) -> list[dict]:
        """Rule-based ranking (due → weak → new). Concepts without PUBLISHED
        questions are excluded so Practice Now cannot dead-end (WAVE-P0-5)."""
        items: list[dict] = []
        seen: set[uuid.UUID] = set()

        due = await self.repo.get_due_for_revision(user_id, datetime.now(UTC), limit)
        for concept, row in due:
            if concept.id in seen:
                continue
            seen.add(concept.id)
            items.append(_recommendation_item(concept, "due_for_revision", row.mastery_score))

        if len(items) < limit:
            weak = await self.repo.get_weak_concepts(user_id, limit - len(items))
            for concept, row in weak:
                if concept.id in seen:
                    continue
                seen.add(concept.id)
                items.append(_recommendation_item(concept, "weak_concept", row.mastery_score))

        if len(items) < limit:
            new = await self.repo.get_new_concepts(user_id, limit - len(items))
            for concept in new:
                if concept.id in seen:
                    continue
                seen.add(concept.id)
                items.append(_recommendation_item(concept, "new_concept", None))

        items = items[:limit]
        counts = await self.repo.published_question_counts([uuid.UUID(i["concept_id"]) for i in items])
        for item in items:
            item["published_question_count"] = counts.get(uuid.UUID(item["concept_id"]), 0)
        return items


def _revision_item(concept: Concept, row: ConceptMastery, published_question_count: int) -> dict:
    return {
        "concept_id": str(concept.id),
        "concept_name": concept.name,
        "mastery_level": row.mastery_level,
        "mastery_score": row.mastery_score,
        "next_review_at": row.next_review_at.isoformat() if row.next_review_at else None,
        "published_question_count": published_question_count,
    }


def _recommendation_item(concept: Concept, reason: str, mastery_score: int | None) -> dict:
    return {
        "concept_id": str(concept.id),
        "concept_name": concept.name,
        "reason": reason,
        "mastery_score": mastery_score,
    }
