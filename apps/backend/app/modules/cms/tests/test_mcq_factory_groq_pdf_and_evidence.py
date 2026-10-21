"""Unit tests for pdf_text_index.py and evidence_selector.py.

Builds tiny real PDFs on disk with PyMuPDF (fitz) — the same technique
``app/modules/cms/tests/test_pyq_extraction.py`` already uses for
extractor.py tests — so these tests exercise real PDF text extraction
without any network or AI call.
"""

from __future__ import annotations

import fitz
import pytest

from app.modules.cms.mcq_factory_groq.evidence_selector import select_evidence_chunk
from app.modules.cms.mcq_factory_groq.pdf_text_index import index_pdf


def _write_pdf(path, pages: list[str]) -> None:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        # insert_text() does not wrap and silently clips long single-line
        # strings at the page edge (confirmed by direct inspection) —
        # insert_textbox() word-wraps within the given rect, so long
        # fixture strings actually extract back out in full.
        rect = fitz.Rect(36, 36, page.rect.width - 36, page.rect.height - 36)
        page.insert_textbox(rect, text, fontsize=11)
    doc.save(str(path))
    doc.close()


def test_index_pdf_extracts_pages_with_stable_doc_id(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(pdf_path, ["Newton's second law states F equals m times a.", "Second page about Ohm's law."])

    doc = index_pdf(pdf_path)
    assert len(doc.pages) == 2
    assert doc.pages[0].page_number == 1
    assert "Newton" in doc.pages[0].text
    assert doc.pages[1].page_number == 2

    # Re-indexing the same file yields the same doc_id (stable identity).
    doc2 = index_pdf(pdf_path)
    assert doc2.doc_id == doc.doc_id


def test_index_pdf_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        index_pdf(tmp_path / "does_not_exist.pdf")


def test_find_snippet_locates_normalized_substring(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(pdf_path, ["The mitochondria is the powerhouse of the cell."])
    doc = index_pdf(pdf_path)

    found = doc.find_snippet("mitochondria is the powerhouse")
    assert found is not None
    page_no, _offset = found
    assert page_no == 1


def test_find_snippet_on_wrong_page_returns_none_for_that_page(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(pdf_path, ["Page one content about Newton.", "Page two content about Ohm."])
    doc = index_pdf(pdf_path)

    # "Ohm" text only exists on page 2; searching restricted to page 1 must fail.
    assert doc.find_snippet("Ohm", page_number=1) is None
    assert doc.find_snippet("Ohm", page_number=2) is not None


def test_find_snippet_not_present_returns_none(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(pdf_path, ["Some unrelated text about photosynthesis."])
    doc = index_pdf(pdf_path)
    assert doc.find_snippet("this text does not appear anywhere") is None


def test_select_evidence_chunk_picks_best_matching_page(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(
        pdf_path,
        [
            "Introduction page with unrelated filler content about geography and maps." * 3,
            "Newtons second law of motion defines force as mass times acceleration in mechanics." * 3,
        ],
    )
    doc = index_pdf(pdf_path)

    chunk = select_evidence_chunk(doc, topic="Newton's second law of motion force mass acceleration")
    assert chunk is not None
    assert chunk.page_number == 2
    assert "Newton" in chunk.text
    assert len(chunk.quoted_snippet) <= 280


def test_select_evidence_chunk_returns_none_when_no_overlap(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(pdf_path, ["Completely unrelated filler text about cooking recipes and ingredients."])
    doc = index_pdf(pdf_path)

    chunk = select_evidence_chunk(doc, topic="quantum chromodynamics gluon confinement")
    assert chunk is None


def test_select_evidence_chunk_bounds_chunk_length(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    long_text = ("Photosynthesis occurs in chloroplasts using light energy. " * 60)
    _write_pdf(pdf_path, [long_text])
    doc = index_pdf(pdf_path)

    chunk = select_evidence_chunk(doc, topic="photosynthesis chloroplasts light energy", max_chunk_chars=100)
    assert chunk is not None
    assert len(chunk.text) <= 100
