"""Phase D pilot — real NCERT corpus grounding (ADR-0032).

Uses actual pilot PDFs and the real ``check_grounding`` gate. AI responses
are mocked only to return facts copied from extracted section text — never
facts invented from general knowledge.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.gateway.base import AIResponse
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.pdf_extraction_service import extract_pages, split_into_sections
from app.modules.ingestion.services.pilot_mcq_orchestration_service import (
    PILOT_SOURCES,
    PilotMcqOrchestrationService,
)
from app.modules.ingestion.services.source_document_resolver import resolve_source_document_path
from app.modules.knowledge.services.grounding_check import check_grounding, is_fact_grounded
from app.modules.knowledge.services.knowledge_structuring_service import KnowledgeStructuringService

pytestmark = [pytest.mark.asyncio(loop_scope="session")]

_PHYSICS_PATH = "Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf"
_CHEMISTRY_PATH = "Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf"
_BIOLOGY_PHOTOSYNTHESIS_PATH = "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf"
_BIOLOGY_PLANT_GROWTH_PATH = "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-13.pdf"


def _grounded_fact_from_section(section_text: str) -> str:
    """Pick a sentence from extracted NCERT text that satisfies overlap grounding."""
    for sentence in section_text.replace("\n", " ").split("."):
        sentence = sentence.strip()
        if len(sentence) < 80:
            continue
        words = [w for w in sentence.split() if len(w) >= 4]
        if len(words) >= 6:
            return sentence
    pytest.fail(
        "could not derive a grounded fact from extracted section text — "
        f"preview={section_text[:200]!r}"
    )


async def _concept_for_chapter(db_session, chapter_code: str):
    from app.modules.academic.models import Chapter, Concept, Topic

    chapter = (
        await db_session.execute(select(Chapter).where(Chapter.code == chapter_code))
    ).scalar_one()
    topic = (
        await db_session.execute(select(Topic).where(Topic.chapter_id == chapter.id).limit(1))
    ).scalar_one()
    return (
        await db_session.execute(select(Concept).where(Concept.topic_id == topic.id).limit(1))
    ).scalar_one()


async def _structured_section_from_pilot_pdf(db_session, relative_path: str, *, min_chars: int = 400):
    doc = await SourceDocumentRepository(db_session).get_by_relative_path(relative_path)
    if doc is None:
        pytest.skip(f"pilot source not registered: {relative_path}")
    resolved = resolve_source_document_path(doc)
    sections = [s for s in split_into_sections(extract_pages(str(resolved))) if len(s.text) >= min_chars]
    if not sections:
        pytest.fail(
            f"no extractable sections from pilot PDF: source_document_id={doc.id} "
            f"file_name={doc.file_name} path={relative_path}"
        )
    return doc, sections[0]


@pytest.mark.real_corpus
async def test_physics_pilot_pdf_extraction_supports_grounding(db_session):
    doc, section = await _structured_section_from_pilot_pdf(db_session, _PHYSICS_PATH)
    fact = _grounded_fact_from_section(section.text)
    passed, detail = check_grounding([fact], section.text)
    assert passed, (
        f"grounding failed for physics pilot PDF: source_document_id={doc.id} "
        f"file_name={doc.file_name} chapter=current-electricity source_page={section.source_page} "
        f"grounding_result={detail!r} candidate_fact={fact[:120]!r}"
    )
    assert is_fact_grounded(fact, section.text)


@pytest.mark.real_corpus
async def test_chemistry_pilot_pdf_extraction_supports_grounding(db_session):
    doc, section = await _structured_section_from_pilot_pdf(db_session, _CHEMISTRY_PATH)
    fact = _grounded_fact_from_section(section.text)
    passed, detail = check_grounding([fact], section.text)
    assert passed, (
        f"grounding failed for chemistry pilot PDF: source_document_id={doc.id} "
        f"file_name={doc.file_name} chapter=chemical-bonding source_page={section.source_page} "
        f"grounding_result={detail!r} candidate_fact={fact[:120]!r}"
    )


@pytest.mark.real_corpus
async def test_physics_pilot_structuring_passes_with_source_derived_facts(db_session, monkeypatch):
    from app.modules.ingestion.models import IngestionJob, IngestionSection

    doc, section = await _structured_section_from_pilot_pdf(db_session, _PHYSICS_PATH)
    fact = _grounded_fact_from_section(section.text)
    concept = await _concept_for_chapter(db_session, "current-electricity")

    job = IngestionJob(
        source_file_path=str(resolve_source_document_path(doc)),
        file_checksum=doc.checksum_sha256,
        source_document_id=doc.id,
        status="STRUCTURING",
    )
    db_session.add(job)
    await db_session.flush()

    section_row = IngestionSection(
        job_id=job.id,
        heading=section.heading,
        source_page=section.source_page,
        raw_text=section.text,
        matched_concept_id=concept.id,
    )
    db_session.add(section_row)
    await db_session.flush()

    async def fake_generate(self, **kwargs):
        return AIResponse(
            text=json.dumps(
                {
                    "structured_facts": [fact],
                    "summary": fact[:120],
                    "extraction_confidence": 0.9,
                }
            ),
            model="test-model",
            prompt_tokens=50,
            completion_tokens=50,
            is_fallback=False,
            cost_usd=0.0,
        )

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    unit = await KnowledgeStructuringService(db_session).structure_section(
        section=section_row, concept=concept, author_id=uuid.uuid4()
    )
    assert unit is not None, (
        f"structuring returned no unit: source_document_id={doc.id} section_page={section.source_page}"
    )
    assert unit.validation_status == "PASSED", (
        f"expected PASSED grounding for physics pilot: source_document_id={doc.id} "
        f"file_name={doc.file_name} section_id={section_row.id} source_page={section.source_page} "
        f"validation_detail={unit.validation_detail!r} candidate_fact={fact[:120]!r}"
    )


@pytest.mark.real_corpus
async def test_biology_plant_growth_pdf_fails_photosynthesis_content_preflight(db_session):
    """chapter-13.pdf is Plant Growth — must not pass photosynthesis content preflight."""
    doc = await SourceDocumentRepository(db_session).get_by_relative_path(_BIOLOGY_PLANT_GROWTH_PATH)
    if doc is None:
        pytest.skip("biology chapter-13 not registered in test DB")

    service = PilotMcqOrchestrationService(db_session)
    with pytest.raises(AppError) as exc:
        service._verify_pilot_pdf_content(doc, "photosynthesis", _BIOLOGY_PLANT_GROWTH_PATH)
    assert exc.value.code == "PILOT_SOURCE_CONTENT_MISMATCH"


@pytest.mark.real_corpus
async def test_biology_photosynthesis_pdf_passes_content_preflight(db_session):
    doc = await SourceDocumentRepository(db_session).get_by_relative_path(_BIOLOGY_PHOTOSYNTHESIS_PATH)
    if doc is None:
        pytest.skip("biology chapter-11 not registered in test DB")

    PilotMcqOrchestrationService(db_session)._verify_pilot_pdf_content(
        doc, "photosynthesis", _BIOLOGY_PHOTOSYNTHESIS_PATH
    )


@pytest.mark.real_corpus
async def test_biology_photosynthesis_extraction_supports_grounding(db_session):
    doc, section = await _structured_section_from_pilot_pdf(db_session, _BIOLOGY_PHOTOSYNTHESIS_PATH)
    fact = _grounded_fact_from_section(section.text)
    passed, detail = check_grounding([fact], section.text)
    assert passed, (
        f"grounding failed for biology photosynthesis PDF: source_document_id={doc.id} "
        f"file_name={doc.file_name} chapter=photosynthesis source_page={section.source_page} "
        f"grounding_result={detail!r} candidate_fact={fact[:120]!r}"
    )


@pytest.mark.real_corpus
async def test_verify_pilot_sources_passes_after_biology_correction(db_session):
    for path in PILOT_SOURCES:
        if await SourceDocumentRepository(db_session).get_by_relative_path(path.relative_source_path) is None:
            pytest.skip(f"pilot source not registered: {path.relative_source_path}")
    await PilotMcqOrchestrationService(db_session).verify_pilot_sources()
