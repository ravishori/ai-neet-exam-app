from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.analytics.services.analytics_service import AnalyticsService
from app.modules.identity.dependencies import get_current_user, require_permission
from app.shared.responses import envelope

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics"],
    dependencies=[Depends(get_current_user), Depends(require_permission("analytics.view"))],
)


@router.get("/assessments")
async def get_assessment_analytics(db: AsyncSession = Depends(get_db)):
    result = await AnalyticsService(db).get_assessment_analytics()
    return envelope(success=True, data=result)


@router.get("/ai-usage")
async def get_ai_usage_analytics(db: AsyncSession = Depends(get_db)):
    result = await AnalyticsService(db).get_ai_usage_analytics()
    return envelope(success=True, data=result)
