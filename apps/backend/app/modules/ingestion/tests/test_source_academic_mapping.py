"""Tests for explicit SourceDocument → academic mapping (ADR-0031)."""

from pathlib import Path

import fitz
import pytest
from sqlalchemy import func, select

from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.ingestion.models.source_document import SourceDocument
from app.modules.ingestion.repositories.source_academic_mapping_repository import SourceAcademicMappingRepository
from app.modules.ingestion.services.source_academic_mapping_service import SourceAcademicMappingService
from app.modules.ingestion.services.study_material_academic_registry import lookup_explicit_mapping

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _write_pdf(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), label)
    doc.save(path)
    doc.close()


async def test_physics_registry_maps_current_electricity():
    ref = lookup_explicit_mapping(source_subject_code="PHYSICS", class_level="12", ncert_chapter_number=3)
    assert ref is not None
    assert ref.academic_subject_code == "PHYSICS"
    assert ref.chapter_code == "current-electricity"


async def test_chemistry_registry_maps_chemical_bonding():
    ref = lookup_explicit_mapping(source_subject_code="CHEMISTRY", class_level="11", ncert_chapter_number=4)
    assert ref is not None
    assert ref.chapter_code == "chemical-bonding"


async def test_biology_registry_maps_photosynthesis_from_chapter_11():
    ref = lookup_explicit_mapping(source_subject_code="BIOLOGY", class_level="11", ncert_chapter_number=11)
    assert ref is not None
    assert ref.academic_subject_code == "BOTANY"
    assert ref.chapter_code == "photosynthesis"


async def test_biology_chapter_13_is_not_mapped_to_photosynthesis():
    """Corpus chapter-13.pdf is Plant Growth — must not map to photosynthesis."""
    ref = lookup_explicit_mapping(source_subject_code="BIOLOGY", class_level="11", ncert_chapter_number=13)
    assert ref is None


async def test_biology_registry_maps_zoology_explicitly():
    ref = lookup_explicit_mapping(source_subject_code="BIOLOGY", class_level="11", ncert_chapter_number=18)
    assert ref is not None
    assert ref.academic_subject_code == "ZOOLOGY"
    assert ref.chapter_code == "body-fluids-circulation"


async def test_unknown_biology_chapter_has_no_registry_entry():
    ref = lookup_explicit_mapping(source_subject_code="BIOLOGY", class_level="11", ncert_chapter_number=1)
    assert ref is None


async def test_sync_marks_unmapped_without_inventing_chapters(db_session, tmp_path):
    chapter_count_before = (await db_session.execute(select(func.count(Chapter.id)))).scalar_one()
    concept_count_before = (await db_session.execute(select(func.count(Concept.id)))).scalar_one()

    unmapped_pdf = tmp_path / "Physics" / "Class 11-Physics" / "ncert-books-class-11-physics-chapter-99.pdf"
    _write_pdf(unmapped_pdf, "missing chapter")

    doc = SourceDocument(
        relative_source_path="Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-99.pdf",
        file_name=unmapped_pdf.name,
        file_type="pdf",
        file_size=unmapped_pdf.stat().st_size,
        checksum_sha256="abc123" * 8,
        class_level="11",
        subject_code="PHYSICS",
        ingestion_status="DISCOVERED",
    )
    db_session.add(doc)
    await db_session.commit()

    mapping, _created = await SourceAcademicMappingService(db_session).upsert_mapping_for_source(doc)
    await db_session.commit()

    assert mapping.mapping_status == "UNMAPPED"
    assert mapping.chapter_id is None

    chapter_count_after = (await db_session.execute(select(func.count(Chapter.id)))).scalar_one()
    concept_count_after = (await db_session.execute(select(func.count(Concept.id)))).scalar_one()
    assert chapter_count_after == chapter_count_before
    assert concept_count_after == concept_count_before


async def test_sync_maps_pilot_physics_source(db_session):
    repo = SourceAcademicMappingRepository(db_session)
    physics_doc = (
        await db_session.execute(
            select(SourceDocument).where(SourceDocument.relative_source_path.like("%physics-part-1-chapter-3.pdf"))
        )
    ).scalar_one_or_none()
    if physics_doc is None:
        pytest.skip("real corpus source document not registered in test DB")

    mapping, _ = await SourceAcademicMappingService(db_session).upsert_mapping_for_source(physics_doc)
    await db_session.commit()

    assert mapping.mapping_status == "MAPPED"
    assert mapping.chapter_code == "current-electricity"
    assert mapping.academic_subject_code == "PHYSICS"
    assert mapping.pilot_ready is True

    chapter = await repo.get_chapter_for_subject(subject_code="PHYSICS", chapter_code="current-electricity")
    assert chapter is not None
    topic_count = (await db_session.execute(select(func.count(Topic.id)).where(Topic.chapter_id == chapter.id))).scalar_one()
    assert topic_count > 0


async def test_sync_maps_biology_chapter_11_to_photosynthesis_pilot_ready(db_session):
    bio = (
        await db_session.execute(
            select(SourceDocument).where(
                SourceDocument.relative_source_path
                == "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf"
            )
        )
    ).scalar_one_or_none()
    if bio is None:
        pytest.skip("biology chapter-11 not registered in test DB")

    mapping, _ = await SourceAcademicMappingService(db_session).upsert_mapping_for_source(bio)
    await db_session.commit()

    assert mapping.mapping_status == "MAPPED"
    assert mapping.academic_subject_code == "BOTANY"
    assert mapping.chapter_code == "photosynthesis"
    assert mapping.ncert_chapter_number == 11
    assert mapping.pilot_ready is True


async def test_sync_unmaps_biology_chapter_13_plant_growth(db_session):
    """Previous incorrect photosynthesis mapping must be cleared on sync."""
    bio = (
        await db_session.execute(
            select(SourceDocument).where(
                SourceDocument.relative_source_path
                == "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-13.pdf"
            )
        )
    ).scalar_one_or_none()
    if bio is None:
        pytest.skip("biology chapter-13 not registered in test DB")

    mapping, _ = await SourceAcademicMappingService(db_session).upsert_mapping_for_source(bio)
    await db_session.commit()

    assert mapping.mapping_status == "UNMAPPED"
    assert mapping.chapter_code is None
    assert mapping.pilot_ready is False


async def test_pilot_ready_false_when_pdf_content_mismatches_mapped_chapter(db_session, monkeypatch):
    """Defense in depth: even a MAPPED registry entry is not pilot_ready on content fail."""
    from app.modules.ingestion.services import source_academic_mapping_service as svc_mod

    physics_doc = (
        await db_session.execute(
            select(SourceDocument).where(SourceDocument.relative_source_path.like("%physics-part-1-chapter-3.pdf"))
        )
    ).scalar_one_or_none()
    if physics_doc is None:
        pytest.skip("physics pilot source not registered")

    monkeypatch.setattr(svc_mod, "pdf_content_matches_chapter", lambda *_a, **_k: False)
    mapping, _ = await SourceAcademicMappingService(db_session).upsert_mapping_for_source(physics_doc)
    await db_session.commit()

    assert mapping.mapping_status == "MAPPED"
    assert mapping.pilot_ready is False
    assert mapping.mapping_notes and "does not match" in mapping.mapping_notes.lower()
