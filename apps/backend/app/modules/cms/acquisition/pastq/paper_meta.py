"""Deterministic paper metadata from filename + PDF text (no unsafe inference)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Documented deterministic filename year pattern (case-insensitive).
# Examples: NEET2015.pdf, Neet2022.pdf, NEET2026-11.pdf, RENeet2026.pdf
FILENAME_YEAR_RE = re.compile(r"^(?:RE)?NEET\s*[-_]?(20\d{2})(?:[-_]\d+)?\.pdf$", re.I)
FILENAME_SET_SUFFIX_RE = re.compile(r"^NEET\s*[-_]?(20\d{2})[-_](\d+)\.pdf$", re.I)
TEXT_UG_YEAR_RE = re.compile(r"NEET\s*\(\s*UG\s*\)\s*[-–—]?\s*(20\d{2})", re.I)
TEXT_PAPER_YEAR_RE = re.compile(r"Paper\s*[-–—]?\s*(20\d{2})", re.I)
CODE_RE = re.compile(
    r"(?:Test\s+Booklet\s+Code|Booklet\s+Code|Code\s*[-–—:_]\s*|Code\s+)([A-Z0-9]{1,6})",
    re.I,
)
SCOPE_YEARS = frozenset(range(2015, 2027))


@dataclass
class PaperMeta:
    exam_name: str = "NEET"
    year: int | None = None
    year_source: str | None = None
    set_code: str | None = None
    set_source: str | None = None
    language: str | None = None
    needs_review: bool = False
    warnings: list[str] = field(default_factory=list)
    is_paper_candidate: bool = True


def filename_year(filename: str) -> int | None:
    m = FILENAME_YEAR_RE.match(filename.strip())
    if not m:
        return None
    year = int(m.group(1))
    return year if year in SCOPE_YEARS else None


def filename_set_suffix(filename: str) -> str | None:
    m = FILENAME_SET_SUFFIX_RE.match(filename.strip())
    return m.group(2) if m else None


def resolve_paper_meta(*, filename: str, corpus_sample: str) -> PaperMeta:
    """Resolve year/set with fail-closed rules.

    Filename year is used only when the documented pattern matches.
    If PDF text asserts a conflicting UG year, year is cleared and NEEDS_REVIEW.
    """
    meta = PaperMeta()
    lower = filename.lower()
    if "syllabus" in lower:
        meta.is_paper_candidate = False
        meta.needs_review = True
        meta.warnings.append("non_paper_syllabus")
        return meta

    fn_year = filename_year(filename)
    ug_years = [int(y) for y in TEXT_UG_YEAR_RE.findall(corpus_sample or "")]
    paper_years = [int(y) for y in TEXT_PAPER_YEAR_RE.findall(corpus_sample or "")]

    if ug_years:
        # Prefer explicit UG year from booklet text when present.
        text_year = ug_years[0]
        if fn_year is not None and fn_year != text_year:
            meta.year = None
            meta.year_source = None
            meta.needs_review = True
            meta.warnings.append(
                f"year_conflict_filename_{fn_year}_vs_text_{text_year}"
            )
        else:
            meta.year = text_year if text_year in SCOPE_YEARS else None
            meta.year_source = "pdf_text_ug"
            if meta.year is None:
                meta.needs_review = True
                meta.warnings.append("ug_year_out_of_scope")
    elif fn_year is not None:
        meta.year = fn_year
        meta.year_source = "filename_deterministic_pattern"
    elif paper_years:
        py = paper_years[0]
        if py in SCOPE_YEARS:
            meta.year = py
            meta.year_source = "pdf_text_paper_marker"
        else:
            meta.needs_review = True
            meta.warnings.append("paper_year_out_of_scope")
    else:
        meta.needs_review = True
        meta.warnings.append("year_undetermined")

    suffix = filename_set_suffix(filename)
    code_m = CODE_RE.search(corpus_sample or "")
    if code_m:
        meta.set_code = code_m.group(1).upper()
        meta.set_source = "pdf_text_booklet_code"
    elif suffix:
        meta.set_code = suffix
        meta.set_source = "filename_suffix"
        meta.warnings.append("set_from_filename_suffix_only")
        meta.needs_review = True
    else:
        meta.warnings.append("set_undetermined")
        # set may remain NULL without forcing review if year is solid

    if re.search(r"\bEnglish\b", corpus_sample or "", re.I):
        meta.language = "en"
    elif re.search(r"\bHindi\b", corpus_sample or "", re.I):
        meta.language = "hi"

    return meta


def classify_filename(filename: str) -> str:
    lower = filename.lower()
    if "syllabus" in lower:
        return "SYLLABUS"
    if "answer" in lower or "key" in lower:
        return "ANSWER_KEY"
    if "solution" in lower:
        return "SOLUTION"
    if FILENAME_YEAR_RE.match(filename.strip()) or "neet" in lower:
        return "NEET_QUESTION_PAPER"
    return "UNKNOWN"
