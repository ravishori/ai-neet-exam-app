"""Integration test: TutorService routes through KnowledgeService, not
direct SQL/repository access (ADR-0028 Phase B), while preserving its
existing public response shape exactly — the tutor router and frontend
depend on `answer`/`concept_name`/`ncert_reference`/`is_fallback`/
`cited_published_notes` unchanged."""
import uuid

import pytest
from sqlalchemy import select

from app.modules.academic.models import Concept
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.gateway.base import AIResponse
from app.modules.ai.services.tutor_service import TutorService
from app.modules.ingestion.models import IngestionJob, IngestionSection
from app.modules.knowledge.models import KnowledgeUnit

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept(db_session) -> Concept:
    result = await db_session.execute(select(Concept).limit(1))
    return result.scalar_one()


def _mock_response(text: str) -> AIResponse:
    return AIResponse(text=text, model="test-model", prompt_tokens=10, completion_tokens=10, is_fallback=False)


async def test_explain_preserves_existing_response_keys_with_no_knowledge_units(db_session, monkeypatch):
    concept = await _any_concept(db_session)
    concept.summary = "Concept summary text."
    await db_session.commit()

    async def fake_generate(self, **kwargs):
        return _mock_response("A tutor answer.")

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = TutorService(db_session)
    result = await service.explain(concept_id=concept.id, question="What is this?", user_id=uuid.uuid4())

    assert result["answer"] == "A tutor answer."
    assert result["concept_name"] == concept.name
    assert result["ncert_reference"] == concept.ncert_reference
    assert result["is_fallback"] is False
    assert result["cited_published_notes"] == 0
    # Additive keys — new, but must not replace anything above.
    assert result["knowledge_units_cited"] == 0
    assert result["visual_assets_available"] == 0


async def test_explain_cites_passed_knowledge_units_when_they_exist(db_session, monkeypatch):
    concept = await _any_concept(db_session)

    job = IngestionJob(source_file_path="test.pdf", file_checksum=uuid.uuid4().hex, status="STRUCTURING")
    db_session.add(job)
    await db_session.flush()
    section = IngestionSection(
        job_id=job.id, heading="3.4 OHM'S LAW", source_page=3,
        raw_text="Ohm's law relates voltage and current.", matched_concept_id=concept.id,
    )
    db_session.add(section)
    await db_session.flush()
    unit = KnowledgeUnit(
        version=1, content_hash=uuid.uuid4().hex, structured_facts=["fact"], summary="Grounded summary.",
        source_section_id=section.id, concept_id=concept.id, extraction_confidence=0.9, validation_status="PASSED",
    )
    db_session.add(unit)
    await db_session.commit()

    async def fake_generate(self, **kwargs):
        return _mock_response("A tutor answer citing the unit.")

    monkeypatch.setattr(AIGateway, "generate", fake_generate)

    service = TutorService(db_session)
    result = await service.explain(concept_id=concept.id, question="Explain Ohm's law", user_id=uuid.uuid4())

    assert result["knowledge_units_cited"] == 1
