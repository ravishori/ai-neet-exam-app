import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.modules.academic.models import Concept
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.services.json_utils import parse_json_response
from app.modules.cms.schemas.content_bodies import validate_body
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.ingestion.models import IngestionJob, IngestionSection
from app.modules.ingestion.prompts import ingestion_concept_note, ingestion_flashcards, ingestion_mcq, ingestion_revision_sheet
from app.modules.ingestion.repositories.ingestion_repository import IngestionRepository
from app.modules.ingestion.services.pdf_extraction_service import (
    ExtractedSection,
    compute_checksum,
    extract_pages,
    split_into_sections,
)
from app.modules.knowledge.services.knowledge_structuring_service import KnowledgeStructuringService

logger = get_logger("ingestion")

# Keeps prompts bounded and cost predictable — the pilot chapter's largest
# section (Wheatstone Bridge, ~11.8k chars) still fits comfortably.
MAX_SECTION_CHARS_IN_PROMPT = 8000

Matched = tuple[ExtractedSection, IngestionSection, Concept]


class IngestionPipelineService:
    """Extract -> match -> generate -> dedup -> store as DRAFT. See ADR-0022
    for why this exists as one bounded pilot instead of the full brief."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IngestionRepository(session)
        self.workflow = ContentWorkflowService(session)
        self.gateway = AIGateway(session)
        self.structuring = KnowledgeStructuringService(session)

    async def start_job(self, *, file_path: str, chapter_code: str) -> IngestionJob:
        checksum = compute_checksum(file_path)
        existing = await self.repo.get_job_by_checksum(checksum)
        if existing and existing.status == "COMPLETED":
            logger.info("ingestion_skip_unchanged", file_path=file_path, job_id=str(existing.id))
            return existing

        chapter = await self.repo.get_chapter_by_code(chapter_code)
        if not chapter:
            raise NotFoundError(f"Chapter '{chapter_code}' not found")

        job = IngestionJob(
            source_file_path=file_path,
            file_checksum=checksum,
            subject_id=chapter.subject_id,
            chapter_id=chapter.id,
            status="PENDING",
        )
        self.repo.add_job(job)
        await self.repo.commit()
        logger.info("ingestion_job_created", job_id=str(job.id), file_path=file_path, chapter_code=chapter_code)
        return job

    async def run(self, *, job_id: uuid.UUID, author_id: uuid.UUID) -> None:
        """Runs from a FastAPI BackgroundTask — exceptions never reach an
        HTTP response, every stage records its own state on the job row
        so a failure is visible via GET /ingestion/jobs/{id}, not silent."""
        job = await self.repo.get_job(job_id)
        if not job:
            logger.error("ingestion_job_not_found", job_id=str(job_id))
            return

        try:
            sections = await self._run_extraction(job)
            matched = await self._run_matching(job, sections)
            await self._run_structuring(job, matched, author_id)
            await self._run_generation(job, matched, author_id)
            await self._run_concept_notes(job, matched, author_id)
            await self._run_revision_sheet(job, matched, author_id)

            job.status = "COMPLETED"
            job.stage_detail = None
            await self.repo.commit()
            logger.info(
                "ingestion_completed",
                job_id=str(job.id),
                sections=job.sections_detected,
                matched=len(matched),
                questions=job.questions_generated,
                deduped=job.questions_deduped,
            )
        except Exception as exc:  # noqa: BLE001 — top-level background-task boundary, must not raise
            job.status = "FAILED"
            job.error_message = str(exc)[:2000]
            await self.repo.commit()
            logger.error("ingestion_failed", job_id=str(job.id), error=str(exc))

    async def _run_extraction(self, job: IngestionJob) -> list[ExtractedSection]:
        job.status = "EXTRACTING"
        job.stage_detail = "Extracting PDF text"
        await self.repo.commit()

        pages = extract_pages(job.source_file_path)
        sections = split_into_sections(pages)
        job.sections_detected = len(sections)
        return sections

    async def _run_matching(
        self, job: IngestionJob, sections: list[ExtractedSection]
    ) -> list[tuple[ExtractedSection, IngestionSection, Concept]]:
        job.status = "MATCHING"
        await self.repo.commit()

        matched: list[tuple[ExtractedSection, IngestionSection, Concept]] = []
        for section in sections:
            result = await self.repo.match_concept_for_heading(job.chapter_id, section.heading)
            section_row = IngestionSection(
                job_id=job.id,
                heading=section.heading,
                source_page=section.source_page,
                raw_text=section.text,
                matched_concept_id=result[0].id if result else None,
            )
            self.repo.add_section(section_row)
            if result:
                matched.append((section, section_row, result[0]))

        job.stage_detail = f"Matched {len(matched)}/{len(sections)} sections to existing concepts"
        await self.repo.flush()
        await self.repo.commit()
        return matched

    async def _run_structuring(self, job: IngestionJob, matched: list[Matched], author_id: uuid.UUID) -> None:
        """Creates a gate-checked Knowledge Unit per matched section — see
        ADR-0024. Deliberately does not feed GENERATING below; that's PR 2.
        A structuring failure (AI fallback, bad JSON, gate rejection) is
        recorded and the pipeline proceeds — generation from raw text is
        unaffected either way in this PR."""
        job.status = "STRUCTURING"
        job.stage_detail = f"Structuring knowledge units for {len(matched)} matched sections"
        await self.repo.commit()

        for _section, section_row, concept in matched:
            unit = await self.structuring.structure_section(section=section_row, concept=concept, author_id=author_id)
            if unit is None:
                continue
            if unit.validation_status == "PASSED":
                job.knowledge_units_created += 1
            else:
                job.knowledge_units_rejected += 1

        await self.repo.commit()

    async def _run_generation(self, job: IngestionJob, matched: list[Matched], author_id: uuid.UUID) -> None:
        job.status = "GENERATING"
        job.stage_detail = f"Generating MCQs and flashcards for {len(matched)} matched sections"
        await self.repo.commit()

        for section, section_row, concept in matched:
            await self._generate_questions_for_section(job=job, section=section, section_row=section_row, concept=concept, author_id=author_id)
            await self._generate_flashcards_for_section(job=job, section=section, concept=concept, author_id=author_id)

    async def _generate_questions_for_section(
        self, *, job: IngestionJob, section: ExtractedSection, section_row: IngestionSection, concept: Concept, author_id: uuid.UUID
    ) -> None:
        user_prompt = ingestion_mcq.build_prompt(
            concept_name=concept.name,
            section_heading=section.heading,
            source_text=section.text[:MAX_SECTION_CHARS_IN_PROMPT],
            source_page=section.source_page,
        )
        response = await self.gateway.generate(
            agent_type="INGESTION_MCQ",
            system_prompt=ingestion_mcq.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            user_id=author_id,
            max_tokens=1500,
        )
        if response.is_fallback:
            logger.info("ingestion_generation_fallback", job_id=str(job.id), asset="mcq", section=section.heading)
            return

        try:
            questions = parse_json_response(response.text)
        except ValueError as exc:
            logger.error("ingestion_bad_json", job_id=str(job.id), asset="mcq", section=section.heading, error=str(exc), raw=response.text[:200])
            return

        for q in questions:
            stem = q.get("stem", "")
            if stem and await self.repo.is_duplicate_stem(concept.id, stem):
                job.questions_deduped += 1
                logger.info("ingestion_duplicate_dropped", job_id=str(job.id), concept=concept.name, stem=stem[:80])
                continue

            validated = validate_body("QUESTION", q)
            await self.workflow.create_item(
                content_type="QUESTION",
                concept_id=concept.id,
                title=f"Ingested question — {concept.name} (p.{section.source_page})",
                slug=f"ingested-{concept.code}-{uuid.uuid4().hex[:8]}",
                tags=["ai-generated", "ingested", f"source-page-{section.source_page}"],
                language="en",
                body=validated,
                author_id=author_id,
            )
            job.questions_generated += 1
            section_row.questions_generated += 1

        await self.repo.commit()

    async def _generate_flashcards_for_section(
        self, *, job: IngestionJob, section: ExtractedSection, concept: Concept, author_id: uuid.UUID
    ) -> None:
        user_prompt = ingestion_flashcards.build_prompt(
            concept_name=concept.name,
            section_heading=section.heading,
            source_text=section.text[:MAX_SECTION_CHARS_IN_PROMPT],
            source_page=section.source_page,
        )
        response = await self.gateway.generate(
            agent_type="INGESTION_FLASHCARD",
            system_prompt=ingestion_flashcards.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            user_id=author_id,
            max_tokens=800,
        )
        if response.is_fallback:
            logger.info("ingestion_generation_fallback", job_id=str(job.id), asset="flashcard", section=section.heading)
            return

        try:
            flashcards = parse_json_response(response.text)
        except ValueError as exc:
            logger.error("ingestion_bad_json", job_id=str(job.id), asset="flashcard", section=section.heading, error=str(exc), raw=response.text[:200])
            return

        for card in flashcards:
            validated = validate_body("FLASHCARD", card)
            await self.workflow.create_item(
                content_type="FLASHCARD",
                concept_id=concept.id,
                title=f"Ingested flashcard — {concept.name} (p.{section.source_page})",
                slug=f"ingested-fc-{concept.code}-{uuid.uuid4().hex[:8]}",
                tags=["ai-generated", "ingested", f"source-page-{section.source_page}"],
                language="en",
                body=validated,
                author_id=author_id,
            )
            job.flashcards_generated += 1

        await self.repo.commit()

    async def _run_concept_notes(self, job: IngestionJob, matched: list[Matched], author_id: uuid.UUID) -> None:
        """One short note per concept — not per section — synthesized from
        every matched section that concept touches. Skipped for concepts
        that already have a non-archived note, so re-running a job (or a
        later chapter mapping to the same concept) never floods duplicates."""
        job.status = "GENERATING"
        concepts_by_id: dict[uuid.UUID, Concept] = {}
        sections_by_concept_id: dict[uuid.UUID, list[ExtractedSection]] = defaultdict(list)
        for section, _section_row, concept in matched:
            concepts_by_id[concept.id] = concept
            sections_by_concept_id[concept.id].append(section)

        job.stage_detail = f"Generating short notes for {len(concepts_by_id)} concepts"
        await self.repo.commit()

        for concept_id, concept in concepts_by_id.items():
            concept_sections = sections_by_concept_id[concept_id]
            if await self.repo.has_concept_note(concept.id):
                logger.info("ingestion_note_skip_exists", job_id=str(job.id), concept=concept.name)
                continue

            excerpts = [(s.heading, s.text[:MAX_SECTION_CHARS_IN_PROMPT]) for s in concept_sections]
            user_prompt = ingestion_concept_note.build_prompt(concept_name=concept.name, excerpts=excerpts)
            response = await self.gateway.generate(
                agent_type="INGESTION_CONCEPT_NOTE",
                system_prompt=ingestion_concept_note.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                user_id=author_id,
                max_tokens=1000,
            )
            if response.is_fallback:
                logger.info("ingestion_generation_fallback", job_id=str(job.id), asset="concept_note", concept=concept.name)
                continue

            try:
                note = parse_json_response(response.text)
            except ValueError as exc:
                logger.error("ingestion_bad_json", job_id=str(job.id), asset="concept_note", concept=concept.name, error=str(exc), raw=response.text[:200])
                continue

            validated = validate_body("CONCEPT_NOTE", note)
            await self.workflow.create_item(
                content_type="CONCEPT_NOTE",
                concept_id=concept.id,
                title=f"Ingested note — {concept.name}",
                slug=f"ingested-note-{concept.code}-{uuid.uuid4().hex[:8]}",
                tags=["ai-generated", "ingested"],
                language="en",
                body=validated,
                author_id=author_id,
            )
            job.notes_generated += 1
            await self.repo.commit()

    async def _run_revision_sheet(self, job: IngestionJob, matched: list[Matched], author_id: uuid.UUID) -> None:
        """One chapter-level revision sheet — concept_id left null since it
        spans every matched concept, not one."""
        if not matched:
            return

        job.status = "GENERATING"
        job.stage_detail = "Generating chapter revision sheet"
        await self.repo.commit()

        chapter = await self.repo.get_chapter(job.chapter_id)
        excerpts = [(section.heading, section.text) for section, _row, _concept in matched]
        user_prompt = ingestion_revision_sheet.build_prompt(chapter_name=chapter.name, excerpts=excerpts)
        response = await self.gateway.generate(
            agent_type="INGESTION_REVISION_SHEET",
            system_prompt=ingestion_revision_sheet.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            user_id=author_id,
            max_tokens=1500,
        )
        if response.is_fallback:
            logger.info("ingestion_generation_fallback", job_id=str(job.id), asset="revision_sheet", chapter=chapter.name)
            return

        try:
            sheet = parse_json_response(response.text)
        except ValueError as exc:
            logger.error("ingestion_bad_json", job_id=str(job.id), asset="revision_sheet", chapter=chapter.name, error=str(exc), raw=response.text[:200])
            return

        validated = validate_body("FORMULA_SHEET", sheet)
        await self.workflow.create_item(
            content_type="FORMULA_SHEET",
            concept_id=None,
            title=f"Ingested revision sheet — {chapter.name}",
            slug=f"ingested-revision-{chapter.code}-{uuid.uuid4().hex[:8]}",
            tags=["ai-generated", "ingested"],
            language="en",
            body=validated,
            author_id=author_id,
        )
        job.revision_sheets_generated += 1
        await self.repo.commit()
