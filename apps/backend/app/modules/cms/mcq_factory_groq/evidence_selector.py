"""Evidence-chunk selector.

Given a syllabus topic/concept and an ``IndexedDocument`` (see
``pdf_text_index.py``), pick ONE small, specific excerpt — never the whole
document, never the whole page's raw byte count unbounded — to ground
generation. Deterministic keyword-overlap scoring only; no AI calls.

Reuses the project's existing significant-word tokenizer
(``app.modules.knowledge.services.grounding_check._significant_words``),
the same helper ``deterministic_batch_runner.py`` and
``ncert_claim_grounding.py`` already use for overlap/grounding scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.cms.mcq_factory_groq.pdf_text_index import IndexedDocument, IndexedPage
from app.modules.knowledge.services.grounding_check import _significant_words

MAX_CHUNK_CHARS = 1200
MIN_CHUNK_CHARS = 200
MIN_QUOTED_SNIPPET_CHARS = 40


@dataclass(frozen=True)
class EvidenceChunk:
    doc_id: str
    source_pdf: str
    page_number: int
    text: str

    @property
    def quoted_snippet(self) -> str:
        """A short, specific, citeable excerpt of this chunk — never the
        whole chunk — so the provenance-relocation check has something
        concrete to re-find rather than trivially matching anything."""
        snippet = " ".join(self.text.split())
        if len(snippet) <= MIN_QUOTED_SNIPPET_CHARS:
            return snippet
        return snippet[:280]


def _score_page(page: IndexedPage, topic_words: set[str]) -> float:
    if not topic_words:
        return 0.0
    page_words = _significant_words(page.text.lower())
    if not page_words:
        return 0.0
    overlap = topic_words & page_words
    return len(overlap) / max(1, len(topic_words))


def select_evidence_chunk(
    document: IndexedDocument,
    *,
    topic: str,
    concept: str | None = None,
    max_chunk_chars: int = MAX_CHUNK_CHARS,
) -> EvidenceChunk | None:
    """Pick the single best-matching page (by topic/concept keyword
    overlap against the extracted page text) and return a bounded excerpt
    from it.

    Returns ``None`` when no page clears a minimal overlap bar — callers
    MUST treat that as "this topic cannot be grounded in this document"
    and must never fall back to using the whole document as evidence.
    """
    needle = f"{topic} {concept or ''}".strip().lower()
    topic_words = _significant_words(needle)
    if not topic_words:
        return None

    scored = sorted(
        ((_score_page(p, topic_words), p) for p in document.pages if p.text.strip()),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not scored or scored[0][0] <= 0.0:
        return None

    _best_score, best_page = scored[0]
    text = best_page.text.strip()
    if len(text) < MIN_CHUNK_CHARS:
        return None
    chunk_text = text[:max_chunk_chars] if len(text) > max_chunk_chars else text
    return EvidenceChunk(
        doc_id=document.doc_id,
        source_pdf=document.source_pdf,
        page_number=best_page.page_number,
        text=chunk_text,
    )


__all__ = ["EvidenceChunk", "select_evidence_chunk", "MAX_CHUNK_CHARS", "MIN_CHUNK_CHARS"]
