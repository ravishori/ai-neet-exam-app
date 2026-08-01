"""AI-assist pass for submitted content — see ADR-0004 / ADR-0014 / ECAEP spec.

Delegates to the real Evaluator agent (app/modules/ai/services/evaluator_service.py).
Kept as its own thin function so ECAEP's import stays stable regardless of how the
AI module's internals evolve — same signature and report shape as the Sprint 3 stub.
"""

from sqlalchemy.ext.asyncio import AsyncSession


async def run_ai_check(session: AsyncSession, *, content_type: str, body: dict) -> dict:
    from app.modules.ai.services.evaluator_service import EvaluatorService

    return await EvaluatorService(session).evaluate(content_type=content_type, body=body)
