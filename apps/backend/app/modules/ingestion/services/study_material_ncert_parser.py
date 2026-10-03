"""Extract NCERT chapter numbers from StudyMaterial PDF filenames."""

from __future__ import annotations

import re

# Matches trailing chapter-N.pdf across naming variants:
#   ncert-books-class-11-physics-chapter-3.pdf
#   ncert-book-class-12-physics-part-1-chapter-3.pdf
_NCERT_CHAPTER_RE = re.compile(r"chapter-(\d+)\.pdf$", re.IGNORECASE)

# NCERT's own internal short-code naming for Physics Class 12 Part 2
# (e.g. leph201.pdf .. leph206.pdf) — NN is the file's 2-digit position
# within Part 2, which continues the chapter count from Part 1's chapters
# 1-8 (Part 2 starts at Chapter 9). The \d{2} requirement means
# non-numeric suffixes (leph2an.pdf = Appendices, leph2ps.pdf = cover
# page — neither is chapter content) correctly never match and keep
# returning None, same as any other unrecognized filename.
#
# The chapter-number arithmetic below (NN + 8) is derived from the NCERT
# book's own fixed Part 1/Part 2 structure, not inferred from this
# filename alone — each of leph201..leph206's resulting chapter numbers
# was independently confirmed against its actual page content before
# this parser change was made. See
# docs/quality/ncert-manual-mapping-expansion-2026-10-01.md and
# docs/quality/ncert-physics-filename-parser-fix-2026-10-01.md.
_LEPH2_PART2_RE = re.compile(r"^leph2(\d{2})\.pdf$", re.IGNORECASE)
_LEPH2_PART2_CHAPTER_OFFSET = 8


def extract_ncert_chapter_number(file_name: str) -> int | None:
    name = file_name.strip()
    match = _NCERT_CHAPTER_RE.search(name)
    if match:
        return int(match.group(1))
    leph2_match = _LEPH2_PART2_RE.match(name)
    if leph2_match:
        return int(leph2_match.group(1)) + _LEPH2_PART2_CHAPTER_OFFSET
    return None
