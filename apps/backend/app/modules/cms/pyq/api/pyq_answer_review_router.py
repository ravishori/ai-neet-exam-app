"""Admin endpoints for individual human review of NEET_PYQ_OFFICIAL
ANSWER_PENDING questions. Every endpoint requires pyq.answer_review.
Never touches cms.content_items or any publication/promotion code path.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.cms.pyq.pyq_answer_review import (
    ReviewQueueFilters,
    get_question_review_detail,
    get_queue_counts,
    list_review_queue,
    save_answer_review,
    skip_question_review,
)
from app.modules.identity.dependencies import require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.modules.system.services.audit_service import AuditService, request_context
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/admin/pyq-answer-review", tags=["pyq-answer-review"])

_PERMISSION = "pyq.answer_review"


@router.get("/counts", dependencies=[Depends(require_permission(_PERMISSION))])
async def queue_counts(db: AsyncSession = Depends(get_db)):
    return envelope(success=True, data=await get_queue_counts(db))


@router.get("", dependencies=[Depends(require_permission(_PERMISSION))])
async def queue_list(
    exam_year: str | None = None,
    subject: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    db: AsyncSession = Depends(get_db),
):
    filters = ReviewQueueFilters(
        exam_year=exam_year, subject=subject, search=search, page=page, page_size=page_size
    )
    return envelope(success=True, data=await list_review_queue(db, filters))


@router.get("/{question_id}", dependencies=[Depends(require_permission(_PERMISSION))])
async def question_detail(question_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return envelope(success=True, data=await get_question_review_detail(db, question_id))


class SaveReviewRequest(BaseModel):
    asserted_option: str = Field(min_length=1, max_length=1)
    evidence_source_type: str
    evidence_locator: str | None = None
    review_note: str | None = None
    expected_state: str
    # Explicit, affirmative confirmation that the reviewer checked this
    # answer against a reference before saving — distinct from merely
    # picking an evidence_source_type value. Required true; the frontend
    # must surface this as a deliberate checkbox/confirm step, not a
    # pre-ticked default (Pydantic's bare `bool` has no implicit default
    # here, so an omitted field is a 422, not a silent False).
    source_consulted_confirmed: bool


@router.post("/{question_id}/review", dependencies=[Depends(verify_csrf)])
async def save_review(
    question_id: uuid.UUID,
    payload: SaveReviewRequest,
    request: Request,
    user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    result = await save_answer_review(
        db,
        question_id=question_id,
        reviewer_user_id=user.id,
        asserted_option=payload.asserted_option,
        evidence_source_type=payload.evidence_source_type,
        evidence_locator=payload.evidence_locator,
        review_note=payload.review_note,
        expected_state=payload.expected_state,
        source_consulted_confirmed=payload.source_consulted_confirmed,
    )
    await AuditService(db).log(
        actor_user_id=user.id,
        action="pyq.answer_review.save",
        entity_type="pyq_question",
        entity_id=question_id,
        metadata={
            "asserted_option": payload.asserted_option,
            "evidence_source_type": payload.evidence_source_type,
            "result_status": result.status,
            "question_state": result.question_state,
        },
        **request_context(request),
    )
    return envelope(
        success=True,
        data={"status": result.status, "question_state": result.question_state, "message": result.message},
    )


@router.post("/{question_id}/skip", dependencies=[Depends(verify_csrf)])
async def skip_review(
    question_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    result = await skip_question_review(db, question_id=question_id, reviewer_user_id=user.id)
    await AuditService(db).log(
        actor_user_id=user.id,
        action="pyq.answer_review.skip",
        entity_type="pyq_question",
        entity_id=question_id,
        metadata={"result_status": result.status},
        **request_context(request),
    )
    return envelope(success=True, data={"status": result.status})
