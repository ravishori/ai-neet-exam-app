"""Integration test: visual asset detection stage (ADR-0026), against the
real pilot PDF already used by ADR-0022/0024/0025. Calls the pipeline
service's detection stage directly rather than the full run() — asset
detection makes no AI calls, so there's no reason to pay for a full
generation pass just to prove this stage works end to end against a real
file."""
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.academic.models import Chapter
from app.modules.ingestion.models import VisualAsset
from app.modules.ingestion.models.ingestion_job import IngestionJob
from app.modules.ingestion.services.ingestion_pipeline_service import IngestionPipelineService
from app.modules.ingestion.services.pdf_extraction_service import compute_checksum

pytestmark = pytest.mark.asyncio(loop_scope="session")


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


async def test_asset_detection_against_real_pdf_creates_rows_and_updates_counters(db_session):
    chapter = (
        await db_session.execute(select(Chapter).where(Chapter.code == "current-electricity"))
    ).scalar_one()
    pdf_path = _real_pdf_path()
    job = IngestionJob(
        source_file_path=pdf_path,
        file_checksum=compute_checksum(pdf_path),
        subject_id=chapter.subject_id,
        chapter_id=chapter.id,
        status="EXTRACTING",
    )
    db_session.add(job)
    await db_session.flush()

    service = IngestionPipelineService(db_session)
    await service._run_asset_detection(job)

    rows = (
        await db_session.execute(select(VisualAsset).where(VisualAsset.job_id == job.id))
    ).scalars().all()

    assert job.visual_assets_detected == len(rows)
    assert job.visual_assets_needing_review <= job.visual_assets_detected
    for row in rows:
        assert row.asset_type in ("image", "diagram", "table", "equation", "chemical_structure")
        assert row.detection_method in ("embedded_image", "vector_cluster", "manual")
        assert row.review_status in ("AUTO_DETECTED", "VERIFIED", "NEEDS_MANUAL_BBOX", "REJECTED")
        assert row.storage_path is not None and Path(row.storage_path).is_file()
        assert row.content_hash is not None and len(row.content_hash) == 64


async def test_asset_detection_does_not_change_existing_pipeline_counters(db_session):
    """Non-interference check, same discipline as ADR-0024's PR 1: running
    asset detection must not touch any counter that predates it."""
    chapter = (
        await db_session.execute(select(Chapter).where(Chapter.code == "current-electricity"))
    ).scalar_one()
    pdf_path = _real_pdf_path()
    job = IngestionJob(
        source_file_path=pdf_path,
        # distinct from the other test's job row, still 64 hex chars
        file_checksum="f" + compute_checksum(pdf_path)[1:],
        subject_id=chapter.subject_id,
        chapter_id=chapter.id,
        status="EXTRACTING",
    )
    db_session.add(job)
    await db_session.flush()

    service = IngestionPipelineService(db_session)
    await service._run_asset_detection(job)

    assert job.sections_detected == 0
    assert job.questions_generated == 0
    assert job.knowledge_units_created == 0
    assert job.knowledge_units_rejected == 0
