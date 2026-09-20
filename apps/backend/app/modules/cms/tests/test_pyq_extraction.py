"""Unit tests for NEET PYQ deterministic extraction (FACTORY-PYQ-P1)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import fitz
import pytest

from app.modules.cms.pyq.pyq_discovery import (
    FileClassification,
    ZipFileEntry,
    classify_entry,
    extract_year,
    normalized_question_hash,
)
from app.modules.cms.pyq.pyq_extraction import (
    AnswerStatus,
    ExtractionMode,
    ValidationStatus,
    authoritative_answers,
    detect_document_extractability,
    extract_paper,
    mark_within_paper_duplicates,
    parse_options,
    question_hash,
    segment_questions_from_text,
    validate_paper_extraction,
)
from app.modules.cms.pyq.pyq_staging import write_paper_staging


def _pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _entry(**kwargs) -> ZipFileEntry:
    defaults = {
        "relative_path": "NEET_PYQ_OFFICIAL/2021/Paper_test.pdf",
        "file_name": "Paper_test.pdf",
        "file_size": 100,
        "compressed_size": 100,
        "sha256": "abc123def4567890",
        "year": "2021",
        "classification": FileClassification.NEET_QUESTION_PAPER,
        "paper_code": "Paper-20211218095515",
        "language": None,
        "set_code": None,
        "notes": "",
    }
    defaults.update(kwargs)
    return ZipFileEntry(**defaults)


SAMPLE_PAPER = """
<<<PAGE:2>>>
Section - A (Physics)
1. What is force?
(1) Push
(2) Pull
(3) Both
(4) None
2. What is energy?
(1) Capacity to do work
(2) Mass
(3) Speed
(4) Heat
Section - A (Chemistry)
51. Water formula?
(1) H2O
(2) CO2
(3) O2
(4) N2
Section - A (Biology : Botany)
101. Chlorophyll is in?
(1) Mitochondria
(2) Chloroplast
(3) Nucleus
(4) Ribosome
Section - A (Mathematics)
201. Integrate x dx?
(1) x
(2) x^2
(3) 1
(4) 0
"""


def test_extract_year_from_path():
    assert extract_year("NEET_PYQ_OFFICIAL/2024/Paper_x.pdf") == "2024"


def test_parse_options_four_choices():
    stem, options = parse_options("5. Sample stem?\n(1) A\n(2) B\n(3) C\n(4) D\n")
    assert "Sample stem" in stem
    assert options["1"] == "A"
    assert options["4"] == "D"


def test_question_hash_and_normalized_hash():
    h = question_hash("Stem", ["A", "B", "C", "D"])
    nh = normalized_question_hash("  Stem  ", ["A", "B", "C", "D"])
    assert len(h) == 64
    assert nh == normalized_question_hash("Stem", ["A", "B", "C", "D"])


def test_segment_questions_assigns_subjects():
    entry = _entry()
    questions = segment_questions_from_text(
        SAMPLE_PAPER,
        paper_id="paper1",
        entry=entry,
        extraction_mode=ExtractionMode.TEXT.value,
        extraction_confidence=0.9,
        ocr_pages=[],
    )
    by_num = {q.question_number: q for q in questions}
    assert by_num[1].subject == "Physics"
    assert by_num[51].subject == "Chemistry"
    assert by_num[101].subject == "Botany"
    assert by_num[201].validation_status == ValidationStatus.EXCLUDED_NON_NEET_SUBJECT.value


def test_duplicate_within_paper_classification():
    entry = _entry()
    corpus = """
<<<PAGE:1>>>
Section - A (Physics)
1. Same question?
(1) A
(2) B
(3) C
(4) D
10. Same question?
(1) A
(2) B
(3) C
(4) D
"""
    questions = segment_questions_from_text(
        corpus,
        paper_id="paper1",
        entry=entry,
        extraction_mode=ExtractionMode.TEXT.value,
        extraction_confidence=0.9,
        ocr_pages=[],
    )
    mark_within_paper_duplicates(questions)
    dupes = [q for q in questions if q.duplicate_within_paper]
    assert len(dupes) == 1
    assert dupes[0].validation_status == ValidationStatus.DUPLICATE_EXTRACTION_CANDIDATE.value


def test_answer_status_pending_without_authoritative_grid():
    answers = authoritative_answers("Important Instructions\nAnswer Sheet is inside\n")
    assert answers == {}
    entry = _entry()
    questions = segment_questions_from_text(
        SAMPLE_PAPER,
        paper_id="paper1",
        entry=entry,
        extraction_mode=ExtractionMode.TEXT.value,
        extraction_confidence=0.9,
        ocr_pages=[],
    )
    assert all(q.answer_status == AnswerStatus.ANSWER_PENDING.value for q in questions)


def test_answer_status_known_from_embedded_grid():
    corpus = """
<<<PAGE:10>>>
Answer Key
1. 2
2. 4
3. 1
4. 3
5. 2
6. 1
7. 4
8. 3
9. 2
10. 1
"""
    answers = authoritative_answers(corpus)
    assert answers[1]["correct_option"] == "2"
    assert answers[10]["correct_option"] == "1"
    assert authoritative_answers("<<<PAGE:1>>>(3)\n1 : c\n") == {}


def test_scanned_pdf_classified_ocr_required():
    from app.modules.cms.pyq.pyq_extraction import PageText

    pages = [PageText(page_number=1, text="", char_count=0, is_scanned=True)]
    mode, confidence, ocr_pages = detect_document_extractability(pages)
    assert mode == ExtractionMode.SCANNED.value
    assert confidence <= 0.2
    assert ocr_pages == [1]


def test_mathematics_file_classification_excluded():
    entry = classify_entry(
        "NEET_PYQ_OFFICIAL/2021/Mathematics_Paper.pdf",
        sha256="math123",
        seen_hashes={},
    )
    assert entry.classification == FileClassification.EXCLUDED_MATHEMATICS


def test_validate_paper_flags_missing_options(tmp_path: Path):
    entry = _entry()
    text = """
<<<PAGE:2>>>
Section - A (Physics)
1. Incomplete?
(1) only one
"""
    result = extract_paper(entry, _pdf_bytes(text.replace("<<<PAGE:2>>>", "")))
    # Re-run with tagged corpus path via direct validation helper
    questions = segment_questions_from_text(
        text,
        paper_id="p1",
        entry=entry,
        extraction_mode=ExtractionMode.TEXT.value,
        extraction_confidence=0.8,
        ocr_pages=[],
    )
    from app.modules.cms.pyq.pyq_extraction import PaperExtractionResult

    paper = PaperExtractionResult(
        paper_id="p1",
        source_file=entry.relative_path,
        source_sha256=entry.sha256,
        exam_year="2021",
        paper_code=None,
        set_code=None,
        language=None,
        page_count=1,
        extraction_mode=ExtractionMode.TEXT.value,
        extraction_confidence=0.8,
        booklet_code=None,
        questions=questions,
    )
    anomalies = validate_paper_extraction(paper)
    assert any("missing_options" in a for a in anomalies)


def test_write_paper_staging_artifacts(tmp_path: Path):
    entry = _entry()
    result = extract_paper(
        entry,
        _pdf_bytes(
            "Section - A (Physics)\n1. Q?\n(1) A\n(2) B\n(3) C\n(4) D\n"
        ),
    )
    paper_dir = write_paper_staging(tmp_path, result)
    assert (paper_dir / "paper.json").exists()
    assert (paper_dir / "questions.jsonl").exists()
    assert (paper_dir / "extraction_report.json").exists()
    records = [json.loads(line) for line in (paper_dir / "questions.jsonl").read_text().splitlines()]
    assert records[0]["subject"] == "Physics"
