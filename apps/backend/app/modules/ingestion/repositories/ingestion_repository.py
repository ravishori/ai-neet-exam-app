import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Chapter, Concept
from app.modules.cms.models import ContentItem
from app.modules.ingestion.models import IngestionJob, IngestionSection

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

    def add_job(self, job: IngestionJob) -> None:
        self.session.add(job)

    def add_section(self, section: IngestionSection) -> None:
        self.session.add(section)

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
