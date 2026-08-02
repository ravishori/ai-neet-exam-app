import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.modules.academic.models import Concept
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.services.json_utils import parse_json_response
from app.modules.cms.schemas.content_bodies import validate_body
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.ingestion.models import IngestionJob, IngestionSection, VisualAsset
from app.modules.ingestion.prompts import ingestion_concept_note, ingestion_flashcards, ingestion_mcq, ingestion_revision_sheet
from app.modules.ingestion.repositories.ingestion_repository import IngestionRepository
from app.modules.ingestion.services.pdf_extraction_service import (
    ExtractedSection,
    compute_checksum,
    extract_pages,
    split_into_sections,
)
from app.modules.ingestion.services.visual_asset_detection_service import crop_and_store, detect_visual_assets
from app.modules.knowledge.models import KnowledgeUnit
from app.modules.knowledge.services.knowledge_rendering import render_facts_for_prompt
from app.modules.knowledge.services.knowledge_structuring_service import KnowledgeStructuringService

logger = get_logger("ingestion")

Matched = tuple[ExtractedSection, IngestionSection, Concept]
# Maps a matched section's IngestionSection.id to the PASSED KnowledgeUnit
# generation is allowed to read from — see ADR-0025. A section absent from
# this dict has no PASSED unit (structuring failed, was rejected by a
# gate, or the AI call itself produced nothing usable) and generation
# must skip it, never fall back to its raw_text.
PassedUnits = dict[uuid.UUID, KnowledgeUnit]


class IngestionPipelineService:
    """Extract -> match -> structure -> generate -> dedup -> store as DRAFT.
    See ADR-0022 for why this exists as one bounded pilot instead of the
    full brief, and ADR-0024/ADR-0025 for why generation reads Knowledge
    Units rather than raw section text."""

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
            await self._run_asset_detection(job)
            matched = await self._run_matching(job, sections)
            knowledge_units = await self._run_structuring(job, matched, author_id)
            await self._run_generation(job, matched, knowledge_units, author_id)
            await self._run_concept_notes(job, matched, knowledge_units, author_id)
            await self._run_revision_sheet(job, matched, knowledge_units, author_id)

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

    async def _run_asset_detection(self, job: IngestionJob) -> None:
        """Detects visual assets (ADR-0026) — independent of section
        matching, so it runs right after text extraction rather than after
        _run_matching. A row is created for every detected asset, whether
        or not its bounding box is confidently isolated (see
        visual_asset_detection_service's module docstring); only the
        review_status differs, never whether a row exists at all."""
        job.stage_detail = "Detecting visual assets"
        await self.repo.commit()

        settings = get_settings()
        detected = detect_visual_assets(job.source_file_path)
        for asset in detected:
            x0, y0, x1, y1 = asset.bounding_box
            row = VisualAsset(
                job_id=job.id,
                source_page=asset.source_page,
                bounding_box={"x0": x0, "y0": y0, "x1": x1, "y1": y1, "unit": "pdf_points_72dpi"},
                asset_type=asset.asset_type,
                detection_method=asset.detection_method,
                review_status=asset.review_status,
            )
            crop_info = crop_and_store(job.source_file_path, asset, settings.visual_assets_dir)
            row.storage_path = crop_info["storage_path"]
            row.content_hash = crop_info["content_hash"]
            row.width_px = crop_info["width_px"]
            row.height_px = crop_info["height_px"]
            row.render_dpi = crop_info["render_dpi"]

            self.repo.add_visual_asset(row)
            job.visual_assets_detected += 1
            if asset.review_status == "NEEDS_MANUAL_BBOX":
                job.visual_assets_needing_review += 1

        job.stage_detail = f"Detected {job.visual_assets_detected} visual assets ({job.visual_assets_needing_review} need review)"
        await self.repo.commit()
        logger.info(
            "ingestion_asset_detection_complete",
            job_id=str(job.id),
            detected=job.visual_assets_detected,
            needing_review=job.visual_assets_needing_review,
        )

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

    async def _run_structuring(self, job: IngestionJob, matched: list[Matched], author_id: uuid.UUID) -> PassedUnits:
        """Creates a gate-checked Knowledge Unit per matched section — see
        ADR-0024. Only PASSED units are handed to generation (ADR-0025); a
        FAILED unit's section is recorded here but excluded from the map
        this returns, and generation treats that section as if it had no
        Knowledge Unit at all."""
        job.status = "STRUCTURING"
        job.stage_detail = f"Structuring knowledge units for {len(matched)} matched sections"
        await self.repo.commit()

        passed_units: PassedUnits = {}
        for _section, section_row, concept in matched:
            unit = await self.structuring.structure_section(section=section_row, concept=concept, author_id=author_id)
            if unit is None:
                continue
            if unit.validation_status == "PASSED":
                job.knowledge_units_created += 1
                passed_units[section_row.id] = unit
            else:
                job.knowledge_units_rejected += 1

        await self.repo.commit()
        return passed_units

    async def _run_generation(
        self, job: IngestionJob, matched: list[Matched], knowledge_units: PassedUnits, author_id: uuid.UUID
    ) -> None:
        job.status = "GENERATING"
        job.stage_detail = f"Generating MCQs and flashcards for {len(matched)} matched sections"
        await self.repo.commit()

        for section, section_row, concept in matched:
            unit = knowledge_units.get(section_row.id)
            if unit is None:
                job.generation_skipped_no_knowledge_unit += 1
                logger.info(
                    "ingestion_generation_skip_no_knowledge_unit", job_id=str(job.id), asset="mcq+flashcard", section=section.heading
                )
                continue
            await self._generate_questions_for_section(
                job=job, section=section, section_row=section_row, concept=concept, unit=unit, author_id=author_id
            )
            await self._generate_flashcards_for_section(job=job, section=section, concept=concept, unit=unit, author_id=author_id)

        await self.repo.commit()

    async def _generate_questions_for_section(
        self,
        *,
        job: IngestionJob,
        section: ExtractedSection,
        section_row: IngestionSection,
        concept: Concept,
        unit: KnowledgeUnit,
        author_id: uuid.UUID,
    ) -> None:
        user_prompt = ingestion_mcq.build_prompt(
            concept_name=concept.name,
            section_heading=section.heading,
            source_text=render_facts_for_prompt(unit),
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
                knowledge_unit_refs=[(unit.id, unit.version)],
                model_used=response.model,
                prompt_version=ingestion_mcq.PROMPT_VERSION,
                confidence_score=unit.extraction_confidence,
                generation_cost_usd=response.cost_usd,
            )
            job.questions_generated += 1
            section_row.questions_generated += 1

        await self.repo.commit()

    async def _generate_flashcards_for_section(
        self, *, job: IngestionJob, section: ExtractedSection, concept: Concept, unit: KnowledgeUnit, author_id: uuid.UUID
    ) -> None:
        user_prompt = ingestion_flashcards.build_prompt(
            concept_name=concept.name,
            section_heading=section.heading,
            source_text=render_facts_for_prompt(unit),
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
                knowledge_unit_refs=[(unit.id, unit.version)],
                model_used=response.model,
                prompt_version=ingestion_flashcards.PROMPT_VERSION,
                confidence_score=unit.extraction_confidence,
                generation_cost_usd=response.cost_usd,
            )
            job.flashcards_generated += 1

        await self.repo.commit()

    async def _run_concept_notes(
        self, job: IngestionJob, matched: list[Matched], knowledge_units: PassedUnits, author_id: uuid.UUID
    ) -> None:
        """One short note per concept — not per section — synthesized from
        every matched section that concept touches and has a PASSED
        Knowledge Unit (ADR-0025); a concept whose sections all failed
        structuring gets no note rather than one built from raw text.
        Skipped for concepts that already have a non-archived note, so
        re-running a job (or a later chapter mapping to the same concept)
        never floods duplicates."""
        job.status = "GENERATING"
        concepts_by_id: dict[uuid.UUID, Concept] = {}
        sections_by_concept_id: dict[uuid.UUID, list[tuple[ExtractedSection, IngestionSection]]] = defaultdict(list)
        for section, section_row, concept in matched:
            concepts_by_id[concept.id] = concept
            sections_by_concept_id[concept.id].append((section, section_row))

        job.stage_detail = f"Generating short notes for {len(concepts_by_id)} concepts"
        await self.repo.commit()

        for concept_id, concept in concepts_by_id.items():
            concept_sections = sections_by_concept_id[concept_id]
            if await self.repo.has_concept_note(concept.id):
                logger.info("ingestion_note_skip_exists", job_id=str(job.id), concept=concept.name)
                continue

            passed = [(s, row) for s, row in concept_sections if row.id in knowledge_units]
            if not passed:
                job.generation_skipped_no_knowledge_unit += 1
                logger.info("ingestion_generation_skip_no_knowledge_unit", job_id=str(job.id), asset="concept_note", concept=concept.name)
                await self.repo.commit()
                continue

            units = [knowledge_units[row.id] for _, row in passed]
            excerpts = [(s.heading, render_facts_for_prompt(knowledge_units[row.id])) for s, row in passed]
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
                knowledge_unit_refs=[(u.id, u.version) for u in units],
                model_used=response.model,
                prompt_version=ingestion_concept_note.PROMPT_VERSION,
                confidence_score=min(u.extraction_confidence for u in units),
                generation_cost_usd=response.cost_usd,
            )
            job.notes_generated += 1
            await self.repo.commit()

    async def _run_revision_sheet(
        self, job: IngestionJob, matched: list[Matched], knowledge_units: PassedUnits, author_id: uuid.UUID
    ) -> None:
        """One chapter-level revision sheet — concept_id left null since it
        spans every matched concept, not one. Built only from sections with
        a PASSED Knowledge Unit (ADR-0025); if none of the chapter's
        matched sections have one, no sheet is generated at all."""
        if not matched:
            return

        passed_matched = [(section, row, concept) for section, row, concept in matched if row.id in knowledge_units]
        if not passed_matched:
            job.generation_skipped_no_knowledge_unit += 1
            logger.info("ingestion_generation_skip_no_knowledge_unit", job_id=str(job.id), asset="revision_sheet")
            await self.repo.commit()
            return

        job.status = "GENERATING"
        job.stage_detail = "Generating chapter revision sheet"
        await self.repo.commit()

        chapter = await self.repo.get_chapter(job.chapter_id)
        units = [knowledge_units[row.id] for _, row, _ in passed_matched]
        excerpts = [(section.heading, render_facts_for_prompt(knowledge_units[row.id])) for section, row, _ in passed_matched]
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
            knowledge_unit_refs=[(u.id, u.version) for u in units],
            model_used=response.model,
            prompt_version=ingestion_revision_sheet.PROMPT_VERSION,
            confidence_score=min(u.extraction_confidence for u in units),
            generation_cost_usd=response.cost_usd,
        )
        job.revision_sheets_generated += 1
        await self.repo.commit()
