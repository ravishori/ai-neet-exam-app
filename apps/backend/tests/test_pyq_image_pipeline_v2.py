"""Tests for the NEET Past Papers_V2 extension to the deterministic PYQ
pipeline (`classify_file_v2`, `segment_v2_2020`, `segment_v2_qa`,
`extract_file_v2` in `scripts/pyq_image_pipeline/extractor.py`).

Follows the same conventions as `test_pyq_image_pipeline.py`: reads real
PDFs from `NEET Past Papers_V2/` and is skipped automatically if that
folder isn't present on this machine (e.g. CI).
"""
from __future__ import annotations

from pathlib import Path

import pytest

SOURCE_DIR = Path(r"D:\ravishori\AI Neet Exam App\NEET Past Papers_V2")
F1_2020_PDF = SOURCE_DIR / "NEET 2020 Question Paper with Solutions and Answers Keys for Code-F1.pdf"
NEET_2022_PDF = SOURCE_DIR / "NEET 2022 Question Paper Solutions with Comprehensive Answers.pdf"
NEET_2023_PDF = SOURCE_DIR / "NEET 2023 Question Paper with Solutions - Boost Your Prep!.pdf"
NEET_2024_PDF = SOURCE_DIR / "NEET UG 2024 Question Paper with Solutions_ FREE PDF Download.pdf"

pytestmark = pytest.mark.skipif(
    not F1_2020_PDF.exists(),
    reason="NEET Past Papers_V2 source PDFs not present on this machine",
)


def test_classify_file_v2_detects_all_four_files():
    from scripts.pyq_image_pipeline.extractor import classify_file_v2

    assert classify_file_v2(F1_2020_PDF.name) == (2020, "NEET (UG) 2020", "F1", "RAW_QUESTION_PAPER_V2_INLINE_SOLUTIONS")
    assert classify_file_v2(NEET_2022_PDF.name)[:2] == (2022, "NEET (UG) 2022")
    assert classify_file_v2(NEET_2022_PDF.name)[3] == "QA_DOC_V2_FULL"
    assert classify_file_v2(NEET_2023_PDF.name) == (2023, "NEET (UG) 2023", None, "QA_DOC_V2_FULL")
    assert classify_file_v2(NEET_2024_PDF.name) == (2024, "NEET (UG) 2024", None, "QA_DOC_V2_FULL")


@pytest.fixture(scope="module")
def extraction_2020(tmp_path_factory):
    from scripts.pyq_image_pipeline.extractor import extract_file_v2

    out_dir = tmp_path_factory.mktemp("pyq_v2_images_2020")
    return extract_file_v2(F1_2020_PDF, out_dir)


@pytest.fixture(scope="module")
def extraction_2022(tmp_path_factory):
    from scripts.pyq_image_pipeline.extractor import extract_file_v2

    out_dir = tmp_path_factory.mktemp("pyq_v2_images_2022")
    return extract_file_v2(NEET_2022_PDF, out_dir)


def test_2020_recovers_all_180_questions_with_no_gaps(extraction_2020):
    questions, _ = extraction_2020
    assert len(questions) == 180
    numbers = sorted(int(q.question_number_raw) for q in questions)
    assert numbers == list(range(1, 181))


def test_2020_q1_matches_known_source_text(extraction_2020):
    """Spot-check against the actual PDF text (verified by direct read
    during this session) -- this must not be a guess."""
    questions, _ = extraction_2020
    q1 = next(q for q in questions if q.question_number_raw == "1")
    assert "plastoquinone" in q1.stem_text
    assert q1.options is not None
    assert q1.options["A"].strip().startswith("PS-I to NADP")
    assert q1.options["D"].strip().startswith("Cytb6f complex to PS-I")


def test_2020_is_honestly_flagged_missing_answer_not_guessed(extraction_2020):
    """This file's text layer has no reliable per-question answer
    letter for the overwhelming majority of questions (verified by
    direct inspection this session: ~18 answer-like token hits across
    180 questions). The pipeline must flag this, never invent an
    answer letter from the worked-solution prose."""
    questions, _ = extraction_2020
    missing_answer_count = sum(1 for q in questions if "missing_answer" in q.review_flags)
    assert missing_answer_count >= 150  # overwhelming majority, not a handful
    for q in questions:
        if "missing_answer" in q.review_flags:
            assert q.answer_raw is None
            assert q.extraction_status == "NEEDS_REVIEW"


def test_2022_recovers_all_200_questions_with_no_gaps(extraction_2022):
    questions, _ = extraction_2022
    assert len(questions) == 200
    numbers = sorted(int(q.question_number_raw) for q in questions)
    assert numbers == list(range(1, 201))


def test_2022_q1_and_q2_answers_match_known_source_text(extraction_2022):
    """Q1's options are an image-only graph (correctly missing_options);
    Q1's Answer: (4) and Q2's Answer: (3) are plain text in the source
    and must be extracted exactly, not guessed."""
    questions, _ = extraction_2022
    q1 = next(q for q in questions if q.question_number_raw == "1")
    q2 = next(q for q in questions if q.question_number_raw == "2")
    assert "de Broglie wavelength" in q1.stem_text
    assert q1.answer_raw == "4"
    assert "missing_options" in q1.review_flags  # graph options, not fabricated
    assert q2.answer_raw == "3"


def test_every_v2_question_has_explicit_status_and_identity(extraction_2020, extraction_2022):
    for questions, _ in (extraction_2020, extraction_2022):
        for q in questions:
            assert q.extraction_status in ("COMPLETE", "PARTIAL", "NEEDS_REVIEW")
            assert q.identity_key
            assert q.source_file_sha256
            defect_flags = {
                "missing_options", "missing_answer", "missing_explanation",
                "uncertain_question_boundary", "ocr_glyph_error_signal",
            }
            if any(f in defect_flags or f.startswith("question_number_gap") for f in q.review_flags):
                assert q.extraction_status != "COMPLETE"


def test_v2_image_extraction_has_explicit_confidence(extraction_2022):
    _, images = extraction_2022
    assert len(images) > 0
    for img in images:
        assert img.association_confidence in ("NONE", "LOW", "MEDIUM", "HIGH")
        assert Path(img.stored_path).exists()
    assert any(img.association_confidence == "MEDIUM" for img in images)
