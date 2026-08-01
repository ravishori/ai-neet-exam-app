from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.prompts import evaluator as evaluator_prompts
from app.modules.ai.services.json_utils import parse_json_response

logger = get_logger("ai")


class EvaluatorService:
    """Real implementation behind app/modules/cms/services/ai_check_service.py's
    run_ai_check() — replaces the Sprint 3 stub in place (ADR-0014)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.gateway = AIGateway(session)

    async def evaluate(self, *, content_type: str, body: dict) -> dict:
        response = await self.gateway.generate(
            agent_type="EVALUATOR",
            system_prompt=evaluator_prompts.SYSTEM_PROMPT,
            user_prompt=evaluator_prompts.build_prompt(content_type=content_type, body=body),
            max_tokens=400,
        )

        if response.is_fallback:
            return {
                "status": "skipped",
                "reason": "AI Gateway is in fallback mode (no ANTHROPIC_API_KEY) — content proceeds to human review unchecked.",
                "flags": [],
                "similarity_matches": [],
                "confidence": None,
                "checked_at": datetime.now(UTC).isoformat(),
            }

        try:
            parsed = parse_json_response(response.text)
        except ValueError as exc:
            logger.error("evaluator_bad_json", error=str(exc), raw=response.text[:200])
            return {
                "status": "error",
                "reason": f"AI response could not be parsed: {exc}",
                "flags": [],
                "similarity_matches": [],
                "confidence": None,
                "checked_at": datetime.now(UTC).isoformat(),
            }

        return {
            "status": "completed",
            "reason": parsed.get("concerns", ""),
            "flags": parsed.get("flags", []),
            "similarity_matches": [],
            "confidence": parsed.get("confidence"),
            "checked_at": datetime.now(UTC).isoformat(),
        }
