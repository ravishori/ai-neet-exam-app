"""Integration tests: generation workers read PASSED Knowledge Units, not
raw section text, and record traceability (ADR-0025).

AIGateway.generate is monkeypatched to return controlled JSON, the same
pattern as test_knowledge_structuring.py — these tests prove the
PASSED-only gating and the ContentVersion/ContentVersionKnowledgeUnit
wiring, not prompt/model behavior itself (proven separately by a real run
against the pilot chapter — see ADR-0025's Tests section).
"""

import uuid

import pytest
from sqlalchemy import select

from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.gateway.base import AIResponse
from app.modules.cms.models import ContentItem, ContentVersion, ContentVersionKnowledgeUnit
from app.modules.ingestion.models import IngestionJob, IngestionSection
from app.modules.ingestion.services.ingestion_pipeline_service import IngestionPipelineService
from app.modules.ingestion.services.pdf_extraction_service import ExtractedSection
from app.modules.knowledge.models import KnowledgeUnit

pytestmark = pytest.mark.asyncio(loop_scope="session")

MCQ_JSON = (
    '[{"stem": "What does Ohm\'s Law state?", '
    '"options": [{"label": "A", "text": "V=IR"}, {"label": "B", "text": "V=I/R"}, '
    '{"label": "C", "text": "V=I+R"}, {"label": "D", "text": "V=I-R"}], '
    '"correct_option": "A", "explanation": "Definition.", "difficulty": "easy", "bloom_level": "recall"}]'
)
FLASHCARD_JSON = '[{"front": "State Ohm\'s Law", "back": "V = IR"}]'
CONCEPT_NOTE_JSON = '{"summary": "Ohm\'s Law relates V, I, R.", "sections": ["V = IR"]}'
FORMULA_SHEET_JSON = '{"formulas": ["Ohms Law: V = IR"]}'


async def _any_concept(db_session) -> Concept:
    result = await db_session.execute(select(Concept).limit(1))
    return result.scalar_one()


async def _chapter_for_concept(db_session, concept: Concept) -> Chapter:
    topic = await db_session.get(Topic, concept.topic_id)
    return await db_session.get(Chapter, topic.chapter_id)


async def _seed_job(db_session, *, chapter_id=None) -> IngestionJob:
    job = IngestionJob(source_file_path="test.pdf", file_checksum=uuid.uuid4().hex, status="GENERATING", chapter_id=chapter_id)
    db_session.add(job)
    await db_session.flush()
    return job


async def _seed_section(db_session, job: IngestionJob, *, concept_id, heading="3.4 OHM'S LAW") -> IngestionSection:
    section = IngestionSection(
        job_id=job.id, heading=heading, source_page=3, raw_text="raw placeholder text", matched_concept_id=concept_id
    )
    db_session.add(section)
    await db_session.flush()
    return section


def _extracted(section: IngestionSection) -> ExtractedSection:
    return ExtractedSection(heading=section.heading, source_page=section.source_page, text=section.raw_text)


def _passed_unit(*, section: IngestionSection, concept: Concept, confidence: float, summary: str = "Summary.") -> KnowledgeUnit:
    return KnowledgeUnit(
        version=1,
        content_hash=uuid.uuid4().hex,
        structured_facts=["Current is proportional to potential difference."],
        summary=summary,
        source_section_id=section.id,
        concept_id=concept.id,
        extraction_confidence=confidence,
        validation_status="PASSED",
    )


def _fake_gateway(responses: dict[str, str], *, cost_usd: float = 0.0042):
    async def fake_generate(self, *, agent_type, **kwargs):
        return AIResponse(
            text=responses[agent_type], model="test-model", prompt_tokens=100, completion_tokens=50, is_fallback=False, cost_usd=cost_usd
        )

    return fake_generate


async def _version_for(db_session, content_type: str) -> ContentVersion:
    return (
        await db_session.execute(
            select(ContentVersion)
            .join(ContentItem, ContentVersion.content_item_id == ContentItem.id)
            .where(ContentItem.content_type == content_type)
        )
    ).scalar_one()


async def _refs_for(db_session, version_id) -> list[ContentVersionKnowledgeUnit]:
    result = await db_session.execute(
        select(ContentVersionKnowledgeUnit).where(ContentVersionKnowledgeUnit.content_version_id == version_id)
    )
    return list(result.scalars().all())


async def test_run_generation_skips_section_without_passed_knowledge_unit(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    job = await _seed_job(db_session)
    section = await _seed_section(db_session, job, concept_id=concept.id)
    matched = [(_extracted(section), section, concept)]

    async def fake_generate(self, **kwargs):
        raise AssertionError("must not call the AI gateway when the section has no PASSED knowledge unit")

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = IngestionPipelineService(db_session)
    await service._run_generation(job, matched, {}, uuid.uuid4())

    assert job.generation_skipped_no_knowledge_unit == 1
    assert job.questions_generated == 0
    assert job.flashcards_generated == 0
    items = (await db_session.execute(select(ContentItem))).scalars().all()
    assert items == []


async def test_run_generation_creates_content_with_traceability_when_passed(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    job = await _seed_job(db_session)
    section = await _seed_section(db_session, job, concept_id=concept.id)
    matched = [(_extracted(section), section, concept)]

    unit = _passed_unit(section=section, concept=concept, confidence=0.87)
    db_session.add(unit)
    await db_session.flush()

    fake = _fake_gateway({"INGESTION_MCQ": MCQ_JSON, "INGESTION_FLASHCARD": FLASHCARD_JSON})
    monkeypatch.setattr(AIGateway, "generate", fake)

    service = IngestionPipelineService(db_session)
    await service._run_generation(job, matched, {section.id: unit}, uuid.uuid4())

    assert job.generation_skipped_no_knowledge_unit == 0
    assert job.questions_generated == 1
    assert job.flashcards_generated == 1

    version = await _version_for(db_session, "QUESTION")
    assert version.knowledge_unit_id == unit.id
    assert version.knowledge_unit_version == unit.version
    assert version.model_used == "test-model"
    assert version.prompt_version == "v1"
    assert version.confidence_score == pytest.approx(0.87)
    assert version.generation_cost_usd == pytest.approx(0.0042)

    refs = await _refs_for(db_session, version.id)
    assert len(refs) == 1
    assert refs[0].knowledge_unit_id == unit.id
    assert refs[0].knowledge_unit_version == unit.version


async def test_concept_note_aggregates_passed_units_and_excludes_unpassed_section(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    job = await _seed_job(db_session)
    section_a = await _seed_section(db_session, job, concept_id=concept.id, heading="3.4 OHM'S LAW")
    section_b = await _seed_section(db_session, job, concept_id=concept.id, heading="3.5 OHM'S LAW CONTD")
    section_c = await _seed_section(db_session, job, concept_id=concept.id, heading="3.6 NO KNOWLEDGE UNIT")

    unit_a = _passed_unit(section=section_a, concept=concept, confidence=0.95, summary="Part A")
    unit_b = _passed_unit(section=section_b, concept=concept, confidence=0.6, summary="Part B")
    db_session.add_all([unit_a, unit_b])
    await db_session.flush()

    matched = [
        (_extracted(section_a), section_a, concept),
        (_extracted(section_b), section_b, concept),
        (_extracted(section_c), section_c, concept),
    ]
    knowledge_units = {section_a.id: unit_a, section_b.id: unit_b}

    fake = _fake_gateway({"INGESTION_CONCEPT_NOTE": CONCEPT_NOTE_JSON})
    monkeypatch.setattr(AIGateway, "generate", fake)

    service = IngestionPipelineService(db_session)
    await service._run_concept_notes(job, matched, knowledge_units, uuid.uuid4())

    assert job.notes_generated == 1
    # section_c is simply excluded from the note's source material — the
    # concept still had enough PASSED units to produce a note, so this is
    # not a "no knowledge unit for this asset at all" skip.
    assert job.generation_skipped_no_knowledge_unit == 0

    version = await _version_for(db_session, "CONCEPT_NOTE")
    assert version.knowledge_unit_id is None  # more than one contributor — no single FK
    assert version.knowledge_unit_version is None
    assert version.confidence_score == pytest.approx(0.6)  # weakest link, not an average

    refs = await _refs_for(db_session, version.id)
    assert {r.knowledge_unit_id for r in refs} == {unit_a.id, unit_b.id}


async def test_concept_note_skipped_when_no_section_has_passed_unit(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    job = await _seed_job(db_session)
    section = await _seed_section(db_session, job, concept_id=concept.id)
    matched = [(_extracted(section), section, concept)]

    async def fake_generate(self, **kwargs):
        raise AssertionError("must not call the AI gateway when the concept has no PASSED knowledge unit")

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = IngestionPipelineService(db_session)
    await service._run_concept_notes(job, matched, {}, uuid.uuid4())

    assert job.notes_generated == 0
    assert job.generation_skipped_no_knowledge_unit == 1


async def test_revision_sheet_skipped_when_no_matched_section_has_passed_unit(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    chapter = await _chapter_for_concept(db_session, concept)
    job = await _seed_job(db_session, chapter_id=chapter.id)
    section = await _seed_section(db_session, job, concept_id=concept.id)
    matched = [(_extracted(section), section, concept)]

    async def fake_generate(self, **kwargs):
        raise AssertionError("must not call the AI gateway when no matched section has a PASSED knowledge unit")

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = IngestionPipelineService(db_session)
    await service._run_revision_sheet(job, matched, {}, uuid.uuid4())

    assert job.revision_sheets_generated == 0
    assert job.generation_skipped_no_knowledge_unit == 1


async def test_revision_sheet_aggregates_passed_units_across_sections(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    chapter = await _chapter_for_concept(db_session, concept)
    job = await _seed_job(db_session, chapter_id=chapter.id)
    section_a = await _seed_section(db_session, job, concept_id=concept.id, heading="3.4 OHM'S LAW")
    section_b = await _seed_section(db_session, job, concept_id=concept.id, heading="3.5 RESISTIVITY")

    unit_a = _passed_unit(section=section_a, concept=concept, confidence=0.9, summary="Part A")
    unit_b = _passed_unit(section=section_b, concept=concept, confidence=0.7, summary="Part B")
    db_session.add_all([unit_a, unit_b])
    await db_session.flush()

    matched = [(_extracted(section_a), section_a, concept), (_extracted(section_b), section_b, concept)]
    knowledge_units = {section_a.id: unit_a, section_b.id: unit_b}

    fake = _fake_gateway({"INGESTION_REVISION_SHEET": FORMULA_SHEET_JSON})
    monkeypatch.setattr(AIGateway, "generate", fake)

    service = IngestionPipelineService(db_session)
    await service._run_revision_sheet(job, matched, knowledge_units, uuid.uuid4())

    assert job.revision_sheets_generated == 1
    version = await _version_for(db_session, "FORMULA_SHEET")
    assert version.knowledge_unit_id is None
    assert version.confidence_score == pytest.approx(0.7)

    refs = await _refs_for(db_session, version.id)
    assert {r.knowledge_unit_id for r in refs} == {unit_a.id, unit_b.id}
