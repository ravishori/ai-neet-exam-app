from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.repositories.analytics_repository import AnalyticsRepository

TREND_DAYS = 14
WEAKEST_CONCEPTS_LIMIT = 10


class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.repo = AnalyticsRepository(session)

    async def get_assessment_analytics(self) -> dict:
        totals = await self.repo.get_attempt_totals()
        trend = await self.repo.get_attempts_trend(TREND_DAYS)
        weakest = await self.repo.get_weakest_concepts(WEAKEST_CONCEPTS_LIMIT)
        return {**totals, "attempts_trend": trend, "weakest_concepts": weakest}

    async def get_ai_usage_analytics(self) -> dict:
        overview = await self.repo.get_ai_usage_overview()
        by_agent = await self.repo.get_ai_usage_by_agent()
        return {**overview, "by_agent": by_agent}
