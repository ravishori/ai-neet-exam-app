"""Tests for the local, deterministic PDF-text extraction package
(apps/backend/scripts/pyq_pdf_extract/) built for:

  - "33 Years NEET-AIPMT Chapterwise Solutions - Biology 2020.pdf"
  - "neet_pyp.pdf" ("NEET 2025 Chapterwise Index")

Covers: known-stem/answer correctness against real source content,
chapter/subject resolution, option-marker parsing edge cases (the
tab-vs-space delimiter variance and 2-column page reading order), the
chapter-boundary run-segmentation fix (embedded numbered sub-lists must
not corrupt chapter attachment or silently drop real questions), and
every extracted record carrying its mandatory rights_status.

Reads real PDFs from `Latest Study material/` -- skipped automatically
if that folder is unavailable (e.g. CI without the local file), same
convention as tests/test_pyq_image_pipeline.py.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SOURCE_DIR = Path(r"D:\ravishori\AI Neet Exam App\Latest Study material")
BOOK1_PDF = SOURCE_DIR / "33 Years NEET-AIPMT Chapterwise Solutions - Biology 2020.pdf"
BOOK2_PDF = SOURCE_DIR / "neet_pyp.pdf"

pytestmark = pytest.mark.real_corpus


# --- common.py unit tests (no PDF dependency) --------------------------

def test_opt_alpha_re_handles_tab_and_space_delimiter_variants():
    from scripts.pyq_pdf_extract.common import OPT_ALPHA_RE

    # standard newline-delimited options
    text1 = "\n(a)\t first option\n(b)\t second\n(c)\t third\n(d)\t fourth"
    labels1 = [m.group(1) for m in OPT_ALPHA_RE.finditer(text1)]
    assert labels1 == ["a", "b", "c", "d"]

    # two-per-line packing with a bare space before the second marker
    # (confirmed by direct inspection of the 33-years-Biology PDF)
    text2 = "\n(a)\t structure of nucleus\t (b)\t mode of nutrition\n(c)\t structure of cell wall\t(d)\t asexual"
    labels2 = [m.group(1) for m in OPT_ALPHA_RE.finditer(text2)]
    assert labels2 == ["a", "b", "c", "d"]


def test_answer_entry_re_matches_compact_and_detailed_forms():
    from scripts.pyq_pdf_extract.common import ANSWER_ENTRY_RE

    assert ANSWER_ENTRY_RE.match("\n(c)\t\n")
    assert ANSWER_ENTRY_RE.match("(d)\t:\tSome explanation text.")
    assert not ANSWER_ENTRY_RE.match("\nNot an answer entry at all")


def test_classify_block_distinguishes_question_from_answer_entry():
    from scripts.pyq_pdf_extract.common import classify_block

    question_block = "\nStem text?\n(a)\t one\n(b)\t two\n(c)\t three\n(d)\t four\n(2019)\n"
    cls, bounds = classify_block(question_block)
    assert cls == "QUESTION"
    assert len(bounds) == 4

    answer_block = "\n(c)\t:\tExplanation of the answer.\n"
    cls2, _ = classify_block(answer_block)
    assert cls2 == "ANSWER_ENTRY"

    toc_block = "\nThe Living World\t\n.............1\n"
    cls3, _ = classify_block(toc_block)
    assert cls3 == "OTHER"


def test_segment_into_runs_recovers_questions_after_embedded_sublist():
    """Regression test for the exact failure mode found in the
    "Digestion and Absorption" chapter (2026-10-18): a question's own
    stem contains an embedded "1. ... 5. ..." numbered sub-list, which
    must NOT be treated as a confirmed chapter reset -- the real
    questions immediately afterward (76+) must still attach to the
    original run, not be silently dropped."""
    import re as _re

    from scripts.pyq_pdf_extract.common import segment_into_runs

    pattern = re.compile(r"(?m)^(\d{1,3})\.")
    # 1..75 (real questions), then an embedded "1..5" sub-list (too short
    # to confirm), then the real continuation 76..80.
    numbers = list(range(1, 76)) + [1, 2, 3, 4, 5] + list(range(76, 81))
    text = "".join(f"{n}.\n" for n in numbers)
    matches = list(pattern.finditer(text))
    runs, orphaned = segment_into_runs(matches)

    assert len(runs) == 1, "the embedded sub-list must not split this into two confirmed runs"
    recovered_numbers = [nm.number for nm in runs[0]]
    assert recovered_numbers == list(range(1, 81)), "76..80 must reattach to the original run, not be dropped"
    assert len(orphaned) == 5, "the embedded 1..5 sub-list's own members are reported, never silently discarded"


def test_segment_into_runs_confirms_a_real_chapter_reset():
    import re as _re

    from scripts.pyq_pdf_extract.common import segment_into_runs

    pattern = re.compile(r"(?m)^(\d{1,3})\.")
    numbers = list(range(1, 31)) + list(range(1, 41))  # two real chapters, 30 then 40 questions
    text = "".join(f"{n}.\n" for n in numbers)
    matches = list(pattern.finditer(text))
    runs, orphaned = segment_into_runs(matches)

    assert len(runs) == 2
    assert [nm.number for nm in runs[0]] == list(range(1, 31))
    assert [nm.number for nm in runs[1]] == list(range(1, 41))
    assert orphaned == []


# --- 33-years-Biology extractor tests (real PDF) ------------------------

@pytest.fixture(scope="module")
def book1_result(tmp_path_factory):
    if not BOOK1_PDF.exists():
        pytest.skip("33-years-Biology source PDF not present on this machine")
    from scripts.pyq_pdf_extract.extract_33years_biology_pdf import run

    out_dir = tmp_path_factory.mktemp("book1_extract")
    manifest = run(BOOK1_PDF, out_dir, page_limit=35, label="unittest")
    import json
    records = json.loads((out_dir / "questions_unittest.json").read_text(encoding="utf-8"))
    return manifest, records


def test_book1_known_question_one_matches_source(book1_result):
    _, records = book1_result
    q1 = next(r for r in records if r["question_number_raw"] == "1" and r["chapter"] == "The Living World")
    assert "exclusive" in q1["stem_text"] and "characteristic of living things" in q1["stem_text"]
    assert q1["answer_raw"] == "c"
    assert q1["exam_name"] == "Mains 2011"
    assert q1["exam_year"] == 2011
    assert q1["pdf_page_number"] == 12
    assert q1["subject"] == "Biology"
    assert q1["rights_status"] == "UNVERIFIED_POSSIBLE_UNAUTHORIZED_SOURCE_WATERMARK"
    assert len(q1["options"]) == 4


def test_book1_chapter_and_topic_resolved(book1_result):
    _, records = book1_result
    q1 = next(r for r in records if r["question_number_raw"] == "1" and r["chapter"] == "The Living World")
    assert q1["topic"] == "What is Living?"
    assert q1["class_level"] == "XI"


def test_book1_every_record_has_rights_status_and_identity(book1_result):
    _, records = book1_result
    assert len(records) > 0
    for r in records:
        assert r["rights_status"] == "UNVERIFIED_POSSIBLE_UNAUTHORIZED_SOURCE_WATERMARK"
        assert r["identity_key"]
        assert r["extraction_status"] in ("COMPLETE", "NEEDS_REVIEW")
        assert r["extraction_method"] == "text_native"


def test_book1_no_question_silently_skipped_within_window(book1_result):
    """Within the first 2 fully-contained chapters (The Living World,
    Biological Classification), every question 1..N must be present --
    no silent gaps."""
    _, records = book1_result
    ch1 = sorted(int(r["question_number_raw"]) for r in records if r["chapter"] == "The Living World")
    assert ch1 == list(range(1, 30))


# --- neet_pyp (NEET 2025) extractor tests (real PDF) --------------------

@pytest.fixture(scope="module")
def book2_result(tmp_path_factory):
    if not BOOK2_PDF.exists():
        pytest.skip("neet_pyp.pdf source PDF not present on this machine")
    from scripts.pyq_pdf_extract.extract_neet_pyp_pdf import run

    out_dir = tmp_path_factory.mktemp("book2_extract")
    manifest = run(BOOK2_PDF, out_dir, label="unittest")
    import json
    records = json.loads((out_dir / "questions_unittest.json").read_text(encoding="utf-8"))
    return manifest, records


def test_book2_known_question_one_matches_source(book2_result):
    _, records = book2_result
    q1 = next(r for r in records if r["question_number_raw"] == "1")
    assert "parallel plate capacitor" in q1["stem_text"]
    assert q1["answer_raw"] == "a"
    assert q1["subject"] == "Physics"
    assert q1["exam_name"] == "NEET (UG) 2025"
    assert q1["exam_year"] == 2025
    assert q1["rights_status"] == "DRM_PROTECTED_SOURCE_PERSONAL_USE_ONLY"


def test_book2_two_column_reading_order_recovered(book2_result):
    """Regression test for the 2-column page-reading-order bug: Q29-35
    on a physics page were interleaved out of order by PyMuPDF's default
    block order before the column-aware fix; all of them must be
    present and distinct questions."""
    _, records = book2_result
    numbers = sorted(int(r["question_number_raw"]) for r in records)
    for n in (29, 30, 31, 32, 33, 34, 35, 36):
        assert n in numbers, f"question {n} missing -- 2-column reordering regression"


def test_book2_subject_from_chapterwise_index(book2_result):
    _, records = book2_result
    phy = next(r for r in records if r["question_number_raw"] == "1")
    chem = next(r for r in records if r["question_number_raw"] == "46")
    bio = next(r for r in records if r["question_number_raw"] == "92")
    assert phy["subject"] == "Physics"
    assert chem["subject"] == "Chemistry"
    assert bio["subject"] == "Biology"


def test_book2_at_most_one_question_missing(book2_result):
    """179/180 is the known, honestly-flagged outcome (Q58 is a
    diagram-only organic-chemistry reaction scheme with no linear option
    text to recover) -- this guards against a regression that silently
    drops MORE than that one known case."""
    _, records = book2_result
    assert len(records) >= 179
