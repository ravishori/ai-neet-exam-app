import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.prompts import question_generator as question_prompts
from app.modules.ai.repositories.ai_repository import AIRepository
from app.modules.ai.services.json_utils import parse_json_response
from app.modules.cms.schemas.content_bodies import validate_body
from app.modules.cms.services.content_workflow_service import ContentWorkflowService

logger = get_logger("ai")

_FALLBACK_QUESTION_BODY = {
    "stem": "[Fallback mode — no ANTHROPIC_API_KEY configured] Placeholder question stem.",
    "options": [
        {"label": "A", "text": "Placeholder option A"},
        {"label": "B", "text": "Placeholder option B"},
        {"label": "C", "text": "Placeholder option C"},
        {"label": "D", "text": "Placeholder option D"},
    ],
    "correct_option": "A",
    "explanation": "This is a fallback placeholder — set ANTHROPIC_API_KEY for a real generated question.",
    "difficulty": "medium",
}


class QuestionGeneratorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AIRepository(session)
        self.gateway = AIGateway(session)
        self.workflow = ContentWorkflowService(session)

    async def generate(self, *, concept_id: uuid.UUID, author_id: uuid.UUID):
        concept = await self.repo.get_concept(concept_id)
        if not concept:
            raise NotFoundError("Concept not found")

        user_prompt = question_prompts.build_prompt(
            concept_name=concept.name, summary=concept.summary, ncert_reference=concept.ncert_reference
        )
        response = await self.gateway.generate(
            agent_type="QUESTION_GENERATOR",
            system_prompt=question_prompts.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            user_id=author_id,
            max_tokens=600,
        )

        if response.is_fallback:
            body = dict(_FALLBACK_QUESTION_BODY)
        else:
            try:
                body = parse_json_response(response.text)
            except ValueError as exc:
                logger.error("question_generator_bad_json", error=str(exc), raw=response.text[:200])
                raise AppError(
                    "AI returned a response that couldn't be parsed as a question — try again.",
                    code="AI_GENERATION_FAILED",
                    status_code=502,
                ) from exc

        validated = validate_body("QUESTION", body)

        # Draft only — same ECAEP pipeline as human-authored content (ADR-0004/0014).
        item = await self.workflow.create_item(
            content_type="QUESTION",
            concept_id=concept_id,
            title=f"AI-drafted question — {concept.name}",
            slug=f"ai-{concept.code}-{uuid.uuid4().hex[:8]}",
            tags=["ai-generated"],
            language="en",
            body=validated,
            author_id=author_id,
        )
        return item, response.is_fallback
