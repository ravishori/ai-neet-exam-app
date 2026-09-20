"""Resolve and persist SourceDocument → academic Chapter mappings (ADR-0031)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.ingestion.models.source_academic_mapping import SourceAcademicMapping
from app.modules.ingestion.models.source_document import SourceDocument
from app.modules.ingestion.repositories.source_academic_mapping_repository import SourceAcademicMappingRepository
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.chapter_content_preflight import (
    content_mismatch_detail,
    pdf_content_matches_chapter,
)
from app.modules.ingestion.services.source_document_resolver import resolve_source_document_path
from app.modules.ingestion.services.study_material_academic_registry import (
    PILOT_CHAPTER_CODES,
    PILOT_SOURCE_RELATIVE_PATHS,
    lookup_explicit_mapping,
)
from app.modules.ingestion.services.study_material_ncert_parser import extract_ncert_chapter_number

logger = get_logger("ingestion.mapping")


@dataclass
class MappingReport:
    processed: int = 0
    mapped: int = 0
    unmapped: int = 0
    pilot_ready: int = 0
    updated: int = 0
    created: int = 0
    pilot_sources: list[dict] = field(default_factory=list)

    def to_api_dict(self) -> dict:
        return {
            "processed": self.processed,
            "mapped": self.mapped,
            "unmapped": self.unmapped,
            "pilot_ready": self.pilot_ready,
            "updated": self.updated,
            "created": self.created,
            "pilot_sources": self.pilot_sources,
        }


@dataclass
class CoverageReport:
    present: int = 0
    mapped: int = 0
    unmapped: int = 0
    pilot_ready: int = 0
    by_subject: dict[str, dict[str, int]] = field(default_factory=dict)
    pilot_sources: list[dict] = field(default_factory=list)

    def to_api_dict(self) -> dict:
        return {
            "present": self.present,
            "mapped": self.mapped,
            "unmapped": self.unmapped,
            "pilot_ready": self.pilot_ready,
            "by_subject": self.by_subject,
            "pilot_sources": self.pilot_sources,
        }


class SourceAcademicMappingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.mapping_repo = SourceAcademicMappingRepository(session)
        self.source_repo = SourceDocumentRepository(session)

    async def resolve_mapping_for_source(self, source: SourceDocument) -> SourceAcademicMapping:
        ncert_num = extract_ncert_chapter_number(source.file_name)
        explicit = lookup_explicit_mapping(
            source_subject_code=source.subject_code,
            class_level=source.class_level,
            ncert_chapter_number=ncert_num,
        )

        if explicit is None:
            return SourceAcademicMapping(
                source_document_id=source.id,
                chapter_id=None,
                mapping_status="UNMAPPED",
                academic_subject_code=None,
                chapter_code=None,
                ncert_chapter_number=ncert_num,
                pilot_ready=False,
                mapping_notes="No explicit registry entry — not guessed",
            )

        chapter = await self.mapping_repo.get_chapter_for_subject(
            subject_code=explicit.academic_subject_code,
            chapter_code=explicit.chapter_code,
        )
        if chapter is None:
            return SourceAcademicMapping(
                source_document_id=source.id,
                chapter_id=None,
                mapping_status="UNMAPPED",
                academic_subject_code=explicit.academic_subject_code,
                chapter_code=explicit.chapter_code,
                ncert_chapter_number=ncert_num,
                pilot_ready=False,
                mapping_notes="Registry entry points to chapter not present in academic seed",
            )

        has_tree = await self.mapping_repo.chapter_has_topic_concept_tree(chapter.id)
        content_ok = False
        content_note = ""
        try:
            resolved_path = resolve_source_document_path(source)
            content_ok = pdf_content_matches_chapter(resolved_path, explicit.chapter_code)
            if not content_ok:
                content_note = content_mismatch_detail(resolved_path, explicit.chapter_code)
        except Exception as exc:  # noqa: BLE001 — missing path must not invent pilot_ready
            content_ok = False
            content_note = f"content preflight unavailable: {exc}"

        # pilot_ready requires registry + topic/concept tree + PDF body match.
        pilot_ready = (
            explicit.chapter_code in PILOT_CHAPTER_CODES
            and has_tree
            and content_ok
        )
        notes = explicit.note or ""
        if content_note and not content_ok:
            notes = f"{notes}; {content_note}".strip("; ").strip()

        return SourceAcademicMapping(
            source_document_id=source.id,
            chapter_id=chapter.id,
            mapping_status="MAPPED",
            academic_subject_code=explicit.academic_subject_code,
            chapter_code=explicit.chapter_code,
            ncert_chapter_number=ncert_num,
            pilot_ready=pilot_ready,
            mapping_notes=notes or None,
        )

    async def upsert_mapping_for_source(self, source: SourceDocument) -> tuple[SourceAcademicMapping, bool]:
        """Return (mapping, created)."""
        resolved = await self.resolve_mapping_for_source(source)
        existing = await self.mapping_repo.get_for_source(source.id)
        if existing is None:
            self.mapping_repo.add(resolved)
            return resolved, True

        existing.chapter_id = resolved.chapter_id
        existing.mapping_status = resolved.mapping_status
        existing.academic_subject_code = resolved.academic_subject_code
        existing.chapter_code = resolved.chapter_code
        existing.ncert_chapter_number = resolved.ncert_chapter_number
        existing.pilot_ready = resolved.pilot_ready
        existing.mapping_notes = resolved.mapping_notes
        return existing, False

    async def sync_all(self) -> MappingReport:
        report = MappingReport()
        docs, total = await self.source_repo.list_neet(limit=500)
        report.processed = total

        for doc in docs:
            mapping, created = await self.upsert_mapping_for_source(doc)
            if created:
                report.created += 1
            else:
                report.updated += 1
            if mapping.mapping_status == "MAPPED":
                report.mapped += 1
            else:
                report.unmapped += 1
            if mapping.pilot_ready:
                report.pilot_ready += 1
            if doc.relative_source_path in PILOT_SOURCE_RELATIVE_PATHS and mapping.pilot_ready:
                report.pilot_sources.append(
                    {
                        "source_document_id": str(doc.id),
                        "relative_source_path": doc.relative_source_path,
                        "chapter_code": mapping.chapter_code,
                        "academic_subject_code": mapping.academic_subject_code,
                    }
                )

        await self.mapping_repo.commit()
        logger.info("source_academic_mapping_sync_complete", **report.to_api_dict())
        return report

    async def get_chapter_code_for_source(self, source_document_id: uuid.UUID) -> str:
        mapping = await self.mapping_repo.get_for_source(source_document_id)
        if mapping is None or mapping.mapping_status != "MAPPED" or not mapping.chapter_code:
            raise ValueError("UNMAPPED")
        return mapping.chapter_code

    async def coverage_report(self) -> CoverageReport:
        docs, total = await self.source_repo.list_neet(limit=500)
        mappings = await self.mapping_repo.list_all()
        by_id = {m.source_document_id: m for m in mappings}

        report = CoverageReport(present=total)
        by_subject: dict[str, dict[str, int]] = {}

        for doc in docs:
            subj = doc.subject_code
            by_subject.setdefault(subj, {"present": 0, "mapped": 0, "unmapped": 0, "pilot_ready": 0})
            by_subject[subj]["present"] += 1

            mapping = by_id.get(doc.id)
            if mapping is None:
                report.unmapped += 1
                by_subject[subj]["unmapped"] += 1
                continue
            if mapping.mapping_status == "MAPPED":
                report.mapped += 1
                by_subject[subj]["mapped"] += 1
            else:
                report.unmapped += 1
                by_subject[subj]["unmapped"] += 1
            if mapping.pilot_ready:
                report.pilot_ready += 1
                by_subject[subj]["pilot_ready"] += 1
            if doc.relative_source_path in PILOT_SOURCE_RELATIVE_PATHS and mapping.pilot_ready:
                report.pilot_sources.append(
                    {
                        "source_document_id": str(doc.id),
                        "relative_source_path": doc.relative_source_path,
                        "chapter_code": mapping.chapter_code,
                        "academic_subject_code": mapping.academic_subject_code,
                    }
                )

        report.by_subject = by_subject
        return report

    def mapping_to_dict(self, mapping: SourceAcademicMapping | None) -> dict | None:
        if mapping is None:
            return None
        return {
            "mapping_status": mapping.mapping_status,
            "academic_subject_code": mapping.academic_subject_code,
            "chapter_code": mapping.chapter_code,
            "ncert_chapter_number": mapping.ncert_chapter_number,
            "pilot_ready": mapping.pilot_ready,
            "mapping_notes": mapping.mapping_notes,
        }
