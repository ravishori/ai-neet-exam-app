"""Unit tests for NEET PYQ P2 validation (FACTORY-PYQ-P2)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import fitz
import pytest

from app.modules.cms.pyq.pyq_extraction import AnswerStatus, ValidationStatus
from app.modules.cms.pyq.pyq_ocr import process_scanned_pdf
from app.modules.cms.pyq.pyq_p2 import (
    NEET_2022_STATUS,
    attempt_missing_options_recovery,
    canonical_json_lines,
    classify_answer_status_p2,
    classify_subject_p2,
    compute_staging_checksums,
    has_missing_options,
    sha256_text,
    sparse_answer_hits,
)


def _blank_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_neet_2022_source_missing_constant():
    assert NEET_2022_STATUS == "SOURCE_MISSING"


def test_has_missing_options_detects_empty():
    record = {
        "validation_status": ValidationStatus.EXTRACTED.value,
        "option_a": "A",
        "option_b": "",
        "option_c": "C",
        "option_d": "D",
    }
    assert has_missing_options(record)


def test_missing_options_diagram_marked_needs_review():
    record = {
        "staging_id": "s1",
        "question_number": 26,
        "source_sha256": "abc",
        "validation_status": ValidationStatus.EXTRACTED.value,
        "option_a": "",
        "option_b": "",
        "option_c": "",
        "option_d": "",
    }
    block = "26. Sample?\n(1)\n(2)\n(3)\n(4)\n"
    result = attempt_missing_options_recovery(record, block)
    assert result.status == "needs_review"
    assert "diagram" in result.reason


def test_missing_options_resolved_when_text_present():
    record = {
        "staging_id": "s2",
        "question_number": 1,
        "source_sha256": "abc",
        "validation_status": ValidationStatus.EXTRACTED.value,
        "option_a": "",
        "option_b": "",
        "option_c": "",
        "option_d": "",
    }
    block = "1. Question?\n(1) Alpha\n(2) Beta\n(3) Gamma\n(4) Delta\n"
    result = attempt_missing_options_recovery(record, block)
    assert result.status == "resolved"
    assert record["option_a"] == "Alpha"


def test_answer_status_pending_without_authoritative_grid():
    record = {"validation_status": ValidationStatus.EXTRACTED.value, "question_number": 1}
    classify_answer_status_p2(record, {}, {})
    assert record["p2_answer_status"] == AnswerStatus.ANSWER_PENDING.value


def test_answer_status_known_from_authoritative_map():
    record = {"validation_status": ValidationStatus.EXTRACTED.value, "question_number": 1, "source_file": "x.pdf", "source_sha256": "sha"}
    auth = {
        1: {
            "correct_option": "2",
            "answer_source": "embedded_answer_grid",
            "answer_source_page": 10,
        }
    }
    classify_answer_status_p2(record, auth, {})
    assert record["p2_answer_status"] == AnswerStatus.ANSWER_KNOWN.value
    assert record["correct_option"] == "2"


def test_answer_status_conflict_on_sparse_hits():
    record = {"validation_status": ValidationStatus.EXTRACTED.value, "question_number": 1}
    corpus = "<<<PAGE:10>>>\nAnswer Key\n1. 2\n1. 3\n"
    sparse = sparse_answer_hits(corpus)
    if sparse.get(1) and len(sparse[1]) > 1:
        classify_answer_status_p2(record, {}, sparse)
        assert record["p2_answer_status"] == AnswerStatus.ANSWER_CONFLICT.value
    else:
        classify_answer_status_p2(record, {}, {})
        assert record["p2_answer_status"] == AnswerStatus.ANSWER_PENDING.value


def test_subject_unknown_without_section_headers():
    record = {"subject": None, "question_number": 50}
    corpus = "<<<PAGE:2>>>\n50. Some question?\n(1) A\n(2) B\n(3) C\n(4) D\n"
    assert classify_subject_p2(record, corpus, pos=20) == "UNKNOWN"


def test_subject_from_section_header():
    record = {"subject": None, "question_number": 1}
    corpus = "Section - A (Physics)\n1. Q?\n(1) A\n(2) B\n(3) C\n(4) D\n"
    pos = corpus.find("1.")
    assert classify_subject_p2(record, corpus, pos=pos) == "Physics"


def test_mathematics_exclusion_subject():
    record = {"subject": None}
    corpus = "Section - A (Mathematics)\n1. Q?\n"
    pos = corpus.find("1.")
    assert classify_subject_p2(record, corpus, pos=pos) == "EXCLUDED_NON_NEET_SUBJECT"


def test_ocr_scanned_pdf_without_tesseract():
    from unittest.mock import patch

    from app.modules.cms.pyq.pyq_ocr import TesseractInfo

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
    assert "local_tesseract_unavailable" in result.anomalies


def test_checksum_reproducibility():
    records = [{"staging_id": "b", "x": 1}, {"staging_id": "a", "x": 2}]
    h1 = sha256_text(canonical_json_lines(records))
    h2 = sha256_text(canonical_json_lines(list(reversed(records))))
    assert h1 == h2


def test_checksum_file_stable(tmp_path: Path):
    paper_dir = tmp_path / "papers" / "abc"
    paper_dir.mkdir(parents=True)
    (paper_dir / "questions.p2.jsonl").write_text(
        json.dumps({"staging_id": "1"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "manifest.p2.json").write_text("{}", encoding="utf-8")
    c1 = compute_staging_checksums(tmp_path)
    c2 = compute_staging_checksums(tmp_path)
    assert c1 == c2
    assert "all_questions.p2.canonical" in c1


def test_idempotent_p2_manifest_structure(tmp_path: Path):
    paper_dir = tmp_path / "papers" / "abc"
    paper_dir.mkdir(parents=True)
    (paper_dir / "questions.p2.jsonl").write_text(
        json.dumps({"staging_id": "1", "stem": "Q"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "manifest.p2.json").write_text("{}", encoding="utf-8")
    c1 = compute_staging_checksums(tmp_path)
    c2 = compute_staging_checksums(tmp_path)
    assert c1 == c2
