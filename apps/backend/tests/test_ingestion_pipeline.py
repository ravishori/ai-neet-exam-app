"""Integration tests: ingestion pipeline trigger endpoint (ADR-0022).

The heavy pipeline itself (PDF extraction, AI generation) is exercised by
the pure-function unit tests in app/modules/ingestion/tests/ and was
proven against the real Current Electricity PDF manually — see ADR-0022.
These tests cover the synchronous, testable slice of the API: permission
gating, path-traversal rejection, and job creation. The background task
is monkeypatched to a no-op so tests don't make real AI calls or depend
on wall-clock PDF processing time.
"""

from pathlib import Path

import pytest

from app.core.config import get_settings
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _noop_background(*args, **kwargs) -> None:
    return None


def _real_pdf_path() -> str:
    settings = get_settings()
    path = (
        Path(settings.study_material_dir)
        / "Physics"
        / "Class 12-Physics"
        / "ncert-book-class-12-physics-part-1-chapter-3.pdf"
    )
    assert path.is_file(), f"expected the real pilot PDF at {path}"
    return str(path)


async def test_start_job_requires_content_create_permission(client, db_session, register_user):
    await register_user(client)  # default STUDENT role — no content.create

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={"file_path": _real_pdf_path(), "chapter_code": "current-electricity"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 403


async def test_start_job_rejects_path_outside_study_material_dir(client, db_session, register_user, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.api.ingestion_router._run_pipeline_in_background", _noop_background)
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={"file_path": __file__, "chapter_code": "current-electricity"},  # this test file, not StudyMaterial
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "INVALID_PATH"


async def test_start_job_rejects_missing_file(client, db_session, register_user, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.api.ingestion_router._run_pipeline_in_background", _noop_background)
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    settings = get_settings()
    missing_path = str(Path(settings.study_material_dir) / "does-not-exist.pdf")

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={"file_path": missing_path, "chapter_code": "current-electricity"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 404


async def test_start_job_rejects_unknown_chapter(client, db_session, register_user, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.api.ingestion_router._run_pipeline_in_background", _noop_background)
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={"file_path": _real_pdf_path(), "chapter_code": "no-such-chapter"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 404


async def test_start_job_creates_pending_job_against_real_pdf(client, db_session, register_user, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.api.ingestion_router._run_pipeline_in_background", _noop_background)
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={"file_path": _real_pdf_path(), "chapter_code": "current-electricity"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()["data"]
    assert data["status"] == "PENDING"
    assert data["sections_detected"] == 0
    assert data["questions_generated"] == 0

    detail = await client.get(f"/api/v1/ingestion/jobs/{data['id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == data["id"]


async def test_start_job_reuses_completed_job_for_unchanged_checksum(client, db_session, register_user, monkeypatch):
    """A file already processed to COMPLETED must not be reprocessed —
    ADR-0022's "process files only once." Seeds a COMPLETED job directly
    (bypassing the real pipeline) rather than waiting on a live AI call."""
    monkeypatch.setattr("app.modules.ingestion.api.ingestion_router._run_pipeline_in_background", _noop_background)
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)

    from sqlalchemy import select

    from app.modules.academic.models import Chapter
    from app.modules.ingestion.models import IngestionJob
    from app.modules.ingestion.services.pdf_extraction_service import compute_checksum

    chapter = (
        await db_session.execute(select(Chapter).where(Chapter.code == "current-electricity"))
    ).scalar_one()
    checksum = compute_checksum(_real_pdf_path())
    existing = IngestionJob(
        source_file_path=_real_pdf_path(),
        file_checksum=checksum,
        subject_id=chapter.subject_id,
        chapter_id=chapter.id,
        status="COMPLETED",
        questions_generated=14,
    )
    db_session.add(existing)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/ingestion/jobs",
        json={"file_path": _real_pdf_path(), "chapter_code": "current-electricity"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["id"] == str(existing.id)
    assert data["status"] == "COMPLETED"
    assert data["questions_generated"] == 14
