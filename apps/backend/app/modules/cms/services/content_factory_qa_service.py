"""FACTORY-P4 automated QA orchestration — DRAFT only, no ECAEP transitions."""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.cms.models.content_factory import ContentBatch
from app.modules.cms.models.content_factory_planning import QuestionBlueprint
from app.modules.cms.models.content_item import ContentItem
from app.modules.cms.models.content_version import ContentVersion
from app.modules.cms.models.factory_qa import QA_VERSION_V1, QAResult, ReviewSample
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.repositories.content_factory_planning_repository import ContentFactoryPlanningRepository
from app.modules.cms.repositories.content_factory_repository import ContentFactoryRepository
from app.modules.cms.schemas.content_factory import GenerationJobCreateRequest, GenerationRunCompleteRequest, GenerationRunCreateRequest
from app.modules.cms.services.content_factory_service import ContentFactoryService
from app.modules.cms.services.factory_candidate_validation import stem_hash
from app.modules.cms.services.factory_dedupe_service import FactoryDedupeService
from app.modules.cms.services.factory_qa_gates import (
    GateOutcome,
    classify_from_gates,
    gate_a_structure,
    gate_e_answer_explanation,
    gate_g_safety,
    option_stem_hash,
)
from app.modules.system.models.audit_log import AuditLog
from app.modules.system.repositories.audit_repository import AuditRepository

logger = get_logger("content_factory_qa")
settings = get_settings()


class ContentFactoryQAService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.factory = ContentFactoryService(session)
        self.factory_repo = ContentFactoryRepository(session)
        self.planning_repo = ContentFactoryPlanningRepository(session)
        self.dedupe = FactoryDedupeService(session)
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

    async def run_batch_qa(
        self,
        batch_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        force_new: bool = False,
        run_id: uuid.UUID | None = None,
        job_key: str | None = None,
        **ctx,
    ) -> dict[str, Any]:
        batch = await self.factory_repo.get_batch(batch_id)
        if not batch:
            raise NotFoundError("Content batch not found")

        qa_version = settings.factory_qa_version or QA_VERSION_V1
        max_n = settings.factory_qa_max_batch_candidates

        filters = [
            GenerationCandidate.batch_id == batch_id,
            GenerationCandidate.status == "CREATED",
            GenerationCandidate.deleted_at.is_(None),
            GenerationCandidate.content_item_id.is_not(None),
        ]
        if run_id:
            filters.append(GenerationCandidate.run_id == run_id)

        total = (
            await self.session.execute(select(func.count(GenerationCandidate.id)).where(*filters))
        ).scalar_one()
        if total > max_n:
            raise AppError(
                f"Batch has {total} CREATED candidates; exceeds QA cap {max_n}",
                code="QA_BATCH_TOO_LARGE",
                status_code=400,
            )

        candidates = list(
            (
                await self.session.execute(
                    select(GenerationCandidate).where(*filters).order_by(GenerationCandidate.created_at)
                )
            ).scalars().all()
        )

        key = job_key or f"qa-{qa_version}-{uuid.uuid4().hex[:10]}"
        job, _ = await self.factory.create_job(
            batch_id,
            GenerationJobCreateRequest(
                job_key=key,
                job_type="VALIDATE",
                requested_count=len(candidates),
                max_retries=1,
            ),
            actor_id=actor_id,
            **ctx,
        )
        qa_run = await self.factory.request_run(
            job.id,
            GenerationRunCreateRequest(
                reason="FACTORY-P4 automated QA",
                execution_metadata={"qa_version": qa_version, "force_new": force_new},
            ),
            actor_id=actor_id,
            **ctx,
        )
        qa_run.status = "RUNNING"
        qa_run.started_at = datetime.now(UTC)
        job.status = "RUNNING"
        if batch.status in {"CREATED", "GENERATING"}:
            batch.status = "QA"
        await self.session.commit()

        self._audit(
            actor_id=actor_id,
            action="factory.qa.started",
            entity_type="generation_run",
            entity_id=qa_run.id,
            metadata={"batch_id": str(batch_id), "qa_version": qa_version, "candidates": len(candidates)},
            **ctx,
        )
        await self.session.commit()

        counters = defaultdict(int)
        results_out: list[dict[str, Any]] = []
        for cand in candidates:
            row = await self.evaluate_candidate(
                cand.id,
                actor_id=actor_id,
                force_new=force_new,
                qa_job_id=job.id,
                qa_run_id=qa_run.id,
                qa_version=qa_version,
                **ctx,
            )
            counters["evaluated"] += 1
            counters[row["classification"]] += 1
            if row["duplicate_class"] in {"EXACT_DUPLICATE", "NORMALIZED_DUPLICATE", "POSSIBLE_DUPLICATE"}:
                counters["duplicate"] += 1
            for code in row.get("failed_checks") or []:
                if code.startswith("A_") or code in {
                    "MISSING_BODY",
                    "EMPTY_STEM",
                    "OPTION_COUNT",
                    "INVALID_ANSWER",
                    "SCHEMA_INVALID",
                    "OPTION_LABELS",
                    "OPTION_TEXTS_UNIQUE",
                    "EMPTY_EXPLANATION",
                    "INVALID_DIFFICULTY",
                }:
                    counters["structural_failures"] += 1
                    break
            gates = row.get("gate_results") or {}
            if gates.get("C_HIERARCHY", {}).get("passed") is False:
                counters["hierarchy_failures"] += 1
            if gates.get("D_PROVENANCE", {}).get("passed") is False:
                counters["provenance_failures"] += 1
            if gates.get("G_SAFETY", {}).get("passed") is False:
                counters["safety_failures"] += 1
            if gates.get("B_BLUEPRINT", {}).get("passed") is False:
                counters["blueprint_failures"] += 1
            results_out.append(
                {
                    "candidate_id": row["candidate_id"],
                    "classification": row["classification"],
                    "duplicate_class": row["duplicate_class"],
                    "qa_result_id": row["qa_result_id"],
                    "idempotent": row.get("idempotent", False),
                }
            )

        green = counters.get("GREEN", 0)
        batch = await self.factory_repo.get_batch(batch_id)
        assert batch is not None
        batch.qa_pass_count = green
        await self.factory.complete_run(
            qa_run.id,
            GenerationRunCompleteRequest(
                status="SUCCEEDED" if candidates else "SUCCEEDED",
                processed_count=counters["evaluated"],
                success_count=green,
                failure_count=counters.get("RED", 0),
                error_summary=None,
                execution_metadata={
                    "qa_version": qa_version,
                    "counters": dict(counters),
                    "note": "AUTOMATED_QA_ONLY — not scientific certification",
                },
            ),
            actor_id=actor_id,
            **ctx,
        )

        self._audit(
            actor_id=actor_id,
            action="factory.qa.completed",
            entity_type="content_batch",
            entity_id=batch_id,
            metadata={
                "qa_run_id": str(qa_run.id),
                "qa_version": qa_version,
                "counters": dict(counters),
                "scientific_certification": False,
            },
            **ctx,
        )
        await self.session.commit()

        return {
            "batch_id": str(batch_id),
            "job_id": str(job.id),
            "run_id": str(qa_run.id),
            "qa_version": qa_version,
            "total_candidates": len(candidates),
            "evaluated": counters["evaluated"],
            "GREEN": counters.get("GREEN", 0),
            "YELLOW": counters.get("YELLOW", 0),
            "RED": counters.get("RED", 0),
            "duplicate": counters.get("duplicate", 0),
            "structural_failures": counters.get("structural_failures", 0),
            "hierarchy_failures": counters.get("hierarchy_failures", 0),
            "provenance_failures": counters.get("provenance_failures", 0),
            "safety_failures": counters.get("safety_failures", 0),
            "blueprint_failures": counters.get("blueprint_failures", 0),
            "disclaimer": "AUTOMATED_QA_ONLY — not scientifically certified; not approved; not publishable",
            "results": results_out,
        }

    async def evaluate_candidate(
        self,
        candidate_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        force_new: bool = False,
        qa_job_id: uuid.UUID | None = None,
        qa_run_id: uuid.UUID | None = None,
        qa_version: str | None = None,
        **ctx,
    ) -> dict[str, Any]:
        qa_version = qa_version or settings.factory_qa_version or QA_VERSION_V1
        cand = (
            await self.session.execute(
                select(GenerationCandidate).where(
                    GenerationCandidate.id == candidate_id,
                    GenerationCandidate.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not cand:
            raise NotFoundError("Generation candidate not found")
        if cand.status != "CREATED" or not cand.content_item_id:
            raise AppError(
                "Only CREATED candidates with content_item_id are QA-eligible",
                code="QA_INELIGIBLE_CANDIDATE",
                status_code=409,
            )

        item = (
            await self.session.execute(
                select(ContentItem).where(ContentItem.id == cand.content_item_id, ContentItem.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if not item:
            raise AppError("Linked content item missing", code="INVALID_REFERENCE", status_code=400)
        if item.status != "DRAFT":
            raise AppError(
                "Factory QA refuses non-DRAFT items (safety)",
                code="QA_NON_DRAFT_REFUSED",
                status_code=409,
            )

        version = None
        if item.latest_version_id:
            version = (
                await self.session.execute(
                    select(ContentVersion).where(ContentVersion.id == item.latest_version_id)
                )
            ).scalar_one_or_none()
        body = version.body if version and isinstance(version.body, dict) else None

        # Idempotency: return latest for same qa_version + content_version unless force_new
        existing = (
            await self.session.execute(
                select(QAResult).where(
                    QAResult.candidate_id == cand.id,
                    QAResult.qa_version == qa_version,
                    QAResult.is_latest.is_(True),
                    QAResult.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing and not force_new:
            if existing.content_version_id == (version.id if version else None):
                return self._serialize_result(existing, idempotent=True)

        gates: list[GateOutcome] = []
        gates.append(gate_a_structure(body))
        gates.append(await self._gate_b_blueprint(cand, item, body))
        gates.append(await self._gate_c_hierarchy(cand, item))
        gates.append(self._gate_d_provenance(cand, version, item))
        gates.append(gate_e_answer_explanation(body))

        if body and body.get("stem"):
            computed_stem = stem_hash(body["stem"])
            cand.option_stem_hash = option_stem_hash(body["stem"], body.get("options") or [])
            if version:
                await self.dedupe.upsert_fingerprint(
                    content_item_id=item.id,
                    content_version_id=version.id,
                    concept_id=item.concept_id,
                    body=body,
                    actor_id=actor_id,
                )
            await self.session.flush()

        finding = await self.dedupe.find_duplicates(candidate=cand, body=body or {}, batch_id=cand.batch_id)
        # Persist stem_hash only when unique — avoids unique-index conflict on CREATED duplicates.
        if body and body.get("stem"):
            computed_stem = stem_hash(body["stem"])
            if finding.duplicate_class == "UNIQUE":
                cand.stem_hash = computed_stem
            elif not cand.stem_hash:
                cand.stem_hash = computed_stem
            await self.session.flush()
        dup_gate = GateOutcome(
            "F_DUPLICATE",
            finding.duplicate_class in {"UNIQUE", "SEMANTIC_UNCHECKED"}
            or finding.duplicate_class == "UNIQUE",
            "RED"
            if finding.duplicate_class in {"EXACT_DUPLICATE", "NORMALIZED_DUPLICATE"}
            else ("YELLOW" if finding.duplicate_class == "POSSIBLE_DUPLICATE" else "INFO"),
            failures=["DUPLICATE"]
            if finding.duplicate_class in {"EXACT_DUPLICATE", "NORMALIZED_DUPLICATE"}
            else [],
            warnings=finding.notes
            + (["POSSIBLE_DUPLICATE"] if finding.duplicate_class == "POSSIBLE_DUPLICATE" else []),
            detail={
                "duplicate_class": finding.duplicate_class,
                "of_item_ids": [str(x) for x in finding.of_item_ids],
                "of_candidate_ids": [str(x) for x in finding.of_candidate_ids],
            },
        )
        # UNIQUE passes; POSSIBLE does not "fail" critically but YELLOW severity
        if finding.duplicate_class == "UNIQUE":
            dup_gate.passed = True
        elif finding.duplicate_class == "POSSIBLE_DUPLICATE":
            dup_gate.passed = False
            dup_gate.severity = "YELLOW"
        else:
            dup_gate.passed = False
        gates.append(dup_gate)
        gates.append(gate_g_safety(body, tags=list(item.tags or [])))

        classification, sampling_eligible, quarantine = classify_from_gates(
            gates, duplicate_class=finding.duplicate_class
        )
        failed = []
        warnings = []
        gate_map: dict[str, Any] = {}
        for g in gates:
            gate_map[g.code] = {
                "passed": g.passed,
                "severity": g.severity,
                "failures": g.failures,
                "warnings": g.warnings,
                "detail": g.detail,
            }
            failed.extend(g.failures)
            warnings.extend(g.warnings)

        eval_no = 1
        if existing:
            if force_new:
                existing.is_latest = False
                eval_no = existing.evaluation_no + 1
            else:
                # version changed — supersede
                existing.is_latest = False
                eval_no = existing.evaluation_no + 1

        result = QAResult(
            candidate_id=cand.id,
            content_item_id=item.id,
            content_version_id=version.id if version else None,
            batch_id=cand.batch_id,
            qa_job_id=qa_job_id,
            qa_run_id=qa_run_id,
            generation_run_id=cand.run_id,
            blueprint_id=cand.blueprint_id,
            blueprint_version=cand.blueprint_version,
            qa_version=qa_version,
            evaluation_no=eval_no,
            is_latest=True,
            classification=classification,
            gate_results=gate_map,
            failed_checks=failed,
            warnings=list(dict.fromkeys(warnings)),
            duplicate_class=finding.duplicate_class
            if finding.duplicate_class != "UNIQUE"
            else "UNIQUE",
            # Always record semantic limitation on UNIQUE path via warnings already
            duplicate_of_item_ids=finding.of_item_ids or None,
            duplicate_of_candidate_ids=finding.of_candidate_ids or None,
            sampling_eligible=sampling_eligible,
            quarantine=quarantine,
            scientific_certification=False,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        # Annotate UNIQUE with semantic limitation warning (does not force YELLOW).
        if finding.duplicate_class == "UNIQUE":
            result.duplicate_class = "UNIQUE"
            extra = [w for w in ("SEMANTIC_UNCHECKED", "SEMANTIC_DEDUPE_NOT_AVAILABLE") if w not in result.warnings]
            if extra:
                result.warnings = list(result.warnings) + extra

        self.session.add(result)
        await self.session.flush()

        cand.qa_classification = classification
        cand.qa_quarantined = quarantine
        cand.latest_qa_result_id = result.id
        cand.updated_by = actor_id

        if quarantine:
            self._audit(
                actor_id=actor_id,
                action="factory.qa.quarantined",
                entity_type="generation_candidate",
                entity_id=cand.id,
                metadata={"classification": classification, "qa_result_id": str(result.id), "qa_version": qa_version},
                **ctx,
            )
        if finding.duplicate_class in {"EXACT_DUPLICATE", "NORMALIZED_DUPLICATE", "POSSIBLE_DUPLICATE"}:
            self._audit(
                actor_id=actor_id,
                action="factory.qa.duplicate_detected",
                entity_type="generation_candidate",
                entity_id=cand.id,
                metadata={"duplicate_class": finding.duplicate_class, "qa_result_id": str(result.id)},
                **ctx,
            )

        await self.session.commit()
        return self._serialize_result(result, idempotent=False)

    async def _gate_b_blueprint(
        self, cand: GenerationCandidate, item: ContentItem, body: dict | None
    ) -> GateOutcome:
        bp = await self.planning_repo.get_blueprint(cand.blueprint_id)
        failures: list[str] = []
        warnings: list[str] = []
        if not bp:
            return GateOutcome("B_BLUEPRINT", False, "RED", failures=["BLUEPRINT_MISSING"])
        if bp.blueprint_version != cand.blueprint_version:
            # Pin mismatch — historical pin vs current row version
            if bp.id == cand.blueprint_id:
                # Same blueprint row should match; if version column drifted, fail
                failures.append("BLUEPRINT_VERSION_MISMATCH")
        if bp.status in {"SUPERSEDED", "ARCHIVED"} and not bp.is_active:
            warnings.append("BLUEPRINT_INACTIVE_AT_QA")
        if item.concept_id != bp.concept_id or item.concept_id != cand.concept_id:
            failures.append("CONCEPT_MISMATCH")
        if body and body.get("difficulty") and body.get("difficulty") != bp.difficulty:
            failures.append("DIFFICULTY_MISMATCH")
        # Subject via hierarchy
        concept = (
            await self.session.execute(
                select(Concept)
                .options(selectinload(Concept.topic).selectinload(Topic.chapter).selectinload(Chapter.subject))
                .where(Concept.id == bp.concept_id)
            )
        ).scalar_one_or_none()
        if concept:
            subject = concept.topic.chapter.subject
            if subject.id != bp.subject_id:
                failures.append("SUBJECT_MISMATCH")
            if concept.topic.chapter.id != bp.chapter_id or concept.topic.id != bp.topic_id:
                failures.append("HIERARCHY_BLUEPRINT_MISMATCH")
        family = bp.question_family or await self.planning_repo.get_family(bp.question_family_id)
        if family and family.difficulty_min and body:
            # family range already validated at blueprint create; soft warn if body off
            pass
        if not bp.learning_objective_id:
            failures.append("OBJECTIVE_MISSING")
        if not bp.question_family_id:
            failures.append("FAMILY_MISSING")
        fmt = (bp.constraints or {}).get("question_format", "MCQ_4")
        if fmt not in {"MCQ_4", "MCQ"}:
            warnings.append("UNUSUAL_FORMAT")
        return GateOutcome("B_BLUEPRINT", not failures, "RED" if failures else "INFO", failures=failures, warnings=warnings)

    async def _gate_c_hierarchy(self, cand: GenerationCandidate, item: ContentItem) -> GateOutcome:
        if not item.concept_id:
            return GateOutcome("C_HIERARCHY", False, "RED", failures=["CONCEPT_MISSING"])
        concept = (
            await self.session.execute(
                select(Concept)
                .options(selectinload(Concept.topic).selectinload(Topic.chapter).selectinload(Chapter.subject))
                .where(Concept.id == item.concept_id)
            )
        ).scalar_one_or_none()
        if not concept or not concept.topic or not concept.topic.chapter or not concept.topic.chapter.subject:
            return GateOutcome("C_HIERARCHY", False, "RED", failures=["HIERARCHY_GAP"])
        if concept.id != cand.concept_id:
            return GateOutcome("C_HIERARCHY", False, "RED", failures=["CANDIDATE_CONCEPT_MISMATCH"])
        return GateOutcome("C_HIERARCHY", True, "INFO")

    def _gate_d_provenance(
        self, cand: GenerationCandidate, version: ContentVersion | None, item: ContentItem
    ) -> GateOutcome:
        failures: list[str] = []
        warnings: list[str] = []
        if not cand.blueprint_id or cand.blueprint_version is None:
            failures.append("MISSING_BLUEPRINT_LINEAGE")
        if not cand.batch_id or not cand.job_id or not cand.run_id:
            failures.append("MISSING_BATCH_JOB_RUN")
        model = (version.model_used if version else None) or cand.model_used
        prompt = (version.prompt_version if version else None) or cand.prompt_version
        if not model:
            failures.append("MISSING_MODEL")
        if not prompt:
            failures.append("MISSING_PROMPT_VERSION")
        tags = item.tags or []
        if "provenance:ai" not in tags and "ai-generated" not in tags:
            warnings.append("MISSING_NONCRITICAL_META")
        # Forbidden official claims in tags
        joined = " ".join(tags).lower()
        if "nta" in joined or "official-ncert" in joined:
            failures.append("FORBIDDEN_OFFICIAL_CLAIM")
        if cand.is_fallback:
            warnings.append("FALLBACK_PROVIDER")
        return GateOutcome("D_PROVENANCE", not failures, "RED" if failures else "INFO", failures=failures, warnings=warnings)

    @staticmethod
    def _serialize_result(result: QAResult, *, idempotent: bool) -> dict[str, Any]:
        return {
            "qa_result_id": str(result.id),
            "candidate_id": str(result.candidate_id),
            "content_item_id": str(result.content_item_id) if result.content_item_id else None,
            "content_version_id": str(result.content_version_id) if result.content_version_id else None,
            "qa_version": result.qa_version,
            "evaluation_no": result.evaluation_no,
            "classification": result.classification,
            "gate_results": result.gate_results,
            "failed_checks": result.failed_checks,
            "warnings": result.warnings,
            "duplicate_class": result.duplicate_class,
            "sampling_eligible": result.sampling_eligible,
            "quarantine": result.quarantine,
            "scientific_certification": False,
            "disclaimer": result.disclaimer,
            "idempotent": idempotent,
        }

    async def get_latest_for_item(self, content_item_id: uuid.UUID) -> QAResult | None:
        return (
            await self.session.execute(
                select(QAResult)
                .where(
                    QAResult.content_item_id == content_item_id,
                    QAResult.is_latest.is_(True),
                    QAResult.deleted_at.is_(None),
                )
                .order_by(QAResult.evaluated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()


class ContentFactorySamplingService:
    """Reproducible stratified GREEN sample + 100% YELLOW + RED quarantine list."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.factory_repo = ContentFactoryRepository(session)
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

    async def create_sample(
        self,
        batch_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        seed: int | None = None,
        sample_key: str | None = None,
        green_size: int | None = None,
        **ctx,
    ) -> dict[str, Any]:
        batch = await self.factory_repo.get_batch(batch_id)
        if not batch:
            raise NotFoundError("Content batch not found")

        policy = settings.factory_sampling_policy_version
        seed_v = int(seed if seed is not None else (uuid.uuid4().int % 2_147_483_647))
        key = sample_key or f"sample-{batch.batch_key}-{seed_v}"

        existing = (
            await self.session.execute(
                select(ReviewSample).where(ReviewSample.sample_key == key, ReviewSample.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if existing:
            return self._serialize_sample(existing, idempotent=True)

        rows = list(
            (
                await self.session.execute(
                    select(GenerationCandidate, QAResult, QuestionBlueprint)
                    .join(QAResult, QAResult.id == GenerationCandidate.latest_qa_result_id)
                    .outerjoin(QuestionBlueprint, QuestionBlueprint.id == GenerationCandidate.blueprint_id)
                    .where(
                        GenerationCandidate.batch_id == batch_id,
                        GenerationCandidate.status == "CREATED",
                        GenerationCandidate.deleted_at.is_(None),
                        QAResult.is_latest.is_(True),
                    )
                )
            ).all()
        )

        green: list[tuple] = []
        yellow_ids: list[uuid.UUID] = []
        red_ids: list[uuid.UUID] = []
        reasons: dict[str, str] = {}

        for cand, qa, bp in rows:
            if qa.classification == "RED" or qa.quarantine:
                red_ids.append(cand.id)
                reasons[str(cand.id)] = "RED_QUARANTINE"
            elif qa.classification == "YELLOW":
                yellow_ids.append(cand.id)
                reasons[str(cand.id)] = "YELLOW_FULL_REVIEW"
            elif qa.classification == "GREEN" and qa.sampling_eligible:
                green.append((cand, qa, bp))
            else:
                reasons[str(cand.id)] = f"EXCLUDED_{qa.classification}"

        n_green = len(green)
        k = settings.factory_green_sample_k
        n_min = settings.factory_green_sample_min
        default_n = min(n_green, max(n_min, int(math.ceil(k * math.sqrt(n_green))))) if n_green else 0
        target = green_size if green_size is not None else default_n
        target = max(0, min(target, n_green))

        selected, strata = self._stratified_draw(green, target=target, seed=seed_v)
        for cid in selected:
            reasons[str(cid)] = reasons.get(str(cid), "GREEN_STRATIFIED_SAMPLE")

        # Uncertainty priority already in YELLOW; also bump uncommon strata into reasons
        sample = ReviewSample(
            sample_key=key,
            batch_id=batch_id,
            policy_version=policy,
            seed=seed_v,
            green_sample_size=len(selected),
            selected_candidate_ids=selected,
            yellow_candidate_ids=yellow_ids,
            red_candidate_ids=red_ids,
            selection_reasons=reasons,
            strata_summary=strata,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        self.session.add(sample)
        await self.session.flush()

        if batch.status == "QA":
            batch.status = "SAMPLING"

        # FACTORY-P5: materialize per-candidate review queue items
        from app.modules.cms.services.content_factory_human_review_service import ContentFactoryHumanReviewService

        await ContentFactoryHumanReviewService(self.session).materialize_sample_items(sample, actor_id=actor_id)

        self._audit(
            actor_id=actor_id,
            action="factory.sampling.created",
            entity_type="review_sample",
            entity_id=sample.id,
            metadata={
                "batch_id": str(batch_id),
                "seed": seed_v,
                "green_selected": len(selected),
                "yellow": len(yellow_ids),
                "red": len(red_ids),
                "policy_version": policy,
            },
            **ctx,
        )
        await self.session.commit()
        reloaded = (
            await self.session.execute(select(ReviewSample).where(ReviewSample.sample_key == key))
        ).scalar_one()
        return self._serialize_sample(reloaded, idempotent=False)

    @staticmethod
    def _stratified_draw(
        green: list[tuple],
        *,
        target: int,
        seed: int,
    ) -> tuple[list[uuid.UUID], dict[str, Any]]:
        """Round-robin across strata keys to avoid single-blueprint concentration."""
        import random

        rng = random.Random(seed)
        buckets: dict[str, list[uuid.UUID]] = defaultdict(list)
        strata_meta: dict[str, int] = defaultdict(int)
        for cand, qa, bp in green:
            difficulty = (bp.difficulty if bp else "unknown")
            family = str(bp.question_family_id) if bp else "unknown"
            subject = str(bp.subject_id) if bp else "unknown"
            key = f"{subject}|{family}|{difficulty}|{cand.blueprint_id}"
            buckets[key].append(cand.id)
            strata_meta[key] += 1

        for key in buckets:
            rng.shuffle(buckets[key])

        selected: list[uuid.UUID] = []
        keys = sorted(buckets.keys())
        if not keys or target <= 0:
            return [], {"strata_counts": dict(strata_meta), "selected_by_strata": {}}

        selected_by: dict[str, int] = defaultdict(int)
        # Round-robin until target met
        while len(selected) < target:
            progressed = False
            for key in keys:
                if len(selected) >= target:
                    break
                if buckets[key]:
                    selected.append(buckets[key].pop())
                    selected_by[key] += 1
                    progressed = True
            if not progressed:
                break

        return selected, {"strata_counts": dict(strata_meta), "selected_by_strata": dict(selected_by)}

    @staticmethod
    def _serialize_sample(sample: ReviewSample, *, idempotent: bool) -> dict[str, Any]:
        return {
            "id": str(sample.id),
            "sample_key": sample.sample_key,
            "batch_id": str(sample.batch_id),
            "policy_version": sample.policy_version,
            "seed": sample.seed,
            "green_sample_size": sample.green_sample_size,
            "selected_candidate_ids": [str(x) for x in (sample.selected_candidate_ids or [])],
            "yellow_candidate_ids": [str(x) for x in (sample.yellow_candidate_ids or [])],
            "red_candidate_ids": [str(x) for x in (sample.red_candidate_ids or [])],
            "selection_reasons": sample.selection_reasons,
            "strata_summary": sample.strata_summary,
            "note": sample.note,
            "idempotent": idempotent,
            "disclaimer": "Sampling eligibility only — not approval, publication, or scientific certification",
        }
