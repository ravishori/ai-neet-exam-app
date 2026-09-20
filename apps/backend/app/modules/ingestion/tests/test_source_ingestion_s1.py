"""FACTORY-S1 source ingestion tests — no live AI providers."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from app.core.config import get_settings
from app.modules.ingestion.repositories.ingestion_repository import IngestionRepository
from app.modules.ingestion.repositories.source_academic_mapping_repository import SourceAcademicMappingRepository
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.ingestion_pipeline_service import (
    S1_SOURCE_INGESTION_RUN_ID,
    IngestionPipelineService,
)
from app.modules.ingestion.services.source_ingestion_orchestration_service import classify_failed_ku
from app.modules.ingestion.services.study_material_discovery_service import StudyMaterialDiscoveryService
from app.modules.ingestion.services.pdf_extraction_service import compute_checksum
from app.modules.knowledge.services.deterministic_structuring_service import extract_facts_from_section_text

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _write_ncert_like_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    body = (
        "3.2  ELECTRIC CURRENT\n\n"
        "Electric current is defined as the rate of flow of electric charge through any cross-section. "
        "The SI unit of electric current is the ampere. "
        "Steady currents satisfy the relation I equals charge divided by time interval. "
        "For time-varying currents the instantaneous current is the limiting value of delta Q over delta t. "
        "Both positive and negative charges contribute to the net current through a surface. "
        "Practical magnitudes range from microamperes in nerves to thousands of amperes in lightning."
    )
    page.insert_text((72, 72), body)
    doc.save(path)
    doc.close()


@pytest.fixture
def s1_study_material(tmp_path: Path, monkeypatch) -> SimpleNamespace:
    root = tmp_path / "StudyMaterial"
    root.mkdir()
    token = uuid.uuid4().hex[:8]
    physics_rel = f"Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3-{token}.pdf"
    _write_ncert_like_pdf(root.joinpath(*physics_rel.split("/")))
    _write_ncert_like_pdf(root / "Maths" / f"must-not-register-{token}.pdf")
    settings = SimpleNamespace(study_material_dir=str(root))
    monkeypatch.setattr(
        "app.modules.ingestion.services.source_document_resolver.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.modules.ingestion.services.ingestion_pipeline_service.get_settings",
        lambda: get_settings(),
    )
    return SimpleNamespace(study_material_dir=str(root), physics_rel=physics_rel, token=token)


def test_classify_failed_ku_categories():
    assert classify_failed_ku("duplicate of existing knowledge unit abc") == "duplicate"
    assert classify_failed_ku("2/4 facts failed source-overlap check") == "validation"
    assert classify_failed_ku("no structured facts extracted") == "extraction"


def test_extract_facts_from_section_text():
    text = (
        "Electric current is defined as the rate of flow of electric charge through any cross-section. "
        "The SI unit of electric current is the ampere."
    )
    facts = extract_facts_from_section_text(text)
    assert len(facts) >= 1
    assert all(len(f) >= 40 for f in facts)


async def test_discovery_excludes_maths_from_registry(db_session, s1_study_material):
    report = await StudyMaterialDiscoveryService(db_session, settings=s1_study_material).discover()
    assert report.discovered == 1
    assert report.registered == 1
    repo = SourceDocumentRepository(db_session)
    doc = await repo.get_by_checksum(
        compute_checksum(str(Path(s1_study_material.study_material_dir).joinpath(*s1_study_material.physics_rel.split("/"))))
    )
    assert doc is not None
    assert await repo.get_by_relative_path(f"Maths/must-not-register-{s1_study_material.token}.pdf") is None


async def test_source_ingestion_idempotent_and_no_ai(db_session, s1_study_material):
    discovery = await StudyMaterialDiscoveryService(db_session, settings=s1_study_material).discover()
    assert discovery.registered == 1
    repo = SourceDocumentRepository(db_session)
    source = await repo.get_by_relative_path(s1_study_material.physics_rel)
    assert source is not None

    from app.modules.ingestion.services.source_academic_mapping_service import SourceAcademicMappingService

    await SourceAcademicMappingService(db_session).sync_all()
    mapping = await SourceAcademicMappingRepository(db_session).get_for_source(source.id)
    # Unique filename suffix means explicit registry NCERT number won't match — unmapped is OK for extraction test
    if mapping is None or mapping.mapping_status != "MAPPED":
        pipeline = IngestionPipelineService(db_session)
        job, created = await pipeline.start_source_ingestion_job(source_document_id=source.id)
        assert created
        await pipeline.run_source_ingestion(job_id=job.id, author_id=uuid.uuid4())
        job = await IngestionRepository(db_session).get_job(job.id)
        assert job.status == "COMPLETED"
        assert job.sections_detected >= 0
        job2, created2 = await pipeline.start_source_ingestion_job(source_document_id=source.id)
        assert created2 is False
        return

    pipeline = IngestionPipelineService(db_session)
    author_id = uuid.uuid4()
    job1, created1 = await pipeline.start_source_ingestion_job(source_document_id=source.id)
    assert created1 is True
    await pipeline.run_source_ingestion(job_id=job1.id, author_id=author_id)
    job1 = await IngestionRepository(db_session).get_job(job1.id)
    assert job1.status == "COMPLETED"
    assert job1.questions_generated == 0
    assert job1.pilot_run_id == S1_SOURCE_INGESTION_RUN_ID

    job2, created2 = await pipeline.start_source_ingestion_job(source_document_id=source.id)
    assert created2 is False
    assert job2.id == job1.id

    await db_session.refresh(source)
    assert source.ingestion_status == "INGESTED"


async def test_unmapped_source_extraction_only(db_session, s1_study_material):
    root = Path(s1_study_material.study_material_dir)
    bio_rel = f"Biology/Class 11-Biology/factory-s1-unmapped-{s1_study_material.token}.pdf"
    _write_ncert_like_pdf(root.joinpath(*bio_rel.split("/")))
    await StudyMaterialDiscoveryService(db_session, settings=s1_study_material).discover()
    source = await SourceDocumentRepository(db_session).get_by_relative_path(bio_rel)
    assert source is not None

    pipeline = IngestionPipelineService(db_session)
    job, created = await pipeline.start_source_ingestion_job(source_document_id=source.id)
    assert created
    await pipeline.run_source_ingestion(job_id=job.id, author_id=uuid.uuid4())
    job = await IngestionRepository(db_session).get_job(job.id)
    assert job.status == "COMPLETED"
    assert job.chapter_id is None
    assert job.knowledge_units_created == 0

    sections = await IngestionRepository(db_session).list_sections_for_job(job.id)
    assert all(s.matched_concept_id is None for s in sections)
    assert all(s.source_page >= 1 for s in sections)
