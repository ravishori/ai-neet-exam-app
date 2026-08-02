"""Integration tests: Knowledge Unit structuring stage (ADR-0024).

AIGateway.generate is monkeypatched to return controlled JSON — the real
grounding-check logic is unit-tested directly (see
app/modules/knowledge/tests/test_grounding_check.py); these tests prove
the service wires that logic, dedup, and persistence together correctly
against a real (transactionally-isolated) database.
"""

import uuid

import pytest
from sqlalchemy import select

from app.modules.academic.models import Concept
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.gateway.base import AIResponse
from app.modules.ingestion.models import IngestionJob, IngestionSection
from app.modules.knowledge.models import KnowledgeUnit
from app.modules.knowledge.services.knowledge_structuring_service import KnowledgeStructuringService

pytestmark = pytest.mark.asyncio(loop_scope="session")

SOURCE_TEXT = (
    "Ohm's Law states that the current through a conductor is directly proportional to the "
    "potential difference across it, provided the temperature remains constant. This is "
    "written V = IR, where R is the resistance of the conductor in ohms."
)


async def _seed_section(db_session, *, concept_id: uuid.UUID, raw_text: str = SOURCE_TEXT) -> IngestionSection:
    job = IngestionJob(
        source_file_path="test.pdf",
        file_checksum=uuid.uuid4().hex,
        status="STRUCTURING",
    )
    db_session.add(job)
    await db_session.flush()

    section = IngestionSection(
        job_id=job.id,
        heading="3.4 OHM'S LAW",
        source_page=3,
        raw_text=raw_text,
        matched_concept_id=concept_id,
    )
    db_session.add(section)
    await db_session.flush()
    return section


async def _any_concept(db_session) -> Concept:
    result = await db_session.execute(select(Concept).limit(1))
    return result.scalar_one()


def _mock_response(text: str, *, is_fallback: bool = False) -> AIResponse:
    return AIResponse(text=text, model="test-model", prompt_tokens=10, completion_tokens=10, is_fallback=is_fallback)


async def test_grounded_response_creates_passed_knowledge_unit(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    section = await _seed_section(db_session, concept_id=concept.id)

    async def fake_generate(self, **kwargs):
        return _mock_response(
            '{"structured_facts": ["Current through a conductor is proportional to potential '
            'difference across it."], "summary": "Ohm\'s Law relates current and voltage.", '
            '"extraction_confidence": 0.95}'
        )

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = KnowledgeStructuringService(db_session)
    unit = await service.structure_section(section=section, concept=concept, author_id=uuid.uuid4())

    assert unit is not None
    assert unit.validation_status == "PASSED"
    assert unit.validation_detail is None
    assert unit.extraction_confidence == pytest.approx(0.95)
    assert unit.source_section_id == section.id
    assert unit.concept_id == concept.id
    assert unit.version == 1

    stored = await db_session.get(KnowledgeUnit, unit.id)
    assert stored is not None
    assert stored.structured_facts == unit.structured_facts


async def test_ungrounded_response_creates_failed_knowledge_unit(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    section = await _seed_section(db_session, concept_id=concept.id)

    async def fake_generate(self, **kwargs):
        return _mock_response(
            '{"structured_facts": ["Photosynthesis occurs in chloroplasts during daylight hours."], '
            '"summary": "Plants convert sunlight into energy.", "extraction_confidence": 0.9}'
        )

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = KnowledgeStructuringService(db_session)
    unit = await service.structure_section(section=section, concept=concept, author_id=uuid.uuid4())

    assert unit is not None
    assert unit.validation_status == "FAILED"
    assert "source-overlap" in unit.validation_detail


async def test_duplicate_of_existing_passed_unit_is_rejected(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    section_a = await _seed_section(db_session, concept_id=concept.id)
    section_b = await _seed_section(db_session, concept_id=concept.id)

    fact = "Current through a conductor is proportional to potential difference across it."
    summary = "Ohm's Law relates current and voltage in a conductor at constant temperature."

    async def fake_generate(self, **kwargs):
        return _mock_response(
            f'{{"structured_facts": ["{fact}"], "summary": "{summary}", "extraction_confidence": 0.9}}'
        )

    monkeypatch.setattr(AIGateway, "generate", fake_generate)
    service = KnowledgeStructuringService(db_session)

    first = await service.structure_section(section=section_a, concept=concept, author_id=uuid.uuid4())
    assert first.validation_status == "PASSED"

    second = await service.structure_section(section=section_b, concept=concept, author_id=uuid.uuid4())
    assert second.validation_status == "FAILED"
    assert "duplicate" in second.validation_detail


async def test_fallback_response_creates_no_knowledge_unit(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    section = await _seed_section(db_session, concept_id=concept.id)

    async def fake_generate(self, **kwargs):
        return _mock_response("", is_fallback=True)

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = KnowledgeStructuringService(db_session)
    unit = await service.structure_section(section=section, concept=concept, author_id=uuid.uuid4())

    assert unit is None


async def test_malformed_json_response_creates_no_knowledge_unit(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    section = await _seed_section(db_session, concept_id=concept.id)

    async def fake_generate(self, **kwargs):
        return _mock_response("not valid json at all")

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = KnowledgeStructuringService(db_session)
    unit = await service.structure_section(section=section, concept=concept, author_id=uuid.uuid4())

    assert unit is None
