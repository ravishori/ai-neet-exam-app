"""Content Factory planning service (FACTORY-P2).

Creates objectives/families/blueprints/coverage plans. Never generates or mutates questions.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.academic.repositories.academic_repository import AcademicRepository
from app.modules.cms.models.content_factory_planning import (
    DIFFICULTY_RANK,
    ContentBatchBlueprint,
    CoverageSlice,
    LearningObjective,
    QuestionBlueprint,
    QuestionFamily,
)
from app.modules.cms.repositories.content_factory_planning_repository import ContentFactoryPlanningRepository
from app.modules.cms.repositories.content_factory_repository import ContentFactoryRepository
from app.modules.cms.schemas.content_factory_planning import (
    BatchBlueprintAttachRequest,
    CoverageSliceCreateRequest,
    LearningObjectiveCreateRequest,
    QuestionBlueprintCreateRequest,
    QuestionFamilyCreateRequest,
)
from app.modules.system.models.audit_log import AuditLog
from app.modules.system.repositories.audit_repository import AuditRepository

logger = get_logger("content_factory_planning")

REQUIRED_CONSTRAINT_KEYS = ("question_format", "correct_option_count", "explanation_required")


class ContentFactoryPlanningService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ContentFactoryPlanningRepository(session)
        self.factory_repo = ContentFactoryRepository(session)
        self.academic = AcademicRepository(session)
        self.audit = AuditRepository(session)

    def _audit(self, *, actor_user_id, action, entity_type, entity_id, metadata=None, **ctx) -> None:
        self.audit.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                log_metadata=metadata,
                ip_address=ctx.get("ip_address"),
                user_agent=ctx.get("user_agent"),
                trace_id=ctx.get("trace_id"),
            )
        )

    async def _load_concept_chain(self, concept_id: uuid.UUID) -> tuple[Concept, Topic, Chapter, Subject]:
        result = await self.session.execute(
            select(Concept)
            .options(selectinload(Concept.topic).selectinload(Topic.chapter).selectinload(Chapter.subject))
            .where(Concept.id == concept_id)
        )
        concept = result.scalar_one_or_none()
        if not concept:
            raise AppError(
                "Concept does not exist — hierarchy gap; do not invent a concept UUID",
                code="HIERARCHY_GAP",
                status_code=400,
            )
        topic = concept.topic
        chapter = topic.chapter
        subject = chapter.subject
        return concept, topic, chapter, subject

    async def create_objective(
        self,
        payload: LearningObjectiveCreateRequest,
        *,
        actor_id: uuid.UUID | None,
        **ctx,
    ) -> tuple[LearningObjective, bool]:
        existing = await self.repo.get_objective_by_key(payload.objective_key)
        if existing:
            return existing, False

        await self._load_concept_chain(payload.concept_id)

        obj = LearningObjective(
            objective_key=payload.objective_key,
            concept_id=payload.concept_id,
            title=payload.title,
            description=payload.description,
            learning_level=payload.learning_level,
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        self.repo.add(obj)
        try:
            await self.repo.flush()
        except IntegrityError:
            await self.session.rollback()
            raced = await self.repo.get_objective_by_key(payload.objective_key)
            if raced:
                return raced, False
            raise AppError("Could not create learning objective", code="CONFLICT", status_code=409) from None

        self._audit(
            actor_user_id=actor_id,
            action="factory.objective.created",
            entity_type="learning_objective",
            entity_id=obj.id,
            metadata={"objective_key": obj.objective_key, "concept_id": str(obj.concept_id)},
            **ctx,
        )
        await self.repo.commit()
        reloaded = await self.repo.get_objective(obj.id)
        assert reloaded
        return reloaded, True

    async def create_family(
        self,
        payload: QuestionFamilyCreateRequest,
        *,
        actor_id: uuid.UUID | None,
        **ctx,
    ) -> tuple[QuestionFamily, bool]:
        existing = await self.repo.get_family_by_key(payload.family_key)
        if existing:
            return existing, False

        # Validate subject codes exist in academic seed
        subjects = await self.academic.list_subjects()
        known = {s.code.upper() for s in subjects}
        unknown = [c for c in payload.applicable_subject_codes if c not in known]
        if unknown:
            raise AppError(
                f"Unknown subject codes: {unknown}",
                code="INVALID_REFERENCE",
                status_code=400,
            )

        family = QuestionFamily(
            family_key=payload.family_key,
            name=payload.name,
            description=payload.description,
            applicable_subject_codes=payload.applicable_subject_codes,
            cognitive_intent=payload.cognitive_intent,
            difficulty_min=payload.difficulty_min,
            difficulty_max=payload.difficulty_max,
            question_format=payload.question_format,
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        self.repo.add(family)
        try:
            await self.repo.flush()
        except IntegrityError:
            await self.session.rollback()
            raced = await self.repo.get_family_by_key(payload.family_key)
            if raced:
                return raced, False
            raise AppError("Could not create question family", code="CONFLICT", status_code=409) from None

        self._audit(
            actor_user_id=actor_id,
            action="factory.family.created",
            entity_type="question_family",
            entity_id=family.id,
            metadata={"family_key": family.family_key, "subjects": family.applicable_subject_codes},
            **ctx,
        )
        await self.repo.commit()
        reloaded = await self.repo.get_family(family.id)
        assert reloaded
        return reloaded, True

    def _validate_blueprint_rules(
        self,
        *,
        subject: Subject,
        chapter: Chapter,
        topic: Topic,
        concept: Concept,
        objective: LearningObjective,
        family: QuestionFamily,
        difficulty: str,
        provenance_tier: str,
        constraints: dict[str, Any],
        expected_subject_id: uuid.UUID,
        expected_chapter_id: uuid.UUID,
        expected_topic_id: uuid.UUID,
        expected_concept_id: uuid.UUID,
    ) -> dict[str, Any]:
        findings: list[dict[str, str]] = []

        def red(code: str, message: str) -> None:
            findings.append({"severity": "RED", "code": code, "message": message})

        def green(code: str, message: str) -> None:
            findings.append({"severity": "GREEN", "code": code, "message": message})

        # Hierarchy integrity (hard block)
        if concept.id != expected_concept_id:
            red("HIERARCHY_GAP", "Concept mismatch")
        if topic.id != expected_topic_id or concept.topic_id != topic.id:
            red("INVALID_HIERARCHY", "Topic does not match concept")
        if chapter.id != expected_chapter_id or topic.chapter_id != chapter.id:
            red("INVALID_HIERARCHY", "Chapter does not match topic")
        if subject.id != expected_subject_id or chapter.subject_id != subject.id:
            red("INVALID_HIERARCHY", "Subject does not match chapter")
        else:
            green("HIERARCHY_OK", "Subject→Chapter→Topic→Concept chain is valid")

        if objective.concept_id != concept.id:
            red("OBJECTIVE_CONCEPT_MISMATCH", "Learning objective does not belong to this concept")
        elif not objective.is_active:
            red("OBJECTIVE_INACTIVE", "Learning objective is inactive")
        elif len(objective.title.strip()) < 8:
            red("OBJECTIVE_VAGUE", "Learning objective title is too vague")
        else:
            green("OBJECTIVE_OK", "Learning objective is valid for concept")

        if not family.is_active:
            red("FAMILY_INACTIVE", "Question family is inactive")
        elif subject.code.upper() not in [c.upper() for c in family.applicable_subject_codes]:
            red(
                "FAMILY_SUBJECT_INCOMPATIBLE",
                f"Family {family.family_key} not applicable to subject {subject.code}",
            )
        else:
            green("FAMILY_OK", "Family is compatible with subject")

        if difficulty not in DIFFICULTY_RANK:
            red("INVALID_DIFFICULTY", f"Unknown difficulty {difficulty}")
        else:
            rank = DIFFICULTY_RANK[difficulty]
            if rank < DIFFICULTY_RANK[family.difficulty_min] or rank > DIFFICULTY_RANK[family.difficulty_max]:
                red(
                    "DIFFICULTY_OUT_OF_FAMILY_RANGE",
                    f"Difficulty {difficulty} outside family range "
                    f"{family.difficulty_min}–{family.difficulty_max}",
                )
            else:
                green("DIFFICULTY_OK", "Difficulty fits family range and project enum")

        if not provenance_tier:
            red("PROVENANCE_UNDEFINED", "provenance_tier is required")
        elif provenance_tier in {"official", "official_source", "nta"}:
            red("PROVENANCE_FALSE_CLAIM", "Must not claim official NTA/NCERT via provenance")
        else:
            green("PROVENANCE_OK", f"Provenance tier '{provenance_tier}' is explicit")

        missing = [k for k in REQUIRED_CONSTRAINT_KEYS if k not in constraints]
        if missing:
            red("CONSTRAINTS_INCOMPLETE", f"Missing constraint keys: {missing}")
        else:
            if constraints.get("question_format") != family.question_format:
                red("FORMAT_MISMATCH", "constraints.question_format must match family.question_format")
            if constraints.get("correct_option_count") != 1:
                red("ANSWER_STRUCTURE", "NEET MCQ requires exactly one correct option")
            if constraints.get("explanation_required") is not True:
                red("EXPLANATION_REQUIRED", "explanation_required must be true")
            if not findings or all(f["code"] != "CONSTRAINTS_INCOMPLETE" for f in findings):
                if not any(f["code"] in {"FORMAT_MISMATCH", "ANSWER_STRUCTURE", "EXPLANATION_REQUIRED"} for f in findings):
                    green("CONSTRAINTS_OK", "Answer/format/explanation constraints defined")

        reds = [f for f in findings if f["severity"] == "RED"]
        return {
            "verdict": "RED" if reds else "GREEN",
            "generation_eligible": len(reds) == 0,
            "findings": findings,
            "hierarchy_gap": any(f["code"] in {"HIERARCHY_GAP", "INVALID_HIERARCHY"} for f in reds),
        }

    async def create_blueprint(
        self,
        payload: QuestionBlueprintCreateRequest,
        *,
        actor_id: uuid.UUID | None,
        **ctx,
    ) -> tuple[QuestionBlueprint, bool]:
        latest = await self.repo.latest_blueprint_version(payload.blueprint_key)
        if latest > 0 and not payload.new_version:
            existing = await self.repo.get_blueprint_by_key_version(payload.blueprint_key, latest)
            if existing:
                return existing, False

        # Hard hierarchy load — missing concept = HIERARCHY_GAP
        try:
            concept, topic, chapter, subject = await self._load_concept_chain(payload.concept_id)
        except AppError:
            raise

        if topic.id != payload.topic_id or chapter.id != payload.chapter_id or subject.id != payload.subject_id:
            raise AppError(
                "Provided subject/chapter/topic/concept combination is invalid",
                code="INVALID_HIERARCHY",
                status_code=400,
            )

        objective = await self.repo.get_objective(payload.learning_objective_id)
        if not objective:
            raise AppError("Learning objective not found", code="INVALID_REFERENCE", status_code=400)
        family = await self.repo.get_family(payload.question_family_id)
        if not family:
            raise AppError("Question family not found", code="INVALID_REFERENCE", status_code=400)

        constraints = dict(payload.constraints or {})
        # Sensible defaults for NEET MCQ if omitted — still validated
        constraints.setdefault("question_format", family.question_format)
        constraints.setdefault("correct_option_count", 1)
        constraints.setdefault("explanation_required", True)
        constraints.setdefault("avoid_paraphrase_duplicates", True)

        validation = self._validate_blueprint_rules(
            subject=subject,
            chapter=chapter,
            topic=topic,
            concept=concept,
            objective=objective,
            family=family,
            difficulty=payload.difficulty,
            provenance_tier=payload.provenance_tier,
            constraints=constraints,
            expected_subject_id=payload.subject_id,
            expected_chapter_id=payload.chapter_id,
            expected_topic_id=payload.topic_id,
            expected_concept_id=payload.concept_id,
        )

        if not validation["generation_eligible"]:
            red_codes = [f["code"] for f in validation["findings"] if f["severity"] == "RED"]
            raise AppError(
                f"Blueprint failed planning validation: {', '.join(red_codes)}",
                code="BLUEPRINT_VALIDATION_FAILED",
                status_code=400,
            )

        if payload.new_version and latest > 0:
            from sqlalchemy import update

            await self.session.execute(
                update(QuestionBlueprint)
                .where(
                    QuestionBlueprint.blueprint_key == payload.blueprint_key,
                    QuestionBlueprint.status.in_(("DRAFT", "ACTIVE")),
                    QuestionBlueprint.deleted_at.is_(None),
                )
                .values(status="SUPERSEDED", generation_eligible=False, is_active=False)
            )
            new_version = latest + 1
        else:
            new_version = 1

        bp = QuestionBlueprint(
            blueprint_key=payload.blueprint_key,
            blueprint_version=new_version,
            subject_id=payload.subject_id,
            chapter_id=payload.chapter_id,
            topic_id=payload.topic_id,
            concept_id=payload.concept_id,
            learning_objective_id=payload.learning_objective_id,
            question_family_id=payload.question_family_id,
            difficulty=payload.difficulty,
            target_count=payload.target_count,
            constraints=constraints,
            provenance_tier=payload.provenance_tier,
            status="ACTIVE",
            generation_eligible=True,
            is_active=True,
            last_validation=validation,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        self.repo.add(bp)
        try:
            await self.repo.flush()
        except IntegrityError:
            await self.session.rollback()
            raced = await self.repo.get_blueprint_by_key_version(payload.blueprint_key, new_version)
            if raced:
                return raced, False
            raise AppError("Could not create blueprint", code="CONFLICT", status_code=409) from None

        self._audit(
            actor_user_id=actor_id,
            action="factory.blueprint.created",
            entity_type="question_blueprint",
            entity_id=bp.id,
            metadata={
                "blueprint_key": bp.blueprint_key,
                "blueprint_version": bp.blueprint_version,
                "verdict": validation["verdict"],
                "generation_eligible": bp.generation_eligible,
                "provenance_tier": bp.provenance_tier,
            },
            **ctx,
        )
        await self.repo.commit()
        reloaded = await self.repo.get_blueprint(bp.id)
        assert reloaded
        return reloaded, True

    async def validate_blueprint(self, blueprint_id: uuid.UUID, *, actor_id: uuid.UUID | None, **ctx) -> dict:
        bp = await self.repo.get_blueprint(blueprint_id)
        if not bp:
            raise NotFoundError("Question blueprint not found")

        try:
            concept, topic, chapter, subject = await self._load_concept_chain(bp.concept_id)
        except AppError as exc:
            validation = {
                "verdict": "RED",
                "generation_eligible": False,
                "findings": [{"severity": "RED", "code": exc.code, "message": exc.message}],
                "hierarchy_gap": True,
            }
            bp.last_validation = validation
            bp.generation_eligible = False
            bp.status = "DRAFT"
            await self.repo.commit()
            return {"blueprint_id": str(bp.id), **validation}

        objective = bp.learning_objective or await self.repo.get_objective(bp.learning_objective_id)
        family = bp.question_family or await self.repo.get_family(bp.question_family_id)
        if not objective or not family:
            raise AppError("Blueprint references missing objective or family", code="INVALID_REFERENCE", status_code=400)

        validation = self._validate_blueprint_rules(
            subject=subject,
            chapter=chapter,
            topic=topic,
            concept=concept,
            objective=objective,
            family=family,
            difficulty=bp.difficulty,
            provenance_tier=bp.provenance_tier,
            constraints=bp.constraints or {},
            expected_subject_id=bp.subject_id,
            expected_chapter_id=bp.chapter_id,
            expected_topic_id=bp.topic_id,
            expected_concept_id=bp.concept_id,
        )
        bp.last_validation = validation
        bp.generation_eligible = validation["generation_eligible"]
        if validation["generation_eligible"] and bp.status == "DRAFT":
            bp.status = "ACTIVE"
        if not validation["generation_eligible"]:
            bp.generation_eligible = False
        bp.updated_by = actor_id
        bp.version = (bp.version or 1) + 1

        self._audit(
            actor_user_id=actor_id,
            action="factory.blueprint.validated",
            entity_type="question_blueprint",
            entity_id=bp.id,
            metadata={"verdict": validation["verdict"], "generation_eligible": validation["generation_eligible"]},
            **ctx,
        )
        await self.repo.commit()
        return {
            "blueprint_id": str(bp.id),
            "blueprint_key": bp.blueprint_key,
            "blueprint_version": bp.blueprint_version,
            **validation,
        }

    async def create_coverage_slice(
        self,
        payload: CoverageSliceCreateRequest,
        *,
        actor_id: uuid.UUID | None,
        **ctx,
    ) -> tuple[CoverageSlice, bool]:
        existing = await self.repo.get_slice_by_key(payload.slice_key)
        if existing:
            return existing, False

        subject = await self.academic.get_subject(payload.subject_id)
        if not subject:
            raise AppError("Unknown subject_id", code="INVALID_REFERENCE", status_code=400)

        if payload.concept_id:
            concept, topic, chapter, subj = await self._load_concept_chain(payload.concept_id)
            if subj.id != payload.subject_id:
                raise AppError("concept_id does not belong to subject_id", code="INVALID_HIERARCHY", status_code=400)
            if payload.topic_id and payload.topic_id != topic.id:
                raise AppError("concept/topic mismatch", code="INVALID_HIERARCHY", status_code=400)
            if payload.chapter_id and payload.chapter_id != chapter.id:
                raise AppError("concept/chapter mismatch", code="INVALID_HIERARCHY", status_code=400)
            # Fill resolved hierarchy
            payload = payload.model_copy(
                update={"chapter_id": chapter.id, "topic_id": topic.id, "concept_id": concept.id}
            )
        elif payload.chapter_id:
            chapter = await self.academic.get_chapter(payload.chapter_id)
            if not chapter or chapter.subject_id != payload.subject_id:
                raise AppError("Invalid chapter for subject", code="INVALID_HIERARCHY", status_code=400)

        if payload.question_family_id:
            family = await self.repo.get_family(payload.question_family_id)
            if not family:
                raise AppError("Unknown question_family_id", code="INVALID_REFERENCE", status_code=400)
            if subject.code.upper() not in [c.upper() for c in family.applicable_subject_codes]:
                raise AppError(
                    "Family incompatible with subject for coverage slice",
                    code="FAMILY_SUBJECT_INCOMPATIBLE",
                    status_code=400,
                )

        slice_row = CoverageSlice(
            slice_key=payload.slice_key,
            subject_id=payload.subject_id,
            chapter_id=payload.chapter_id,
            topic_id=payload.topic_id,
            concept_id=payload.concept_id,
            difficulty=payload.difficulty,
            question_family_id=payload.question_family_id,
            target_count=payload.target_count,
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        self.repo.add(slice_row)
        try:
            await self.repo.flush()
        except IntegrityError:
            await self.session.rollback()
            raced = await self.repo.get_slice_by_key(payload.slice_key)
            if raced:
                return raced, False
            raise AppError("Could not create coverage slice", code="CONFLICT", status_code=409) from None

        self._audit(
            actor_user_id=actor_id,
            action="factory.coverage_slice.created",
            entity_type="coverage_slice",
            entity_id=slice_row.id,
            metadata={"slice_key": slice_row.slice_key, "target_count": slice_row.target_count},
            **ctx,
        )
        await self.repo.commit()
        reloaded = await self.repo.get_slice(slice_row.id)
        assert reloaded
        return reloaded, True

    async def coverage_report(
        self,
        *,
        subject_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        slices, total = await self.repo.list_slices(subject_id=subject_id, limit=limit, offset=offset)
        rows = []
        for s in slices:
            existing = 0
            published = 0
            if s.concept_id:
                existing = await self.repo.count_questions_for_concept(
                    s.concept_id, difficulty=s.difficulty, published_only=False
                )
                published = await self.repo.count_questions_for_concept(
                    s.concept_id, difficulty=s.difficulty, published_only=True
                )
            planned = await self.repo.sum_planned_targets(
                subject_id=s.subject_id,
                concept_id=s.concept_id,
                difficulty=s.difficulty,
                family_id=s.question_family_id,
            )
            # GENERATED reserved for factory-produced items (P3); 0 until then.
            generated = 0
            gap_vs_published = max(0, s.target_count - published)
            gap_vs_existing = max(0, s.target_count - existing)
            demand_signal = "empty" if existing == 0 else ("low" if existing < s.target_count else "met_or_over")
            if existing > s.target_count * 1.5 and s.target_count > 0:
                demand_signal = "overrepresented"

            rows.append(
                {
                    "id": str(s.id),
                    "slice_key": s.slice_key,
                    "subject_id": str(s.subject_id),
                    "chapter_id": str(s.chapter_id) if s.chapter_id else None,
                    "topic_id": str(s.topic_id) if s.topic_id else None,
                    "concept_id": str(s.concept_id) if s.concept_id else None,
                    "difficulty": s.difficulty,
                    "question_family_id": str(s.question_family_id) if s.question_family_id else None,
                    "target": s.target_count,
                    "existing": existing,
                    "planned": planned,
                    "generated": generated,
                    "published": published,
                    "gap_vs_published": gap_vs_published,
                    "gap_vs_existing": gap_vs_existing,
                    "demand_signal": demand_signal,
                    "note": "DRAFT counts toward existing but not published",
                }
            )
        return {"slices": rows, "total": total, "limit": limit, "offset": offset}

    async def attach_blueprint_to_batch(
        self,
        batch_id: uuid.UUID,
        payload: BatchBlueprintAttachRequest,
        *,
        actor_id: uuid.UUID | None,
        **ctx,
    ) -> tuple[ContentBatchBlueprint, bool]:
        batch = await self.factory_repo.get_batch(batch_id)
        if not batch:
            raise NotFoundError("Content batch not found")
        bp = await self.repo.get_blueprint(payload.blueprint_id)
        if not bp:
            raise NotFoundError("Question blueprint not found")
        if not bp.generation_eligible:
            raise AppError(
                "Blueprint is not generation-eligible; fix validation findings first",
                code="BLUEPRINT_NOT_ELIGIBLE",
                status_code=409,
            )

        existing = await self.repo.get_batch_blueprint_link(batch_id, payload.blueprint_id)
        if existing:
            return existing, False

        link = ContentBatchBlueprint(
            batch_id=batch_id,
            blueprint_id=payload.blueprint_id,
            requested_count=payload.requested_count,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        self.repo.add(link)
        try:
            await self.repo.flush()
        except IntegrityError:
            await self.session.rollback()
            raced = await self.repo.get_batch_blueprint_link(batch_id, payload.blueprint_id)
            if raced:
                return raced, False
            raise AppError("Could not attach blueprint", code="CONFLICT", status_code=409) from None

        self._audit(
            actor_user_id=actor_id,
            action="factory.batch.blueprint_attached",
            entity_type="content_batch_blueprint",
            entity_id=link.id,
            metadata={
                "batch_id": str(batch_id),
                "blueprint_id": str(payload.blueprint_id),
                "blueprint_version": bp.blueprint_version,
                "requested_count": payload.requested_count,
            },
            **ctx,
        )
        await self.repo.commit()
        reloaded = await self.repo.get_batch_blueprint_link(batch_id, payload.blueprint_id)
        assert reloaded
        return reloaded, True
