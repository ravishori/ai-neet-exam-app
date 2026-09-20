"""Content Factory persistence (FACTORY-P1)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.cms.models.content_factory import ContentBatch, GenerationJob, GenerationRun


class ContentFactoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add_batch(self, batch: ContentBatch) -> None:
        self.session.add(batch)

    def add_job(self, job: GenerationJob) -> None:
        self.session.add(job)

    def add_run(self, run: GenerationRun) -> None:
        self.session.add(run)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def get_batch_by_key(self, batch_key: str) -> ContentBatch | None:
        result = await self.session.execute(
            select(ContentBatch)
            .options(selectinload(ContentBatch.jobs).selectinload(GenerationJob.runs))
            .where(ContentBatch.batch_key == batch_key, ContentBatch.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_batch(self, batch_id: uuid.UUID) -> ContentBatch | None:
        result = await self.session.execute(
            select(ContentBatch)
            .options(selectinload(ContentBatch.jobs).selectinload(GenerationJob.runs))
            .where(ContentBatch.id == batch_id, ContentBatch.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_batches(
        self,
        *,
        status: str | None = None,
        subject_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContentBatch], int]:
        filters = [ContentBatch.deleted_at.is_(None)]
        if status:
            filters.append(ContentBatch.status == status)
        if subject_id:
            filters.append(ContentBatch.subject_id == subject_id)

        count_q = select(func.count(ContentBatch.id)).where(*filters)
        total = (await self.session.execute(count_q)).scalar_one()

        result = await self.session.execute(
            select(ContentBatch)
            .where(*filters)
            .order_by(ContentBatch.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def get_job(self, job_id: uuid.UUID) -> GenerationJob | None:
        result = await self.session.execute(
            select(GenerationJob)
            .options(selectinload(GenerationJob.runs), selectinload(GenerationJob.batch))
            .where(GenerationJob.id == job_id, GenerationJob.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_job_by_key(self, batch_id: uuid.UUID, job_key: str) -> GenerationJob | None:
        result = await self.session.execute(
            select(GenerationJob)
            .options(selectinload(GenerationJob.runs))
            .where(
                GenerationJob.batch_id == batch_id,
                GenerationJob.job_key == job_key,
                GenerationJob.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        batch_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[GenerationJob], int]:
        filters = [GenerationJob.batch_id == batch_id, GenerationJob.deleted_at.is_(None)]
        total = (
            await self.session.execute(select(func.count(GenerationJob.id)).where(*filters))
        ).scalar_one()
        result = await self.session.execute(
            select(GenerationJob)
            .options(selectinload(GenerationJob.runs))
            .where(*filters)
            .order_by(GenerationJob.created_at.asc())
            .limit(limit)
            .offset(offset)
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all()), total

    async def get_run(self, run_id: uuid.UUID) -> GenerationRun | None:
        result = await self.session.execute(
            select(GenerationRun)
            .options(selectinload(GenerationRun.job))
            .where(GenerationRun.id == run_id, GenerationRun.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def next_attempt_number(self, job_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(GenerationRun.attempt_number), 0)).where(
                GenerationRun.job_id == job_id,
                GenerationRun.deleted_at.is_(None),
            )
        )
        return int(result.scalar_one()) + 1
