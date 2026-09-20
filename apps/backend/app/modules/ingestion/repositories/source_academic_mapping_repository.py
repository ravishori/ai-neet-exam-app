"""Persistence for ingestion.source_academic_mappings (ADR-0031)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.academic.models import Chapter, Subject, Topic
from app.modules.ingestion.models.source_academic_mapping import SourceAcademicMapping
from app.modules.ingestion.models.source_document import SourceDocument


class SourceAcademicMappingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_source(self, source_document_id: uuid.UUID) -> SourceAcademicMapping | None:
        result = await self.session.execute(
            select(SourceAcademicMapping).where(
                SourceAcademicMapping.source_document_id == source_document_id,
                SourceAcademicMapping.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_with_source(self, source_document_id: uuid.UUID) -> SourceAcademicMapping | None:
        result = await self.session.execute(
            select(SourceAcademicMapping)
            .options(selectinload(SourceAcademicMapping.source_document))
            .where(
                SourceAcademicMapping.source_document_id == source_document_id,
                SourceAcademicMapping.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[SourceAcademicMapping]:
        result = await self.session.execute(
            select(SourceAcademicMapping)
            .where(SourceAcademicMapping.deleted_at.is_(None))
            .order_by(SourceAcademicMapping.created_at)
        )
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(SourceAcademicMapping.mapping_status, func.count(SourceAcademicMapping.id))
                .where(SourceAcademicMapping.deleted_at.is_(None))
                .group_by(SourceAcademicMapping.mapping_status)
            )
        ).all()
        return {status: count for status, count in rows}

    async def get_chapter_for_subject(self, *, subject_code: str, chapter_code: str) -> Chapter | None:
        result = await self.session.execute(
            select(Chapter)
            .join(Subject, Chapter.subject_id == Subject.id)
            .where(Subject.code == subject_code, Chapter.code == chapter_code)
        )
        return result.scalar_one_or_none()

    async def chapter_has_topic_concept_tree(self, chapter_id: uuid.UUID) -> bool:
        """True when the chapter has at least one topic with at least one concept."""
        from app.modules.academic.models import Concept

        result = await self.session.execute(
            select(func.count(Concept.id)).join(Topic, Concept.topic_id == Topic.id).where(Topic.chapter_id == chapter_id)
        )
        return (result.scalar_one() or 0) > 0

    async def list_source_documents_without_mapping(self) -> list[SourceDocument]:
        mapped_ids = select(SourceAcademicMapping.source_document_id).where(SourceAcademicMapping.deleted_at.is_(None))
        result = await self.session.execute(
            select(SourceDocument).where(
                SourceDocument.deleted_at.is_(None),
                SourceDocument.id.not_in(mapped_ids),
            )
        )
        return list(result.scalars().all())

    def add(self, mapping: SourceAcademicMapping) -> None:
        self.session.add(mapping)

    async def commit(self) -> None:
        await self.session.commit()
