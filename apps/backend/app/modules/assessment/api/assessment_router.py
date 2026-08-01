import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.modules.assessment.models import Assessment, Attempt
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.assessment.schemas.assessment import AnswerRequest, GenerateRequest
from app.modules.assessment.services.assessment_service import AssessmentService, get_content_body
from app.modules.identity.dependencies import get_current_user, verify_csrf
from app.modules.identity.models.user import User
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1", tags=["assessment"], dependencies=[Depends(get_current_user)])


def _assessment(a: Assessment) -> dict:
    return {
        "id": str(a.id),
        "assessment_type": a.assessment_type,
        "scope_type": a.scope_type,
        "scope_id": str(a.scope_id) if a.scope_id else None,
        "title": a.title,
        "duration_minutes": a.duration_minutes,
        "marks_per_question": float(a.marks_per_question),
        "negative_marks_per_question": float(a.negative_marks_per_question),
        "question_count": a.question_count,
    }


def _attempt_summary(a: Attempt) -> dict:
    return {
        "id": str(a.id),
        "assessment_id": str(a.assessment_id),
        "status": a.status,
        "started_at": a.started_at,
        "submitted_at": a.submitted_at,
        "score": float(a.score) if a.score is not None else None,
        "correct_count": a.correct_count,
        "incorrect_count": a.incorrect_count,
        "skipped_count": a.skipped_count,
    }


def _public_question(item, selected_option: str | None) -> dict:
    """In-progress view — never leaks correct_option/explanation."""
    body = get_content_body(item)
    return {
        "content_item_id": str(item.id),
        "stem": body.get("stem"),
        "options": body.get("options", []),
        "difficulty": body.get("difficulty"),
        "selected_option": selected_option,
    }


def _result_question(item, answer) -> dict:
    body = get_content_body(item)
    return {
        "content_item_id": str(item.id),
        "stem": body.get("stem"),
        "options": body.get("options", []),
        "correct_option": body.get("correct_option"),
        "explanation": body.get("explanation"),
        "selected_option": answer.selected_option if answer else None,
        "is_correct": answer.is_correct if answer else None,
    }


@router.post("/assessments/practice", dependencies=[Depends(verify_csrf)])
async def generate_practice(payload: GenerateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = AssessmentService(db)
    scope_id = uuid.UUID(payload.scope_id) if payload.scope_id else None
    assessment = await service.generate_practice(
        scope_type=payload.scope_type, scope_id=scope_id, question_count=payload.question_count, user_id=user.id
    )
    return envelope(success=True, data=_assessment(assessment), status_code=201)


@router.post("/assessments/mock", dependencies=[Depends(verify_csrf)])
async def generate_mock(payload: GenerateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = AssessmentService(db)
    scope_id = uuid.UUID(payload.scope_id) if payload.scope_id else None
    assessment = await service.generate_mock(
        scope_type=payload.scope_type, scope_id=scope_id, question_count=payload.question_count, user_id=user.id
    )
    return envelope(success=True, data=_assessment(assessment), status_code=201)


@router.post("/assessments/{assessment_id}/attempts", dependencies=[Depends(verify_csrf)])
async def start_attempt(assessment_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = AssessmentService(db)
    attempt = await service.start_attempt(assessment_id, user.id)
    return envelope(success=True, data=_attempt_summary(attempt), status_code=201)


@router.get("/attempts")
async def list_attempts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = AssessmentRepository(db)
    attempts = await repo.list_attempts_for_user(user.id)
    return envelope(success=True, data=[_attempt_summary(a) for a in attempts])


@router.get("/attempts/{attempt_id}")
async def get_attempt(attempt_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = AssessmentRepository(db)
    attempt = await repo.get_attempt(attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise NotFoundError("Attempt not found")

    assessment = await repo.get_assessment(attempt.assessment_id)
    question_ids = [q.content_item_id for q in assessment.questions]
    items_by_id = {i.id: i for i in await repo.get_content_items(question_ids)}
    answers_by_question = {a.content_item_id: a for a in attempt.answers}

    if attempt.status == "IN_PROGRESS":
        questions = [
            _public_question(items_by_id[qid], answers_by_question.get(qid).selected_option if answers_by_question.get(qid) else None)
            for qid in question_ids
        ]
    else:
        questions = [_result_question(items_by_id[qid], answers_by_question.get(qid)) for qid in question_ids]

    return envelope(
        success=True,
        data={**_attempt_summary(attempt), "assessment": _assessment(assessment), "questions": questions},
    )


@router.post("/attempts/{attempt_id}/answers", dependencies=[Depends(verify_csrf)])
async def save_answer(
    attempt_id: uuid.UUID, payload: AnswerRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    service = AssessmentService(db)
    await service.save_answer(
        attempt_id, user.id, content_item_id=uuid.UUID(payload.content_item_id), selected_option=payload.selected_option
    )
    return envelope(success=True, data={"saved": True})


@router.post("/attempts/{attempt_id}/submit", dependencies=[Depends(verify_csrf)])
async def submit_attempt(attempt_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = AssessmentService(db)
    attempt = await service.submit_attempt(attempt_id, user.id)
    return envelope(success=True, data=_attempt_summary(attempt))
