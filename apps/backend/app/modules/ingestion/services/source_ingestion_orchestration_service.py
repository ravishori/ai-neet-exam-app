"""FACTORY-S1 orchestration: discover → map → source-ingest (no AI, no MCQ)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.ingestion_pipeline_service import (
    S1_SOURCE_INGESTION_RUN_ID,
    IngestionPipelineService,
)
from app.modules.ingestion.services.source_academic_mapping_service import SourceAcademicMappingService
from app.modules.ingestion.services.study_material_discovery_service import StudyMaterialDiscoveryService

logger = get_logger("ingestion.s1")


@dataclass
class FailedKuClassification:
    knowledge_unit_id: str
    subject: str
    chapter: str
    concept: str
    category: str
    detail: str


@dataclass
class SourceIngestionItemResult:
    source_document_id: str
    relative_path: str
    status: str
    skipped: bool
    job_id: str | None = None
    sections: int = 0
    ku_passed: int = 0
    ku_rejected: int = 0
    error: str | None = None


@dataclass
class SourceIngestionReport:
    discovery_registered: int = 0
    mapping_processed: int = 0
    mapping_mapped: int = 0
    sources_before: int = 0
    sources_after: int = 0
    ingested_before: int = 0
    ingested_after: int = 0
    sections_before: int = 0
    sections_after: int = 0
    ku_total_before: int = 0
    ku_total_after: int = 0
    ku_passed_before: int = 0
    ku_passed_after: int = 0
    ku_failed_before: int = 0
    ku_failed_after: int = 0
    chapters_full_before: int = 0
    chapters_full_after: int = 0
    items: list[SourceIngestionItemResult] = field(default_factory=list)
    failed_ku_classifications: list[FailedKuClassification] = field(default_factory=list)
    maths_in_registry: int = 0
    duplicate_jobs_skipped: int = 0
    errors: int = 0

    def to_dict(self) -> dict:
        return {
            "discovery_registered": self.discovery_registered,
            "mapping_processed": self.mapping_processed,
            "mapping_mapped": self.mapping_mapped,
            "sources_before": self.sources_before,
            "sources_after": self.sources_after,
            "ingested_before": self.ingested_before,
            "ingested_after": self.ingested_after,
            "sections_before": self.sections_before,
            "sections_after": self.sections_after,
            "ku_total_before": self.ku_total_before,
            "ku_total_after": self.ku_total_after,
            "ku_passed_before": self.ku_passed_before,
            "ku_passed_after": self.ku_passed_after,
            "ku_failed_before": self.ku_failed_before,
            "ku_failed_after": self.ku_failed_after,
            "chapters_full_before": self.chapters_full_before,
            "chapters_full_after": self.chapters_full_after,
            "duplicate_jobs_skipped": self.duplicate_jobs_skipped,
            "errors": self.errors,
            "items": [item.__dict__ for item in self.items],
            "failed_ku_classifications": [f.__dict__ for f in self.failed_ku_classifications],
            "maths_in_registry": self.maths_in_registry,
        }


def classify_failed_ku(detail: str | None) -> str:
    text_ = (detail or "").lower()
    if "duplicate" in text_:
        return "duplicate"
    if "source-overlap" in text_ or "grounding" in text_ or "facts failed" in text_:
        return "validation"
    if "no structured facts" in text_:
        return "extraction"
    if "unmapped" in text_ or "mapping" in text_:
        return "missing_mapping"
    if "malformed" in text_ or "json" in text_:
        return "malformed_source"
    if "provenance" in text_:
        return "provenance"
    return "other"


class SourceIngestionOrchestrationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pipeline = IngestionPipelineService(session)
        self.discovery = StudyMaterialDiscoveryService(session)
        self.mapping = SourceAcademicMappingService(session)
        self.source_repo = SourceDocumentRepository(session)

    async def _snapshot(self) -> dict:
        conn = await self.session.connection()
        async def scalar(q: str) -> int:
            return int((await conn.execute(text(q))).scalar_one())

        full_chapters = await scalar(
            """
            SELECT COUNT(DISTINCT ch.id)
            FROM academic.chapters ch
            JOIN ingestion.source_academic_mappings sam ON sam.chapter_id = ch.id AND sam.mapping_status = 'MAPPED'
            JOIN ingestion.source_documents sd ON sd.id = sam.source_document_id
            JOIN ingestion.ingestion_jobs ij ON ij.source_document_id = sd.id AND ij.status = 'COMPLETED'
            JOIN ingestion.ingestion_sections sec ON sec.job_id = ij.id
            JOIN knowledge.knowledge_units ku ON ku.source_section_id = sec.id AND ku.validation_status = 'PASSED'
            """
        )
        ingested = await scalar(
            "SELECT COUNT(DISTINCT source_document_id) FROM ingestion.ingestion_jobs WHERE status = 'COMPLETED' AND sections_detected > 0"
        )
        return {
            "sources": await scalar("SELECT COUNT(*) FROM ingestion.source_documents WHERE deleted_at IS NULL"),
            "ingested": ingested,
            "sections": await scalar("SELECT COUNT(*) FROM ingestion.ingestion_sections"),
            "ku_total": await scalar("SELECT COUNT(*) FROM knowledge.knowledge_units"),
            "ku_passed": await scalar("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE validation_status = 'PASSED'"),
            "ku_failed": await scalar("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE validation_status = 'FAILED'"),
            "chapters_full": full_chapters,
            "maths": await scalar("SELECT COUNT(*) FROM ingestion.source_documents WHERE subject_code = 'MATHS'"),
        }

    async def _load_failed_ku_classifications(self) -> list[FailedKuClassification]:
        conn = await self.session.connection()
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT ku.id, ku.validation_detail, s.code AS subject, ch.code AS chapter, co.code AS concept
                    FROM knowledge.knowledge_units ku
                    JOIN academic.concepts co ON co.id = ku.concept_id
                    JOIN academic.topics t ON t.id = co.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ku.validation_status = 'FAILED'
                    ORDER BY ku.created_at
                    """
                )
            )
        ).mappings().all()
        return [
            FailedKuClassification(
                knowledge_unit_id=str(r["id"]),
                subject=r["subject"],
                chapter=r["chapter"],
                concept=r["concept"],
                category=classify_failed_ku(r["validation_detail"]),
                detail=(r["validation_detail"] or "")[:300],
            )
            for r in rows
        ]

    async def run(
        self,
        *,
        author_id: uuid.UUID,
        dry_run: bool = False,
        force_rerun: bool = False,
    ) -> SourceIngestionReport:
        report = SourceIngestionReport()
        before = await self._snapshot()
        report.sources_before = before["sources"]
        report.ingested_before = before["ingested"]
        report.sections_before = before["sections"]
        report.ku_total_before = before["ku_total"]
        report.ku_passed_before = before["ku_passed"]
        report.ku_failed_before = before["ku_failed"]
        report.chapters_full_before = before["chapters_full"]
        report.maths_in_registry = before["maths"]

        discovery = await self.discovery.discover(dry_run=dry_run)
        report.discovery_registered = discovery.registered

        if not dry_run:
            mapping_report = await self.mapping.sync_all()
            report.mapping_processed = mapping_report.processed
            report.mapping_mapped = mapping_report.mapped

        docs, _total = await self.source_repo.list_neet(limit=500)
        for doc in docs:
            if doc.subject_code not in ("PHYSICS", "CHEMISTRY", "BIOLOGY"):
                continue
            item = SourceIngestionItemResult(
                source_document_id=str(doc.id),
                relative_path=doc.relative_source_path,
                status="PENDING",
                skipped=False,
            )
            if dry_run:
                item.status = "DRY_RUN"
                report.items.append(item)
                continue

            try:
                job, created = await self.pipeline.start_source_ingestion_job(
                    source_document_id=doc.id,
                    ingestion_run_id=S1_SOURCE_INGESTION_RUN_ID,
                    force_rerun=force_rerun,
                )
                item.job_id = str(job.id)
                if not created and job.status == "COMPLETED":
                    item.skipped = True
                    item.status = "SKIPPED"
                    report.duplicate_jobs_skipped += 1
                    item.sections = job.sections_detected
                    report.items.append(item)
                    continue

                await self.pipeline.run_source_ingestion(job_id=job.id, author_id=author_id)
                job = await self.pipeline.repo.get_job(job.id)
                if job is None:
                    raise RuntimeError("job missing after run")
                item.status = job.status
                item.sections = job.sections_detected
                item.ku_passed = job.knowledge_units_created
                item.ku_rejected = job.knowledge_units_rejected
                if job.status == "FAILED":
                    item.error = job.error_message
                    report.errors += 1
            except Exception as exc:  # noqa: BLE001 — per-source isolation
                item.status = "ERROR"
                item.error = str(exc)[:500]
                report.errors += 1
                logger.error("s1_source_failed", source=doc.relative_source_path, error=str(exc))
            report.items.append(item)

        after = await self._snapshot()
        report.sources_after = after["sources"]
        report.ingested_after = after["ingested"]
        report.sections_after = after["sections"]
        report.ku_total_after = after["ku_total"]
        report.ku_passed_after = after["ku_passed"]
        report.ku_failed_after = after["ku_failed"]
        report.chapters_full_after = after["chapters_full"]
        report.failed_ku_classifications = await self._load_failed_ku_classifications()
        report.maths_in_registry = after["maths"]

        if not dry_run:
            await self._sync_ingestion_statuses()

        return report

    async def _sync_ingestion_statuses(self) -> None:
        """Mark registry rows INGESTED when a completed job with sections exists."""
        conn = await self.session.connection()
        await conn.execute(
            text(
                """
                UPDATE ingestion.source_documents sd
                SET ingestion_status = 'INGESTED', updated_at = NOW()
                WHERE sd.deleted_at IS NULL
                  AND sd.ingestion_status != 'INGESTED'
                  AND EXISTS (
                    SELECT 1 FROM ingestion.ingestion_jobs ij
                    WHERE ij.source_document_id = sd.id
                      AND ij.status = 'COMPLETED'
                      AND ij.sections_detected > 0
                  )
                """
            )
        )
        await self.session.commit()
