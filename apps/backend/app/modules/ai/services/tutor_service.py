import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.prompts import tutor as tutor_prompts
from app.modules.ai.repositories.ai_repository import AIRepository


class TutorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AIRepository(session)
        self.gateway = AIGateway(session)

    async def explain(self, *, concept_id: uuid.UUID, question: str, user_id: uuid.UUID) -> dict:
        concept = await self.repo.get_concept(concept_id)
        if not concept:
            raise NotFoundError("Concept not found")

        notes = await self.repo.get_published_notes(concept_id)
        user_prompt = tutor_prompts.build_prompt(
            concept_name=concept.name,
            summary=concept.summary,
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
        }
