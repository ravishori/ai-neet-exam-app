"""Content Factory orchestration APIs (FACTORY-P1). No generation / publish."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.cms.models.content_factory import ContentBatch, GenerationJob, GenerationRun
from app.modules.cms.repositories.content_factory_repository import ContentFactoryRepository
from app.modules.cms.schemas.content_factory import (
    BatchStatusTransitionRequest,
    ContentBatchCreateRequest,
    GenerationJobCreateRequest,
    GenerationRunCompleteRequest,
    GenerationRunCreateRequest,
    JobStatusTransitionRequest,
)
from app.modules.cms.services.content_factory_service import ContentFactoryService
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.modules.system.services.audit_service import request_context
from app.shared.responses import envelope

router = APIRouter(tags=["cms-factory"])


def _run(run: GenerationRun) -> dict:
    return {
        "id": str(run.id),
        "job_id": str(run.job_id),
        "attempt_number": run.attempt_number,
        "status": run.status,
        "processed_count": run.processed_count,
        "success_count": run.success_count,
        "failure_count": run.failure_count,
        "error_summary": run.error_summary,
        "execution_metadata": run.execution_metadata,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _job(job: GenerationJob, *, include_runs: bool = True) -> dict:
    data = {
        "id": str(job.id),
        "batch_id": str(job.batch_id),
        "job_key": job.job_key,
        "job_type": job.job_type,
        "status": job.status,
        "requested_count": job.requested_count,
        "processed_count": job.processed_count,
        "success_count": job.success_count,
        "failure_count": job.failure_count,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "error_code": job.error_code,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "created_by": str(job.created_by) if job.created_by else None,
        "blueprint_id": str(job.blueprint_id) if getattr(job, "blueprint_id", None) else None,
        "blueprint_version": getattr(job, "blueprint_version", None),
    }
    if include_runs and job.runs is not None:
        data["runs"] = [_run(r) for r in job.runs]
        data["run_count"] = len(job.runs)
    return data


def _batch(batch: ContentBatch, *, include_jobs: bool = False) -> dict:
    data = {
        "id": str(batch.id),
        "batch_key": batch.batch_key,
        "name": batch.name,
        "description": batch.description,
        "subject_id": str(batch.subject_id),
        "chapter_id": str(batch.chapter_id) if batch.chapter_id else None,
        "topic_id": str(batch.topic_id) if batch.topic_id else None,
        "concept_id": str(batch.concept_id) if batch.concept_id else None,
        "source_type": batch.source_type,
        "source_tier": batch.source_tier,
        "target_count": batch.target_count,
        "created_count": batch.created_count,
        "failed_count": batch.failed_count,
        "qa_pass_count": batch.qa_pass_count,
        "status": batch.status,
        "created_by": str(batch.created_by) if batch.created_by else None,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
        "job_count": len(batch.jobs) if batch.jobs is not None else 0,
        "note": "Batch status is orchestration-only; CERTIFIED/RELEASED ≠ question APPROVED/PUBLISHED",
    }
    if include_jobs and batch.jobs is not None:
        data["jobs"] = [_job(j) for j in batch.jobs]
    return data


@router.post(
    "/content-batches",
    dependencies=[Depends(require_permission("content.factory.create")), Depends(verify_csrf)],
)
async def create_content_batch(
    payload: ContentBatchCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContentFactoryService(db)
    batch, created = await service.create_batch(
        payload,
        actor_id=user.id,
        **request_context(request),
    )
    return envelope(
        success=True,
        data=_batch(batch, include_jobs=True),
        meta={"created": created, "idempotent": not created},
        status_code=201 if created else 200,
    )


@router.get(
    "/content-batches",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def list_content_batches(
    status: str | None = None,
    subject_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = ContentFactoryRepository(db)
    batches, total = await repo.list_batches(status=status, subject_id=subject_id, limit=limit, offset=offset)
    return envelope(
        success=True,
        data=[_batch(b) for b in batches],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get(
    "/content-batches/{batch_id}",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def get_content_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = ContentFactoryRepository(db)
    batch = await repo.get_batch(batch_id)
    if not batch:
        raise NotFoundError("Content batch not found")
    return envelope(success=True, data=_batch(batch, include_jobs=True))


@router.post(
    "/content-batches/{batch_id}/status",
    dependencies=[Depends(require_permission("content.factory.create")), Depends(verify_csrf)],
)
async def transition_content_batch_status(
    batch_id: uuid.UUID,
    payload: BatchStatusTransitionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explicit state-machine transition. Not a generic field update.

    CERTIFIED / RELEASE_CANDIDATE / RELEASED do not publish questions.
    """
    service = ContentFactoryService(db)
    batch = await service.transition_batch(
        batch_id,
        payload,
        actor_id=user.id,
        **request_context(request),
    )
    return envelope(success=True, data=_batch(batch, include_jobs=True))


@router.post(
    "/content-batches/{batch_id}/jobs",
    dependencies=[Depends(require_permission("content.factory.create")), Depends(verify_csrf)],
)
async def create_generation_job(
    batch_id: uuid.UUID,
    payload: GenerationJobCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContentFactoryService(db)
    job, created = await service.create_job(
        batch_id,
        payload,
        actor_id=user.id,
        **request_context(request),
    )
    return envelope(
        success=True,
        data=_job(job),
        meta={"created": created, "idempotent": not created},
        status_code=201 if created else 200,
    )


@router.get(
    "/content-batches/{batch_id}/jobs",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def list_generation_jobs(
    batch_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = ContentFactoryRepository(db)
    batch = await repo.get_batch(batch_id)
    if not batch:
        raise NotFoundError("Content batch not found")
    jobs, total = await repo.list_jobs(batch_id, limit=limit, offset=offset)
    return envelope(
        success=True,
        data=[_job(j) for j in jobs],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get(
    "/generation-jobs/{job_id}",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def get_generation_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = ContentFactoryRepository(db)
    job = await repo.get_job(job_id)
    if not job:
        raise NotFoundError("Generation job not found")
    return envelope(success=True, data=_job(job))


@router.post(
    "/generation-jobs/{job_id}/status",
    dependencies=[Depends(require_permission("content.factory.execute")), Depends(verify_csrf)],
)
async def transition_generation_job_status(
    job_id: uuid.UUID,
    payload: JobStatusTransitionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContentFactoryService(db)
    job = await service.transition_job(
        job_id,
        payload.to_status,
        actor_id=user.id,
        **request_context(request),
    )
    return envelope(success=True, data=_job(job))


@router.post(
    "/generation-jobs/{job_id}/runs",
    dependencies=[Depends(require_permission("content.factory.execute")), Depends(verify_csrf)],
)
async def create_generation_run(
    job_id: uuid.UUID,
    payload: GenerationRunCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a run/retry attempt. Does not generate questions."""
    service = ContentFactoryService(db)
    run = await service.request_run(
        job_id,
        payload,
        actor_id=user.id,
        **request_context(request),
    )
    return envelope(success=True, data=_run(run), status_code=201)


@router.post(
    "/generation-runs/{run_id}/complete",
    dependencies=[Depends(require_permission("content.factory.execute")), Depends(verify_csrf)],
)
async def complete_generation_run(
    run_id: uuid.UUID,
    payload: GenerationRunCompleteRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bookkeeping-only completion. Does not create or mutate questions."""
    service = ContentFactoryService(db)
    run = await service.complete_run(
        run_id,
        payload,
        actor_id=user.id,
        **request_context(request),
    )
    return envelope(success=True, data=_run(run))


@router.get(
    "/generation-runs/{run_id}",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def get_generation_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = ContentFactoryRepository(db)
    run = await repo.get_run(run_id)
    if not run:
        raise NotFoundError("Generation run not found")
    return envelope(success=True, data=_run(run))
