"""Integration tests: KnowledgeService (ADR-0028 Phase B) — the single
entry point AI Tutor (and future consumers) read educational content
through, composing the existing repositories rather than duplicating them.
"""
import uuid

import pytest
from sqlalchemy import select

from app.modules.academic.models import Concept
from app.modules.ingestion.models import IngestionJob, IngestionSection, VisualAsset
from app.modules.knowledge.models import KnowledgeUnit
from app.modules.knowledge.services.knowledge_service import KnowledgeService

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _any_concept(db_session) -> Concept:
    result = await db_session.execute(select(Concept).limit(1))
    return result.scalar_one()


async def _seed_passed_unit_with_asset(db_session, *, concept_id: uuid.UUID) -> tuple[KnowledgeUnit, VisualAsset]:
    job = IngestionJob(source_file_path="test.pdf", file_checksum=uuid.uuid4().hex, status="STRUCTURING")
    db_session.add(job)
    await db_session.flush()

    section = IngestionSection(
        job_id=job.id, heading="3.4 OHM'S LAW", source_page=3,
        raw_text="Ohm's law relates voltage and current.", matched_concept_id=concept_id,
    )
    db_session.add(section)
    await db_session.flush()

    unit = KnowledgeUnit(
        version=1, content_hash=uuid.uuid4().hex,
        structured_facts=["Ohm's law relates voltage and current."],
        summary="Ohm's law: V = IR.",
        source_section_id=section.id, concept_id=concept_id,
        extraction_confidence=0.95, validation_status="PASSED",
    )
    db_session.add(unit)
    await db_session.flush()

    asset = VisualAsset(
        job_id=job.id, source_page=3, asset_type="diagram", detection_method="vector_cluster",
        review_status="AUTO_DETECTED", knowledge_unit_id=unit.id,
    )
    db_session.add(asset)
    await db_session.commit()
    return unit, asset


async def test_get_teaching_explanation_falls_back_to_concept_summary_with_no_units(db_session):
    concept = await _any_concept(db_session)
    concept.summary = "Fallback summary text."
    await db_session.commit()

    service = KnowledgeService(db_session)
    explanation = await service.get_teaching_explanation(concept.id)

    assert explanation == "Fallback summary text."


async def test_get_teaching_explanation_prefers_passed_knowledge_units(db_session):
    concept = await _any_concept(db_session)
    unit, _asset = await _seed_passed_unit_with_asset(db_session, concept_id=concept.id)

    service = KnowledgeService(db_session)
    explanation = await service.get_teaching_explanation(concept.id)

    assert unit.summary in explanation


async def test_get_knowledge_context_includes_units_and_linked_visual_assets(db_session):
    concept = await _any_concept(db_session)
    unit, asset = await _seed_passed_unit_with_asset(db_session, concept_id=concept.id)

    service = KnowledgeService(db_session)
    context = await service.get_knowledge_context(concept.id)

    assert context["concept"].id == concept.id
    assert unit.id in [u.id for u in context["knowledge_units"]]
    assert asset.id in [a.id for a in context["visual_assets"]]


async def test_get_visual_assets_returns_only_assets_for_that_unit(db_session):
    concept = await _any_concept(db_session)
    unit, asset = await _seed_passed_unit_with_asset(db_session, concept_id=concept.id)

    service = KnowledgeService(db_session)
    assets = await service.get_visual_assets(unit.id)

    assert [a.id for a in assets] == [asset.id]


async def test_get_weak_areas_returns_empty_list_with_no_mastery_rows(db_session):
    service = KnowledgeService(db_session)
    weak_areas = await service.get_weak_areas(uuid.uuid4())
    assert weak_areas == []
