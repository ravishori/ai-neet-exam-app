"""Content Factory planning APIs (FACTORY-P2). No generation / publish."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.cms.models.content_factory_planning import (
    CoverageSlice,
    LearningObjective,
    QuestionBlueprint,
    QuestionFamily,
)
from app.modules.cms.repositories.content_factory_planning_repository import ContentFactoryPlanningRepository
from app.modules.cms.schemas.content_factory_planning import (
    BatchBlueprintAttachRequest,
    CoverageSliceCreateRequest,
    FactoryGenerateRequest,
    FactoryQARequest,
    FactoryReviewDecisionRequest,
    FactorySampleRequest,
    LearningObjectiveCreateRequest,
    QuestionBlueprintCreateRequest,
    QuestionFamilyCreateRequest,
)
from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService
from app.modules.cms.services.content_factory_human_review_service import ContentFactoryHumanReviewService
from app.modules.cms.services.content_factory_planning_service import ContentFactoryPlanningService
from app.modules.cms.services.content_factory_qa_service import ContentFactoryQAService, ContentFactorySamplingService
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.modules.system.services.audit_service import request_context
from app.shared.responses import envelope

router = APIRouter(tags=["cms-factory-planning"])


def _objective(o: LearningObjective) -> dict:
    return {
        "id": str(o.id),
        "objective_key": o.objective_key,
        "concept_id": str(o.concept_id),
        "title": o.title,
        "description": o.description,
        "learning_level": o.learning_level,
        "is_active": o.is_active,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
    }


def _family(f: QuestionFamily) -> dict:
    return {
        "id": str(f.id),
        "family_key": f.family_key,
        "name": f.name,
        "description": f.description,
        "applicable_subject_codes": f.applicable_subject_codes,
        "cognitive_intent": f.cognitive_intent,
        "difficulty_min": f.difficulty_min,
        "difficulty_max": f.difficulty_max,
        "question_format": f.question_format,
        "is_active": f.is_active,
        "created_at": f.created_at,
    }


def _blueprint(bp: QuestionBlueprint) -> dict:
    return {
        "id": str(bp.id),
        "blueprint_key": bp.blueprint_key,
        "blueprint_version": bp.blueprint_version,
        "subject_id": str(bp.subject_id),
        "chapter_id": str(bp.chapter_id),
        "topic_id": str(bp.topic_id),
        "concept_id": str(bp.concept_id),
        "learning_objective_id": str(bp.learning_objective_id),
        "question_family_id": str(bp.question_family_id),
        "difficulty": bp.difficulty,
        "target_count": bp.target_count,
        "constraints": bp.constraints,
        "provenance_tier": bp.provenance_tier,
        "status": bp.status,
        "generation_eligible": bp.generation_eligible,
        "is_active": bp.is_active,
        "last_validation": bp.last_validation,
        "created_at": bp.created_at,
        "updated_at": bp.updated_at,
        "note": "Blueprint is a generation contract — not a question; CERTIFIED batch ≠ PUBLISHED",
    }


def _slice(s: CoverageSlice) -> dict:
    return {
        "id": str(s.id),
        "slice_key": s.slice_key,
        "subject_id": str(s.subject_id),
        "chapter_id": str(s.chapter_id) if s.chapter_id else None,
        "topic_id": str(s.topic_id) if s.topic_id else None,
        "concept_id": str(s.concept_id) if s.concept_id else None,
        "difficulty": s.difficulty,
        "question_family_id": str(s.question_family_id) if s.question_family_id else None,
        "target_count": s.target_count,
        "is_active": s.is_active,
    }


@router.post(
    "/learning-objectives",
    dependencies=[Depends(require_permission("content.factory.create")), Depends(verify_csrf)],
)
async def create_learning_objective(
    payload: LearningObjectiveCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    obj, created = await ContentFactoryPlanningService(db).create_objective(
        payload, actor_id=user.id, **request_context(request)
    )
    return envelope(
        success=True,
        data=_objective(obj),
        meta={"created": created, "idempotent": not created},
        status_code=201 if created else 200,
    )


@router.get(
    "/learning-objectives",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def list_learning_objectives(
    concept_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows, total = await ContentFactoryPlanningRepository(db).list_objectives(
        concept_id=concept_id, limit=limit, offset=offset
    )
    return envelope(success=True, data=[_objective(o) for o in rows], meta={"total": total, "limit": limit, "offset": offset})


@router.post(
    "/question-families",
    dependencies=[Depends(require_permission("content.factory.create")), Depends(verify_csrf)],
)
async def create_question_family(
    payload: QuestionFamilyCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    family, created = await ContentFactoryPlanningService(db).create_family(
        payload, actor_id=user.id, **request_context(request)
    )
    return envelope(
        success=True,
        data=_family(family),
        meta={"created": created, "idempotent": not created},
        status_code=201 if created else 200,
    )


@router.get(
    "/question-families",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def list_question_families(
    subject_code: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows, total = await ContentFactoryPlanningRepository(db).list_families(
        subject_code=subject_code, limit=limit, offset=offset
    )
    return envelope(success=True, data=[_family(f) for f in rows], meta={"total": total, "limit": limit, "offset": offset})


@router.post(
    "/question-blueprints",
    dependencies=[Depends(require_permission("content.factory.create")), Depends(verify_csrf)],
)
async def create_question_blueprint(
    payload: QuestionBlueprintCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bp, created = await ContentFactoryPlanningService(db).create_blueprint(
        payload, actor_id=user.id, **request_context(request)
    )
    return envelope(
        success=True,
        data=_blueprint(bp),
        meta={"created": created, "idempotent": not created},
        status_code=201 if created else 200,
    )


@router.get(
    "/question-blueprints",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def list_question_blueprints(
    concept_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows, total = await ContentFactoryPlanningRepository(db).list_blueprints(
        concept_id=concept_id, subject_id=subject_id, status=status, limit=limit, offset=offset
    )
    return envelope(
        success=True, data=[_blueprint(b) for b in rows], meta={"total": total, "limit": limit, "offset": offset}
    )


@router.get(
    "/question-blueprints/{blueprint_id}",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def get_question_blueprint(
    blueprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    bp = await ContentFactoryPlanningRepository(db).get_blueprint(blueprint_id)
    if not bp:
        raise NotFoundError("Question blueprint not found")
    return envelope(success=True, data=_blueprint(bp))


@router.post(
    "/question-blueprints/{blueprint_id}/validate",
    dependencies=[Depends(require_permission("content.factory.create")), Depends(verify_csrf)],
)
async def validate_question_blueprint(
    blueprint_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await ContentFactoryPlanningService(db).validate_blueprint(
        blueprint_id, actor_id=user.id, **request_context(request)
    )
    return envelope(success=True, data=result)


@router.post(
    "/coverage-slices",
    dependencies=[Depends(require_permission("content.factory.create")), Depends(verify_csrf)],
)
async def create_coverage_slice(
    payload: CoverageSliceCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row, created = await ContentFactoryPlanningService(db).create_coverage_slice(
        payload, actor_id=user.id, **request_context(request)
    )
    return envelope(
        success=True,
        data=_slice(row),
        meta={"created": created, "idempotent": not created},
        status_code=201 if created else 200,
    )


@router.get(
    "/content-coverage",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def get_content_coverage(
    subject_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    report = await ContentFactoryPlanningService(db).coverage_report(
        subject_id=subject_id, limit=limit, offset=offset
    )
    return envelope(success=True, data=report["slices"], meta={k: report[k] for k in ("total", "limit", "offset")})


@router.post(
    "/content-batches/{batch_id}/blueprints",
    dependencies=[Depends(require_permission("content.factory.create")), Depends(verify_csrf)],
)
async def attach_blueprint_to_batch(
    batch_id: uuid.UUID,
    payload: BatchBlueprintAttachRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    link, created = await ContentFactoryPlanningService(db).attach_blueprint_to_batch(
        batch_id, payload, actor_id=user.id, **request_context(request)
    )
    return envelope(
        success=True,
        data={
            "id": str(link.id),
            "batch_id": str(link.batch_id),
            "blueprint_id": str(link.blueprint_id),
            "requested_count": link.requested_count,
        },
        meta={"created": created, "idempotent": not created},
        status_code=201 if created else 200,
    )


@router.post(
    "/content-batches/{batch_id}/generate",
    dependencies=[Depends(require_permission("content.factory.execute")), Depends(verify_csrf)],
)
async def generate_from_blueprint(
    batch_id: uuid.UUID,
    payload: FactoryGenerateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FACTORY-P3: blueprint-driven AI generation into DRAFT only.

    Synchronous pilot path (capped by factory_max_sync_generation_count).
    Never submits, approves, or publishes. Uses existing AI Gateway.
    """
    result = await ContentFactoryGenerationService(db).generate_for_batch(
        batch_id,
        blueprint_id=payload.blueprint_id,
        target_count=payload.target_count,
        actor_id=user.id,
        job_key=payload.job_key,
        sync_cap=True,
        **request_context(request),
    )
    return envelope(success=True, data=result)


@router.post(
    "/content-batches/{batch_id}/qa",
    dependencies=[Depends(require_permission("content.factory.execute")), Depends(verify_csrf)],
)
async def run_batch_qa(
    batch_id: uuid.UUID,
    payload: FactoryQARequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FACTORY-P4: deterministic automated QA → GREEN/YELLOW/RED. Never approves/publishes."""
    result = await ContentFactoryQAService(db).run_batch_qa(
        batch_id,
        actor_id=user.id,
        force_new=payload.force_new,
        run_id=payload.run_id,
        job_key=payload.job_key,
        **request_context(request),
    )
    return envelope(success=True, data=result)


@router.post(
    "/generation-candidates/{candidate_id}/qa",
    dependencies=[Depends(require_permission("content.factory.execute")), Depends(verify_csrf)],
)
async def run_candidate_qa(
    candidate_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    force_new: bool = False,
):
    result = await ContentFactoryQAService(db).evaluate_candidate(
        candidate_id,
        actor_id=user.id,
        force_new=force_new,
        **request_context(request),
    )
    return envelope(success=True, data=result)


@router.get(
    "/content-batches/{batch_id}/qa-summary",
    dependencies=[Depends(require_permission("content.factory.view"))],
)
async def batch_qa_summary(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    from sqlalchemy import func, select

    from app.modules.cms.models.factory_qa import QAResult
    from app.modules.cms.models.generation_candidate import GenerationCandidate

    rows = (
        await db.execute(
            select(QAResult.classification, func.count())
            .join(GenerationCandidate, GenerationCandidate.id == QAResult.candidate_id)
            .where(
                QAResult.batch_id == batch_id,
                QAResult.is_latest.is_(True),
                QAResult.deleted_at.is_(None),
            )
            .group_by(QAResult.classification)
        )
    ).all()
    counts = {c: n for c, n in rows}
    return envelope(
        success=True,
        data={
            "batch_id": str(batch_id),
            "GREEN": counts.get("GREEN", 0),
            "YELLOW": counts.get("YELLOW", 0),
            "RED": counts.get("RED", 0),
            "disclaimer": "AUTOMATED_QA_ONLY — not scientifically certified",
        },
    )


@router.post(
    "/content-batches/{batch_id}/sample",
    dependencies=[Depends(require_permission("content.factory.execute")), Depends(verify_csrf)],
)
async def create_review_sample(
    batch_id: uuid.UUID,
    payload: FactorySampleRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FACTORY-P4 sampling eligibility — not certification or ECAEP submit."""
    result = await ContentFactorySamplingService(db).create_sample(
        batch_id,
        actor_id=user.id,
        seed=payload.seed,
        sample_key=payload.sample_key,
        green_size=payload.green_size,
        **request_context(request),
    )
    return envelope(success=True, data=result)


@router.get(
    "/factory-review/dashboard",
    dependencies=[Depends(require_permission("content.review"))],
)
async def factory_review_dashboard(
    batch_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """FACTORY-P5 progress dashboard — not scientific accuracy."""
    data = await ContentFactoryHumanReviewService(db).dashboard(batch_id=batch_id)
    return envelope(success=True, data=data)


@router.get(
    "/factory-review/queue",
    dependencies=[Depends(require_permission("content.review"))],
)
async def factory_review_queue(
    batch_id: uuid.UUID | None = None,
    selection_class: str | None = None,
    review_status: str | None = None,
    needs_review: bool = False,
    subject_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
    difficulty: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    blueprint_id: uuid.UUID | None = None,
    sort: str = Query("risk"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = await ContentFactoryHumanReviewService(db).list_queue(
        batch_id=batch_id,
        selection_class=selection_class,
        review_status=review_status,
        needs_review=needs_review,
        subject_id=subject_id,
        chapter_id=chapter_id,
        difficulty=difficulty,
        model=model,
        prompt_version=prompt_version,
        blueprint_id=blueprint_id,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return envelope(success=True, data=data["items"], meta={k: data[k] for k in ("total", "limit", "offset", "sort", "note")})


@router.get(
    "/factory-review/items/{item_id}",
    dependencies=[Depends(require_permission("content.review"))],
)
async def factory_review_packet(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = await ContentFactoryHumanReviewService(db).get_review_packet(item_id)
    return envelope(success=True, data=data)


@router.post(
    "/factory-review/items/{item_id}/decision",
    dependencies=[Depends(require_permission("content.review")), Depends(verify_csrf)],
)
async def factory_review_decision(
    item_id: uuid.UUID,
    payload: FactoryReviewDecisionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record human factory decision — never auto-approves or publishes."""
    data = await ContentFactoryHumanReviewService(db).submit_decision(
        item_id,
        decision=payload.decision,
        actor_id=user.id,
        checklist=payload.checklist,
        failure_reasons=payload.failure_reasons,
        reviewer_note=payload.reviewer_note,
        **request_context(request),
    )
    return envelope(success=True, data=data)


@router.post(
    "/review-samples/{sample_id}/materialize",
    dependencies=[Depends(require_permission("content.factory.execute")), Depends(verify_csrf)],
)
async def materialize_sample(
    sample_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sample = await ContentFactoryHumanReviewService(db).ensure_sample_materialized(
        sample_id, actor_id=user.id
    )
    return envelope(
        success=True,
        data={"sample_id": str(sample.id), "sample_key": sample.sample_key},
    )
