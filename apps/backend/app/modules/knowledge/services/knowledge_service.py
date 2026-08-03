import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Concept
from app.modules.ai.repositories.ai_repository import AIRepository
from app.modules.ingestion.models import VisualAsset
from app.modules.knowledge.models import KnowledgeUnit
from app.modules.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.modules.learning.services.mastery_service import MasteryService


class KnowledgeService:
    """The single entry point consumers (AI Tutor, and future consumers)
    use to read educational content — see ADR-0028 Phase B. Composes the
    existing repositories (KnowledgeRepository for KnowledgeUnit/VisualAsset,
    AIRepository for Concept/published-content lookups, MasteryService for
    weak-area analysis) rather than duplicating their queries — no new
    "eku_repository" is introduced, per ADR-0028's explicit naming rule.

    Every method here reads only PASSED Knowledge Units — a FAILED unit's
    facts never reached a real consumer before this service existed, and
    that stays true through it.
    """

    def __init__(self, session: AsyncSession):
        self.repo = KnowledgeRepository(session)
        self.ai_repo = AIRepository(session)
        self.mastery = MasteryService(session)

    async def get_knowledge_unit(self, knowledge_unit_id: uuid.UUID) -> KnowledgeUnit | None:
        return await self.repo.get(knowledge_unit_id)

    async def get_knowledge_context(self, concept_id: uuid.UUID) -> dict:
        """The combined context a consumer needs to teach or answer
        questions about a concept: the concept itself, its verified
        Knowledge Units, and any visual assets those units cite."""
        concept = await self.ai_repo.get_concept(concept_id)
        units = await self.repo.list_passed_for_concept(concept_id)
        visual_assets: list[VisualAsset] = []
        for unit in units:
            visual_assets.extend(await self.repo.get_visual_assets_for_knowledge_unit(unit.id))
        return {"concept": concept, "knowledge_units": units, "visual_assets": visual_assets}

    async def get_teaching_explanation(self, concept_id: uuid.UUID) -> str:
        """The grounded, citable explanation text for a concept — every
        PASSED Knowledge Unit's summary, joined. Falls back to the
        concept's own `summary` field when no Knowledge Units exist yet
        (a concept that predates ingestion, or hasn't been processed by it),
        the same "fall back rather than show nothing" philosophy ADR-0019
        already established for missing translations."""
        units = await self.repo.list_passed_for_concept(concept_id)
        if units:
            return " ".join(unit.summary for unit in units if unit.summary)
        concept = await self.ai_repo.get_concept(concept_id)
        return concept.summary if concept and concept.summary else ""

    async def get_visual_assets(self, knowledge_unit_id: uuid.UUID) -> list[VisualAsset]:
        return await self.repo.get_visual_assets_for_knowledge_unit(knowledge_unit_id)

    async def get_revision_material(self, concept_id: uuid.UUID) -> list[str]:
        """Published CONCEPT_NOTE summaries for a concept — reuses
        AIRepository's existing, already-tested query rather than
        duplicating it. Real data (published notes), not every generated
        Flashcard/MCQ body — this project doesn't have a single "revision
        material" content type to draw from beyond notes today."""
        return await self.ai_repo.get_published_notes(concept_id)

    async def get_weak_areas(self, user_id: uuid.UUID, limit: int = 10) -> list[dict]:
        """Knowledge-Unit-grained weak-area analysis — see ADR-0028 Phase D.
        Returns [] for a user with no knowledge_unit_mastery rows yet
        (nothing answered from ingestion-generated content), not an error."""
        return await self.mastery.get_weak_knowledge_units(user_id, limit)

    # Deliberately not implemented: GetExamples, GetLearningHistory. Neither
    # has a real data source in this codebase today (no worked-examples
    # entity; no per-attempt history view beyond what MasteryService already
    # aggregates) — building either now would mean fabricating a return
    # shape with nothing real behind it. Add them when a real consumer and
    # a real data source both exist, the same discipline ADR-0027 applied
    # to its TranslationService stub.
