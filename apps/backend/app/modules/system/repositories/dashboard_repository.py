from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cms.models import ContentItem, ContentReport
from app.modules.identity.models.user import User
from app.modules.ingestion.models import IngestionJob, VisualAsset

PENDING_VISUAL_ASSET_STATUSES = ("AUTO_DETECTED", "NEEDS_MANUAL_BBOX")


class DashboardRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def content_counts_by_status(self) -> dict[str, int]:
        result = await self.session.execute(
            select(ContentItem.status, func.count(ContentItem.id)).group_by(ContentItem.status)
        )
        return {status: count for status, count in result.all()}

    async def ingestion_counts_by_status(self) -> dict[str, int]:
        result = await self.session.execute(
            select(IngestionJob.status, func.count(IngestionJob.id)).group_by(IngestionJob.status)
        )
        return {status: count for status, count in result.all()}

    async def pending_visual_assets_count(self) -> int:
        result = await self.session.execute(
            select(func.count(VisualAsset.id)).where(VisualAsset.review_status.in_(PENDING_VISUAL_ASSET_STATUSES))
        )
        return result.scalar_one()

    async def open_content_reports_count(self) -> int:
        result = await self.session.execute(select(func.count(ContentReport.id)).where(ContentReport.status == "OPEN"))
        return result.scalar_one()

    async def total_users_count(self) -> int:
        result = await self.session.execute(select(func.count(User.id)).where(User.deleted_at.is_(None)))
        return result.scalar_one()
