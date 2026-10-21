"""NEET-SYLLABUS-DRIVEN-GENERATION-20261014 — on-demand NCERT evidence
lookup ACROSS the whole local NCERT corpus, generalizing
``evidence_selector.select_evidence_chunk`` (which only ever searches ONE
pre-selected, pre-indexed ``IndexedDocument``) to the real ~100-PDF
``NCERT Books/`` tree.

Reused UNMODIFIED, never reimplemented:
    - ``pdf_text_index.index_pdf`` — the actual PDF text extraction.
    - ``evidence_selector.select_evidence_chunk`` — the actual
      deterministic keyword-overlap best-page selection within one doc.
    - ``app.modules.knowledge.services.grounding_check._significant_words``
      — the same tokenizer ``evidence_selector`` itself already uses, for
      the cross-document ranking step this module adds (see
      ``_chunk_overlap_score`` below; it does NOT duplicate
      ``evidence_selector``'s internal per-page scoring, only reuses the
      same primitive to compare across documents, since
      ``select_evidence_chunk`` only returns a chunk, never the score that
      produced it).

What this module adds (no existing equivalent):
    - ``list_corpus_pdfs`` — deterministic subject/class-level -> PDF-list
      resolution against the real ``NCERT Books/Class {11,12}/<Subject>``
      directory layout, skipping preliminary ("...ps.pdf") and
      answer-key ("...an.pdf") files, which carry no chapter content.
    - A process-lifetime in-memory cache of already-extracted
      ``IndexedDocument``s, so a syllabus-driven batch that looks up many
      sub-topics against the same ~10-40 PDFs per subject only ever pays
      the PDF-extraction cost once per file, not once per sub-topic.
    - ``find_ncert_passage`` — scans candidate PDFs in deterministic order,
      keeps the single best-scoring (document, chunk) pair across ALL of
      them, and returns ``None`` (a legitimate, reportable gap) when
      nothing clears ``select_evidence_chunk``'s own minimal-overlap bar
      in any scanned PDF. NEVER falls back to forcing a weak match.

No AI/LLM call anywhere in this module. No network. No database access.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.modules.cms.mcq_factory_groq.evidence_selector import EvidenceChunk, select_evidence_chunk
from app.modules.cms.mcq_factory_groq.pdf_text_index import IndexedDocument, index_pdf
from app.modules.knowledge.services.grounding_check import _significant_words

# Real on-disk directory names under "NCERT Books/Class {11,12}/" that
# carry each subject's PDFs (confirmed by directory listing during this
# task — Class 11 Chemistry nests both parts under one "Chemistry" dir;
# Class 12 Chemistry splits into two top-level dirs instead).
_SUBJECT_DIR_NAMES: dict[str, tuple[str, ...]] = {
    "BIOLOGY": ("Biology",),
    "CHEMISTRY": ("Chemistry", "Chemistry 1", "Chemistry 2"),
    "PHYSICS": ("Physics",),
}

_DEFAULT_MAX_PDFS_TO_SCAN = 40

# Process-lifetime cache: resolved absolute PDF path -> already-extracted
# IndexedDocument. A syllabus-driven batch that looks up dozens/hundreds
# of sub-topics against the same subject's PDFs re-extracts each PDF at
# most once per process, not once per lookup.
_INDEXED_DOC_CACHE: dict[str, IndexedDocument] = {}


def _cached_index_pdf(pdf_path: Path) -> IndexedDocument | None:
    key = str(pdf_path.resolve())
    doc = _INDEXED_DOC_CACHE.get(key)
    if doc is not None:
        return doc
    try:
        doc = index_pdf(pdf_path)
    except FileNotFoundError:
        return None
    _INDEXED_DOC_CACHE[key] = doc
    return doc


def clear_ncert_corpus_cache() -> None:
    """Test/process-lifecycle helper — never required in normal use."""
    _INDEXED_DOC_CACHE.clear()


def default_corpus_root() -> Path:
    # .../app/modules/cms/mcq_factory_groq/ncert_corpus_lookup.py -> repo root
    return Path(__file__).resolve().parents[6] / "NCERT Books"


def list_corpus_pdfs(
    subject: str,
    *,
    class_level: str | None = None,
    corpus_root: Path | None = None,
) -> list[Path]:
    """Deterministic, sorted list of real chapter-content PDFs for
    ``subject`` (optionally restricted to one NCERT class level). Skips
    "...ps.pdf" (preliminary/contents) and "...an.pdf" (end-of-chapter
    answers) files, which carry no groundable chapter text."""
    subject_key = subject.upper()
    dir_names = _SUBJECT_DIR_NAMES.get(subject_key)
    if not dir_names:
        raise ValueError(f"unknown subject for NCERT corpus lookup: {subject!r}")

    root = corpus_root or default_corpus_root()
    class_dirs = [f"Class {class_level}"] if class_level else ["Class 11", "Class 12"]

    found: list[Path] = []
    for class_dir in class_dirs:
        base = root / class_dir
        if not base.is_dir():
            continue
        for dir_name in dir_names:
            subdir = base / dir_name
            if not subdir.is_dir():
                continue
            for pdf in sorted(subdir.rglob("*.pdf")):
                stem_lower = pdf.stem.lower()
                if stem_lower.endswith("ps") or stem_lower.endswith("an"):
                    continue
                found.append(pdf)
    return found


def _chunk_overlap_score(chunk: EvidenceChunk, topic_words: set[str]) -> float:
    """Cross-document ranking signal only — reuses the same
    ``_significant_words`` primitive ``evidence_selector`` already uses,
    never duplicating its internal per-page scoring logic."""
    if not topic_words:
        return 0.0
    chunk_words = _significant_words(chunk.text.lower())
    if not chunk_words:
        return 0.0
    return len(topic_words & chunk_words) / max(1, len(topic_words))


@dataclass(frozen=True)
class NcertLookupResult:
    """A real, locatable NCERT passage for one (subject, sub-topic)
    lookup, plus the full ``IndexedDocument`` it came from (the
    orchestrator's ``process_fact`` needs the whole document, not just
    the chunk, to independently re-locate the citation)."""

    chunk: EvidenceChunk
    document: IndexedDocument
    score: float


def find_ncert_passage(
    *,
    subject: str,
    unit_name: str,
    subtopic_text: str,
    class_level: str | None = None,
    corpus_root: Path | None = None,
    candidate_pdfs: list[Path] | None = None,
    max_pdfs_to_scan: int = _DEFAULT_MAX_PDFS_TO_SCAN,
) -> NcertLookupResult | None:
    """Search across real NCERT PDFs for ``subtopic_text`` (scoped to
    ``subject``/``unit_name``/``class_level``) and return the single
    best-matching real passage, or ``None`` if no PDF clears
    ``select_evidence_chunk``'s minimal-overlap bar — a legitimate,
    reportable gap, never a forced weak match.

    ``candidate_pdfs`` lets callers (tests, or a caller that already knows
    the right chapter) restrict the scan to specific files instead of the
    full subject corpus — when given, ``subject``/``class_level``/
    ``corpus_root`` are not used for file discovery.
    """
    pdfs = (
        candidate_pdfs
        if candidate_pdfs is not None
        else list_corpus_pdfs(subject, class_level=class_level, corpus_root=corpus_root)
    )
    pdfs = pdfs[:max_pdfs_to_scan]

    topic_words = _significant_words(f"{unit_name} {subtopic_text}".lower())

    best: NcertLookupResult | None = None
    for pdf_path in pdfs:
        doc = _cached_index_pdf(pdf_path)
        if doc is None:
            continue
        chunk = select_evidence_chunk(doc, topic=subtopic_text, concept=unit_name)
        if chunk is None:
            continue
        score = _chunk_overlap_score(chunk, topic_words)
        if score <= 0.0:
            continue
        if best is None or score > best.score:
            best = NcertLookupResult(chunk=chunk, document=doc, score=score)
    return best


__all__ = [
    "NcertLookupResult",
    "clear_ncert_corpus_cache",
    "default_corpus_root",
    "list_corpus_pdfs",
    "find_ncert_passage",
]
