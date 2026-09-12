"""Tests for FACTORY-PYQ-P2.1B resegment-only mode."""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.cms.pyq.pyq_p2_1b import (
    annotate_rough_work_pages,
    build_corpus_excluding_rough_work,
    canonical_questions_hash,
    classify_quality,
    deterministic_staging_id,
    enrich_resegment_record,
)


def test_deterministic_staging_id_stable():
    a = deterministic_staging_id(
        source_sha256="abc",
        question_number=1,
        source_page=2,
        stem="What is force?",
        options=["A", "B", "C", "D"],
    )
    b = deterministic_staging_id(
        source_sha256="abc",
        question_number=1,
        source_page=2,
        stem="What is force?",
        options=["A", "B", "C", "D"],
    )
    assert a == b
    assert len(a) == 64


def test_rough_work_excluded_from_corpus():
    pages = annotate_rough_work_pages(
        [
            {"page_number": 1, "raw_text": "1. Q?\n(1) A\n(2) B\n(3) C\n(4) D", "status": "OCR_SUCCESS"},
            {
                "page_number": 32,
                "raw_text": "SPACE FOR ROUGH WORK\nG2_English | 32",
                "status": "NEEDS_REVIEW",
                "text_chars": 36,
            },
        ]
    )
    assert pages[1]["rough_work_blank_page"] is True
    assert pages[1]["status"] == "OCR_SUCCESS"
    corpus = build_corpus_excluding_rough_work(pages)
    assert "SPACE FOR ROUGH WORK" not in corpus
    assert "<<<PAGE:32>>>" in corpus


def test_classify_instruction_as_incorrect_candidate():
    record = {
        "stem": "The candidates should ensure Admit Card is shown to Invigilator.",
        "raw_extracted_text": "Read carefully the following instructions : Attendance Sheet",
        "missing_options": True,
        "option_a": "",
        "option_b": "",
        "option_c": "",
        "option_d": "",
    }
    assert classify_quality(record) == "INCORRECT_CANDIDATE"


def test_classify_diagram_dependent():
    record = {
        "stem": "The magnitude and direction of the current in the following circuit is",
        "raw_extracted_text": "circuit",
        "missing_options": True,
        "option_a": "",
        "option_b": "",
        "option_c": "",
        "option_d": "",
    }
    assert classify_quality(record) == "DIAGRAM_DEPENDENT"


def test_canonical_hash_idempotent_ordering():
    r1 = {
        "staging_id": "b",
        "source_sha256": "s",
        "question_number": 2,
        "source_page": 1,
        "stem": "B",
        "option_a": "1",
        "option_b": "2",
        "option_c": "3",
        "option_d": "4",
        "validation_status": "EXTRACTED",
        "p2_1b_quality_status": "VALID",
        "missing_options": False,
    }
    r2 = dict(r1, staging_id="a", question_number=1, stem="A")
    assert canonical_questions_hash([r1, r2]) == canonical_questions_hash([r2, r1])


def test_enrich_sets_resegment_provenance():
    record = {
        "staging_id": "old",
        "source_sha256": "deadbeef",
        "source_file": "x.pdf",
        "exam_year": "2023",
        "paper_code": None,
        "set_code": None,
        "question_number": 1,
        "source_page": 2,
        "stem": "A sufficiently long stem for a normal physics question about motion?",
        "option_a": "A",
        "option_b": "B",
        "option_c": "C",
        "option_d": "D",
        "missing_options": False,
        "raw_extracted_text": "stem",
        "anomalies": [],
        "duplicate_within_paper": False,
        "answer_status": "ANSWER_PENDING",
    }
    out = enrich_resegment_record(record, ocr_meta={"dpi": 200, "tesseract_version": "v5"}, page_anomalies={2: []})
    assert out["extraction_method"] == "resegment_only_from_ocr_pages_p2_1"
    assert out["p2_1b_quality_status"] == "VALID"
    assert out["p2_1_provenance"]["source_ocr_artifact"] == "ocr.pages.p2_1.jsonl"
    assert out["staging_id"] != "old"


def test_resegment_module_exports():
    from app.modules.cms.pyq import pyq_p2_1b

    assert callable(pyq_p2_1b.run_resegment_only)
    assert callable(pyq_p2_1b.resegment_paper)
