"""Content Factory orchestration service (FACTORY-P1).

Creates and tracks batches/jobs/runs only. Never mutates ContentItem/ContentVersion
or ECAEP statuses. Never invokes AI generation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.modules.academic.models import Concept, Topic
from app.modules.academic.repositories.academic_repository import AcademicRepository
from app.modules.cms.models.content_factory import (
    BATCH_TRANSITIONS,
    DEFAULT_MAX_RETRIES,
    JOB_TRANSITIONS,
    ContentBatch,
    GenerationJob,
    GenerationRun,
)
from app.modules.cms.repositories.content_factory_repository import ContentFactoryRepository
from app.modules.cms.schemas.content_factory import (
    BatchStatusTransitionRequest,
    ContentBatchCreateRequest,
    GenerationJobCreateRequest,
    GenerationRunCompleteRequest,
    GenerationRunCreateRequest,
    InitialJobRequest,
)
from app.modules.system.models.audit_log import AuditLog
from app.modules.system.repositories.audit_repository import AuditRepository

logger = get_logger("content_factory")


class ContentFactoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ContentFactoryRepository(session)
        self.academic = AcademicRepository(session)
        self.audit = AuditRepository(session)

    def _audit(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.audit.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                log_metadata=metadata,
                ip_address=ip_address,
                user_agent=user_agent,
                trace_id=trace_id,
            )
        )

    async def _validate_hierarchy(
        self,
        *,
        subject_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        topic_id: uuid.UUID | None,
        concept_id: uuid.UUID | None,
    ) -> tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None, uuid.UUID | None]:
        subject = await self.academic.get_subject(subject_id)
        if not subject:
            raise AppError("Unknown subject_id", code="INVALID_REFERENCE", status_code=400)

        resolved_chapter = chapter_id
        resolved_topic = topic_id
        resolved_concept = concept_id

        from sqlalchemy import select

        if concept_id:
            result = await self.session.execute(
                select(Concept)
                .options(selectinload(Concept.topic).selectinload(Topic.chapter))
                .where(Concept.id == concept_id)
            )
            concept = result.scalar_one_or_none()
            if not concept:
                raise AppError("Unknown concept_id", code="INVALID_REFERENCE", status_code=400)
            topic = concept.topic
            chapter = topic.chapter
            if topic_id and topic_id != topic.id:
                raise AppError("concept_id does not belong to topic_id", code="INVALID_HIERARCHY", status_code=400)
            if chapter_id and chapter_id != chapter.id:
                raise AppError("concept_id does not belong to chapter_id", code="INVALID_HIERARCHY", status_code=400)
            if chapter.subject_id != subject_id:
                raise AppError("concept_id does not belong to subject_id", code="INVALID_HIERARCHY", status_code=400)
            resolved_topic = topic.id
            resolved_chapter = chapter.id
            resolved_concept = concept.id
        elif topic_id:
            result = await self.session.execute(
                select(Topic).options(selectinload(Topic.chapter)).where(Topic.id == topic_id)
            )
            topic = result.scalar_one_or_none()
            if not topic:
                raise AppError("Unknown topic_id", code="INVALID_REFERENCE", status_code=400)
            chapter = topic.chapter
            if chapter_id and chapter_id != chapter.id:
                raise AppError("topic_id does not belong to chapter_id", code="INVALID_HIERARCHY", status_code=400)
            if chapter.subject_id != subject_id:
                raise AppError("topic_id does not belong to subject_id", code="INVALID_HIERARCHY", status_code=400)
            resolved_chapter = chapter.id
            resolved_topic = topic.id
        elif chapter_id:
            chapter = await self.academic.get_chapter(chapter_id)
            if not chapter:
                raise AppError("Unknown chapter_id", code="INVALID_REFERENCE", status_code=400)
            if chapter.subject_id != subject_id:
                raise AppError("chapter_id does not belong to subject_id", code="INVALID_HIERARCHY", status_code=400)
            resolved_chapter = chapter.id

        return subject_id, resolved_chapter, resolved_topic, resolved_concept

    def _new_job(
        self,
        *,
        batch_id: uuid.UUID,
        spec: InitialJobRequest | GenerationJobCreateRequest,
        actor_id: uuid.UUID | None,
        blueprint_id: uuid.UUID | None = None,
        blueprint_version: int | None = None,
    ) -> GenerationJob:
        return GenerationJob(
            batch_id=batch_id,
            job_key=spec.job_key.strip(),
            job_type=spec.job_type,
            status="PENDING",
            requested_count=spec.requested_count,
            processed_count=0,
            success_count=0,
            failure_count=0,
            retry_count=0,
            max_retries=getattr(spec, "max_retries", DEFAULT_MAX_RETRIES),
            blueprint_id=blueprint_id,
            blueprint_version=blueprint_version,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )

    async def create_job(
        self,
        batch_id: uuid.UUID,
        payload: GenerationJobCreateRequest,
        *,
        actor_id: uuid.UUID | None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[GenerationJob, bool]:
        batch = await self.repo.get_batch(batch_id)
        if not batch:
            raise NotFoundError("Content batch not found")

        existing = await self.repo.get_job_by_key(batch_id, payload.job_key.strip())
        if existing:
            return existing, False

        blueprint_id = getattr(payload, "blueprint_id", None)
        blueprint_version = None
        if blueprint_id:
            from app.modules.cms.repositories.content_factory_planning_repository import (
                ContentFactoryPlanningRepository,
            )

            planning = ContentFactoryPlanningRepository(self.session)
            bp = await planning.get_blueprint(blueprint_id)
            if not bp:
                raise AppError("Unknown blueprint_id", code="INVALID_REFERENCE", status_code=400)
            if not bp.generation_eligible:
                raise AppError(
                    "Blueprint is not generation-eligible",
                    code="BLUEPRINT_NOT_ELIGIBLE",
                    status_code=409,
                )
            blueprint_version = bp.blueprint_version

        job = self._new_job(
            batch_id=batch_id,
            spec=payload,
            actor_id=actor_id,
            blueprint_id=blueprint_id,
            blueprint_version=blueprint_version,
        )
        self.repo.add_job(job)
        try:
            await self.repo.flush()
            self._audit(
                actor_user_id=actor_id,
                action="factory.job.created",
                entity_type="generation_job",
                entity_id=job.id,
                metadata={
                    "batch_id": str(batch_id),
                    "job_key": job.job_key,
                    "job_type": job.job_type,
                    "previous_status": None,
                    "new_status": job.status,
                    "blueprint_id": str(blueprint_id) if blueprint_id else None,
                    "blueprint_version": blueprint_version,
                },
                trace_id=trace_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except IntegrityError:
            await self.session.rollback()
            raced = await self.repo.get_job_by_key(batch_id, payload.job_key.strip())
            if raced:
                return raced, False
            raise AppError(
                "Could not create generation job due to a conflict.",
                code="CONFLICT",
                status_code=409,
            ) from None

        await self.repo.commit()
        reloaded = await self.repo.get_job(job.id)
        assert reloaded is not None
        return reloaded, True

    async def create_batch(
        self,
        payload: ContentBatchCreateRequest,
        *,
        actor_id: uuid.UUID | None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[ContentBatch, bool]:
        """Return (batch, created). Idempotent on batch_key."""
        existing = await self.repo.get_batch_by_key(payload.batch_key)
        if existing:
            logger.info(
                "content_batch_idempotent_hit",
                batch_key=payload.batch_key,
                batch_id=str(existing.id),
                trace_id=trace_id,
            )
            return existing, False

        subject_id, chapter_id, topic_id, concept_id = await self._validate_hierarchy(
            subject_id=payload.subject_id,
            chapter_id=payload.chapter_id,
            topic_id=payload.topic_id,
            concept_id=payload.concept_id,
        )

        batch = ContentBatch(
            batch_key=payload.batch_key,
            name=payload.name,
            description=payload.description,
            subject_id=subject_id,
            chapter_id=chapter_id,
            topic_id=topic_id,
            concept_id=concept_id,
            source_type=payload.source_type,
            source_tier=payload.source_tier,
            target_count=payload.target_count,
            created_count=0,
            failed_count=0,
            qa_pass_count=0,
            status="CREATED",
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        self.repo.add_batch(batch)
        try:
            await self.repo.flush()
            if payload.initial_job:
                job = self._new_job(batch_id=batch.id, spec=payload.initial_job, actor_id=actor_id)
                self.repo.add_job(job)
                await self.repo.flush()
                self._audit(
                    actor_user_id=actor_id,
                    action="factory.job.created",
                    entity_type="generation_job",
                    entity_id=job.id,
                    metadata={
                        "batch_id": str(batch.id),
                        "job_key": job.job_key,
                        "job_type": job.job_type,
                        "status": job.status,
                    },
                    trace_id=trace_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            self._audit(
                actor_user_id=actor_id,
                action="factory.batch.created",
                entity_type="content_batch",
                entity_id=batch.id,
                metadata={
                    "batch_key": batch.batch_key,
                    "status": batch.status,
                    "subject_id": str(batch.subject_id),
                    "target_count": batch.target_count,
                    "has_initial_job": payload.initial_job is not None,
                },
                trace_id=trace_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except IntegrityError:
            await self.session.rollback()
            raced = await self.repo.get_batch_by_key(payload.batch_key)
            if raced:
                return raced, False
            raise AppError(
                "Could not create content batch due to a conflict.",
                code="CONFLICT",
                status_code=409,
            ) from None

        await self.repo.commit()
        reloaded = await self.repo.get_batch(batch.id)
        assert reloaded is not None
        logger.info(
            "content_batch_created",
            batch_id=str(reloaded.id),
            batch_key=reloaded.batch_key,
            status=reloaded.status,
            trace_id=trace_id,
        )
        return reloaded, True

    async def transition_batch(
        self,
        batch_id: uuid.UUID,
        payload: BatchStatusTransitionRequest,
        *,
        actor_id: uuid.UUID | None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ContentBatch:
        batch = await self.repo.get_batch(batch_id)
        if not batch:
            raise NotFoundError("Content batch not found")

        allowed = BATCH_TRANSITIONS.get(batch.status, frozenset())
        if payload.to_status not in allowed:
            raise AppError(
                f"Invalid batch transition {batch.status} → {payload.to_status}",
                code="INVALID_STATE_TRANSITION",
                status_code=409,
            )

        previous = batch.status
        batch.status = payload.to_status
        batch.updated_by = actor_id
        batch.version = (batch.version or 1) + 1

        self._audit(
            actor_user_id=actor_id,
            action="factory.batch.status_changed",
            entity_type="content_batch",
            entity_id=batch.id,
            metadata={
                "previous_status": previous,
                "new_status": batch.status,
                "batch_key": batch.batch_key,
                "note": "Batch status does not approve or publish questions",
            },
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.repo.commit()
        reloaded = await self.repo.get_batch(batch_id)
        assert reloaded is not None
        return reloaded

    async def transition_job(
        self,
        job_id: uuid.UUID,
        to_status: str,
        *,
        actor_id: uuid.UUID | None,
        error_code: str | None = None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationJob:
        job = await self.repo.get_job(job_id)
        if not job:
            raise NotFoundError("Generation job not found")

        allowed = JOB_TRANSITIONS.get(job.status, frozenset())
        if to_status not in allowed:
            raise AppError(
                f"Invalid job transition {job.status} → {to_status}",
                code="INVALID_STATE_TRANSITION",
                status_code=409,
            )

        previous = job.status
        now = datetime.now(UTC)
        job.status = to_status
        job.updated_by = actor_id
        job.version = (job.version or 1) + 1
        if to_status == "RUNNING" and job.started_at is None:
            job.started_at = now
        if to_status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            job.completed_at = now
        if error_code is not None:
            job.error_code = error_code

        self._audit(
            actor_user_id=actor_id,
            action="factory.job.status_changed",
            entity_type="generation_job",
            entity_id=job.id,
            metadata={
                "previous_status": previous,
                "new_status": job.status,
                "batch_id": str(job.batch_id),
                "error_code": job.error_code,
            },
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.repo.commit()
        reloaded = await self.repo.get_job(job_id)
        assert reloaded is not None
        return reloaded

    async def request_run(
        self,
        job_id: uuid.UUID,
        payload: GenerationRunCreateRequest,
        *,
        actor_id: uuid.UUID | None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationRun:
        """Create a GenerationRun attempt. Does not execute generation."""
        job = await self.repo.get_job(job_id)
        if not job:
            raise NotFoundError("Generation job not found")

        if job.status == "SUCCEEDED":
            raise AppError(
                "Cannot create a run for a succeeded job — successful work must not be duplicated.",
                code="JOB_ALREADY_SUCCEEDED",
                status_code=409,
            )
        if job.status == "CANCELLED":
            raise AppError("Cannot create a run for a cancelled job.", code="JOB_CANCELLED", status_code=409)
        if job.status == "RUNNING" or any(r.status in {"PENDING", "RUNNING"} for r in job.runs):
            raise AppError(
                "Job already has an active run.",
                code="JOB_ALREADY_RUNNING",
                status_code=409,
            )

        has_prior_failure = job.status == "FAILED" or any(r.status == "FAILED" for r in job.runs)
        if has_prior_failure and job.retry_count >= job.max_retries:
            raise AppError(
                f"Retry limit reached ({job.max_retries}).",
                code="RETRY_LIMIT_EXCEEDED",
                status_code=409,
            )

        previous_job_status = job.status
        if has_prior_failure:
            job.retry_count += 1
            job.status = "PENDING"
            job.completed_at = None
            job.error_code = None

        attempt = await self.repo.next_attempt_number(job_id)
        meta = dict(payload.execution_metadata or {})
        for banned in ("password", "api_key", "secret", "token", "prompt", "authorization"):
            meta.pop(banned, None)
            meta.pop(banned.upper(), None)

        run = GenerationRun(
            job_id=job_id,
            attempt_number=attempt,
            status="PENDING",
            processed_count=0,
            success_count=0,
            failure_count=0,
            error_summary=None,
            execution_metadata=meta or None,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        self.repo.add_run(run)
        try:
            await self.repo.flush()
            action = "factory.run.retry_requested" if has_prior_failure else "factory.run.created"
            self._audit(
                actor_user_id=actor_id,
                action=action,
                entity_type="generation_run",
                entity_id=run.id,
                metadata={
                    "job_id": str(job_id),
                    "attempt_number": attempt,
                    "previous_job_status": previous_job_status,
                    "new_status": run.status,
                    "reason": payload.reason,
                    "retry_count": job.retry_count,
                },
                trace_id=trace_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(
                "Could not create generation run due to a conflict.",
                code="CONFLICT",
                status_code=409,
            ) from exc

        await self.repo.commit()
        reloaded = await self.repo.get_run(run.id)
        assert reloaded is not None
        return reloaded

    async def complete_run(
        self,
        run_id: uuid.UUID,
        payload: GenerationRunCompleteRequest,
        *,
        actor_id: uuid.UUID | None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationRun:
        """Bookkeeping-only run completion — no question generation."""
        run = await self.repo.get_run(run_id)
        if not run:
            raise NotFoundError("Generation run not found")

        job = await self.repo.get_job(run.job_id)
        if not job:
            raise NotFoundError("Generation job not found")

        if run.status in {"SUCCEEDED", "FAILED"}:
            raise AppError(
                f"Run already completed with status {run.status}",
                code="RUN_ALREADY_COMPLETED",
                status_code=409,
            )
        if payload.status not in {"SUCCEEDED", "FAILED"}:
            raise AppError("Run completion status must be SUCCEEDED or FAILED", code="VALIDATION_ERROR", status_code=422)

        now = datetime.now(UTC)
        previous_run = run.status
        if run.status == "PENDING":
            run.status = "RUNNING"
            run.started_at = now
            if job.status == "PENDING":
                job.status = "RUNNING"
                if job.started_at is None:
                    job.started_at = now

        if run.status != "RUNNING":
            raise AppError(
                f"Invalid run transition {run.status} → {payload.status}",
                code="INVALID_STATE_TRANSITION",
                status_code=409,
            )

        run.status = payload.status
        run.processed_count = payload.processed_count
        run.success_count = payload.success_count
        run.failure_count = payload.failure_count
        run.error_summary = payload.error_summary
        run.completed_at = now
        run.updated_by = actor_id
        run.version = (run.version or 1) + 1
        if payload.execution_metadata is not None:
            meta = dict(payload.execution_metadata)
            for banned in ("password", "api_key", "secret", "token", "prompt", "authorization"):
                meta.pop(banned, None)
            run.execution_metadata = {**(run.execution_metadata or {}), **meta}

        previous_job = job.status
        job.processed_count = payload.processed_count
        job.success_count = payload.success_count
        job.failure_count = payload.failure_count
        job.updated_by = actor_id
        job.version = (job.version or 1) + 1
        if payload.status == "SUCCEEDED":
            job.status = "SUCCEEDED"
            job.completed_at = now
            job.error_code = None
        else:
            job.status = "FAILED"
            job.completed_at = now
            job.error_code = payload.error_code or "RUN_FAILED"

        self._audit(
            actor_user_id=actor_id,
            action="factory.run.completed" if payload.status == "SUCCEEDED" else "factory.run.failed",
            entity_type="generation_run",
            entity_id=run.id,
            metadata={
                "previous_status": previous_run,
                "new_status": run.status,
                "job_id": str(job.id),
                "previous_job_status": previous_job,
                "new_job_status": job.status,
                "attempt_number": run.attempt_number,
                "error_code": job.error_code,
            },
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._audit(
            actor_user_id=actor_id,
            action="factory.job.status_changed",
            entity_type="generation_job",
            entity_id=job.id,
            metadata={
                "previous_status": previous_job,
                "new_status": job.status,
                "via_run_id": str(run.id),
            },
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.repo.commit()
        reloaded = await self.repo.get_run(run_id)
        assert reloaded is not None
        return reloaded
