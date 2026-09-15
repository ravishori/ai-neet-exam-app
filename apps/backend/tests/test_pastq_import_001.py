"""PASTQ-IMPORT-001 tests — fixtures only; no bulk DB import required."""

from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from app.modules.cms.acquisition.pastq.dedupe import classify_duplicates
from app.modules.cms.acquisition.pastq.enrich import (
    enrich_inline_answers,
    map_option_to_letter,
    parse_letter_options,
    repair_letter_options,
)
from app.modules.cms.acquisition.pastq.importer import build_question_body
from app.modules.cms.acquisition.pastq.inventory import inventory_source_root
from app.modules.cms.acquisition.pastq.paper_meta import filename_year, resolve_paper_meta
from app.modules.cms.acquisition.pastq.validate import validate_extracted_question
from app.modules.cms.pyq.pyq_discovery import FileClassification, ZipFileEntry, sha256_bytes, sha256_file
from app.modules.cms.pyq.pyq_extraction import ExtractedQuestion, extract_paper

REPO = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPO / "PastQuestionPapers"


def _make_pdf(tmp_path: Path, pages: list[str]) -> Path:
    path = tmp_path / "fixture.pdf"
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


def test_inventory_sha256_and_pages(tmp_path):
    pdf = _make_pdf(tmp_path, ["NEET (UG) - 2024\n1. Hello\n(1) a\n(2) b\n(3) c\n(4) d\n"])
    root = tmp_path / "PastQuestionPapers"
    root.mkdir()
    target = root / "NEET2024.pdf"
    target.write_bytes(pdf.read_bytes())
    inv = inventory_source_root(root)
    assert inv.total_files == 1
    f = inv.files[0]
    assert f.sha256 == sha256_file(target)
    assert f.page_count == 1
    assert f.readable is True


def test_filename_year_deterministic():
    assert filename_year("NEET2015.pdf") == 2015
    assert filename_year("Neet2022.pdf") == 2022
    assert filename_year("NEET2026-11.pdf") == 2026
    assert filename_year("NeetSyllabus.pdf") is None


def test_year_conflict_filename_vs_text():
    meta = resolve_paper_meta(
        filename="NEET2026.pdf",
        corpus_sample="NEET (UG) - 2025 Code 45 ENGLISH",
    )
    assert meta.year is None
    assert meta.needs_review is True
    assert any("year_conflict" in w for w in meta.warnings)


def test_set_detection_from_text():
    meta = resolve_paper_meta(
        filename="NEET2024.pdf",
        corpus_sample="Test Booklet Code T3\nNEET (UG) - 2024",
    )
    assert meta.year == 2024
    assert meta.set_code == "T3"


def test_letter_option_parsing():
    block = (
        "51. Radial symmetry is NOT found in adults of phylum\n"
        "a. Echinodermata\n"
        "b. Ctenophora\n"
        "c. Hemichordata\n"
        "d. Coelenterata\n"
    )
    stem, opts = parse_letter_options(block)
    assert "Radial symmetry" in stem
    assert opts["1"].startswith("Echinodermata")
    assert opts["4"].startswith("Coelenterata")


def test_inline_answer_association_and_conflict():
    q = ExtractedQuestion(
        staging_id="s1",
        paper_id="p",
        exam_year="2019",
        paper_code=None,
        set_code=None,
        language="en",
        question_number=1,
        subject="Chemistry",
        subsection=None,
        stem="Q",
        option_a="a",
        option_b="b",
        option_c="c",
        option_d="d",
        correct_option=None,
        answer_status="ANSWER_PENDING",
        answer_source=None,
        answer_source_page=None,
        source_file="NEET2019.pdf",
        source_sha256="abc",
        source_page=1,
        question_hash="h",
        normalized_question_hash="n",
        extraction_mode="TEXT",
        extraction_confidence=0.9,
        validation_status="EXTRACTED",
        raw_extracted_text="1. stem\n(1) a\n(2) b\n(3) c\n(4) d\nAns. (1)",
    )
    conflicts = enrich_inline_answers([q])
    assert conflicts == []
    assert map_option_to_letter(q.correct_option) == "A"
    assert q.answer_status == "ANSWER_KNOWN"

    q2 = ExtractedQuestion(**{**q.__dict__, "staging_id": "s2", "raw_extracted_text": "Ans. (1) Ans. (2)"})
    conflicts2 = enrich_inline_answers([q2])
    assert conflicts2
    assert q2.answer_status == "ANSWER_CONFLICT"


def test_validation_four_options_and_answer():
    q = ExtractedQuestion(
        staging_id="s",
        paper_id="p",
        exam_year="2018",
        paper_code="AA",
        set_code="AA",
        language="en",
        question_number=2,
        subject="Physics",
        subsection=None,
        stem="A body initially at rest",
        option_a="1",
        option_b="2",
        option_c="3",
        option_d="4",
        correct_option="1",
        answer_status="ANSWER_KNOWN",
        answer_source="inline_ans_marker",
        answer_source_page=1,
        source_file="NEET2018.pdf",
        source_sha256="x" * 64,
        source_page=2,
        question_hash="h",
        normalized_question_hash="n",
        extraction_mode="TEXT",
        extraction_confidence=0.9,
        validation_status="EXTRACTED",
        raw_extracted_text="stem",
    )
    v = validate_extracted_question(q, inventory_sha256="x" * 64, paper_year=2018)
    assert v.ok
    assert v.ready_for_import


def test_validation_rejects_empty_option_and_sha_mismatch():
    q = ExtractedQuestion(
        staging_id="s",
        paper_id="p",
        exam_year="2018",
        paper_code=None,
        set_code=None,
        language=None,
        question_number=1,
        subject=None,
        subsection=None,
        stem="stem",
        option_a="a",
        option_b="",
        option_c="c",
        option_d="d",
        correct_option=None,
        answer_status="ANSWER_PENDING",
        answer_source=None,
        answer_source_page=None,
        source_file="f.pdf",
        source_sha256="aaa",
        source_page=1,
        question_hash="",
        normalized_question_hash="",
        extraction_mode="TEXT",
        extraction_confidence=0.5,
        validation_status="EXTRACTED",
        raw_extracted_text="answer key should not be here",
    )
    v = validate_extracted_question(q, inventory_sha256="bbb", paper_year=None)
    assert v.ok is False
    assert "EMPTY_OPTION" in v.errors
    assert "SHA256_MISMATCH" in v.errors


def test_duplicate_classification():
    recs = [
        {
            "hashes": {"normalized_question_hash": "same"},
            "paper": {"paper_id": "p1"},
            "quality": {},
        },
        {
            "hashes": {"normalized_question_hash": "same"},
            "paper": {"paper_id": "p1"},
            "quality": {},
        },
        {
            "hashes": {"normalized_question_hash": "other"},
            "paper": {"paper_id": "p2"},
            "quality": {},
        },
    ]
    counts = classify_duplicates(recs)
    assert counts["DUPLICATE_WITHIN_IMPORT"] == 1
    assert counts["UNIQUE"] >= 1


def test_provenance_body_not_ncert_derived():
    rec = {
        "question": {
            "stem": "Test stem long enough",
            "number": 1,
            "subject": "Physics",
            "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "chapter": None,
            "topic": None,
            "concept": None,
        },
        "answer": {"value": "B", "source": "inline_ans_marker"},
        "paper": {"year": 2019, "paper_id": "p"},
        "source": {"file": "NEET2019.pdf", "page_start": 1, "sha256": "abc"},
        "quality": {"extraction_confidence": 0.9},
        "hashes": {"staging_id": "s", "normalized_question_hash": "n"},
    }
    body = build_question_body(rec)
    assert body["provenance"]["origin"] == "past_question_paper"
    assert "ncert_evidence" not in body
    assert body["correct_option"] == "B"
    assert body["pyq_year"] == 2019


def test_visual_marker_and_missing_metadata_review():
    q = ExtractedQuestion(
        staging_id="s",
        paper_id="p",
        exam_year=None,
        paper_code=None,
        set_code=None,
        language=None,
        question_number=3,
        subject=None,
        subsection=None,
        stem="As shown in the figure, a body slides",
        option_a="a",
        option_b="b",
        option_c="c",
        option_d="d",
        correct_option="2",
        answer_status="ANSWER_KNOWN",
        answer_source="inline_ans_marker",
        answer_source_page=1,
        source_file="f.pdf",
        source_sha256="z" * 64,
        source_page=3,
        question_hash="h",
        normalized_question_hash="n",
        extraction_mode="TEXT",
        extraction_confidence=0.8,
        validation_status="EXTRACTED",
        raw_extracted_text="as shown in the figure",
        anomalies=["VISUAL_REVIEW_REQUIRED"],
    )
    v = validate_extracted_question(q, inventory_sha256="z" * 64, paper_year=None, paper_needs_review=True)
    assert "VISUAL_REVIEW_REQUIRED" in v.warnings
    assert "ACADEMIC_MAPPING_REVIEW_REQUIRED" in v.warnings
    assert "YEAR_NULL" in v.warnings
    assert v.needs_review is True


@pytest.mark.skipif(not SOURCE_ROOT.exists(), reason="PastQuestionPapers missing")
def test_live_extract_neet2019_sample():
    path = SOURCE_ROOT / "NEET2019.pdf"
    data = path.read_bytes()
    entry = ZipFileEntry(
        relative_path="NEET2019.pdf",
        file_name="NEET2019.pdf",
        file_size=len(data),
        compressed_size=len(data),
        sha256=sha256_bytes(data),
        year="2019",
        classification=FileClassification.NEET_QUESTION_PAPER,
    )
    result = extract_paper(entry, data)
    assert result.page_count > 0
    repair_letter_options(result.questions)
    enrich_inline_answers(result.questions)
    known = [q for q in result.questions if q.answer_status == "ANSWER_KNOWN" and q.option_a]
    assert len(known) >= 1


def test_map_option_letters():
    assert map_option_to_letter("1") == "A"
    assert map_option_to_letter("d") == "D"
    assert map_option_to_letter("Z") is None
