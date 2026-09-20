"""Provenance: SourceDocument → IngestionJob wiring (ADR-0031)."""

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.modules.ingestion.models import IngestionJob, SourceDocument
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.ingestion_pipeline_service import IngestionPipelineService
from app.modules.ingestion.services.pdf_extraction_service import compute_checksum
from app.modules.ingestion.services.source_academic_mapping_service import SourceAcademicMappingService
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _noop_background(*args, **kwargs) -> None:
    return None


def _real_pdf_path() -> str:
    settings = get_settings()
    path = Path(settings.study_material_dir) / "Physics" / "Class 12-Physics" / "ncert-book-class-12-physics-part-1-chapter-3.pdf"
    if not path.is_file():
        pytest.skip(f"real pilot PDF missing at {path}")
    return str(path)


async def test_path_based_job_auto_links_source_document(client, register_user, db_session, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.api.ingestion_router._run_pipeline_in_background", _noop_background)
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)

    pdf_path = _real_pdf_path()
    checksum = compute_checksum(pdf_path)
    source = await SourceDocumentRepository(db_session).get_by_checksum(checksum)
    if source is None:
        pytest.skip("pilot source document not registered — run discovery first")

    await SourceAcademicMappingService(db_session).upsert_mapping_for_source(source)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={"file_path": pdf_path, "chapter_code": "current-electricity"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["source_document_id"] == str(source.id)

    job = await db_session.get(IngestionJob, uuid.UUID(job_id))
    assert job is not None
    assert job.source_document_id == source.id


async def test_source_document_id_job_uses_mapping(client, register_user, db_session, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.api.ingestion_router._run_pipeline_in_background", _noop_background)
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)

    pdf_path = _real_pdf_path()
    source = await SourceDocumentRepository(db_session).get_by_checksum(compute_checksum(pdf_path))
    if source is None:
        pytest.skip("pilot source document not registered")

    await SourceAcademicMappingService(db_session).upsert_mapping_for_source(source)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={"source_document_id": str(source.id)},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["data"]["source_document_id"] == str(source.id)


async def test_rejects_both_source_id_and_path(client, register_user, db_session, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.api.ingestion_router._run_pipeline_in_background", _noop_background)
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={
            "source_document_id": str(uuid.uuid4()),
            "file_path": _real_pdf_path(),
            "chapter_code": "current-electricity",
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422


async def test_rejects_unknown_source_document_id(client, register_user, db_session, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.api.ingestion_router._run_pipeline_in_background", _noop_background)
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={"source_document_id": str(uuid.uuid4())},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 404


async def test_rejects_stale_checksum(db_session, tmp_path, monkeypatch):
    root = tmp_path / "StudyMaterial"
    rel_dir = root / "Physics" / "Class 12-Physics"
    rel_dir.mkdir(parents=True)
    pdf = rel_dir / "ncert-book-class-12-physics-part-1-chapter-3.pdf"
    pdf.write_bytes(b"%PDF-original")
    checksum = compute_checksum(str(pdf))

    source = SourceDocument(
        relative_source_path="Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf",
        file_name=pdf.name,
        file_type="pdf",
        file_size=pdf.stat().st_size,
        checksum_sha256=checksum,
        class_level="12",
        subject_code="PHYSICS",
        ingestion_status="DISCOVERED",
    )
    db_session.add(source)
    await db_session.commit()

    await SourceAcademicMappingService(db_session).upsert_mapping_for_source(source)
    await db_session.commit()

    pdf.write_bytes(b"%PDF-modified-content")
    monkeypatch.setattr(
        "app.modules.ingestion.services.source_document_resolver.get_settings",
        lambda: SimpleNamespace(study_material_dir=str(root)),
    )

    pipeline = IngestionPipelineService(db_session)
    with pytest.raises(AppError) as exc:
        await pipeline.start_job(source_document_id=source.id)
    assert exc.value.code == "SOURCE_CHECKSUM_MISMATCH"


async def test_rejects_unmapped_source_document(db_session, tmp_path, monkeypatch):
    root = tmp_path / "StudyMaterial"
    rel_dir = root / "Physics" / "Class 11-Physics"
    rel_dir.mkdir(parents=True)
    pdf = rel_dir / "ncert-books-class-11-physics-chapter-99.pdf"
    pdf.write_bytes(b"%PDF-unmapped")
    checksum = compute_checksum(str(pdf))

    source = SourceDocument(
        relative_source_path="Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-99.pdf",
        file_name=pdf.name,
        file_type="pdf",
        file_size=pdf.stat().st_size,
        checksum_sha256=checksum,
        class_level="11",
        subject_code="PHYSICS",
        ingestion_status="DISCOVERED",
    )
    db_session.add(source)
    await db_session.commit()

    monkeypatch.setattr(
        "app.modules.ingestion.services.source_document_resolver.get_settings",
        lambda: SimpleNamespace(study_material_dir=str(root)),
    )

    pipeline = IngestionPipelineService(db_session)
    with pytest.raises(AppError) as exc:
        await pipeline.start_job(source_document_id=source.id)
    assert exc.value.code == "UNMAPPED_SOURCE"
