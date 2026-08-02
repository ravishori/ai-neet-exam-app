import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import KnowledgeUnit

# Same threshold and rationale as the existing question-stem dedup in
# ingestion_repository.py — two genuinely different pieces of knowledge on
# the same concept rarely exceed ~0.4 summary similarity.
DEDUP_SIMILARITY_THRESHOLD = 0.6


class KnowledgeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, unit: KnowledgeUnit) -> None:
        self.session.add(unit)

    async def get(self, unit_id: uuid.UUID) -> KnowledgeUnit | None:
        result = await self.session.execute(select(KnowledgeUnit).where(KnowledgeUnit.id == unit_id))
        return result.scalar_one_or_none()

    async def list_for_concept(self, concept_id: uuid.UUID) -> list[KnowledgeUnit]:
        result = await self.session.execute(
            select(KnowledgeUnit).where(KnowledgeUnit.concept_id == concept_id).order_by(KnowledgeUnit.created_at)
        )
        return list(result.scalars().all())

    async def find_duplicate(self, concept_id: uuid.UUID, summary: str) -> KnowledgeUnit | None:
        """True duplicate check via Postgres trigram similarity, scoped to
        PASSED units on the same concept only — a FAILED unit's summary
        shouldn't block a later, better extraction from being accepted."""
        result = await self.session.execute(
            text(
                """
                SELECT id
                FROM knowledge.knowledge_units
                WHERE concept_id = :concept_id
                  AND validation_status = 'PASSED'
                  AND similarity(:summary, summary) > :threshold
                ORDER BY similarity(:summary, summary) DESC
                LIMIT 1
                """
            ),
            {"concept_id": str(concept_id), "summary": summary, "threshold": DEDUP_SIMILARITY_THRESHOLD},
        )
        row = result.first()
        if not row:
            return None
        return await self.get(row.id)

    async def commit(self) -> None:
        await self.session.commit()

    async def flush(self) -> None:
        await self.session.flush()
