"""Read-only unit tests for NEET PYQ ZIP discovery (FACTORY-PYQ-P0)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import fitz
import pytest

from app.modules.cms.pyq.pyq_discovery import (
    FileClassification,
    classify_entry,
    extract_year,
    inventory_zip,
    normalized_question_hash,
    probe_pdf_bytes,
    sha256_bytes,
)


def _minimal_pdf(text: str = "PHYSICS\n1. Sample question?\n(1) A\n(2) B\n(3) C\n(4) D") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _build_sample_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("NEET_PYQ_OFFICIAL/2020/Paper_20201106054349.pdf", _minimal_pdf())
        zf.writestr("NEET_PYQ_OFFICIAL/2021/Paper_20211218095515.pdf", _minimal_pdf("CHEMISTRY\n(1) opt"))
        zf.writestr("NEET_PYQ_OFFICIAL/2021/Mathematics_Paper_2021.pdf", _minimal_pdf("MATHEMATICS"))
        zf.writestr("NEET_PYQ_OFFICIAL/2025/NEET_2025_EN_45_NTA.pdf.pdf", _minimal_pdf("BIOLOGY"))
    return buf.getvalue()


def test_extract_year_from_path():
    assert extract_year("NEET_PYQ_OFFICIAL/2023/Paper_x.pdf") == "2023"
    assert extract_year("no-year/file.pdf") is None


def test_classify_mathematics_exclusion():
    entry = classify_entry(
        "NEET_PYQ_OFFICIAL/2021/Mathematics_Paper_2021.pdf",
        sha256="abc",
        seen_hashes={},
    )
    assert entry.classification == FileClassification.EXCLUDED_MATHEMATICS


def test_classify_duplicate_paper_by_hash():
    seen = {"deadbeef": "first.pdf"}
    entry = classify_entry("NEET_PYQ_OFFICIAL/2020/Paper_dup.pdf", sha256="deadbeef", seen_hashes=seen)
    assert entry.classification == FileClassification.DUPLICATE_PAPER


def test_inventory_zip_counts_and_missing_2022(tmp_path: Path):
    zip_path = tmp_path / "sample.zip"
    zip_path.write_bytes(_build_sample_zip())
    report = inventory_zip(zip_path)
    assert report.pdf_count == 4
    assert report.scope_pdf_count == 4
    assert "2020" in report.by_year
    assert "2022" not in report.by_year
    assert any("MISSING_YEAR" in b for b in report.blockers)
    assert report.by_classification[FileClassification.EXCLUDED_MATHEMATICS.value] == 1


def test_probe_pdf_text_extractability():
    result = probe_pdf_bytes("sample.pdf", _minimal_pdf())
    assert result.page_count == 1
    assert result.text_chars > 50
    assert result.extractability in {"TEXT", "MIXED"}
    assert result.question_number_hits >= 0


def test_normalized_question_hash_stable():
    h1 = normalized_question_hash("What is force?", ["A", "B", "C", "D"])
    h2 = normalized_question_hash("  What   is force? ", ["A", "B", "C", "D"])
    assert h1 == h2


def test_sha256_bytes_deterministic():
    data = b"hello"
    assert sha256_bytes(data) == sha256_bytes(data)
