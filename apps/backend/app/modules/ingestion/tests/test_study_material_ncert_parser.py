"""Unit tests for NCERT chapter number extraction."""

import pytest

from app.modules.ingestion.services.study_material_ncert_parser import extract_ncert_chapter_number


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        # Existing patterns — regression protection, must remain unchanged.
        ("ncert-books-class-11-physics-chapter-3.pdf", 3),
        ("ncert-book-class-12-physics-part-1-chapter-3.pdf", 3),
        ("ncert-books-class-11-chemistry-chapter-4.pdf", 4),
        ("ncert-books-class-11-biology-chapter-13.pdf", 13),
        ("not-a-chapter.pdf", None),
    ],
)
def test_extract_ncert_chapter_number(file_name: str, expected: int | None):
    assert extract_ncert_chapter_number(file_name) == expected


@pytest.mark.parametrize(
    ("file_name", "expected_chapter"),
    [
        # Physics Class 12 Part 2 — leph2NN.pdf, NN continues the chapter
        # count from Part 1 (chapters 1-8), so leph201 = Chapter 9, etc.
        # Expected chapter numbers match the directly-verified page content
        # (Ray Optics=9, Wave Optics=10, Dual Nature of Radiation=11,
        # Atoms=12, Nuclei=13, Electronic Devices=14) — see
        # docs/quality/ncert-physics-filename-parser-fix-2026-10-01.md.
        ("leph201.pdf", 9),
        ("leph202.pdf", 10),
        ("leph203.pdf", 11),
        ("leph204.pdf", 12),
        ("leph205.pdf", 13),
        ("leph206.pdf", 14),
        # Case-insensitivity, matching the existing pattern's behavior.
        ("LEPH201.PDF", 9),
        ("Leph206.Pdf", 14),
    ],
)
def test_extract_ncert_chapter_number_leph2_part2(file_name: str, expected_chapter: int):
    assert extract_ncert_chapter_number(file_name) == expected_chapter


@pytest.mark.parametrize(
    "file_name",
    [
        # Appendices — not chapter content, must stay unmapped.
        "leph2an.pdf",
        # Cover page — not chapter content, must stay unmapped.
        "leph2ps.pdf",
        # Three-digit / malformed variants must not accidentally match.
        "leph2007.pdf",
        "leph2.pdf",
        "leph2a.pdf",
        # Unrelated file sharing a substring must not false-positive.
        "notleph201.pdf",
    ],
)
def test_extract_ncert_chapter_number_leph2_non_chapter_files_stay_none(file_name: str):
    assert extract_ncert_chapter_number(file_name) is None
