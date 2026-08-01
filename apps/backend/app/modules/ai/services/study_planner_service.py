import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.models import StudyPlan
from app.modules.ai.prompts import study_planner as planner_prompts
from app.modules.ai.repositories.ai_repository import AIRepository
from app.modules.ai.services.json_utils import parse_json_response

logger = get_logger("ai")

_FALLBACK_PLAN = {
    "summary": "[Fallback mode — no ANTHROPIC_API_KEY configured] Set a real key for a personalized plan.",
    "weekly_focus": ["Revisit weak concepts", "Attempt one mock test", "Review NCERT chapters"],
    "daily_schedule": [{"day": 1, "focus": "Placeholder — configure ANTHROPIC_API_KEY", "duration_minutes": 60}],
}


class StudyPlannerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AIRepository(session)
        self.gateway = AIGateway(session)

    async def generate(
        self, *, user_id: uuid.UUID, target_score: int, current_score: int, exam_date: date, hours_per_day: int
    ) -> StudyPlan:
        days_remaining = max(1, (exam_date - date.today()).days)
        weak_concepts = await self.repo.get_weak_concept_names(user_id)

        user_prompt = planner_prompts.build_prompt(
            target_score=target_score,
            current_score=current_score,
            days_remaining=days_remaining,
            hours_per_day=hours_per_day,
            weak_concepts=weak_concepts,
        )
        response = await self.gateway.generate(
            agent_type="STUDY_PLANNER",
            system_prompt=planner_prompts.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            user_id=user_id,
            max_tokens=1200,
        )

        if response.is_fallback:
            plan_data = dict(_FALLBACK_PLAN)
        else:
            try:
                plan_data = parse_json_response(response.text)
            except ValueError as exc:
                logger.error("study_planner_bad_json", error=str(exc), raw=response.text[:200])
                raise AppError(
                    "AI returned a response that couldn't be parsed as a plan — try again.",
                    code="AI_GENERATION_FAILED",
                    status_code=502,
                ) from exc

        plan = StudyPlan(
            user_id=user_id,
            target_score=target_score,
            current_score=current_score,
            exam_date=exam_date,
            hours_per_day=hours_per_day,
            plan=plan_data,
        )
        self.repo.add_study_plan(plan)
        await self.repo.commit()
        return plan
