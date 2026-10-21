"""Local NCERT/StudyMaterial PDF extraction + page-indexed text.

Reuses the PyMuPDF (fitz) access pattern already established in
``scripts/pyq_image_pipeline/extractor.py`` — specifically its
``sha256_file`` identity helper and its per-page ``fitz`` text-extraction
walk — rather than writing a second PDF-reading implementation.

What is deliberately NOT reused from ``extractor.py``: its regex
*segmenters* (``segment_2015``, ``segment_2025``, ``segment_v2_2020``,
``segment_v2_qa``). Those parse the fixed "<n>. stem / (1)..(4) options /
Solution:" layout of NEET Past-Paper PDFs — a structure arbitrary NCERT
textbook pages do not have. This module instead exposes plain per-page
text, and lets ``evidence_selector.py`` pick a grounded excerpt from it.

No AI/LLM calls anywhere in this module. No network. No database access.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.pyq_image_pipeline.extractor import sha256_file


@dataclass(frozen=True)
class IndexedPage:
    """One page of extracted text, carrying the same doc+page identifiers
    ``extractor.py``'s ``ExtractedQuestion``/``ExtractedImage`` records use
    (a stable sha256 document id, plus a 1-indexed page number)."""

    doc_id: str
    source_pdf: str
    page_number: int
    text: str


@dataclass(frozen=True)
class IndexedDocument:
    doc_id: str
    source_pdf: str
    pages: tuple[IndexedPage, ...]

    def page(self, page_number: int) -> IndexedPage | None:
        for p in self.pages:
            if p.page_number == page_number:
                return p
        return None

    def find_snippet(
        self, snippet: str, *, page_number: int | None = None
    ) -> tuple[int, int] | None:
        """Independently re-locate ``snippet`` inside the actually-extracted
        text. Returns ``(page_number, char_offset)`` of the first match, or
        ``None`` if the snippet is not found anywhere searched.

        Matching is whitespace/punctuation-normalized (via the project's
        existing ``normalize_stem`` helper) so trivial OCR/typography
        differences (curly quotes, extra spaces) don't cause a false
        "fabricated citation" rejection, while still requiring the
        substance of the quoted text to actually be present. This is used
        by the provenance-provenance validator and must NEVER be bypassed
        in favour of trusting a model's self-reported citation.
        """
        from app.modules.cms.services.factory_candidate_validation import normalize_stem

        needle = normalize_stem(snippet)
        if not needle:
            return None
        pages = [p for p in self.pages if page_number is None or p.page_number == page_number]
        for p in pages:
            haystack = normalize_stem(p.text)
            idx = haystack.find(needle)
            if idx != -1:
                return (p.page_number, idx)
        return None


def index_pdf(pdf_path: Path | str) -> IndexedDocument:
    """Extract per-page text from a local PDF. No network, no AI.

    Raises ``FileNotFoundError`` if ``pdf_path`` does not resolve to an
    existing file — this function never silently returns an empty index
    for a missing source.
    """
    import fitz  # PyMuPDF — same dependency extractor.py already uses

    resolved = Path(pdf_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"PDF not found: {resolved}")
    doc_id = sha256_file(resolved)
    doc = fitz.open(str(resolved))
    try:
        pages = tuple(
            IndexedPage(
                doc_id=doc_id,
                source_pdf=str(resolved),
                page_number=i + 1,
                text=doc.load_page(i).get_text("text") or "",
            )
            for i in range(doc.page_count)
        )
    finally:
        doc.close()
    return IndexedDocument(doc_id=doc_id, source_pdf=str(resolved), pages=pages)


__all__ = ["IndexedPage", "IndexedDocument", "index_pdf"]
