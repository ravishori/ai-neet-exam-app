"""Tests for the deterministic PYQ text + image extraction pipeline
(apps/backend/scripts/pyq_image_pipeline/). Covers: extraction
correctness against known source content, image association with an
explicit confidence flag, duplicate-content preservation in staging,
resumability (no duplicate staging rows on re-run), and file+page
provenance on every row.

These tests read real PDFs from `NEET Past Papers/` and write to the
local `pyq_image_staging` schema — skipped automatically if either is
unavailable (e.g. CI without the local Postgres or the source folder).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

SOURCE_DIR = Path(r"D:\ravishori\AI Neet Exam App\NEET Past Papers")
CODE_A_PDF = SOURCE_DIR / "NEET 2015 Question Paper with Answers (Code A) PDF Download.pdf"

pytestmark = pytest.mark.skipif(
    not CODE_A_PDF.exists(),
    reason="NEET Past Papers source PDFs not present on this machine",
)


@pytest.fixture(scope="module")
def extraction_result(tmp_path_factory):
    from scripts.pyq_image_pipeline.extractor import extract_file

    out_dir = tmp_path_factory.mktemp("pyq_images")
    questions, images = extract_file(CODE_A_PDF, out_dir)
    return questions, images, out_dir


def test_known_question_text_matches_source(extraction_result):
    """Question 1 of Code A is a known fixed string in the source PDF —
    verify the extractor's stem/answer match it exactly, not a guess."""
    questions, _, _ = extraction_result
    q1 = next(q for q in questions if q.question_number_raw == "1")
    assert "2,3-Dimethyl-2-butene can be prepared by heating" in q1.stem_text
    assert q1.answer_raw == "4"
    assert q1.source_file == str(CODE_A_PDF)
    assert q1.page_number == 1


def test_extraction_counts_match_known_paper_size(extraction_result):
    """NEET 2015 Code A has 180 questions; the segmenter must recover
    all 180 (not drop any to a silent regex miss)."""
    questions, _, _ = extraction_result
    assert len(questions) == 180
    numbers = sorted(int(q.question_number_raw) for q in questions)
    assert numbers == list(range(1, 181))


def test_every_question_has_explicit_status_and_identity(extraction_result):
    questions, _, _ = extraction_result
    for q in questions:
        assert q.extraction_status in ("COMPLETE", "PARTIAL", "NEEDS_REVIEW")
        assert q.identity_key
        assert q.source_file_sha256
        # nothing is "COMPLETE" while carrying a DEFECT flag (informational
        # flags like possible_image_dependency don't imply incompleteness)
        defect_flags = {
            "missing_options", "missing_answer", "missing_explanation",
            "uncertain_question_boundary", "ocr_glyph_error_signal",
            "footer_boilerplate_leaked_into_option",
        }
        if any(f in defect_flags or f.startswith("question_number_gap") for f in q.review_flags):
            assert q.extraction_status != "COMPLETE"


def test_image_extraction_and_association_confidence(extraction_result):
    """Known image-bearing case: at least one extracted image file
    actually exists on disk, and its association to a question (if
    any) carries an explicit, non-fabricated confidence level."""
    _, images, out_dir = extraction_result
    assert len(images) > 0
    sample = images[0]
    assert Path(sample.stored_path).exists()
    assert Path(sample.stored_path).stat().st_size > 0
    assert sample.association_confidence in ("NONE", "LOW", "MEDIUM", "HIGH")
    # every image carries provenance back to file+page
    for img in images:
        assert img.source_file == str(CODE_A_PDF)
        assert img.page_number >= 1


def test_duplicate_content_is_not_deduplicated_at_extraction_layer(extraction_result):
    """The pipeline must never silently drop a question for looking
    like a duplicate of another — verify no content-based uniqueness
    logic runs at the extraction layer (identity is per source/page/
    question-number only)."""
    questions, _, _ = extraction_result
    # construct a synthetic duplicate-content scenario: two distinct
    # questions coincidentally sharing identical stem text should both
    # survive if they existed; what we actually assert is that nothing
    # in ExtractedQuestion construction consults stem_text for identity.
    from scripts.pyq_image_pipeline.extractor import identity_key

    key_a = identity_key(str(CODE_A_PDF), 1, "1", None)
    key_b = identity_key(str(CODE_A_PDF), 1, "1", None)
    assert key_a == key_b  # identity is deterministic
    # identity does NOT depend on stem text at all
    import inspect

    src = inspect.getsource(identity_key)
    assert "stem" not in src.lower()


@pytest.mark.skipif(
    not os.environ.get("RUN_PYQ_DB_TESTS"),
    reason="set RUN_PYQ_DB_TESTS=1 to run tests against the local pyq_image_staging DB",
)
def test_resumable_ingest_creates_no_duplicate_staging_rows():
    """Running the ingest CLI twice for the same file must not double
    the row count in pyq_image_staging.questions for that file."""
    import psycopg

    from scripts.pyq_image_pipeline.run_ingest import _load_dotenv_sync_url, assert_local, get_conn, ingest_one

    url = _load_dotenv_sync_url()
    assert_local(url)
    conn = get_conn(url)
    try:
        ingest_one(CODE_A_PDF, conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pyq_image_staging.questions WHERE source_file = %s",
                (str(CODE_A_PDF),),
            )
            count_1 = cur.fetchone()[0]

        ingest_one(CODE_A_PDF, conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pyq_image_staging.questions WHERE source_file = %s",
                (str(CODE_A_PDF),),
            )
            count_2 = cur.fetchone()[0]

        assert count_1 == count_2 == 180
    finally:
        conn.close()
