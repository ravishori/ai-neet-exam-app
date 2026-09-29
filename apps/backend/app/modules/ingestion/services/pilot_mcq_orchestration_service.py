"""Phase D mandatory 30-MCQ pilot orchestration (ADR-0032).

Runs exactly 10 Physics + 10 Chemistry + 10 Biology MCQs through the existing
source-aware ingestion pipeline. Idempotent per pilot_run_id.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.cms.models import ContentItem, ContentVersion, ContentVersionKnowledgeUnit
from app.modules.ingestion.models import IngestionJob, IngestionSection
from app.modules.ingestion.repositories.source_academic_mapping_repository import SourceAcademicMappingRepository
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.chapter_content_preflight import (
    content_mismatch_detail,
    pdf_content_matches_chapter,
)
from app.modules.ingestion.services.ingestion_pipeline_service import IngestionPipelineService
from app.modules.ingestion.services.source_document_resolver import resolve_source_document_path, verify_source_checksum
from app.modules.knowledge.models import KnowledgeUnit

logger = get_logger("ingestion.pilot")

PHASE_D_PILOT_RUN_ID = "phase-d-30-mcq-v1"
PHASE_D_MCQ_PER_SUBJECT = 10

# Primary Biology pilot = Botany photosynthesis (not Zoology alternative).
PILOT_SUBJECT_ORDER = ("PHYSICS", "CHEMISTRY", "BIOLOGY")


@dataclass(frozen=True)
class PilotSourceSpec:
    label: str
    relative_source_path: str
    chapter_code: str
    academic_subject_code: str


PILOT_SOURCES: tuple[PilotSourceSpec, ...] = (
    PilotSourceSpec(
        "PHYSICS",
        "Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf",
        "current-electricity",
        "PHYSICS",
    ),
    PilotSourceSpec(
        "CHEMISTRY",
        "Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf",
        "chemical-bonding",
        "CHEMISTRY",
    ),
    PilotSourceSpec(
        "BIOLOGY",
        "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf",
        "photosynthesis",
        "BOTANY",
    ),
)


@dataclass
class PilotSubjectResult:
    label: str
    source_document_id: str | None = None
    ingestion_job_id: str | None = None
    chapter_code: str | None = None
    questions_generated: int = 0
    questions_target: int = PHASE_D_MCQ_PER_SUBJECT
    status: str = "pending"
    error: str | None = None
    skipped_existing: bool = False


@dataclass
class PilotRunReport:
    pilot_run_id: str = PHASE_D_PILOT_RUN_ID
    subjects: list[PilotSubjectResult] = field(default_factory=list)
    total_generated: int = 0
    total_target: int = 30
    blocked: bool = False
    block_reason: str | None = None

    def to_api_dict(self) -> dict:
        return {
            "pilot_run_id": self.pilot_run_id,
            "subjects": [s.__dict__ for s in self.subjects],
            "total_generated": self.total_generated,
            "total_target": self.total_target,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
        }


class PilotMcqOrchestrationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.source_repo = SourceDocumentRepository(session)
        self.mapping_repo = SourceAcademicMappingRepository(session)
        self.pipeline = IngestionPipelineService(session)

    async def verify_pilot_sources(self) -> None:
        """Raise AppError if any primary pilot source is missing or invalid."""
        errors: list[str] = []
        for spec in PILOT_SOURCES:
            try:
                await self._verify_single_pilot_source(spec)
            except AppError as exc:
                errors.append(f"{spec.label}: {exc.message}")
        if errors:
            raise AppError(
                "; ".join(errors),
                code="PILOT_SOURCES_INVALID",
                status_code=422,
            )

    async def _verify_single_pilot_source(self, spec: PilotSourceSpec) -> None:
        doc = await self.source_repo.get_by_relative_path(spec.relative_source_path)
        if doc is None:
            raise AppError(
                f"Pilot source not registered: {spec.relative_source_path}",
                code="PILOT_SOURCE_NOT_FOUND",
                status_code=422,
            )
        verify_source_checksum(doc)
        mapping = await self.mapping_repo.get_for_source(doc.id)
        if mapping is None or mapping.mapping_status != "MAPPED":
            raise AppError(
                f"Pilot source unmapped: {spec.relative_source_path}",
                code="UNMAPPED_SOURCE",
                status_code=422,
            )
        if not mapping.pilot_ready:
            raise AppError(
                f"Pilot source not pilot-ready (no topic/concept tree): {spec.chapter_code}",
                code="PILOT_NOT_READY",
                status_code=422,
            )
        if mapping.chapter_code != spec.chapter_code:
            raise AppError(
                f"Pilot mapping mismatch for {spec.label}: expected {spec.chapter_code}, got {mapping.chapter_code}",
                code="PILOT_MAPPING_MISMATCH",
                status_code=422,
            )
        self._verify_pilot_pdf_content(doc, spec.chapter_code, spec.relative_source_path)

    def _verify_pilot_pdf_content(self, doc, chapter_code: str, relative_path: str) -> None:
        resolved = resolve_source_document_path(doc)
        if not pdf_content_matches_chapter(resolved, chapter_code):
            raise AppError(
                content_mismatch_detail(resolved, chapter_code),
                code="PILOT_SOURCE_CONTENT_MISMATCH",
                status_code=422,
            )

    async def run(
        self,
        *,
        author_id: uuid.UUID,
        pilot_run_id: str = PHASE_D_PILOT_RUN_ID,
        force: bool = False,
        dry_run: bool = False,
    ) -> PilotRunReport:
        report = PilotRunReport(pilot_run_id=pilot_run_id)
        preflight_errors: list[str] = []

        for spec in PILOT_SOURCES:
            subject_result = PilotSubjectResult(label=spec.label, chapter_code=spec.chapter_code)
            report.subjects.append(subject_result)
            try:
                await self._verify_single_pilot_source(spec)
            except AppError as exc:
                subject_result.status = "blocked"
                subject_result.error = exc.message
                preflight_errors.append(f"{spec.label}: {exc.message}")
                continue

            doc = await self.source_repo.get_by_relative_path(spec.relative_source_path)
            assert doc is not None
            subject_result.source_document_id = str(doc.id)

            if dry_run:
                subject_result.status = "dry_run"
                continue

            if force:
                existing = await self.pipeline.repo.get_pilot_job(
                    source_document_id=doc.id, pilot_run_id=pilot_run_id
                )
                if (
                    existing
                    and existing.status == "COMPLETED"
                    and existing.questions_generated >= PHASE_D_MCQ_PER_SUBJECT
                ):
                    subject_result.skipped_existing = True
                    subject_result.ingestion_job_id = str(existing.id)
                    subject_result.questions_generated = existing.questions_generated
                    subject_result.status = "skipped_existing"
                    report.total_generated += existing.questions_generated
                    continue

            job = await self.pipeline.start_job(
                source_document_id=doc.id,
                target_mcq_count=PHASE_D_MCQ_PER_SUBJECT,
                pilot_run_id=pilot_run_id,
                force_pilot_rerun=force,
            )
            subject_result.ingestion_job_id = str(job.id)

            if job.status == "COMPLETED" and job.pilot_run_id == pilot_run_id:
                subject_result.skipped_existing = True
                subject_result.questions_generated = job.questions_generated
                subject_result.status = "skipped_existing"
                report.total_generated += job.questions_generated
                continue

            await self.pipeline.run(job_id=job.id, author_id=author_id)
            job = await self.pipeline.repo.get_job(job.id)
            assert job is not None

            subject_result.questions_generated = job.questions_generated
            report.total_generated += job.questions_generated
            if job.status == "COMPLETED" and job.questions_generated >= PHASE_D_MCQ_PER_SUBJECT:
                subject_result.status = "completed"
            elif job.status == "FAILED":
                subject_result.status = "failed"
                subject_result.error = job.error_message
            else:
                subject_result.status = "incomplete"
                subject_result.error = (
                    f"Generated {job.questions_generated}/{PHASE_D_MCQ_PER_SUBJECT} — "
                    f"status={job.status}"
                )

        if preflight_errors and report.total_generated == 0 and dry_run:
            report.blocked = True
            report.block_reason = "; ".join(preflight_errors)
        elif preflight_errors and not dry_run:
            report.block_reason = "; ".join(preflight_errors)

        if report.total_generated < report.total_target and not dry_run:
            logger.warning(
                "pilot_mcq_incomplete",
                generated=report.total_generated,
                target=report.total_target,
            )

        return report

    async def provenance_summary(self, *, pilot_run_id: str = PHASE_D_PILOT_RUN_ID) -> dict:
        """Audit lineage for pilot-generated DRAFT questions."""
        jobs = (
            await self.session.execute(
                select(IngestionJob).where(IngestionJob.pilot_run_id == pilot_run_id)
            )
        ).scalars().all()

        question_rows = []
        for job in jobs:
            versions = (
                await self.session.execute(
                    select(ContentVersion, ContentItem)
                    .join(ContentItem, ContentVersion.content_item_id == ContentItem.id)
                    .where(
                        ContentItem.content_type == "QUESTION",
                        ContentItem.tags.contains(["ingested"]),
                        ContentItem.status == "DRAFT",
                    )
                )
            ).all()
            # Filter to questions from this job's sections via KU lineage
            section_ids = {
                s.id
                for s in (
                    await self.session.execute(
                        select(IngestionSection).where(IngestionSection.job_id == job.id)
                    )
                ).scalars()
            }
            for version, item in versions:
                refs = (
                    await self.session.execute(
                        select(ContentVersionKnowledgeUnit, KnowledgeUnit)
                        .join(KnowledgeUnit, ContentVersionKnowledgeUnit.knowledge_unit_id == KnowledgeUnit.id)
                        .where(ContentVersionKnowledgeUnit.content_version_id == version.id)
                    )
                ).all()
                for _ref, ku in refs:
                    if ku.source_section_id not in section_ids:
                        continue
                    section = await self.session.get(IngestionSection, ku.source_section_id)
                    question_rows.append(
                        {
                            "content_item_id": str(item.id),
                            "ingestion_job_id": str(job.id),
                            "source_document_id": str(job.source_document_id) if job.source_document_id else None,
                            "source_page": section.source_page if section else None,
                            "knowledge_unit_id": str(ku.id),
                            "cms_status": item.status,
                        }
                    )

        draft_count = (
            await self.session.execute(
                select(func.count(ContentItem.id)).where(
                    ContentItem.content_type == "QUESTION",
                    ContentItem.status == "DRAFT",
                    ContentItem.tags.contains(["ingested"]),
                )
            )
        ).scalar_one()

        return {
            "pilot_run_id": pilot_run_id,
            "ingestion_jobs": len(jobs),
            "draft_questions_with_lineage": len(question_rows),
            "draft_ingested_questions_total": draft_count,
            "samples": question_rows[:5],
        }
