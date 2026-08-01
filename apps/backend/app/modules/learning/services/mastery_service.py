import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.models import ConceptMastery
from app.modules.learning.repositories.mastery_repository import MasteryRepository

MASTERY_ATTEMPT_FLOOR = 3
MASTERY_SCORE_THRESHOLD = 80


def compute_mastery(attempts_count: int, correct_count: int) -> tuple[int, str]:
    if attempts_count == 0:
        return 0, "NOT_STARTED"

    score = round(100 * correct_count / attempts_count)

    if attempts_count < MASTERY_ATTEMPT_FLOOR:
        return score, "LEARNING"
    if score >= MASTERY_SCORE_THRESHOLD:
        return score, "MASTERED"
    return score, "PRACTICING"


class MasteryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MasteryRepository(session)

    async def recompute_for_content_items(self, user_id: uuid.UUID, content_item_ids: list[uuid.UUID]) -> None:
        concept_ids = await self.repo.concept_ids_for_content_items(content_item_ids)
        for concept_id in concept_ids:
            await self._recompute_one(user_id, concept_id)
        await self.repo.commit()

    async def _recompute_one(self, user_id: uuid.UUID, concept_id: uuid.UUID) -> None:
        attempts_count, correct_count, last_attempt_at = await self.repo.aggregate_answers(user_id, concept_id)
        score, level = compute_mastery(attempts_count, correct_count)

        row = await self.repo.get(user_id, concept_id)
        if row is None:
            row = ConceptMastery(user_id=user_id, concept_id=concept_id)
            self.repo.add(row)

        row.attempts_count = attempts_count
        row.correct_count = correct_count
        row.mastery_score = score
        row.mastery_level = level
        row.last_attempt_at = last_attempt_at

    async def get_concept_mastery(self, user_id: uuid.UUID, concept_id: uuid.UUID) -> dict:
        row = await self.repo.get(user_id, concept_id)
        return _row_to_dict(concept_id, row)

    async def get_topic_mastery(self, user_id: uuid.UUID, topic_id: uuid.UUID) -> dict:
        pairs = await self.repo.get_for_topic(user_id, topic_id)
        concepts = [
            {"concept_id": str(concept.id), "concept_name": concept.name, **_row_to_dict(concept.id, row)}
            for concept, row in pairs
        ]
        attempted = [c for c in concepts if c["attempts_count"] > 0]
        average_score = round(sum(c["mastery_score"] for c in attempted) / len(attempted), 1) if attempted else 0.0
        return {"topic_id": str(topic_id), "average_score": average_score, "concepts": concepts}

    async def get_overview(self, user_id: uuid.UUID) -> list[dict]:
        return await self.repo.get_overview(user_id)


def _row_to_dict(concept_id: uuid.UUID, row: ConceptMastery | None) -> dict:
    if row is None:
        return {
            "concept_id": str(concept_id),
            "attempts_count": 0,
            "correct_count": 0,
            "mastery_score": 0,
            "mastery_level": "NOT_STARTED",
            "last_attempt_at": None,
        }
    return {
        "concept_id": str(concept_id),
        "attempts_count": row.attempts_count,
        "correct_count": row.correct_count,
        "mastery_score": row.mastery_score,
        "mastery_level": row.mastery_level,
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
    }
