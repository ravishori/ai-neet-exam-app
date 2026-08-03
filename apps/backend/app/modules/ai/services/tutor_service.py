import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.prompts import tutor as tutor_prompts
from app.modules.knowledge.services.knowledge_service import KnowledgeService


class TutorService:
    """See ADR-0028 Phase B: the AI Tutor no longer queries Concept/CMS
    directly (no repository, no SQL, in this class) — everything it reads
    comes from KnowledgeService, which is the one place that logic lives."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.knowledge = KnowledgeService(session)
        self.gateway = AIGateway(session)

    async def explain(self, *, concept_id: uuid.UUID, question: str, user_id: uuid.UUID) -> dict:
        context = await self.knowledge.get_knowledge_context(concept_id)
        concept = context["concept"]
        if not concept:
            raise NotFoundError("Concept not found")

        # Grounded explanation now prefers verified Knowledge Units (ADR-0024
        # gate-checked facts) over the concept's own free-text summary,
        # falling back to it automatically when no Knowledge Units exist yet
        # — see KnowledgeService.get_teaching_explanation.
        explanation = await self.knowledge.get_teaching_explanation(concept_id)
        notes = await self.knowledge.get_revision_material(concept_id)
        user_prompt = tutor_prompts.build_prompt(
            concept_name=concept.name,
            summary=explanation or concept.summary,
            ncert_reference=concept.ncert_reference,
            published_notes=notes,
            question=question,
        )
        response = await self.gateway.generate(
            agent_type="TUTOR",
            system_prompt=tutor_prompts.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            user_id=user_id,
            max_tokens=4096,
        )
        return {
            "answer": response.text,
            "concept_name": concept.name,
            "ncert_reference": concept.ncert_reference,
            "is_fallback": response.is_fallback,
            "cited_published_notes": len(notes),
            # Additive, per ADR-0028 — existing keys above are unchanged so
            # no existing caller (the tutor router, the frontend) breaks.
            "knowledge_units_cited": len(context["knowledge_units"]),
            "visual_assets_available": len(context["visual_assets"]),
        }
