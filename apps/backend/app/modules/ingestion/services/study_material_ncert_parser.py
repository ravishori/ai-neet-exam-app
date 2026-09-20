"""Extract NCERT chapter numbers from StudyMaterial PDF filenames."""

from __future__ import annotations

import re

# Matches trailing chapter-N.pdf across naming variants:
#   ncert-books-class-11-physics-chapter-3.pdf
#   ncert-book-class-12-physics-part-1-chapter-3.pdf
_NCERT_CHAPTER_RE = re.compile(r"chapter-(\d+)\.pdf$", re.IGNORECASE)


def extract_ncert_chapter_number(file_name: str) -> int | None:
    match = _NCERT_CHAPTER_RE.search(file_name.strip())
    if not match:
        return None
    return int(match.group(1))
