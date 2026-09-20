"""Persistence for ingestion.source_documents (ADR-0030)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.models.source_document import SourceDocument


class SourceDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, document_id: uuid.UUID) -> SourceDocument | None:
        result = await self.session.execute(select(SourceDocument).where(SourceDocument.id == document_id))
        return result.scalar_one_or_none()

    async def get_by_checksum(self, checksum: str) -> SourceDocument | None:
        result = await self.session.execute(
            select(SourceDocument).where(
                SourceDocument.checksum_sha256 == checksum,
                SourceDocument.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_relative_path(self, relative_path: str) -> SourceDocument | None:
        result = await self.session.execute(
            select(SourceDocument).where(
                SourceDocument.relative_source_path == relative_path,
                SourceDocument.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_neet(
        self,
        *,
        subject_code: str | None = None,
        class_level: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SourceDocument], int]:
        base = select(SourceDocument).where(SourceDocument.deleted_at.is_(None))
        count_query = select(func.count(SourceDocument.id)).where(SourceDocument.deleted_at.is_(None))
        if subject_code:
            base = base.where(SourceDocument.subject_code == subject_code)
            count_query = count_query.where(SourceDocument.subject_code == subject_code)
        if class_level:
            base = base.where(SourceDocument.class_level == class_level)
            count_query = count_query.where(SourceDocument.class_level == class_level)

        total = (await self.session.execute(count_query)).scalar_one()
        result = await self.session.execute(
            base.order_by(SourceDocument.subject_code, SourceDocument.class_level, SourceDocument.relative_source_path)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    def add(self, document: SourceDocument) -> None:
        self.session.add(document)

    async def commit(self) -> None:
        await self.session.commit()
