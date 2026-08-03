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

    async def explain_question(self, *, question_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """PR 8 — a focused walkthrough of one specific question, not the
        full concept-teaching template explain() above uses. Deliberately
        only reachable for PUBLISHED questions with the answer already
        revealed to the caller elsewhere (the results/review screen after a
        submitted attempt) — this never introduces a new way to see an
        answer without practicing first; it explains an answer the student
        can already see."""
        from app.modules.cms.repositories.cms_repository import CmsRepository

        cms_repo = CmsRepository(self.session)
        item = await cms_repo.get_item(question_id)
        if not item or item.content_type != "QUESTION" or item.status != "PUBLISHED":
            raise NotFoundError("Question not found")
        if not item.concept_id:
            raise NotFoundError("This question has no linked concept to explain against")

        by_id = {v.id: v for v in item.versions}
        version = by_id.get(item.current_version_id)
        body = version.body if version else {}

        context = await self.knowledge.get_knowledge_context(item.concept_id)
        concept = context["concept"]
        if not concept:
            raise NotFoundError("Concept not found")
        grounded_explanation = await self.knowledge.get_teaching_explanation(item.concept_id)

        user_prompt = tutor_prompts.build_question_prompt(
            concept_name=concept.name,
            summary=grounded_explanation or concept.summary,
            ncert_reference=concept.ncert_reference,
            stem=body.get("stem", ""),
            options=body.get("options", []),
            correct_option=body.get("correct_option", ""),
            explanation=body.get("explanation"),
        )
        response = await self.gateway.generate(
            agent_type="TUTOR",
            system_prompt=tutor_prompts.QUESTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            user_id=user_id,
            max_tokens=2048,
        )
        return {
            "answer": response.text,
            "concept_name": concept.name,
            "ncert_reference": concept.ncert_reference,
            "is_fallback": response.is_fallback,
        }
