import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models.user import User
from app.modules.learning.services.mastery_service import MasteryService
from app.modules.learning.services.recommendation_service import RecommendationService
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/learning", tags=["learning"], dependencies=[Depends(get_current_user)])


@router.get("/mastery/concepts/{concept_id}")
async def get_concept_mastery(concept_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await MasteryService(db).get_concept_mastery(user.id, concept_id)
    return envelope(success=True, data=result)


@router.get("/mastery/concepts/{concept_id}/micro-competencies")
async def get_concept_micro_competency_breakdown(
    concept_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await MasteryService(db).get_micro_competency_breakdown(user.id, concept_id)
    return envelope(success=True, data=result)


@router.get("/mastery/topics/{topic_id}")
async def get_topic_mastery(topic_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await MasteryService(db).get_topic_mastery(user.id, topic_id)
    return envelope(success=True, data=result)


@router.get("/mastery/overview")
async def get_mastery_overview(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await MasteryService(db).get_overview(user.id)
    return envelope(success=True, data=result)


@router.get("/revision/due")
async def get_revision_due(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await RecommendationService(db).get_due_for_revision(user.id)
    return envelope(success=True, data=result)


@router.get("/recommendations")
async def get_recommendations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await RecommendationService(db).get_recommendations(user.id)
    return envelope(success=True, data=result)
