"""Integration tests for NEET StudyMaterial discovery (ADR-0030)."""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import fitz
import pytest

from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.study_material_discovery_service import StudyMaterialDiscoveryService
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")

# Unique relative paths so assertions stay valid even when trinetra_test_db
# already contains a previously discovered real NEET corpus (global totals
# are not authoritative for these tests).
_PHYSICS_REL = "Physics/Class 11-Physics/phase-a-sample-physics.pdf"
_CHEMISTRY_REL = "Chemistry/Class 11- Chemistry/phase-a-sample-chemistry.pdf"
_BIOLOGY_REL = "Biology/Class 12-Biology/phase-a-sample-biology.pdf"
_CORPUS_RELS = (_PHYSICS_REL, _CHEMISTRY_REL, _BIOLOGY_REL)


def _write_minimal_pdf(path: Path, text: str = "NEET sample") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def _build_temp_corpus(root: Path) -> None:
    # Unique PDF bytes per file so SHA-256 never collides with the real corpus
    # or with other tests in the same DB.
    token = uuid4().hex
    _write_minimal_pdf(root.joinpath(*_PHYSICS_REL.split("/")), f"physics-{token}")
    _write_minimal_pdf(root.joinpath(*_CHEMISTRY_REL.split("/")), f"chemistry-{token}")
    _write_minimal_pdf(root.joinpath(*_BIOLOGY_REL.split("/")), f"biology-{token}")
    _write_minimal_pdf(root / "Maths" / "sample.pdf", f"maths-out-of-scope-{token}")
    _write_minimal_pdf(root / "Uploads" / "sample.pdf", f"upload-excluded-{token}")


@pytest.fixture
def temp_study_material(tmp_path: Path) -> SimpleNamespace:
    root = tmp_path / "StudyMaterial"
    root.mkdir()
    _build_temp_corpus(root)
    return SimpleNamespace(study_material_dir=str(root))


async def _assert_corpus_docs(repo: SourceDocumentRepository) -> list:
    docs = []
    for rel in _CORPUS_RELS:
        doc = await repo.get_by_relative_path(rel)
        assert doc is not None, f"missing registered source: {rel}"
        docs.append(doc)
    assert {d.subject_code for d in docs} == {"PHYSICS", "CHEMISTRY", "BIOLOGY"}
    assert all(d.subject_code != "MATHS" for d in docs)
    assert not any("Maths" in d.relative_source_path for d in docs)
    assert not any("Uploads" in d.relative_source_path for d in docs)
    assert await repo.get_by_relative_path("Maths/sample.pdf") is None
    assert await repo.get_by_relative_path("Uploads/sample.pdf") is None
    return docs


async def test_discovery_registers_neet_only_and_is_idempotent(db_session, temp_study_material):
    service = StudyMaterialDiscoveryService(db_session, settings=temp_study_material)

    first = await service.discover()
    assert first.discovered == 3
    assert first.registered == 3
    assert first.duplicates == 0
    assert first.by_subject_class["PHYSICS"]["11"] == 1
    assert first.by_subject_class["CHEMISTRY"]["11"] == 1
    assert first.by_subject_class["BIOLOGY"]["12"] == 1

    repo = SourceDocumentRepository(db_session)
    await _assert_corpus_docs(repo)

    second = await service.discover()
    assert second.discovered == 3
    assert second.registered == 0
    assert second.duplicates == 3
    await _assert_corpus_docs(repo)


async def test_discovery_dry_run_writes_nothing(db_session, temp_study_material):
    service = StudyMaterialDiscoveryService(db_session, settings=temp_study_material)
    report = await service.discover(dry_run=True)
    assert report.discovered == 3
    assert report.registered == 3  # would-register
    assert report.dry_run is True

    repo = SourceDocumentRepository(db_session)
    for rel in _CORPUS_RELS:
        assert await repo.get_by_relative_path(rel) is None


async def test_discovery_api_endpoint(client, register_user, db_session, temp_study_material, monkeypatch):
    monkeypatch.setattr(
        "app.modules.ingestion.services.study_material_discovery_service.get_settings",
        lambda: temp_study_material,
    )

    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    headers = csrf_headers(client)

    response = await client.post("/api/v1/ingestion/source-documents/discover", json={}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["discovered"] == 3
    assert data["registered"] == 3
    assert "absolute_source_path" not in str(data)

    again = await client.post("/api/v1/ingestion/source-documents/discover", json={}, headers=headers)
    assert again.json()["data"]["registered"] == 0
    assert again.json()["data"]["duplicates"] == 3

    listed = await client.get("/api/v1/ingestion/source-documents?limit=200", headers=headers)
    assert listed.status_code == 200
    paths = {item["relative_source_path"] for item in listed.json()["data"]}
    assert set(_CORPUS_RELS).issubset(paths)
    assert not any(p.startswith("Maths/") for p in paths)
    assert not any(p.startswith("Uploads/") for p in paths)

    # Authoritative path lookups (list pagination must not be the only proof).
    repo = SourceDocumentRepository(db_session)
    await _assert_corpus_docs(repo)
