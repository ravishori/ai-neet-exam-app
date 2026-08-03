import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.rate_limit import rate_limit_per_user
from app.modules.ai.models import StudyPlan
from app.modules.ai.repositories.ai_repository import AIRepository
from app.modules.ai.schemas.ai import ExplainQuestionRequest, GenerateQuestionRequest, StudyPlanRequest, TutorExplainRequest
from app.modules.ai.services.question_generator_service import QuestionGeneratorService
from app.modules.ai.services.study_planner_service import StudyPlannerService
from app.modules.ai.services.tutor_service import TutorService
from app.modules.cms.models import ContentItem
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/ai", tags=["ai"], dependencies=[Depends(get_current_user)])


def _content_item(item: ContentItem) -> dict:
    return {
        "id": str(item.id),
        "content_type": item.content_type,
        "concept_id": str(item.concept_id) if item.concept_id else None,
        "title": item.title,
        "slug": item.slug,
        "status": item.status,
    }


def _study_plan(p: StudyPlan) -> dict:
    return {
        "id": str(p.id),
        "target_score": p.target_score,
        "current_score": p.current_score,
        "exam_date": p.exam_date.isoformat(),
        "hours_per_day": p.hours_per_day,
        "plan": p.plan,
        "created_at": p.created_at,
    }


@router.post(
    "/tutor/explain",
    dependencies=[
        Depends(require_permission("ai.use")),
        Depends(verify_csrf),
        Depends(rate_limit_per_user("ai.tutor", limit=20, window_seconds=300)),
    ],
)
async def tutor_explain(payload: TutorExplainRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = TutorService(db)
    result = await service.explain(concept_id=uuid.UUID(payload.concept_id), question=payload.question, user_id=user.id)
    return envelope(success=True, data=result)


@router.post(
    "/tutor/explain-question",
    dependencies=[
        Depends(require_permission("ai.use")),
        Depends(verify_csrf),
        Depends(rate_limit_per_user("ai.tutor", limit=20, window_seconds=300)),
    ],
)
async def tutor_explain_question(
    payload: ExplainQuestionRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    service = TutorService(db)
    result = await service.explain_question(question_id=uuid.UUID(payload.question_id), user_id=user.id)
    return envelope(success=True, data=result)


@router.post(
    "/questions/generate",
    dependencies=[
        Depends(require_permission("content.create")),
        Depends(verify_csrf),
        Depends(rate_limit_per_user("ai.question_generator", limit=10, window_seconds=600)),
    ],
)
async def generate_question(payload: GenerateQuestionRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = QuestionGeneratorService(db)
    item, is_fallback = await service.generate(concept_id=uuid.UUID(payload.concept_id), author_id=user.id)
    return envelope(success=True, data={**_content_item(item), "is_fallback": is_fallback}, status_code=201)


@router.post(
    "/study-plan",
    dependencies=[
        Depends(require_permission("ai.use")),
        Depends(verify_csrf),
        Depends(rate_limit_per_user("ai.study_planner", limit=5, window_seconds=3600)),
    ],
)
async def generate_study_plan(payload: StudyPlanRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = StudyPlannerService(db)
    plan = await service.generate(
        user_id=user.id,
        target_score=payload.target_score,
        current_score=payload.current_score,
        exam_date=payload.exam_date,
        hours_per_day=payload.hours_per_day,
    )
    return envelope(success=True, data=_study_plan(plan), status_code=201)


@router.get("/study-plan", dependencies=[Depends(require_permission("ai.use"))])
async def get_study_plan(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = AIRepository(db)
    plan = await repo.get_latest_study_plan(user.id)
    if not plan:
        raise NotFoundError("No study plan yet")
    return envelope(success=True, data=_study_plan(plan))
