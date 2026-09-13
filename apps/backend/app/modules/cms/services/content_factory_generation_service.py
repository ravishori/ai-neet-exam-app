"""FACTORY-P3 controlled blueprint-driven AI generation (DRAFT only).

Semantics: target_count = desired valid unique DRAFT questions.
Attempts bounded by multiplier; budget capped by cost + count settings.
Never submit / approve / publish. Never mutate existing questions.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.ingestion.services.ncert_canonical_source import (
    assert_blueprint_ncert_source,
)
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.gateway.base import (
    PROVIDER_AUTH_FAILED,
    PROVIDER_BLOCKED,
    PROVIDER_COST_UNKNOWN,
    AIProvider,
    AIResponse,
    ProviderError,
)
from app.modules.cms.models.content_factory import ContentBatch, GenerationJob, GenerationRun
from app.modules.cms.models.content_factory_planning import QuestionBlueprint
from app.modules.cms.models.content_item import ContentItem
from app.modules.cms.models.content_version import ContentVersion
from app.modules.cms.models.generation_candidate import GenerationCandidate

# ContentVersion FK → knowledge.knowledge_units requires the target table on metadata.
import app.modules.knowledge.models  # noqa: F401
from app.modules.cms.prompts.factory_mcq import (
    AGENT_TYPE,
    GENERATOR_VERSION,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.modules.cms.repositories.content_factory_planning_repository import ContentFactoryPlanningRepository
from app.modules.cms.repositories.content_factory_repository import ContentFactoryRepository
from app.modules.cms.schemas.content_factory import GenerationRunCompleteRequest, GenerationRunCreateRequest
from app.modules.cms.schemas.content_factory_planning import BatchBlueprintAttachRequest
from app.modules.cms.services.content_factory_planning_service import ContentFactoryPlanningService
from app.modules.cms.services.content_factory_service import ContentFactoryService
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.cms.services.factory_candidate_validation import (
    parse_mcq_json,
    stem_hash,
    validate_candidate_body,
)
from app.modules.cms.services.factory_seed_diversity import (
    classify_against_prior,
    format_prior_stems_for_prompt,
)
from app.modules.system.models.audit_log import AuditLog
from app.modules.system.repositories.audit_repository import AuditRepository

logger = get_logger("content_factory_generation")
settings = get_settings()


@dataclass
class GenerationStats:
    requested: int = 0
    attempted: int = 0
    created: int = 0
    rejected_validation: int = 0
    duplicate: int = 0
    diversity_rejected: int = 0
    failed_provider: int = 0
    failed_parse: int = 0
    cost_usd: float = 0.0
    models: dict[str, int] = field(default_factory=dict)
    providers: dict[str, int] = field(default_factory=dict)
    provider_attempts: list[dict] = field(default_factory=list)
    routing_policy: str | None = None
    stop_reason: str | None = None
    content_item_ids: list[str] = field(default_factory=list)
    latency_ms: int = 0


class ContentFactoryGenerationService:
    def __init__(self, session: AsyncSession, *, provider: AIProvider | None = None):
        self.session = session
        self.factory = ContentFactoryService(session)
        self.planning = ContentFactoryPlanningService(session)
        self.planning_repo = ContentFactoryPlanningRepository(session)
        self.factory_repo = ContentFactoryRepository(session)
        self.workflow = ContentWorkflowService(session)
        self.gateway = AIGateway(session, provider=provider)
        self.audit = AuditRepository(session)

    def _audit(self, *, actor_id, action, entity_type, entity_id, metadata, **ctx) -> None:
        self.audit.add(
            AuditLog(
                actor_user_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                log_metadata=metadata,
                ip_address=ctx.get("ip_address"),
                user_agent=ctx.get("user_agent"),
                trace_id=ctx.get("trace_id"),
            )
        )

    async def _existing_stem_hashes(self, concept_id: uuid.UUID) -> set[str]:
        result = await self.session.execute(
            select(ContentVersion.body)
            .join(ContentItem, ContentItem.latest_version_id == ContentVersion.id)
            .where(
                ContentItem.content_type == "QUESTION",
                ContentItem.deleted_at.is_(None),
                ContentItem.concept_id == concept_id,
            )
        )
        hashes: set[str] = set()
        for (body,) in result.all():
            if isinstance(body, dict) and body.get("stem"):
                hashes.add(stem_hash(body["stem"]))
        # Also include successful factory candidates for this concept
        cand = await self.session.execute(
            select(GenerationCandidate.stem_hash).where(
                GenerationCandidate.concept_id == concept_id,
                GenerationCandidate.status == "CREATED",
                GenerationCandidate.stem_hash.is_not(None),
                GenerationCandidate.deleted_at.is_(None),
            )
        )
        for (h,) in cand.all():
            if h:
                hashes.add(h)
        return hashes

    async def _batch_created_stems(self, batch_id: uuid.UUID) -> list[str]:
        """Prior CREATED stems in this batch (for in-batch anti-paraphrase / template diversity)."""
        rows = (
            await self.session.execute(
                select(ContentVersion.body)
                .join(ContentItem, ContentItem.latest_version_id == ContentVersion.id)
                .join(GenerationCandidate, GenerationCandidate.content_item_id == ContentItem.id)
                .where(
                    GenerationCandidate.batch_id == batch_id,
                    GenerationCandidate.status == "CREATED",
                    GenerationCandidate.deleted_at.is_(None),
                    ContentItem.deleted_at.is_(None),
                )
                .order_by(GenerationCandidate.created_at.asc())
            )
        ).all()
        stems: list[str] = []
        for (body,) in rows:
            if isinstance(body, dict) and body.get("stem"):
                stems.append(str(body["stem"]))
        return stems

    async def _assert_blueprint_eligible(self, blueprint_id: uuid.UUID) -> QuestionBlueprint:
        bp = await self.planning_repo.get_blueprint(blueprint_id)
        if not bp:
            raise AppError("Blueprint not found", code="INVALID_REFERENCE", status_code=400)
        if not bp.is_active:
            raise AppError("Blueprint is not active", code="BLUEPRINT_INACTIVE", status_code=409)
        if bp.status == "SUPERSEDED" or bp.status == "ARCHIVED":
            raise AppError("Blueprint version is superseded or archived", code="BLUEPRINT_INACTIVE", status_code=409)
        if not bp.generation_eligible:
            raise AppError(
                "Blueprint is not generation-eligible (must be GREEN)",
                code="BLUEPRINT_NOT_ELIGIBLE",
                status_code=409,
            )
        # CF-SOURCE-001: NCERT-derived blueprints must bind a PDF under NCERT_SOURCE_ROOT.
        # Fail closed — no StudyMaterial / model-memory / web fallback.
        assert_blueprint_ncert_source(bp.constraints, provenance_tier=bp.provenance_tier)
        # Hierarchy must still resolve
        await self._load_context(bp)
        return bp

    async def _load_context(self, bp: QuestionBlueprint) -> dict[str, Any]:
        result = await self.session.execute(
            select(Concept)
            .options(selectinload(Concept.topic).selectinload(Topic.chapter).selectinload(Chapter.subject))
            .where(Concept.id == bp.concept_id)
        )
        concept = result.scalar_one_or_none()
        if not concept:
            raise AppError("Concept missing — hierarchy gap", code="HIERARCHY_GAP", status_code=400)
        topic = concept.topic
        chapter = topic.chapter
        subject = chapter.subject
        objective = bp.learning_objective or await self.planning_repo.get_objective(bp.learning_objective_id)
        family = bp.question_family or await self.planning_repo.get_family(bp.question_family_id)
        if not objective or not family:
            raise AppError("Objective or family missing", code="INVALID_REFERENCE", status_code=400)
        # Plain values only — AIGateway commits invalidate lazy ORM IO.
        return {
            "concept_id": concept.id,
            "concept_name": concept.name,
            "concept_summary": concept.summary,
            "topic_name": topic.name,
            "chapter_name": chapter.name,
            "subject_name": subject.name,
            "objective_title": objective.title,
            "objective_description": objective.description,
            "family_name": family.name,
            "family_intent": family.cognitive_intent,
            "family_key": family.family_key,
        }

    async def generate_for_batch(
        self,
        batch_id: uuid.UUID,
        *,
        blueprint_id: uuid.UUID,
        target_count: int,
        actor_id: uuid.UUID,
        job_key: str | None = None,
        sync_cap: bool = True,
        **ctx,
    ) -> dict[str, Any]:
        """Create/attach job+run and generate until target valid unique DRAFTs or bounds hit."""
        started = time.perf_counter()
        max_count = settings.factory_max_pilot_generation_count
        if sync_cap:
            max_count = min(max_count, settings.factory_max_sync_generation_count)
        if target_count < 1:
            raise AppError("target_count must be >= 1", code="VALIDATION_ERROR", status_code=422)
        if target_count > max_count:
            raise AppError(
                f"target_count exceeds pilot cap ({max_count})",
                code="PILOT_LIMIT_EXCEEDED",
                status_code=400,
            )

        batch = await self.factory_repo.get_batch(batch_id)
        if not batch:
            raise NotFoundError("Content batch not found")

        bp = await self._assert_blueprint_eligible(blueprint_id)
        await self.planning.attach_blueprint_to_batch(
            batch_id,
            BatchBlueprintAttachRequest(blueprint_id=blueprint_id, requested_count=target_count),
            actor_id=actor_id,
            **ctx,
        )

        from app.modules.cms.schemas.content_factory import GenerationJobCreateRequest

        key = job_key or f"gen-bp-{bp.blueprint_key}-v{bp.blueprint_version}"
        job, _ = await self.factory.create_job(
            batch_id,
            GenerationJobCreateRequest(
                job_key=key,
                job_type="GENERATE",
                requested_count=target_count,
                max_retries=3,
                blueprint_id=blueprint_id,
            ),
            actor_id=actor_id,
            **ctx,
        )
        # Ensure pin matches current eligible version
        if job.blueprint_id != blueprint_id or job.blueprint_version != bp.blueprint_version:
            job.blueprint_id = blueprint_id
            job.blueprint_version = bp.blueprint_version
            await self.session.commit()

        run = await self.factory.request_run(
            job.id,
            GenerationRunCreateRequest(
                reason="FACTORY-P3 pilot generation",
                execution_metadata={
                    "prompt_version": PROMPT_VERSION,
                    "generator_version": GENERATOR_VERSION,
                    "target_count": target_count,
                    "blueprint_version": bp.blueprint_version,
                    "routing_policy": self.gateway.routing_policy.describe(),
                    "factory_provider_mode": settings.factory_provider_mode,
                    "factory_provider": settings.factory_provider,
                },
            ),
            actor_id=actor_id,
            **ctx,
        )

        pinned_bp_version = bp.blueprint_version
        pinned_job_id = job.id
        pinned_run_id = run.id

        stats = await self._execute_run(
            batch=batch,
            job=job,
            run=run,
            blueprint=bp,
            target_count=target_count,
            actor_id=actor_id,
            **ctx,
        )
        stats.latency_ms = int((time.perf_counter() - started) * 1000)

        # Complete run bookkeeping
        if stats.created > 0:
            terminal = "SUCCEEDED"
        else:
            terminal = "FAILED"

        await self.factory.complete_run(
            pinned_run_id,
            GenerationRunCompleteRequest(
                status=terminal,
                processed_count=stats.attempted,
                success_count=stats.created,
                failure_count=stats.attempted - stats.created,
                error_summary=stats.stop_reason,
                error_code=stats.stop_reason,
                execution_metadata={
                    "stats": {
                        "requested": stats.requested,
                        "attempted": stats.attempted,
                        "created": stats.created,
                        "rejected_validation": stats.rejected_validation,
                        "duplicate": stats.duplicate,
                        "diversity_rejected": stats.diversity_rejected,
                        "failed_provider": stats.failed_provider,
                        "failed_parse": stats.failed_parse,
                        "cost_usd": round(stats.cost_usd, 6),
                        "models": stats.models,
                        "providers": stats.providers,
                        "stop_reason": stats.stop_reason,
                    },
                    "prompt_version": PROMPT_VERSION,
                    "generator_version": GENERATOR_VERSION,
                    "routing_policy": stats.routing_policy,
                    "provider_attempts": stats.provider_attempts,
                },
            ),
            actor_id=actor_id,
            **ctx,
        )

        # Refresh batch counters from DB
        batch = await self.factory_repo.get_batch(batch_id)
        assert batch is not None
        await self.session.commit()

        self._audit(
            actor_id=actor_id,
            action="factory.generation.completed",
            entity_type="generation_run",
            entity_id=pinned_run_id,
            metadata={
                "batch_id": str(batch_id),
                "job_id": str(pinned_job_id),
                "blueprint_id": str(blueprint_id),
                "blueprint_version": pinned_bp_version,
                "created": stats.created,
                "requested": stats.requested,
                "stop_reason": stats.stop_reason,
                "cost_usd": round(stats.cost_usd, 6),
            },
            **ctx,
        )
        await self.session.commit()

        return {
            "batch_id": str(batch_id),
            "job_id": str(pinned_job_id),
            "run_id": str(pinned_run_id),
            "blueprint_id": str(blueprint_id),
            "blueprint_version": pinned_bp_version,
            "prompt_version": PROMPT_VERSION,
            "generator_version": GENERATOR_VERSION,
            "status": terminal,
            "note": "All created questions are DRAFT only — not submitted, approved, or published",
            **stats.__dict__,
        }

    async def _execute_run(
        self,
        *,
        batch: ContentBatch,
        job: GenerationJob,
        run: GenerationRun,
        blueprint: QuestionBlueprint,
        target_count: int,
        actor_id: uuid.UUID,
        **ctx,
    ) -> GenerationStats:
        stats = GenerationStats(requested=target_count)
        stats.routing_policy = self.gateway.routing_policy.describe()
        max_attempts = max(target_count, int(target_count * settings.factory_max_pilot_attempt_multiplier))
        max_cost = settings.factory_max_pilot_cost_usd
        ctx_data = await self._load_context(blueprint)
        known_hashes = await self._existing_stem_hashes(blueprint.concept_id)
        prior_stems = await self._batch_created_stems(batch.id)

        # Snapshot IDs/fields before any commit expires ORM state.
        bp_id = blueprint.id
        bp_version = blueprint.blueprint_version
        bp_concept_id = blueprint.concept_id
        bp_difficulty = blueprint.difficulty
        bp_constraints = dict(blueprint.constraints or {})
        batch_id = batch.id
        job_id = job.id
        run_id = run.id

        # Mark run/job running
        now = datetime.now(UTC)
        run.status = "RUNNING"
        run.started_at = now
        job.status = "RUNNING"
        if job.started_at is None:
            job.started_at = now
        if batch.status == "CREATED":
            batch.status = "GENERATING"
        await self.session.commit()

        attempt = 0
        while stats.created < target_count and attempt < max_attempts:
            if stats.cost_usd >= max_cost:
                stats.stop_reason = "BUDGET_EXCEEDED"
                break

            attempt += 1
            stats.attempted += 1
            candidate = GenerationCandidate(
                batch_id=batch_id,
                job_id=job_id,
                run_id=run_id,
                blueprint_id=bp_id,
                blueprint_version=bp_version,
                concept_id=bp_concept_id,
                attempt_no=attempt,
                status="FAILED_PARSE",
                prompt_version=PROMPT_VERSION,
                generator_version=GENERATOR_VERSION,
                routing_policy=stats.routing_policy,
                created_by=actor_id,
                updated_by=actor_id,
                version=1,
            )
            self.session.add(candidate)
            await self.session.flush()

            user_prompt = build_user_prompt(
                subject_name=ctx_data["subject_name"],
                chapter_name=ctx_data["chapter_name"],
                topic_name=ctx_data["topic_name"],
                concept_name=ctx_data["concept_name"],
                concept_summary=ctx_data["concept_summary"],
                objective_title=ctx_data["objective_title"],
                objective_description=ctx_data["objective_description"],
                family_name=ctx_data["family_name"],
                family_intent=ctx_data["family_intent"],
                difficulty=bp_difficulty,
                constraints=bp_constraints,
                provenance_note="ai",
                prior_stems=format_prior_stems_for_prompt(prior_stems),
            )

            try:
                response: AIResponse = await self.gateway.generate(
                    agent_type=AGENT_TYPE,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    user_id=actor_id,
                    max_tokens=1200,
                    generation_run_id=str(run_id),
                    blueprint_id=str(bp_id),
                    blueprint_version=bp_version,
                    prompt_version=PROMPT_VERSION,
                    require_json=True,
                    correlation_id=str(candidate.id),
                )
            except ProviderError as exc:
                attempts = getattr(exc, "attempts", None) or [
                    {
                        "attempt_no": 1,
                        "provider": exc.provider,
                        "status": exc.code,
                        "error_code": exc.code,
                        "error_message": str(exc)[:300],
                    }
                ]
                stats.provider_attempts.extend(attempts)
                candidate.status = "FAILED_PROVIDER"
                candidate.error_code = exc.code
                candidate.error_summary = str(exc)[:500]
                candidate.provider = exc.provider
                candidate.routing_policy = getattr(exc, "routing_policy", None) or stats.routing_policy
                stats.failed_provider += 1
                await self.session.commit()
                if exc.code in {PROVIDER_BLOCKED, PROVIDER_AUTH_FAILED} or not exc.retryable:
                    stats.stop_reason = exc.code
                    break
                continue
            except Exception as exc:  # noqa: BLE001
                candidate.status = "FAILED_PROVIDER"
                candidate.error_code = "PROVIDER_ERROR"
                candidate.error_summary = str(exc)[:500]
                stats.failed_provider += 1
                await self.session.commit()
                msg = str(exc).lower()
                if any(
                    token in msg
                    for token in (
                        "credit balance is too low",
                        "invalid api key",
                        "authentication",
                        "permission",
                        "401",
                        "403",
                    )
                ):
                    stats.stop_reason = PROVIDER_BLOCKED
                    break
                continue

            for att in (response.safe_metadata or {}).get("provider_attempts") or []:
                stats.provider_attempts.append(att)

            # Fail closed: unknown cost cannot safely enforce budget
            if (response.cost_status or "").upper() == "UNAVAILABLE" and not response.is_fallback:
                candidate.status = "FAILED_BUDGET"
                candidate.error_code = PROVIDER_COST_UNKNOWN
                candidate.error_summary = "Provider cost unavailable — budget fail-closed"
                candidate.provider = response.provider
                candidate.model_used = response.model
                candidate.cost_status = response.cost_status
                candidate.routing_policy = response.routing_policy or stats.routing_policy
                candidate.provider_attempt_no = response.provider_attempt_no
                candidate.provider_request_id = response.provider_request_id
                stats.failed_provider += 1
                await self.session.commit()
                stats.stop_reason = PROVIDER_COST_UNKNOWN
                break

            estimated_next = stats.cost_usd + float(response.cost_usd or 0.0)
            if estimated_next > max_cost and stats.created == 0 and float(response.cost_usd or 0) > max_cost:
                candidate.status = "FAILED_BUDGET"
                candidate.error_code = "BUDGET_EXCEEDED"
                candidate.error_summary = "Single-call estimate exceeds pilot cost cap"
                candidate.provider = response.provider
                candidate.model_used = response.model
                candidate.cost_usd = response.cost_usd
                candidate.cost_status = response.cost_status
                stats.failed_provider += 1
                await self.session.commit()
                stats.stop_reason = "BUDGET_EXCEEDED"
                break

            stats.cost_usd += response.cost_usd or 0.0
            candidate.model_used = response.model
            candidate.provider = response.provider
            candidate.cost_usd = response.cost_usd
            candidate.cost_status = response.cost_status
            candidate.is_fallback = bool(response.is_fallback)
            candidate.routing_policy = response.routing_policy or stats.routing_policy
            candidate.provider_attempt_no = response.provider_attempt_no
            candidate.provider_request_id = response.provider_request_id
            candidate.generator_version = GENERATOR_VERSION
            stats.models[response.model] = stats.models.get(response.model, 0) + 1
            stats.providers[response.provider] = stats.providers.get(response.provider, 0) + 1

            if response.is_fallback:
                # FallbackProvider is not a real MCQ generator — treat as provider failure.
                candidate.status = "FAILED_PROVIDER"
                candidate.error_code = "FALLBACK_NOT_ALLOWED"
                candidate.error_summary = "Fallback provider cannot produce pilot MCQs"
                stats.failed_provider += 1
                await self.session.commit()
                stats.stop_reason = "FALLBACK_PROVIDER"
                break

            try:
                raw_body = parse_mcq_json(response.text)
            except (ValueError, json.JSONDecodeError) as exc:
                candidate.status = "FAILED_PARSE"
                candidate.error_code = "MALFORMED_JSON"
                # Include finish_reason when present (sanitized; no raw model body / secrets).
                fr = (response.finish_reason or "").strip()
                summary = str(exc)[:500]
                if fr:
                    summary = f"finishReason={fr}: {summary}"[:500]
                candidate.error_summary = summary
                stats.failed_parse += 1
                await self.session.commit()
                continue

            # Force blueprint difficulty (do not silently accept wrong difficulty)
            raw_body["difficulty"] = bp_difficulty
            # Seed V2: attach deterministic visual when blueprint requires it (not NCERT evidence).
            if bp_constraints.get("visual_required"):
                from app.modules.cms.services.factory_v2_visual import attach_visual_to_body

                raw_body = attach_visual_to_body(raw_body, constraints=bp_constraints)
            validated, verrs = validate_candidate_body(
                raw_body, expected_difficulty=bp_difficulty, constraints=bp_constraints
            )
            if verrs or not validated:
                candidate.status = "REJECTED_VALIDATION"
                candidate.error_code = ",".join(verrs) if verrs else "VALIDATION_FAILED"
                candidate.error_summary = candidate.error_code
                stats.rejected_validation += 1
                await self.session.commit()
                continue

            h = stem_hash(validated["stem"])
            candidate.stem_hash = h
            if h in known_hashes:
                candidate.status = "REJECTED_DUPLICATE"
                candidate.error_code = "DUPLICATE_STEM"
                stats.duplicate += 1
                await self.session.commit()
                continue

            existing_created = (
                await self.session.execute(
                    select(GenerationCandidate.id).where(
                        GenerationCandidate.concept_id == bp_concept_id,
                        GenerationCandidate.stem_hash == h,
                        GenerationCandidate.status == "CREATED",
                        GenerationCandidate.deleted_at.is_(None),
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if existing_created:
                candidate.status = "REJECTED_DUPLICATE"
                candidate.error_code = "DUPLICATE_STEM"
                stats.duplicate += 1
                known_hashes.add(h)
                await self.session.commit()
                continue

            # C remediation: prior-stem / forbidden-template diversity (seed / explicit opt-in only)
            enforce_div = bool(
                bp_constraints.get("seed_slot_id") or bp_constraints.get("enforce_prior_stem_diversity")
            )
            if enforce_div:
                opt_texts = [str(o.get("text", "")) for o in (validated.get("options") or [])]
                _div_label, div_code = classify_against_prior(
                    stem=validated["stem"],
                    option_texts=opt_texts,
                    prior_stems=prior_stems,
                    reject_forbidden_templates=bool(bp_constraints.get("forbidden_templates")),
                )
                if div_code:
                    candidate.status = "REJECTED_VALIDATION"
                    candidate.error_code = div_code
                    candidate.error_summary = f"{_div_label}:{div_code}"
                    stats.diversity_rejected += 1
                    stats.rejected_validation += 1
                    await self.session.commit()
                    continue

            title = self._safe_title(validated["stem"], bp_difficulty)
            slug = f"factory-p3-{uuid.uuid4().hex[:12]}"
            tags = [
                "factory-p3",
                f"batch:{batch_id}",
                f"job:{job_id}",
                f"run:{run_id}",
                f"blueprint:{bp_id}",
                f"bp-v:{bp_version}",
                f"family:{ctx_data['family_key']}",
                f"provider:{response.provider}",
                f"model:{response.model}",
                f"routing:{response.routing_policy or stats.routing_policy}",
                "provenance:ai",
            ]
            try:
                item = await self.workflow.create_item(
                    content_type="QUESTION",
                    concept_id=bp_concept_id,
                    title=title,
                    slug=slug,
                    tags=tags,
                    language="en",
                    body=validated,
                    author_id=actor_id,
                    model_used=response.model,
                    prompt_version=PROMPT_VERSION,
                    confidence_score=None,
                    generation_cost_usd=response.cost_usd,
                    commit=False,
                )
                if item.status != "DRAFT":
                    raise AppError(
                        "Factory generation produced non-DRAFT item",
                        code="SAFETY_VIOLATION",
                        status_code=500,
                    )
                candidate.status = "CREATED"
                candidate.content_item_id = item.id
                live_batch = await self.session.get(ContentBatch, batch_id)
                if live_batch is not None:
                    live_batch.created_count = (live_batch.created_count or 0) + 1
                await self.session.flush()
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                stats.duplicate += 1
                known_hashes.add(h)
                continue
            except Exception as exc:  # noqa: BLE001
                await self.session.rollback()
                # Recreate failed attempt marker without orphan content
                failed = GenerationCandidate(
                    batch_id=batch_id,
                    job_id=job_id,
                    run_id=run_id,
                    blueprint_id=bp_id,
                    blueprint_version=bp_version,
                    concept_id=bp_concept_id,
                    attempt_no=attempt,
                    status="REJECTED_VALIDATION",
                    stem_hash=h,
                    error_code="CREATE_FAILED",
                    error_summary=str(exc)[:500],
                    model_used=response.model,
                    provider=response.provider,
                    prompt_version=PROMPT_VERSION,
                    generator_version=GENERATOR_VERSION,
                    cost_usd=response.cost_usd,
                    cost_status=response.cost_status,
                    routing_policy=response.routing_policy or stats.routing_policy,
                    provider_attempt_no=response.provider_attempt_no,
                    is_fallback=bool(response.is_fallback),
                    created_by=actor_id,
                    updated_by=actor_id,
                    version=1,
                )
                self.session.add(failed)
                stats.rejected_validation += 1
                await self.session.commit()
                continue
            known_hashes.add(h)
            prior_stems.append(validated["stem"])
            stats.created += 1
            stats.content_item_ids.append(str(item.id))
            logger.info(
                "factory_question_created",
                item_id=str(item.id),
                run_id=str(run_id),
                attempt=attempt,
                provider=response.provider,
                model=response.model,
            )

        if stats.created >= target_count:
            stats.stop_reason = "TARGET_MET"
        elif stats.stop_reason is None:
            stats.stop_reason = "ATTEMPT_LIMIT" if attempt >= max_attempts else "SHORTFALL"

        return stats

    @staticmethod
    def _safe_title(stem: str, difficulty: str) -> str:
        clean = re.sub(r"\s+", " ", stem).strip()
        if len(clean) > 80:
            clean = clean[:77] + "..."
        return f"[{difficulty}] {clean}"
