import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.models import VisualAsset
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

    async def list_passed_for_concept(self, concept_id: uuid.UUID) -> list[KnowledgeUnit]:
        """Same as list_for_concept, scoped to PASSED units only — see
        ADR-0028 Phase B (KnowledgeService). A FAILED unit's facts didn't
        clear the grounding/dedup gates and shouldn't reach the AI Tutor or
        any other consumer as if they were verified."""
        result = await self.session.execute(
            select(KnowledgeUnit)
            .where(KnowledgeUnit.concept_id == concept_id, KnowledgeUnit.validation_status == "PASSED")
            .order_by(KnowledgeUnit.created_at)
        )
        return list(result.scalars().all())

    async def get_visual_assets_for_knowledge_unit(self, knowledge_unit_id: uuid.UUID) -> list[VisualAsset]:
        result = await self.session.execute(
            select(VisualAsset).where(VisualAsset.knowledge_unit_id == knowledge_unit_id)
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

    async def get_visual_assets_for_page(self, job_id: uuid.UUID, source_page: int) -> list[VisualAsset]:
        """Visual assets detected (ADR-0026) on the same job/page as a
        section being structured — see ADR-0028 Phase C. Only assets with
        no Knowledge Unit yet are returned, so re-running structuring for a
        section never overwrites an existing, already-cited association."""
        result = await self.session.execute(
            select(VisualAsset).where(
                VisualAsset.job_id == job_id,
                VisualAsset.source_page == source_page,
                VisualAsset.knowledge_unit_id.is_(None),
            )
        )
        return list(result.scalars().all())

    async def commit(self) -> None:
        await self.session.commit()

    async def flush(self) -> None:
        await self.session.flush()
