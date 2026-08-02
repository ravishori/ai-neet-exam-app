"""Integration test: language metadata on ingestion sections (ADR-0027),
against the real pilot PDF already used by ADR-0022/0024/0025/0026. Calls
extraction + matching directly rather than the full run() — neither stage
makes an AI call, so there's no reason to pay for a full generation pass
just to prove language detection runs end to end against a real file."""
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.academic.models import Chapter
from app.modules.ingestion.models import IngestionSection
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


async def test_real_english_pdf_sections_are_detected_as_english(db_session):
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
    sections = await service._run_extraction(job)
    matched = await service._run_matching(job, sections)

    assert len(matched) > 0, "expected at least one matched section in the real pilot chapter"

    rows = (
        await db_session.execute(select(IngestionSection).where(IngestionSection.job_id == job.id))
    ).scalars().all()
    assert len(rows) == len(sections)

    for row in rows:
        # This is a real English-language NCERT physics chapter — every
        # section should detect as English with reasonably high confidence,
        # not a hardcoded assumption.
        assert row.language_code == "en"
        assert row.language_name == "English"
        assert row.language_confidence is not None and row.language_confidence > 0.8
