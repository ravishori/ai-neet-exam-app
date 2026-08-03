from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.services.analytics_service import AnalyticsService
from app.modules.system.repositories.dashboard_repository import DashboardRepository


class DashboardService:
    """Admin Portal (PR11) Module 1 — a single aggregation call for the admin
    landing page's KPI tiles, so it doesn't fan out into 6+ requests."""

    def __init__(self, session: AsyncSession):
        self.repo = DashboardRepository(session)
        self.analytics = AnalyticsService(session)

    async def get_overview(self) -> dict:
        content_by_status = await self.repo.content_counts_by_status()
        ingestion_by_status = await self.repo.ingestion_counts_by_status()
        pending_visual_assets = await self.repo.pending_visual_assets_count()
        open_reports = await self.repo.open_content_reports_count()
        total_users = await self.repo.total_users_count()
        ai_usage = await self.analytics.get_ai_usage_analytics()

        return {
            "content_by_status": content_by_status,
            "ingestion_by_status": ingestion_by_status,
            "pending_visual_assets": pending_visual_assets,
            "open_content_reports": open_reports,
            "total_users": total_users,
            "ai_total_requests": ai_usage["total_requests"],
            "ai_total_cost_usd": ai_usage["total_cost_usd"],
        }
