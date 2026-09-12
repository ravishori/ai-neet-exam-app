"""Phase D pilot tests — Layer A (mocked integration) + unit checks (ADR-0032).

Real NCERT corpus grounding lives in ``test_pilot_mcq_real_corpus.py``.
Production ``check_grounding`` is never patched or disabled here.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.cms.models import ContentItem, ContentVersion, ContentVersionKnowledgeUnit
from app.modules.ingestion.models import IngestionJob, IngestionSection
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.ingestion_pipeline_service import IngestionPipelineService
from app.modules.ingestion.services.pilot_mcq_orchestration_service import (
    PHASE_D_MCQ_PER_SUBJECT,
    PILOT_SOURCES,
    PilotMcqOrchestrationService,
    PilotSourceSpec,
)
from app.modules.ingestion.services.study_material_academic_registry import PILOT_SOURCE_RELATIVE_PATHS
from app.modules.ingestion.tests.pilot_test_helpers import (
    mock_empty_visual_assets,
    mock_extraction_patch,
    pilot_ai_gateway_factory,
    unique_pilot_run_id,
)
from app.modules.knowledge.models import KnowledgeUnit
from app.modules.knowledge.services.grounding_check import check_grounding

pytestmark = [pytest.mark.asyncio(loop_scope="session")]


async def _author_id(db_session) -> uuid.UUID:
    from app.modules.identity.models.user import User

    return (await db_session.execute(select(User.id).limit(1))).scalar_one()


async def _require_physics_pilot_source(db_session):
    doc = await SourceDocumentRepository(db_session).get_by_relative_path(
        "Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf"
    )
    if doc is None:
        pytest.skip("physics pilot source not registered in test DB")
    return doc


def _apply_controlled_extraction(monkeypatch) -> None:
    fake_extract, fake_split = mock_extraction_patch()
    monkeypatch.setattr(
        "app.modules.ingestion.services.ingestion_pipeline_service.extract_pages",
        fake_extract,
    )
    monkeypatch.setattr(
        "app.modules.ingestion.services.ingestion_pipeline_service.split_into_sections",
        fake_split,
    )
    monkeypatch.setattr(
        "app.modules.ingestion.services.ingestion_pipeline_service.detect_visual_assets",
        mock_empty_visual_assets,
    )


@pytest.mark.unit
async def test_mock_ku_facts_pass_real_grounding_check():
    passed, detail = check_grounding(
        ["Current through a conductor is proportional to potential difference across it."],
        (
            "Ohm's Law states that the current through a conductor is directly proportional "
            "to the potential difference across it, provided the temperature remains constant."
        ),
    )
    assert passed is True
    assert detail is None


@pytest.mark.unit
async def test_verify_pilot_sources_rejects_plant_growth_as_photosynthesis(db_session):
    """Negative case: Plant Growth PDF must fail photosynthesis content preflight."""
    from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository

    doc = await SourceDocumentRepository(db_session).get_by_relative_path(
        "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-13.pdf"
    )
    if doc is None:
        pytest.skip("biology chapter-13 not registered in test DB")
    with pytest.raises(AppError) as exc:
        PilotMcqOrchestrationService(db_session)._verify_pilot_pdf_content(
            doc, "photosynthesis", doc.relative_source_path
        )
    assert exc.value.code == "PILOT_SOURCE_CONTENT_MISMATCH"


@pytest.mark.unit
async def test_verify_pilot_sources_accepts_corrected_biology_mapping(db_session):
    for path in PILOT_SOURCE_RELATIVE_PATHS:
        if await SourceDocumentRepository(db_session).get_by_relative_path(path) is None:
            pytest.skip("pilot sources not registered in test DB")
    await PilotMcqOrchestrationService(db_session).verify_pilot_sources()


@pytest.mark.integration
async def test_pilot_pipeline_question_enters_draft_cms(db_session, monkeypatch):
    """Controlled extraction + coherent KU facts → real grounding → CMS DRAFT."""
    doc = await _require_physics_pilot_source(db_session)
    _apply_controlled_extraction(monkeypatch)
    monkeypatch.setattr(AIGateway, "generate", pilot_ai_gateway_factory())

    run_id = unique_pilot_run_id("test-draft")
    pipeline = IngestionPipelineService(db_session)
    job = await pipeline.start_job(
        source_document_id=doc.id,
        target_mcq_count=1,
        pilot_run_id=run_id,
        force_pilot_rerun=True,
    )
    await pipeline.run(job_id=job.id, author_id=await _author_id(db_session))
    job = await pipeline.repo.get_job(job.id)
    assert job is not None
    assert job.status == "COMPLETED"
    assert job.questions_generated >= 1

    question = (
        await db_session.execute(
            select(ContentItem)
            .join(ContentVersion, ContentVersion.content_item_id == ContentItem.id)
            .join(
                ContentVersionKnowledgeUnit,
                ContentVersionKnowledgeUnit.content_version_id == ContentVersion.id,
            )
            .join(KnowledgeUnit, KnowledgeUnit.id == ContentVersionKnowledgeUnit.knowledge_unit_id)
            .join(IngestionSection, IngestionSection.id == KnowledgeUnit.source_section_id)
            .where(
                IngestionSection.job_id == job.id,
                ContentItem.content_type == "QUESTION",
                ContentItem.status == "DRAFT",
            )
        )
    ).scalar_one()
    assert question.status == "DRAFT"

    ku = (
        await db_session.execute(
            select(KnowledgeUnit)
            .join(IngestionSection, IngestionSection.id == KnowledgeUnit.source_section_id)
            .where(IngestionSection.job_id == job.id, KnowledgeUnit.validation_status == "PASSED")
        )
    ).scalar_one()
    assert ku.validation_status == "PASSED"


@pytest.mark.integration
async def test_pilot_orchestration_idempotent_second_run_skips(db_session, monkeypatch):
    """First run completes all subjects; second run creates zero new pipeline executions."""
    for path in PILOT_SOURCE_RELATIVE_PATHS:
        if await SourceDocumentRepository(db_session).get_by_relative_path(path) is None:
            pytest.skip("pilot sources not registered in test DB")

    run_id = unique_pilot_run_id("test-idempotent")
    author = await _author_id(db_session)
    pipeline_runs: list[uuid.UUID] = []

    async def pass_preflight_only(self, spec: PilotSourceSpec) -> None:
        """Layer A: skip real PDF preflight — idempotency under test, not corpus validation."""
        doc = await self.source_repo.get_by_relative_path(spec.relative_source_path)
        if doc is None:
            raise AppError(f"Pilot source not registered: {spec.relative_source_path}", code="PILOT_SOURCE_NOT_FOUND")

    async def mock_pipeline_run(self, *, job_id: uuid.UUID, author_id: uuid.UUID) -> None:
        pipeline_runs.append(job_id)
        job = await self.repo.get_job(job_id)
        assert job is not None
        job.status = "COMPLETED"
        job.questions_generated = PHASE_D_MCQ_PER_SUBJECT
        await self.repo.commit()

    monkeypatch.setattr(PilotMcqOrchestrationService, "_verify_single_pilot_source", pass_preflight_only)
    monkeypatch.setattr(IngestionPipelineService, "run", mock_pipeline_run)

    service = PilotMcqOrchestrationService(db_session)
    first = await service.run(author_id=author, pilot_run_id=run_id, force=True)

    assert len(first.subjects) == len(PILOT_SOURCES)
    for subject in first.subjects:
        assert subject.status == "completed", subject.error or subject.status
        assert subject.questions_generated == PHASE_D_MCQ_PER_SUBJECT
    assert first.total_generated == PHASE_D_MCQ_PER_SUBJECT * len(PILOT_SOURCES)
    assert len(pipeline_runs) == len(PILOT_SOURCES)

    jobs_after_first = (
        await db_session.execute(select(func.count()).select_from(IngestionJob).where(IngestionJob.pilot_run_id == run_id))
    ).scalar_one()

    second = await service.run(author_id=author, pilot_run_id=run_id)
    assert len(pipeline_runs) == len(PILOT_SOURCES), "second run must not invoke pipeline.run again"

    jobs_after_second = (
        await db_session.execute(select(func.count()).select_from(IngestionJob).where(IngestionJob.pilot_run_id == run_id))
    ).scalar_one()
    assert jobs_after_second == jobs_after_first

    for subject in second.subjects:
        assert subject.skipped_existing is True
        assert subject.status == "skipped_existing"
        assert subject.questions_generated == PHASE_D_MCQ_PER_SUBJECT
    assert second.total_generated == first.total_generated
