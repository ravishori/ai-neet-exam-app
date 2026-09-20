"""Unit tests for NCERT chapter number extraction."""

import pytest

from app.modules.ingestion.services.study_material_ncert_parser import extract_ncert_chapter_number


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("ncert-books-class-11-physics-chapter-3.pdf", 3),
        ("ncert-book-class-12-physics-part-1-chapter-3.pdf", 3),
        ("ncert-books-class-11-chemistry-chapter-4.pdf", 4),
        ("ncert-books-class-11-biology-chapter-13.pdf", 13),
        ("not-a-chapter.pdf", None),
    ],
)
def test_extract_ncert_chapter_number(file_name: str, expected: int | None):
    assert extract_ncert_chapter_number(file_name) == expected
