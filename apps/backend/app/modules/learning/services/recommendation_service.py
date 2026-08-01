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
        return [_revision_item(concept, row) for concept, row in pairs]

    async def get_recommendations(self, user_id: uuid.UUID, limit: int = DEFAULT_RECOMMENDATION_LIMIT) -> list[dict]:
        items: list[dict] = []

        due = await self.repo.get_due_for_revision(user_id, datetime.now(UTC), limit)
        items.extend(_recommendation_item(concept, "due_for_revision", row.mastery_score) for concept, row in due)

        if len(items) < limit:
            weak = await self.repo.get_weak_concepts(user_id, limit - len(items))
            items.extend(_recommendation_item(concept, "weak_concept", row.mastery_score) for concept, row in weak)

        if len(items) < limit:
            new = await self.repo.get_new_concepts(user_id, limit - len(items))
            items.extend(_recommendation_item(concept, "new_concept", None) for concept in new)

        return items[:limit]


def _revision_item(concept: Concept, row: ConceptMastery) -> dict:
    return {
        "concept_id": str(concept.id),
        "concept_name": concept.name,
        "mastery_level": row.mastery_level,
        "mastery_score": row.mastery_score,
        "next_review_at": row.next_review_at.isoformat() if row.next_review_at else None,
    }


def _recommendation_item(concept: Concept, reason: str, mastery_score: int | None) -> dict:
    return {
        "concept_id": str(concept.id),
        "concept_name": concept.name,
        "reason": reason,
        "mastery_score": mastery_score,
    }
