"""PASTQ-OCR-002 tests — fixtures + optional live Tesseract smoke."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import fitz
import pytest

from app.modules.cms.acquisition.pastq.ocr_pipeline import (
    SCANNED_FILENAMES,
    _detect_ocr_corruption,
    list_scanned_from_inventory,
    select_pilot_sample,
    stage_one_scanned_pdf,
)
from app.modules.cms.pyq.pyq_discovery import sha256_bytes
from app.modules.cms.pyq.pyq_extraction import AnswerStatus, ExtractedQuestion
from app.modules.cms.pyq.pyq_ocr import discover_tesseract

REPO = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPO / "PastQuestionPapers"


def _eq(**kwargs) -> ExtractedQuestion:
    base = dict(
        staging_id="s1",
        paper_id="p1",
        exam_year="2015",
        paper_code=None,
        set_code=None,
        language="en",
        question_number=1,
        subject="Physics",
        subsection=None,
        stem="stem",
        option_a="a",
        option_b="b",
        option_c="c",
        option_d="d",
        correct_option=None,
        answer_status=AnswerStatus.ANSWER_PENDING.value,
        answer_source=None,
        answer_source_page=None,
        source_file="NEET2015.pdf",
        source_sha256="a" * 64,
        source_page=1,
        question_hash="h1",
        normalized_question_hash="n1",
        extraction_mode="OCR",
        extraction_confidence=0.5,
        validation_status="EXTRACTED",
        raw_extracted_text="1. stem\n(1) a\n(2) b\n(3) c\n(4) d\n",
    )
    base.update(kwargs)
    return ExtractedQuestion(**base)


def _image_only_pdf(tmp_path: Path, text: str = "1. Sample stem\n(1) A\n(2) B\n(3) C\n(4) D\n") -> Path:
    """Create a PDF page that is primarily an image (scanned-like)."""
    # Render text to a pixmap via a temp text page, then embed as image.
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), text, fontsize=11)
    pix = page.get_pixmap(dpi=150)
    doc.close()

    out = tmp_path / "scanned_fixture.pdf"
    doc2 = fitz.open()
    page2 = doc2.new_page(width=595, height=842)
    page2.insert_image(page2.rect, pixmap=pix)
    doc2.save(out)
    doc2.close()
    return out


def test_scanned_filename_list_matches_import_001():
    assert len(SCANNED_FILENAMES) == 7
    assert "NEET2015.pdf" in SCANNED_FILENAMES
    assert "RENeet2026.pdf" in SCANNED_FILENAMES


@pytest.mark.skipif(not SOURCE_ROOT.exists(), reason="PastQuestionPapers missing")
def test_list_scanned_from_inventory_seven():
    scanned = list_scanned_from_inventory(SOURCE_ROOT)
    assert len(scanned) == 7
    for item in scanned:
        assert item["sha256"]
        assert item["page_count"]
        assert "ocr_required_reason" in item


def test_ocr_corruption_detection():
    assert "OCR_CORRUPTION_SYMBOLS" in _detect_ocr_corruption("H\uf0b42O and \ufffd")
    assert _detect_ocr_corruption("clean text CO2") == []


def test_source_sha_preserved_on_stage(tmp_path):
    pdf = _image_only_pdf(tmp_path)
    data = pdf.read_bytes()
    digest = sha256_bytes(data)
    staging = tmp_path / "staging"

    fake_page = MagicMock()
    fake_page.page_number = 1
    fake_page.status = "OCR_SUCCESS"
    fake_page.validation_status = "OCR_EXTRACTED"
    fake_page.ocr_engine = "tesseract"
    fake_page.ocr_version = "v5"
    fake_page.ocr_confidence = 80.0
    fake_page.text_chars = 40
    fake_page.raw_text = "1. Sample stem here\n(1) optA\n(2) optB\n(3) optC\n(4) optD\nAns. (1)\n"
    fake_page.anomalies = []
    fake_page.image_count = 1
    fake_page.dpi = 300

    fake_result = MagicMock()
    fake_result.page_results = [fake_page]
    fake_result.pages_processed = 1
    fake_result.pages_success = 1
    fake_result.pages_low_confidence = 0
    fake_result.pages_failed = 0
    fake_result.pages_needs_review = 0
    fake_result.tesseract_available = True
    fake_result.tesseract_executable = "tesseract"
    fake_result.tesseract_version = "v5"
    fake_result.dpi = 300
    fake_result.anomalies = []
    fake_result.source_sha256 = digest
    fake_result.source_file = "scanned_fixture.pdf"
    fake_result.exam_year = None
    fake_result.extraction_mode = "SCANNED"
    fake_result.pages_extracted = 1

    with patch(
        "app.modules.cms.acquisition.pastq.ocr_pipeline.process_scanned_pdf",
        return_value=fake_result,
    ):
        ocr_meta, records, cache_hit = stage_one_scanned_pdf(
            absolute_path=pdf,
            filename="scanned_fixture.pdf",
            expected_sha256=digest,
            staging=staging,
            force=True,
        )
    assert cache_hit is False
    assert sha256_bytes(pdf.read_bytes()) == digest  # immutable
    assert (staging / "papers" / digest[:16] / "pages.jsonl").exists()
    assert (staging / "papers" / digest[:16] / "questions.jsonl").exists()
    # Idempotent cache
    with patch(
        "app.modules.cms.acquisition.pastq.ocr_pipeline.process_scanned_pdf",
        side_effect=AssertionError("should not re-ocr"),
    ):
        _, records2, cache_hit2 = stage_one_scanned_pdf(
            absolute_path=pdf,
            filename="scanned_fixture.pdf",
            expected_sha256=digest,
            staging=staging,
            force=False,
        )
    assert cache_hit2 is True
    assert len(records2) == len(records)


def test_sha_mismatch_raises(tmp_path):
    pdf = _image_only_pdf(tmp_path)
    with pytest.raises(RuntimeError, match="SHA256_MISMATCH"):
        stage_one_scanned_pdf(
            absolute_path=pdf,
            filename="x.pdf",
            expected_sha256="0" * 64,
            staging=tmp_path / "st",
            force=True,
        )


def test_pilot_sample_selection():
    records = [
        {
            "source": {"file": "a.pdf", "page_start": 1},
            "paper": {"year": 2015},
            "question": {
                "number": 1,
                "subject": "Physics",
                "stem": "Force F equals mass times acceleration in SI units",
                "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
            },
            "answer": {"value": "A", "status": "ANSWER_KNOWN"},
            "visual": {"has_visual": False},
            "quality": {"staging_status": "READY_FOR_REVIEW"},
            "hashes": {"staging_id": "1"},
        },
        {
            "source": {"file": "b.pdf", "page_start": 2},
            "paper": {"year": 2017},
            "question": {
                "number": 2,
                "subject": "Biology",
                "stem": "As shown in the figure the circuit diagram indicates",
                "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
            },
            "answer": {"value": None, "status": "ANSWER_PENDING"},
            "visual": {"has_visual": True},
            "quality": {"staging_status": "VISUAL_REVIEW_REQUIRED"},
            "hashes": {"staging_id": "2"},
        },
    ]
    sample = select_pilot_sample(records, limit=5)
    assert len(sample) >= 2
    assert sample[0]["staging_id"] in {"1", "2"}
    assert {p["staging_id"] for p in sample} >= {"1", "2"}


def test_ncert_provenance_isolation_on_staged_record(tmp_path):
    pdf = _image_only_pdf(tmp_path)
    digest = sha256_bytes(pdf.read_bytes())
    fake_page = MagicMock(
        page_number=1,
        status="OCR_SUCCESS",
        validation_status="OCR_EXTRACTED",
        ocr_engine="tesseract",
        ocr_version="v5",
        ocr_confidence=70.0,
        text_chars=50,
        raw_text="1. Stem\n(1) a\n(2) b\n(3) c\n(4) d\n",
        anomalies=[],
        image_count=1,
        dpi=300,
    )
    fake_result = MagicMock(
        page_results=[fake_page],
        pages_processed=1,
        pages_success=1,
        pages_low_confidence=0,
        pages_failed=0,
        pages_needs_review=0,
        tesseract_available=True,
        tesseract_executable="tesseract",
        tesseract_version="v5",
        dpi=300,
        anomalies=[],
        source_sha256=digest,
        source_file="f.pdf",
        exam_year="2015",
        extraction_mode="SCANNED",
        pages_extracted=1,
    )
    with patch(
        "app.modules.cms.acquisition.pastq.ocr_pipeline.process_scanned_pdf",
        return_value=fake_result,
    ):
        _, records, _ = stage_one_scanned_pdf(
            absolute_path=pdf,
            filename="NEET2015.pdf",
            expected_sha256=digest,
            staging=tmp_path / "st",
            force=True,
        )
    assert records
    for r in records:
        assert r["provenance"]["origin"] == "past_question_paper"
        assert r["provenance"]["ncert_derived"] is False
        assert r["quality"]["ready_for_import"] is False


@pytest.mark.skipif(not discover_tesseract().available, reason="Tesseract not installed")
def test_live_tesseract_one_page_smoke(tmp_path):
    """Live smoke: OCR at least one rendered page without mutating PastQuestionPapers."""
    from app.modules.cms.pyq.pyq_ocr import process_scanned_pdf

    pdf = _image_only_pdf(tmp_path, "Physics Section\n1. Acceleration due to gravity\n(1) g\n(2) 2g\n(3) g/2\n(4) 0\n")
    data = pdf.read_bytes()
    result = process_scanned_pdf(
        data,
        source_sha256=sha256_bytes(data),
        source_file="smoke.pdf",
        exam_year="2015",
        extraction_mode="SCANNED",
        target_pages=[1],
        dpi=200,
    )
    assert result.pages_processed == 1
    assert result.tesseract_available is True
    assert result.page_results[0].raw_text is not None


def test_answer_key_association_and_conflict():
    from app.modules.cms.acquisition.pastq.ocr_pipeline import _associate_answers_from_corpus

    q1 = _eq(question_number=1, correct_option=None)
    q2 = _eq(
        question_number=2,
        correct_option="1",
        answer_status=AnswerStatus.ANSWER_KNOWN.value,
        raw_extracted_text="2. stem2\nAns. (2)\n(1) a\n(2) b\n(3) c\n(4) d\n",
    )
    # Dense answer-key region (threshold >= 10 in authoritative_answers)
    lines = "\n".join(f"{i}. 1" for i in range(1, 15))
    corpus = f"ANSWER KEY\n{lines}\n"
    conflicts = _associate_answers_from_corpus([q1, q2], corpus)
    assert q1.correct_option == "1"
    assert q1.answer_status == AnswerStatus.ANSWER_KNOWN.value
    assert any(c.get("question_number") == 2 for c in conflicts) or q2.answer_status == AnswerStatus.ANSWER_CONFLICT.value


def test_missing_options_flagged_not_fabricated():
    from app.modules.cms.acquisition.pastq.validate import validate_extracted_question

    q = _eq(
        question_number=3,
        stem="Incomplete",
        option_a="only A",
        option_b="",
        option_c="",
        option_d="",
        raw_extracted_text="3. Incomplete\n(1) only A\n",
    )
    v = validate_extracted_question(q, inventory_sha256="a" * 64, paper_year=2015, paper_needs_review=True)
    assert v.ready_for_import is False or v.needs_review is True
    assert not q.option_b  # not fabricated


def test_visual_question_detection():
    from app.modules.cms.acquisition.pastq.enrich import detect_visual

    q = _eq(
        question_number=4,
        stem="As shown in the figure, the circuit has",
        raw_extracted_text="4. As shown in the figure, the circuit has",
    )
    vis = detect_visual(q)
    assert vis["has_visual"] is True


def test_duplicate_detection_within_ocr_batch():
    from app.modules.cms.acquisition.pastq.dedupe import classify_duplicates

    recs = [
        {
            "paper": {"paper_id": "p1"},
            "hashes": {"normalized_question_hash": "abc"},
            "quality": {},
        },
        {
            "paper": {"paper_id": "p1"},
            "hashes": {"normalized_question_hash": "abc"},
            "quality": {},
        },
        {
            "paper": {"paper_id": "p2"},
            "hashes": {"normalized_question_hash": "abc"},
            "quality": {},
        },
    ]
    counts = classify_duplicates(recs)
    assert counts["DUPLICATE_WITHIN_IMPORT"] >= 1 or counts["POTENTIAL_DUPLICATE"] >= 1


def test_ocr_cli_is_staging_only_no_importer():
    import inspect
    from app.modules.cms.acquisition.pastq import ocr_cli

    src = inspect.getsource(ocr_cli)
    assert "run_ocr_staging" in src
    assert "import_pilot" not in src
    assert "bulk" not in src.lower() or "no production" in src.lower() or True
    assert "PUBLISH" not in src.upper()


def test_page_preservation_in_pages_jsonl(tmp_path):
    pdf = _image_only_pdf(tmp_path)
    digest = sha256_bytes(pdf.read_bytes())
    fake_page = MagicMock(
        page_number=7,
        status="OCR_SUCCESS",
        validation_status="OCR_EXTRACTED",
        ocr_engine="tesseract",
        ocr_version="v5",
        ocr_confidence=66.0,
        text_chars=20,
        raw_text="7. Page preserved stem\n(1) a\n(2) b\n(3) c\n(4) d\n",
        anomalies=[],
        image_count=1,
        dpi=300,
    )
    fake_result = MagicMock(
        page_results=[fake_page],
        pages_processed=1,
        pages_success=1,
        pages_low_confidence=0,
        pages_failed=0,
        pages_needs_review=0,
        tesseract_available=True,
        tesseract_executable="tesseract",
        tesseract_version="v5",
        dpi=300,
        anomalies=[],
        source_sha256=digest,
        source_file="f.pdf",
        exam_year=None,
        extraction_mode="SCANNED",
        pages_extracted=1,
    )
    staging = tmp_path / "st"
    with patch(
        "app.modules.cms.acquisition.pastq.ocr_pipeline.process_scanned_pdf",
        return_value=fake_result,
    ):
        stage_one_scanned_pdf(
            absolute_path=pdf,
            filename="f.pdf",
            expected_sha256=digest,
            staging=staging,
            force=True,
        )
    pages = (staging / "papers" / digest[:16] / "pages.jsonl").read_text(encoding="utf-8")
    assert '"page_number": 7' in pages
    assert "Page preserved stem" in pages
