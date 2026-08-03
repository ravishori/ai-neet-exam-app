import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Chapter, Concept
from app.modules.cms.models import ContentItem
from app.modules.ingestion.models import IngestionJob, IngestionSection, VisualAsset

# Empirically chosen against the real Current Electricity pilot chapter —
# see ADR-0022. "3.4 OHM'S LAW" -> concept "Ohm's Law" scores 0.71;
# "3.5 DRIFT OF ELECTRONS..." -> "Drift Velocity" scores 0.13; the
# highest false-positive noise among unrelated heading/concept pairs in
# that same chapter tops out at 0.11. 0.12 sits in the gap between them.
CONCEPT_MATCH_THRESHOLD = 0.12

# Full-sentence near-duplicate detection needs a much tighter bar than
# heading-to-concept-name matching — two genuinely different NEET
# questions on the same concept rarely exceed ~0.4 stem similarity.
DEDUP_SIMILARITY_THRESHOLD = 0.6


class IngestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_job_by_checksum(self, checksum: str) -> IngestionJob | None:
        result = await self.session.execute(select(IngestionJob).where(IngestionJob.file_checksum == checksum))
        return result.scalars().first()

    async def get_job(self, job_id: uuid.UUID) -> IngestionJob | None:
        result = await self.session.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        return result.scalar_one_or_none()

    async def list_jobs(self, limit: int = 50) -> list[IngestionJob]:
        result = await self.session.execute(select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def list_jobs_paginated(
        self, *, status: str | None = None, limit: int = 20, offset: int = 0
    ) -> tuple[list[IngestionJob], int]:
        """Admin Portal (PR11) Module 4 — the existing list_jobs() has no
        pagination/filter and is used by the live-polling admin table, which
        would break if changed; kept as a separate method instead."""
        base = select(IngestionJob)
        count_query = select(func.count(IngestionJob.id))
        if status:
            base = base.where(IngestionJob.status == status)
            count_query = count_query.where(IngestionJob.status == status)

        total = (await self.session.execute(count_query)).scalar_one()
        base = base.order_by(IngestionJob.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(base)
        return list(result.scalars().all()), total

    async def list_sections_for_job(self, job_id: uuid.UUID) -> list[IngestionSection]:
        result = await self.session.execute(
            select(IngestionSection).where(IngestionSection.job_id == job_id).order_by(IngestionSection.source_page)
        )
        return list(result.scalars().all())

    async def list_visual_assets_for_job(self, job_id: uuid.UUID) -> list[VisualAsset]:
        result = await self.session.execute(
            select(VisualAsset).where(VisualAsset.job_id == job_id).order_by(VisualAsset.source_page)
        )
        return list(result.scalars().all())

    async def list_visual_assets_paginated(
        self,
        *,
        review_status: str | None = None,
        asset_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[VisualAsset], int]:
        """Admin Portal (PR11) Module 5 — Visual Asset Review. No list/browse
        endpoint existed for this table before PR11 — every prior consumer
        only ever fetched VERIFIED assets scoped to one question/knowledge
        unit (PR7's image serving, PR2's question browse)."""
        base = select(VisualAsset)
        count_query = select(func.count(VisualAsset.id))
        if review_status:
            base = base.where(VisualAsset.review_status == review_status)
            count_query = count_query.where(VisualAsset.review_status == review_status)
        if asset_type:
            base = base.where(VisualAsset.asset_type == asset_type)
            count_query = count_query.where(VisualAsset.asset_type == asset_type)

        total = (await self.session.execute(count_query)).scalar_one()
        base = base.order_by(VisualAsset.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(base)
        return list(result.scalars().all()), total

    async def get_visual_asset(self, asset_id: uuid.UUID) -> VisualAsset | None:
        result = await self.session.execute(select(VisualAsset).where(VisualAsset.id == asset_id))
        return result.scalar_one_or_none()

    def add_job(self, job: IngestionJob) -> None:
        self.session.add(job)

    def add_section(self, section: IngestionSection) -> None:
        self.session.add(section)

    def add_visual_asset(self, asset: VisualAsset) -> None:
        self.session.add(asset)

    async def get_chapter_by_code(self, chapter_code: str) -> Chapter | None:
        result = await self.session.execute(select(Chapter).where(Chapter.code == chapter_code))
        return result.scalars().first()

    async def get_chapter(self, chapter_id: uuid.UUID) -> Chapter | None:
        result = await self.session.execute(select(Chapter).where(Chapter.id == chapter_id))
        return result.scalar_one_or_none()

    async def match_concept_for_heading(self, chapter_id: uuid.UUID, heading: str) -> tuple[Concept, float] | None:
        """Best-matching concept under this chapter for a section heading,
        via Postgres trigram similarity — see CONCEPT_MATCH_THRESHOLD."""
        result = await self.session.execute(
            text(
                """
                SELECT c.id, similarity(:heading, c.name) AS sim
                FROM academic.concepts c
                JOIN academic.topics t ON t.id = c.topic_id
                WHERE t.chapter_id = :chapter_id
                ORDER BY sim DESC
                LIMIT 1
                """
            ),
            {"heading": heading, "chapter_id": str(chapter_id)},
        )
        row = result.first()
        if not row or row.sim < CONCEPT_MATCH_THRESHOLD:
            return None
        concept_result = await self.session.execute(select(Concept).where(Concept.id == row.id))
        concept = concept_result.scalar_one()
        return concept, float(row.sim)

    async def is_duplicate_stem(self, concept_id: uuid.UUID, stem: str) -> bool:
        """True if an existing (non-archived) question on this concept has a
        near-identical stem, via Postgres trigram similarity."""
        result = await self.session.execute(
            text(
                """
                SELECT 1
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.concept_id = :concept_id
                  AND ci.content_type = 'QUESTION'
                  AND ci.status != 'ARCHIVED'
                  AND similarity(:stem, cv.body ->> 'stem') > :threshold
                LIMIT 1
                """
            ),
            {"concept_id": str(concept_id), "stem": stem, "threshold": DEDUP_SIMILARITY_THRESHOLD},
        )
        return result.first() is not None

    async def has_concept_note(self, concept_id: uuid.UUID) -> bool:
        """True if this concept already has a non-archived CONCEPT_NOTE —
        keeps re-running a job (or ingesting another chapter section that
        maps to the same concept) from flooding duplicate notes."""
        result = await self.session.execute(
            select(ContentItem.id).where(
                ContentItem.concept_id == concept_id,
                ContentItem.content_type == "CONCEPT_NOTE",
                ContentItem.status != "ARCHIVED",
            )
        )
        return result.first() is not None

    async def commit(self) -> None:
        await self.session.commit()

    async def flush(self) -> None:
        await self.session.flush()
