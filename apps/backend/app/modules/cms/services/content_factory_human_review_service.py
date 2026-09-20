"""FACTORY-P5 human sampling / exception review — no ECAEP auto-transitions.

Regeneration deferred: CORRECTION_REQUIRED links to existing CMS edit workflow only.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.cms.models.content_factory_planning import QuestionBlueprint
from app.modules.cms.models.content_item import ContentItem
from app.modules.cms.models.content_version import ContentVersion
from app.modules.cms.models.factory_qa import (
    FACTORY_FAILURE_REASONS,
    FACTORY_HUMAN_CHECKLIST,
    FACTORY_REVIEW_DECISIONS,
    FactoryReviewItem,
    QAResult,
    ReviewSample,
)
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.repositories.content_factory_planning_repository import ContentFactoryPlanningRepository
from app.modules.cms.repositories.content_factory_repository import ContentFactoryRepository
from app.modules.system.models.audit_log import AuditLog
from app.modules.system.repositories.audit_repository import AuditRepository

logger = get_logger("content_factory_human_review")


class ContentFactoryHumanReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.factory_repo = ContentFactoryRepository(session)
        self.planning_repo = ContentFactoryPlanningRepository(session)
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

    async def materialize_sample_items(
        self,
        sample: ReviewSample,
        *,
        actor_id: uuid.UUID | None,
    ) -> list[FactoryReviewItem]:
        """Create FactoryReviewItem rows from ReviewSample arrays (idempotent)."""
        existing = {
            r.candidate_id: r
            for r in (
                await self.session.execute(
                    select(FactoryReviewItem).where(
                        FactoryReviewItem.sample_id == sample.id,
                        FactoryReviewItem.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
        }
        created: list[FactoryReviewItem] = []
        plans: list[tuple[uuid.UUID, str]] = []
        for cid in sample.selected_candidate_ids or []:
            plans.append((cid, "GREEN_SAMPLE"))
        for cid in sample.yellow_candidate_ids or []:
            plans.append((cid, "YELLOW"))
        for cid in sample.red_candidate_ids or []:
            plans.append((cid, "RED"))

        reasons = sample.selection_reasons or {}
        for candidate_id, selection_class in plans:
            if candidate_id in existing:
                created.append(existing[candidate_id])
                continue
            cand = (
                await self.session.execute(
                    select(GenerationCandidate).where(
                        GenerationCandidate.id == candidate_id,
                        GenerationCandidate.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if not cand:
                continue
            qa = None
            if cand.latest_qa_result_id:
                qa = (
                    await self.session.execute(
                        select(QAResult).where(QAResult.id == cand.latest_qa_result_id)
                    )
                ).scalar_one_or_none()
            item = FactoryReviewItem(
                sample_id=sample.id,
                batch_id=sample.batch_id,
                candidate_id=candidate_id,
                content_item_id=cand.content_item_id,
                qa_result_id=qa.id if qa else cand.latest_qa_result_id,
                qa_version=qa.qa_version if qa else None,
                policy_version=sample.policy_version,
                selection_class=selection_class,
                selection_reason=reasons.get(str(candidate_id)),
                review_status="SELECTED",
                checklist={},
                failure_reasons=[],
                created_by=actor_id,
                updated_by=actor_id,
                version=1,
            )
            self.session.add(item)
            await self.session.flush()
            cand.factory_review_status = "SELECTED"
            cand.latest_factory_review_item_id = item.id
            # RED remains quarantined at factory QA layer
            if selection_class == "RED" and not cand.qa_quarantined:
                cand.qa_quarantined = True
            existing[candidate_id] = item
            created.append(item)
        await self.session.flush()
        return created

    async def ensure_sample_materialized(self, sample_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> ReviewSample:
        sample = (
            await self.session.execute(
                select(ReviewSample).where(ReviewSample.id == sample_id, ReviewSample.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if not sample:
            raise NotFoundError("Review sample not found")
        await self.materialize_sample_items(sample, actor_id=actor_id)
        await self.session.commit()
        return sample

    async def dashboard(self, batch_id: uuid.UUID | None = None) -> dict[str, Any]:
        filters = [GenerationCandidate.status == "CREATED", GenerationCandidate.deleted_at.is_(None)]
        if batch_id:
            filters.append(GenerationCandidate.batch_id == batch_id)

        class_rows = (
            await self.session.execute(
                select(GenerationCandidate.qa_classification, func.count())
                .where(*filters)
                .group_by(GenerationCandidate.qa_classification)
            )
        ).all()
        qa_counts = {c or "UNCLASSIFIED": n for c, n in class_rows}

        item_filters = [FactoryReviewItem.deleted_at.is_(None)]
        if batch_id:
            item_filters.append(FactoryReviewItem.batch_id == batch_id)

        rows = (
            await self.session.execute(
                select(
                    FactoryReviewItem.selection_class,
                    FactoryReviewItem.review_status,
                    func.count(),
                )
                .where(*item_filters)
                .group_by(FactoryReviewItem.selection_class, FactoryReviewItem.review_status)
            )
        ).all()

        metrics: dict[str, Any] = {
            "total_candidates": sum(qa_counts.values()),
            "GREEN": qa_counts.get("GREEN", 0),
            "YELLOW": qa_counts.get("YELLOW", 0),
            "RED": qa_counts.get("RED", 0),
            "green_sampled": 0,
            "green_reviewed": 0,
            "green_accepted": 0,
            "green_rejected": 0,
            "green_correction_required": 0,
            "green_pending": 0,
            "yellow_total_in_queue": 0,
            "yellow_reviewed": 0,
            "yellow_accepted": 0,
            "yellow_rejected": 0,
            "yellow_correction_required": 0,
            "yellow_pending": 0,
            "red_total_in_queue": 0,
            "red_reviewed": 0,
            "red_accepted": 0,
            "red_rejected": 0,
            "red_correction_required": 0,
            "red_pending": 0,
            "disclaimer": "Counts are factory human-review progress — not scientific accuracy of the batch.",
        }

        prefix = {"GREEN_SAMPLE": "green", "YELLOW": "yellow", "RED": "red"}
        for sel, status, n in rows:
            b = prefix.get(sel)
            if not b:
                continue
            total_key = "green_sampled" if b == "green" else f"{b}_total_in_queue"
            metrics[total_key] = metrics.get(total_key, 0) + n
            if status in {"SELECTED", "IN_REVIEW"}:
                metrics[f"{b}_pending"] += n
            if status in {"ACCEPTED", "REJECTED", "CORRECTION_REQUIRED"}:
                metrics[f"{b}_reviewed"] += n
            if status == "ACCEPTED":
                metrics[f"{b}_accepted"] += n
            elif status == "REJECTED":
                metrics[f"{b}_rejected"] += n
            elif status == "CORRECTION_REQUIRED":
                metrics[f"{b}_correction_required"] += n

        reason_counts: dict[str, int] = {}
        reason_rows = (
            await self.session.execute(
                select(FactoryReviewItem.failure_reasons)
                .where(*item_filters, FactoryReviewItem.decision.is_not(None))
                .limit(5000)
            )
        ).scalars().all()
        for reasons in reason_rows:
            for r in reasons or []:
                reason_counts[r] = reason_counts.get(r, 0) + 1

        return {
            **metrics,
            "failure_reason_counts": reason_counts,
            "batch_id": str(batch_id) if batch_id else None,
            "checklist_template": list(FACTORY_HUMAN_CHECKLIST),
            "failure_reason_taxonomy": list(FACTORY_FAILURE_REASONS),
        }

    async def list_queue(
        self,
        *,
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
        sort: str = "risk",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = min(max(limit, 1), 200)
        filters = [FactoryReviewItem.deleted_at.is_(None)]
        if batch_id:
            filters.append(FactoryReviewItem.batch_id == batch_id)
        if selection_class:
            filters.append(FactoryReviewItem.selection_class == selection_class.upper())
        if review_status:
            filters.append(FactoryReviewItem.review_status == review_status.upper())
        if needs_review:
            filters.append(FactoryReviewItem.review_status.in_(["SELECTED", "IN_REVIEW"]))

        q = (
            select(FactoryReviewItem, GenerationCandidate, ContentItem, QAResult, QuestionBlueprint)
            .join(GenerationCandidate, GenerationCandidate.id == FactoryReviewItem.candidate_id)
            .outerjoin(ContentItem, ContentItem.id == FactoryReviewItem.content_item_id)
            .outerjoin(QAResult, QAResult.id == FactoryReviewItem.qa_result_id)
            .outerjoin(QuestionBlueprint, QuestionBlueprint.id == GenerationCandidate.blueprint_id)
            .where(*filters)
        )
        if subject_id:
            q = q.where(QuestionBlueprint.subject_id == subject_id)
        if chapter_id:
            q = q.where(QuestionBlueprint.chapter_id == chapter_id)
        if difficulty:
            q = q.where(QuestionBlueprint.difficulty == difficulty)
        if blueprint_id:
            q = q.where(GenerationCandidate.blueprint_id == blueprint_id)
        if model:
            q = q.where(GenerationCandidate.model_used == model)
        if prompt_version:
            q = q.where(GenerationCandidate.prompt_version == prompt_version)

        risk_order = case(
            (FactoryReviewItem.selection_class == "RED", 0),
            (FactoryReviewItem.selection_class == "YELLOW", 1),
            else_=2,
        )
        if sort == "newest":
            q = q.order_by(FactoryReviewItem.created_at.desc())
        elif sort == "oldest":
            q = q.order_by(FactoryReviewItem.created_at.asc())
        elif sort == "priority":
            q = q.order_by(risk_order, FactoryReviewItem.created_at.asc())
        else:
            q = q.order_by(risk_order, FactoryReviewItem.created_at.asc())

        count_base = (
            select(func.count(FactoryReviewItem.id))
            .select_from(FactoryReviewItem)
            .join(GenerationCandidate, GenerationCandidate.id == FactoryReviewItem.candidate_id)
            .outerjoin(QuestionBlueprint, QuestionBlueprint.id == GenerationCandidate.blueprint_id)
            .where(*filters)
        )
        if subject_id:
            count_base = count_base.where(QuestionBlueprint.subject_id == subject_id)
        if chapter_id:
            count_base = count_base.where(QuestionBlueprint.chapter_id == chapter_id)
        if difficulty:
            count_base = count_base.where(QuestionBlueprint.difficulty == difficulty)
        if blueprint_id:
            count_base = count_base.where(GenerationCandidate.blueprint_id == blueprint_id)
        if model:
            count_base = count_base.where(GenerationCandidate.model_used == model)
        if prompt_version:
            count_base = count_base.where(GenerationCandidate.prompt_version == prompt_version)
        total = (await self.session.execute(count_base)).scalar_one()
        rows = (await self.session.execute(q.limit(limit).offset(offset))).all()

        items = []
        for fri, cand, item, qa, bp in rows:
            items.append(
                {
                    "factory_review_item_id": str(fri.id),
                    "sample_id": str(fri.sample_id),
                    "candidate_id": str(fri.candidate_id),
                    "content_item_id": str(fri.content_item_id) if fri.content_item_id else None,
                    "batch_id": str(fri.batch_id),
                    "selection_class": fri.selection_class,
                    "selection_reason": fri.selection_reason,
                    "review_status": fri.review_status,
                    "decision": fri.decision,
                    "qa_classification": cand.qa_classification or (qa.classification if qa else None),
                    "quarantine": bool(cand.qa_quarantined or (qa.quarantine if qa else False)),
                    "title": item.title if item else None,
                    "ecaep_status": item.status if item else None,
                    "difficulty": bp.difficulty if bp else None,
                    "blueprint_id": str(cand.blueprint_id),
                    "blueprint_version": cand.blueprint_version,
                    "model_used": cand.model_used,
                    "provider": cand.provider,
                    "prompt_version": cand.prompt_version,
                    "routing_policy": cand.routing_policy,
                    "failed_checks": qa.failed_checks if qa else [],
                    "duplicate_class": qa.duplicate_class if qa else None,
                    "disclaimer": "Automated QA — NOT scientific certification",
                }
            )
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "sort": sort,
            "note": "Factory review queue — ACCEPT does not approve or publish",
        }

    async def get_review_packet(self, factory_review_item_id: uuid.UUID) -> dict[str, Any]:
        fri = (
            await self.session.execute(
                select(FactoryReviewItem).where(
                    FactoryReviewItem.id == factory_review_item_id,
                    FactoryReviewItem.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not fri:
            raise NotFoundError("Factory review item not found")

        cand = (
            await self.session.execute(
                select(GenerationCandidate).where(GenerationCandidate.id == fri.candidate_id)
            )
        ).scalar_one_or_none()
        if not cand:
            raise NotFoundError("Candidate not found")

        item = None
        version = None
        if fri.content_item_id:
            item = (
                await self.session.execute(select(ContentItem).where(ContentItem.id == fri.content_item_id))
            ).scalar_one_or_none()
            if item and item.latest_version_id:
                version = (
                    await self.session.execute(
                        select(ContentVersion).where(ContentVersion.id == item.latest_version_id)
                    )
                ).scalar_one_or_none()

        qa = None
        if fri.qa_result_id:
            qa = (await self.session.execute(select(QAResult).where(QAResult.id == fri.qa_result_id))).scalar_one_or_none()

        bp = await self.planning_repo.get_blueprint(cand.blueprint_id)
        family = None
        objective = None
        academic = None
        if bp:
            family = bp.question_family or await self.planning_repo.get_family(bp.question_family_id)
            objective = bp.learning_objective or await self.planning_repo.get_objective(bp.learning_objective_id)
            concept = (
                await self.session.execute(
                    select(Concept)
                    .options(selectinload(Concept.topic).selectinload(Topic.chapter).selectinload(Chapter.subject))
                    .where(Concept.id == bp.concept_id)
                )
            ).scalar_one_or_none()
            if concept:
                academic = {
                    "subject": concept.topic.chapter.subject.name,
                    "chapter": concept.topic.chapter.name,
                    "topic": concept.topic.name,
                    "concept": concept.name,
                }

        body = version.body if version and isinstance(version.body, dict) else {}
        sample = (
            await self.session.execute(select(ReviewSample).where(ReviewSample.id == fri.sample_id))
        ).scalar_one_or_none()

        # Mark opened → IN_REVIEW if still SELECTED (does not touch ECAEP)
        if fri.review_status == "SELECTED":
            fri.review_status = "IN_REVIEW"
            cand.factory_review_status = "IN_REVIEW"
            await self.session.commit()

        return {
            "factory_review_item_id": str(fri.id),
            "selection_class": fri.selection_class,
            "selection_reason": fri.selection_reason,
            "review_status": fri.review_status,
            "decision": fri.decision,
            "reviewer_note": fri.reviewer_note,
            "checklist": fri.checklist or {},
            "failure_reasons": fri.failure_reasons or [],
            "ecaep_submit_eligible": fri.ecaep_submit_eligible,
            "policy_version": fri.policy_version,
            "sample": {
                "id": str(sample.id) if sample else None,
                "sample_key": sample.sample_key if sample else None,
                "seed": sample.seed if sample else None,
                "policy_version": sample.policy_version if sample else None,
                "strata_summary": sample.strata_summary if sample else {},
            },
            "question": {
                "stem": body.get("stem"),
                "options": body.get("options"),
                "correct_option": body.get("correct_option"),
                "explanation": body.get("explanation"),
                "difficulty": body.get("difficulty"),
            },
            "academic_mapping": {
                **(academic or {}),
                "learning_objective": objective.title if objective else None,
                "question_family": family.name if family else None,
                "blueprint_id": str(cand.blueprint_id),
                "blueprint_version": cand.blueprint_version,
                "blueprint_key": bp.blueprint_key if bp else None,
            },
            "generation_lineage": {
                "batch_id": str(cand.batch_id),
                "job_id": str(cand.job_id),
                "run_id": str(cand.run_id),
                "provider": cand.provider,
                "model_used": cand.model_used or (version.model_used if version else None),
                "prompt_version": cand.prompt_version or (version.prompt_version if version else None),
                "generator_version": cand.generator_version,
                "routing_policy": cand.routing_policy,
                "provider_attempt_no": cand.provider_attempt_no,
                "cost_status": cand.cost_status,
                "is_fallback": cand.is_fallback,
                "provenance": "ai",
                "content_item_id": str(fri.content_item_id) if fri.content_item_id else None,
                "ecaep_status": item.status if item else None,
            },
            "automated_qa": {
                "label": "Automated QA — NOT scientific certification",
                "classification": qa.classification if qa else cand.qa_classification,
                "qa_version": qa.qa_version if qa else fri.qa_version,
                "gate_results": qa.gate_results if qa else {},
                "failed_checks": qa.failed_checks if qa else [],
                "warnings": qa.warnings if qa else [],
                "duplicate_class": qa.duplicate_class if qa else None,
                "duplicate_of_item_ids": [str(x) for x in (qa.duplicate_of_item_ids or [])] if qa else [],
                "quarantine": qa.quarantine if qa else cand.qa_quarantined,
                "scientific_certification": False,
            },
            "human_checklist_template": list(FACTORY_HUMAN_CHECKLIST),
            "allowed_decisions": list(FACTORY_REVIEW_DECISIONS),
            "failure_reason_taxonomy": list(FACTORY_FAILURE_REASONS),
            "ecaep_note": (
                "Factory ACCEPT marks ecaep_submit_eligible only. "
                "Use normal CMS submit (DRAFT→IN_REVIEW) separately — no bypass."
            ),
            "regeneration": "DEFERRED — use CMS edit for corrections; do not overwrite historical candidates",
            "disclaimer": fri.disclaimer,
        }

    async def submit_decision(
        self,
        factory_review_item_id: uuid.UUID,
        *,
        decision: str,
        actor_id: uuid.UUID,
        checklist: dict[str, bool] | None = None,
        failure_reasons: list[str] | None = None,
        reviewer_note: str | None = None,
        **ctx,
    ) -> dict[str, Any]:
        decision = decision.strip().upper()
        if decision not in FACTORY_REVIEW_DECISIONS:
            raise AppError(
                f"decision must be one of {FACTORY_REVIEW_DECISIONS}",
                code="VALIDATION_ERROR",
                status_code=422,
            )

        fri = (
            await self.session.execute(
                select(FactoryReviewItem).where(
                    FactoryReviewItem.id == factory_review_item_id,
                    FactoryReviewItem.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not fri:
            raise NotFoundError("Factory review item not found")

        if decision in {"CORRECTION_REQUIRED", "REJECT"} and not (reviewer_note or "").strip():
            raise AppError(
                "reviewer_note is required for CORRECTION_REQUIRED and REJECT",
                code="VALIDATION_ERROR",
                status_code=422,
            )

        reasons = list(failure_reasons or [])
        for r in reasons:
            if r not in FACTORY_FAILURE_REASONS:
                raise AppError(f"Unknown failure reason: {r}", code="VALIDATION_ERROR", status_code=422)

        fri.decision = decision
        fri.review_status = decision  # ACCEPTED / CORRECTION_REQUIRED / REJECTED aligned
        if decision == "ACCEPT":
            fri.review_status = "ACCEPTED"
        fri.reviewer_id = actor_id
        fri.reviewed_at = datetime.now(UTC)
        fri.reviewer_note = (reviewer_note or "").strip() or None
        fri.checklist = checklist or {}
        fri.failure_reasons = reasons
        fri.ecaep_submit_eligible = decision == "ACCEPT"
        fri.updated_by = actor_id

        cand = (
            await self.session.execute(
                select(GenerationCandidate).where(GenerationCandidate.id == fri.candidate_id)
            )
        ).scalar_one_or_none()
        if cand:
            cand.factory_review_status = fri.review_status
            cand.latest_factory_review_item_id = fri.id
            # Never mutate ContentItem.status here

        if fri.content_item_id:
            item = (
                await self.session.execute(select(ContentItem).where(ContentItem.id == fri.content_item_id))
            ).scalar_one_or_none()
            if item and item.status != "DRAFT":
                # Safety: refuse to claim eligibility weirdness but still record factory decision
                logger.warning(
                    "factory_review_non_draft_item",
                    item_id=str(item.id),
                    status=item.status,
                )

        action = {
            "ACCEPT": "factory.review.accepted",
            "CORRECTION_REQUIRED": "factory.review.correction_required",
            "REJECT": "factory.review.rejected",
        }[decision]
        self._audit(
            actor_id=actor_id,
            action=action,
            entity_type="factory_review_item",
            entity_id=fri.id,
            metadata={
                "candidate_id": str(fri.candidate_id),
                "batch_id": str(fri.batch_id),
                "qa_result_id": str(fri.qa_result_id) if fri.qa_result_id else None,
                "sample_id": str(fri.sample_id),
                "selection_class": fri.selection_class,
                "decision": decision,
                "failure_reasons": reasons,
                "policy_version": fri.policy_version,
                "ecaep_status_unchanged": True,
            },
            **ctx,
        )
        await self.session.commit()
        return {
            "factory_review_item_id": str(fri.id),
            "decision": fri.decision,
            "review_status": fri.review_status,
            "ecaep_submit_eligible": fri.ecaep_submit_eligible,
            "content_item_id": str(fri.content_item_id) if fri.content_item_id else None,
            "note": "ECAEP status unchanged — use CMS submit/approve/publish separately if eligible",
        }
