"""P2.3 Human Gold Review Sandbox API — isolated from production MCQs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.cms.schemas.human_gold_sandbox import HumanGoldReviewSaveRequest, ImportConfirmRequest
from app.modules.cms.services.human_gold_sandbox_service import (
    HumanGoldSandboxService,
    resolve_human_gold_repo_root,
)
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.modules.system.services.audit_service import request_context
from app.shared.responses import envelope

router = APIRouter(tags=["cms-human-gold-sandbox"])

REPO_ROOT = resolve_human_gold_repo_root(__file__)


def _svc(db: AsyncSession) -> HumanGoldSandboxService:
    return HumanGoldSandboxService(db, repo_root=REPO_ROOT)


@router.post("/human-gold-sandbox/upload", dependencies=[Depends(require_permission("content.review")), Depends(verify_csrf)])
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    result = await _svc(db).validate_csv_upload(
        filename=file.filename or "upload.csv",
        content_type=file.content_type,
        data=data,
        actor_id=user.id,
    )
    await db.commit()
    return envelope(success=True, data=result, meta=request_context(request))


@router.post("/human-gold-sandbox/import", dependencies=[Depends(require_permission("content.review")), Depends(verify_csrf)])
async def import_csv(
    payload: ImportConfirmRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db).import_upload(
        upload_id=uuid.UUID(payload.upload_id),
        session_name=payload.session_name,
        actor_id=user.id,
    )
    return envelope(success=True, data=result, meta=request_context(request))


@router.get("/human-gold-sandbox/sessions/{session_id}/dashboard", dependencies=[Depends(require_permission("content.review"))])
async def session_dashboard(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await _svc(db).dashboard(session_id, actor_id=user.id)
    return envelope(success=True, data=data)


@router.get("/human-gold-sandbox/sessions/{session_id}/queue", dependencies=[Depends(require_permission("content.review"))])
async def session_queue(
    session_id: uuid.UUID,
    filter: str = Query("all", alias="filter"),
    limit: int = Query(100, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await _svc(db).queue(session_id, actor_id=user.id, filter_key=filter, limit=limit, offset=offset)
    return envelope(success=True, data={"items": data})


@router.get(
    "/human-gold-sandbox/sessions/{session_id}/questions/{question_id}",
    dependencies=[Depends(require_permission("content.review"))],
)
async def get_question(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await _svc(db).get_question(session_id, question_id, actor_id=user.id)
    return envelope(success=True, data=data)


@router.patch(
    "/human-gold-sandbox/sessions/{session_id}/questions/{question_id}/human-review",
    dependencies=[Depends(require_permission("content.review")), Depends(verify_csrf)],
)
async def save_human_review(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: HumanGoldReviewSaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await _svc(db).save_human_review(
        session_id,
        question_id,
        payload.model_dump(by_alias=True, exclude_none=True),
        actor_id=user.id,
    )
    return envelope(success=True, data=data)


@router.post(
    "/human-gold-sandbox/sessions/{session_id}/ai-check",
    dependencies=[Depends(require_permission("content.review")), Depends(verify_csrf)],
)
async def run_ai_check(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    question_id: uuid.UUID | None = Query(None),
    batch: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await _svc(db).run_ai_check(session_id, question_id, actor_id=user.id, batch=batch)
    return envelope(success=True, data=data)


@router.post(
    "/human-gold-sandbox/sessions/{session_id}/export",
    dependencies=[Depends(require_permission("content.review")), Depends(verify_csrf)],
)
async def export_session(
    session_id: uuid.UUID,
    fmt: str = Query("csv"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await _svc(db).export_session(session_id, actor_id=user.id, fmt=fmt)
    return envelope(success=True, data=data)


@router.post(
    "/human-gold-sandbox/sessions/{session_id}/run-gate",
    dependencies=[Depends(require_permission("content.review")), Depends(verify_csrf)],
)
async def run_gate(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await _svc(db).run_gate(session_id, actor_id=user.id)
    return envelope(success=True, data=data)


@router.delete(
    "/human-gold-sandbox/sessions/{session_id}",
    dependencies=[Depends(require_permission("content.review")), Depends(verify_csrf)],
)
async def delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db).delete_session(session_id, actor_id=user.id)
    return envelope(success=True, data={"status": "SESSION DELETED"})
