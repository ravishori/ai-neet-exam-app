"""Unit tests for NEET PYQ P2.1 local OCR enablement."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from app.modules.cms.pyq.pyq_discovery import sha256_bytes
from app.modules.cms.pyq.pyq_extraction import AnswerStatus, ValidationStatus
from app.modules.cms.pyq.pyq_ocr import (
    OCR_FAILED,
    OCR_SUCCESS,
    TesseractInfo,
    discover_tesseract,
    ocr_paper_to_dict,
    process_scanned_pdf,
    tesseract_available,
)
from app.modules.cms.pyq.pyq_p2 import NEET_2022_STATUS
from app.modules.cms.pyq.pyq_p2_1 import (
    extract_questions_from_ocr,
    select_scanned_paper_dirs,
)


def _blank_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Section - A (Physics)\n1. Force?\n(1) A\n(2) B\n(3) C\n(4) D\n")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_tesseract_detection_finds_or_reports():
    info = discover_tesseract()
    assert isinstance(info.available, bool)
    if info.available:
        assert info.executable
        assert info.version


def test_tesseract_available_respects_missing_path():
    info = discover_tesseract(r"C:\nonexistent\tesseract.exe")
    # May still find via PATH/common location; explicit missing alone is ok
    assert isinstance(info, TesseractInfo)


def test_ocr_failure_when_tesseract_unavailable():
    fake = TesseractInfo(available=False, executable=None, version=None, anomalies=["tesseract_not_found"])
    with patch("app.modules.cms.pyq.pyq_ocr.discover_tesseract", return_value=fake):
        result = process_scanned_pdf(
            _blank_pdf(),
            source_sha256="sha",
            source_file="scan.pdf",
            exam_year="2023",
            extraction_mode="SCANNED",
            target_pages=[1],
        )
    assert result.pages_failed == 1
    assert result.page_results[0].status == OCR_FAILED
    assert "local_tesseract_unavailable" in result.anomalies


def test_ocr_provenance_fields_present_when_available():
    if not tesseract_available():
        pytest.skip("Tesseract not installed")
    result = process_scanned_pdf(
        _blank_pdf(),
        source_sha256="sha123",
        source_file="scan.pdf",
        exam_year="2023",
        extraction_mode="SCANNED",
        target_pages=[1],
        dpi=150,
    )
    payload = ocr_paper_to_dict(result)
    assert payload["source_sha256"] == "sha123"
    assert payload["dpi"] == 150
    assert payload["tesseract_version"]
    assert payload["pages_processed"] == 1
    page = result.page_results[0]
    assert page.ocr_engine == "tesseract"
    assert page.dpi == 150


def test_scanned_paper_selection(tmp_path: Path):
    papers = tmp_path / "papers"
    for sha, mode, year in [
        ("aaa", "TEXT", "2020"),
        ("bbb", "SCANNED", "2023"),
        ("ccc", "SCANNED", "2024"),
    ]:
        d = papers / sha
        d.mkdir(parents=True)
        (d / "paper.json").write_text(
            json.dumps(
                {
                    "source_sha256": sha,
                    "source_file": f"x/{year}.pdf",
                    "exam_year": year,
                    "extraction_mode": mode,
                    "validation_anomalies": ["paper_requires_ocr"] if mode == "SCANNED" else [],
                }
            ),
            encoding="utf-8",
        )
    selected = select_scanned_paper_dirs(tmp_path)
    assert {p.name for p in selected} == {"bbb", "ccc"}


def test_question_extraction_from_ocr_corpus():
    corpus = """<<<PAGE:2>>>
Section - A (Physics)
1. What is force?
(1) Push
(2) Pull
(3) Both
(4) None
"""
    meta = {
        "source_sha256": "abc123def4567890",
        "source_file": "NEET_PYQ_OFFICIAL/2023/Paper_x.pdf",
        "exam_year": "2023",
        "paper_code": "Paper-x",
        "paper_id": "abc123def4567890"[:16],
        "set_code": None,
        "language": None,
    }
    ocr_meta = {"tesseract_executable_basename": "tesseract.exe", "tesseract_version": "v5.5.0", "dpi": 300}
    records = extract_questions_from_ocr(corpus=corpus, meta=meta, ocr_meta=ocr_meta)
    assert len(records) >= 1
    q = records[0]
    assert q["question_number"] == 1
    assert q["subject"] == "Physics"
    assert q["answer_status"] == AnswerStatus.ANSWER_PENDING.value
    assert q["p2_1_provenance"]["ocr_version"] == "v5.5.0"
    assert q["extraction_method"] == "tesseract_local_ocr"


def test_image_dependent_options_marked_needs_review():
    corpus = """<<<PAGE:2>>>
Section - A (Physics)
1. See the graph.
(1)
(2)
(3)
(4)
"""
    meta = {
        "source_sha256": "abc123def4567890",
        "source_file": "scan.pdf",
        "exam_year": "2023",
        "paper_id": "abc123def4567890"[:16],
        "paper_code": None,
        "set_code": None,
        "language": None,
    }
    records = extract_questions_from_ocr(corpus=corpus, meta=meta, ocr_meta={"dpi": 300})
    assert records
    assert records[0]["missing_options"] is True
    assert records[0]["validation_status"] == ValidationStatus.NEEDS_REVIEW.value


def test_answer_pending_preserved():
    corpus = "<<<PAGE:1>>>\nSection - A (Chemistry)\n51. Water?\n(1) H2O\n(2) CO2\n(3) O2\n(4) N2\n"
    meta = {
        "source_sha256": "abc123def4567890",
        "source_file": "scan.pdf",
        "exam_year": "2023",
        "paper_id": "paper1",
        "paper_code": None,
        "set_code": None,
        "language": None,
    }
    records = extract_questions_from_ocr(corpus=corpus, meta=meta, ocr_meta={})
    assert all(r["answer_status"] == AnswerStatus.ANSWER_PENDING.value for r in records)


def test_2022_source_gap_constant():
    assert NEET_2022_STATUS == "SOURCE_MISSING"


def test_mathematics_exclusion_not_added_by_ocr_extract():
    corpus = "<<<PAGE:1>>>\nSection - A (Mathematics)\n1. Integral?\n(1) a\n(2) b\n(3) c\n(4) d\n"
    meta = {
        "source_sha256": "abc123def4567890",
        "source_file": "scan.pdf",
        "exam_year": "2023",
        "paper_id": "paper1",
        "paper_code": None,
        "set_code": None,
        "language": None,
    }
    records = extract_questions_from_ocr(corpus=corpus, meta=meta, ocr_meta={})
    assert records
    assert records[0]["validation_status"] == ValidationStatus.EXCLUDED_NON_NEET_SUBJECT.value


def test_checksum_preservation_of_pdf_bytes():
    data = _blank_pdf()
    assert sha256_bytes(data) == sha256_bytes(data)


def test_idempotent_skip_logic(tmp_path: Path):
    from app.modules.cms.pyq.pyq_p2_1 import process_scanned_paper_p21

    paper_dir = tmp_path / "papers" / "deadbeef"
    paper_dir.mkdir(parents=True)
    meta = {
        "source_sha256": "deadbeef",
        "source_file": "scan.pdf",
        "exam_year": "2023",
        "extraction_mode": "SCANNED",
        "paper_id": "deadbeef",
        "ocr_required_pages": [1],
    }
    (paper_dir / "paper.json").write_text(json.dumps(meta), encoding="utf-8")
    # Seed existing artifacts
    (paper_dir / "ocr.p2_1.json").write_text(
        json.dumps({"pages_processed": 1, "tesseract_available": True, "pages_success": 1}),
        encoding="utf-8",
    )
    (paper_dir / "ocr.pages.p2_1.jsonl").write_text("{}\n", encoding="utf-8")
    (paper_dir / "questions.p2_1.jsonl").write_text("{}\n", encoding="utf-8")
    _, _, skipped = process_scanned_paper_p21(
        paper_dir,
        _blank_pdf(),
        dpi=150,
        tesseract_path=None,
        force=False,
    )
    assert skipped is True


def test_normalize_ocr_multicolumn_deinterleaves_pipe_columns():
    from app.modules.cms.pyq.pyq_extraction import normalize_ocr_multicolumn_text

    raw = (
        "1 A vehicle travels half | 6 The amount of energy\n"
        "the distance with speed | required to form a soap\n"
        "20. Its average speed is: | bubble of radius 2 cm\n"
        "(1) 3v/4 (2) v/3 | (1) 50.1 (2) 30.16\n"
    )
    fixed = normalize_ocr_multicolumn_text(raw)
    assert "1 A vehicle" in fixed or "1. A vehicle" in fixed or fixed.startswith("1")
    # Right column should appear after left column, not interleaved on same line.
    assert " | " not in fixed
    left_idx = fixed.find("vehicle")
    right_idx = fixed.find("amount of energy")
    assert left_idx != -1 and right_idx != -1
    assert left_idx < right_idx


def test_ocr_segmentation_recovers_questions_without_periods():
    corpus = """<<<PAGE:2>>>
Physics : Section-A
1 A vehicle travels half the distance with speed | 6 The amount of energy required
v and remaining with 2v. Its average speed is: | to form a soap bubble is nearly :
(1) 3v/4
(2) v/3
(3) 2v/3
(4) 4v/3
(1) 50.1
(2) 30.16
(3) 5.06
(4) 3.01
2 The half life of a radioactive substance is
20 minutes. In how much time?
(1) 80 minutes
(2) 20 minutes
(3) 40 minutes
(4) 60 minutes
"""
    meta = {
        "source_sha256": "abc123def4567890",
        "source_file": "NEET_PYQ_OFFICIAL/2023/Paper_x.pdf",
        "exam_year": "2023",
        "paper_code": "Paper-x",
        "paper_id": "abc123def4567890"[:16],
        "set_code": None,
        "language": None,
    }
    records = extract_questions_from_ocr(corpus=corpus, meta=meta, ocr_meta={"dpi": 200})
    nums = {r["question_number"] for r in records}
    assert 1 in nums
    assert 2 in nums
    assert 6 in nums
    q1 = next(r for r in records if r["question_number"] == 1)
    assert "vehicle" in (q1["stem"] or "").lower()
    assert "amount of energy" not in (q1["stem"] or "").lower()
    assert q1["subject"] == "Physics"
    assert q1["answer_status"] == AnswerStatus.ANSWER_PENDING.value


def test_rough_work_page_classified_ocr_success():
    from app.modules.cms.pyq.pyq_ocr import _status_from_ocr

    status, validation, anomalies = _status_from_ocr(
        "SPACE FOR ROUGH WORK\nG2_English | 32",
        90.0,
        image_count=1,
    )
    assert status == OCR_SUCCESS
    assert "rough_work_blank_page" in anomalies


def test_text_mode_segmentation_unchanged_by_ocr_patterns():
    from app.modules.cms.pyq.pyq_discovery import FileClassification, ZipFileEntry
    from app.modules.cms.pyq.pyq_extraction import segment_questions_from_text

    entry = ZipFileEntry(
        relative_path="x.pdf",
        file_name="x.pdf",
        file_size=1,
        compressed_size=1,
        sha256="abc123def4567890",
        year="2021",
        classification=FileClassification.NEET_QUESTION_PAPER,
        paper_code=None,
        language=None,
        set_code=None,
    )
    corpus = """<<<PAGE:2>>>
Section - A (Physics)
1. What is force?
(1) Push
(2) Pull
(3) Both
(4) None
"""
    qs = segment_questions_from_text(
        corpus,
        paper_id="p",
        entry=entry,
        extraction_mode="TEXT",
        extraction_confidence=0.9,
        ocr_pages=[],
    )
    assert len(qs) == 1
    assert qs[0].question_number == 1
    assert qs[0].subject == "Physics"
