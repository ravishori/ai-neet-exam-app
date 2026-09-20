"""Unit tests for chapter PDF content preflight (Phase B.1)."""

from pathlib import Path

import fitz
import pytest

from app.core.config import get_settings
from app.modules.ingestion.services.chapter_content_preflight import (
    pdf_content_matches_chapter,
)


def _write_pdf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


@pytest.mark.unit
def test_photosynthesis_marker_rejects_plant_growth_pdf(tmp_path):
    pdf = tmp_path / "plant-growth.pdf"
    _write_pdf(pdf, "13.1 GROWTH\nPlant Growth Regulators\nAbscisic acid")
    assert pdf_content_matches_chapter(pdf, "photosynthesis") is False


@pytest.mark.unit
def test_photosynthesis_marker_accepts_higher_plants_title(tmp_path):
    pdf = tmp_path / "photosynthesis.pdf"
    _write_pdf(pdf, "PHOTOSYNTHESIS IN HIGHER PLANTS\nChloroplasts and light reaction")
    assert pdf_content_matches_chapter(pdf, "photosynthesis") is True


@pytest.mark.real_corpus
def test_real_corpus_chapter_13_fails_photosynthesis_preflight():
    root = Path(get_settings().study_material_dir)
    path = root / "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-13.pdf"
    if not path.is_file():
        pytest.skip("corpus PDF missing")
    assert pdf_content_matches_chapter(path, "photosynthesis") is False


@pytest.mark.real_corpus
def test_real_corpus_chapter_11_passes_photosynthesis_preflight():
    root = Path(get_settings().study_material_dir)
    path = root / "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf"
    if not path.is_file():
        pytest.skip("corpus PDF missing")
    assert pdf_content_matches_chapter(path, "photosynthesis") is True


@pytest.mark.real_corpus
def test_real_corpus_physics_and_chemistry_still_match():
    root = Path(get_settings().study_material_dir)
    physics = root / "Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf"
    chemistry = root / "Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf"
    if not physics.is_file() or not chemistry.is_file():
        pytest.skip("corpus PDFs missing")
    assert pdf_content_matches_chapter(physics, "current-electricity") is True
    assert pdf_content_matches_chapter(chemistry, "chemical-bonding") is True
