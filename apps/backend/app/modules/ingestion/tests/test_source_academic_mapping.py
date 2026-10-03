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
    # chapter_code corrected 2026-10-01 to match the rebaselined academic.chapters
    # seed (curriculum_baseline_rationalised_2026_27) — see
    # study_material_academic_registry.py's module docstring.
    ref = lookup_explicit_mapping(source_subject_code="PHYSICS", class_level="12", ncert_chapter_number=3)
    assert ref is not None
    assert ref.academic_subject_code == "PHYSICS"
    assert ref.chapter_code == "PHYSICS-U12"


async def test_chemistry_registry_maps_chemical_bonding():
    ref = lookup_explicit_mapping(source_subject_code="CHEMISTRY", class_level="11", ncert_chapter_number=4)
    assert ref is not None
    assert ref.chapter_code == "CHEMISTRY-U03"


async def test_biology_registry_maps_photosynthesis_from_chapter_11():
    # RESOLVED 2026-10-01 (docs/quality/ncert-manual-mapping-expansion-2026-10-01.md):
    # direct page evidence confirms Ch11 = Photosynthesis, under the broad
    # BIOLOGY-U04 unit (Class 11 Biology taxonomy is unit-level, not
    # per-chapter, in the current seed).
    ref = lookup_explicit_mapping(source_subject_code="BIOLOGY", class_level="11", ncert_chapter_number=11)
    assert ref is not None
    # BIOLOGY-U04 belongs to subject BIOLOGY in the live seed (not the
    # finer BOTANY/ZOOLOGY split, which only exists for the Class-12
    # XII-BIO-* chapter-exact codes).
    assert ref.academic_subject_code == "BIOLOGY"
    assert ref.chapter_code == "BIOLOGY-U04"


async def test_biology_chapter_13_maps_to_same_broad_unit_as_chapter_11():
    """Corpus chapter-13.pdf is Plant Growth and Development — a different
    NCERT chapter than Ch11 (Photosynthesis), but both are directly confirmed
    (Unit-4 divider page) to belong to the same broad BIOLOGY-U04 unit under
    this seed's unit-level-only Class 11 Biology taxonomy. This is not a
    guess: the taxonomy genuinely has no finer granularity to distinguish
    them at this class level (see BOTANY/ZOOLOGY's XII-BIO-* codes for the
    finer, chapter-exact alternative available at Class 12 only)."""
    ref = lookup_explicit_mapping(source_subject_code="BIOLOGY", class_level="11", ncert_chapter_number=13)
    assert ref is not None
    assert ref.chapter_code == "BIOLOGY-U04"


async def test_biology_registry_maps_zoology_explicitly():
    # RESOLVED 2026-10-01: Ch18 is directly confirmed as "Neural Control and
    # Coordination" (not Body Fluids — that's Ch15), but both share the same
    # broad BIOLOGY-U05 unit, so the mapping target is still correct.
    ref = lookup_explicit_mapping(source_subject_code="BIOLOGY", class_level="11", ncert_chapter_number=18)
    assert ref is not None
    assert ref.academic_subject_code == "BIOLOGY"
    assert ref.chapter_code == "BIOLOGY-U05"


async def test_unknown_biology_chapter_has_no_registry_entry():
    # Ch1 is now a real, mapped entry (BIOLOGY-U01) — use a chapter number
    # that genuinely doesn't exist in any NCERT Biology book to test the
    # "no registry entry" case.
    ref = lookup_explicit_mapping(source_subject_code="BIOLOGY", class_level="11", ncert_chapter_number=99)
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
    assert mapping.chapter_code == "PHYSICS-U12"
    assert mapping.academic_subject_code == "PHYSICS"
    assert mapping.pilot_ready is True

    chapter = await repo.get_chapter_for_subject(subject_code="PHYSICS", chapter_code="PHYSICS-U12")
    assert chapter is not None
    topic_count = (await db_session.execute(select(func.count(Topic.id)).where(Topic.chapter_id == chapter.id))).scalar_one()
    assert topic_count > 0


async def test_sync_maps_biology_chapter_11_to_biology_u04(db_session):
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
    assert mapping.academic_subject_code == "BIOLOGY"
    assert mapping.chapter_code == "BIOLOGY-U04"
    assert mapping.ncert_chapter_number == 11
    # BIOLOGY-U04 is not in PILOT_CHAPTER_CODES / CHAPTER_CONTENT_MARKERS
    # (not extended this round — see registry module docstring), so
    # pilot_ready is correctly False despite mapping_status == MAPPED.
    assert mapping.pilot_ready is False


async def test_sync_maps_biology_chapter_13_to_same_unit_as_chapter_11(db_session):
    """Ch13 (Plant Growth and Development) is a different NCERT chapter than
    Ch11 (Photosynthesis) but both correctly map to the same broad
    BIOLOGY-U04 unit — this seed's Class 11 Biology taxonomy has no finer
    granularity, confirmed directly, not guessed."""
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

    assert mapping.mapping_status == "MAPPED"
    assert mapping.chapter_code == "BIOLOGY-U04"
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
