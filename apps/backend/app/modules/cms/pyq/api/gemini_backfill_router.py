"""Admin-only endpoints for the one-time Gemini Stage-2 PYQ backfill.
Starting/running the job requires content.factory.execute (an expensive,
side-effecting AI operation); status is content.factory.view (read-only).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.modules.cms.pyq.pyq_gemini_backfill import (
    BackfillAlreadyRunning,
    get_backfill_status,
    run_backfill,
    start_full_backfill,
)
from app.modules.identity.dependencies import require_permission
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/admin/pyq-gemini-backfill", tags=["pyq-gemini-backfill"])


@router.post("/start", dependencies=[Depends(require_permission("content.factory.execute"))])
async def start_backfill(db: AsyncSession = Depends(get_db)):
    try:
        job_id = await start_full_backfill(db)
    except BackfillAlreadyRunning as exc:
        raise AppError(str(exc), code="BACKFILL_ALREADY_RUNNING", status_code=409) from exc
    return envelope(success=True, data=await get_backfill_status(db, job_id))


@router.post("/{job_id}/run", dependencies=[Depends(require_permission("content.factory.execute"))])
async def run_backfill_endpoint(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        result = await run_backfill(db, job_id)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc
    return envelope(success=True, data=result)


@router.get("/{job_id}/status", dependencies=[Depends(require_permission("content.factory.view"))])
async def backfill_status(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        result = await get_backfill_status(db, job_id)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc
    return envelope(success=True, data=result)
