"""MCQ-NCERT-GROUNDING-001 — resolve canonical NCERT evidence for generation.

Fail-closed sufficiency gate: NCERT-derived blueprints must receive a
non-empty, relevant evidence pack *before* any provider call.

Path policy remains in ``ncert_canonical_source``; this module extracts text.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.modules.ingestion.services.ncert_canonical_source import (
    ValidatedNcertSource,
    assert_blueprint_ncert_source,
    blueprint_declares_ncert_source,
    extract_blueprint_ncert_path,
)
from app.modules.knowledge.services.grounding_check import _significant_words

EvidenceStatus = Literal[
    "NCERT_EVIDENCE_READY",
    "NCERT_EVIDENCE_INSUFFICIENT",
    "NCERT_EVIDENCE_NOT_REQUIRED",
]

MIN_EVIDENCE_CHARS = 400
MAX_EVIDENCE_CHARS = 12000
MAX_PAGES_SELECTED = 8
MIN_KEYWORD_HITS = 2


@dataclass(frozen=True)
class NcertEvidencePack:
    """First-class NCERT evidence input for MCQ generation + grounding."""

    status: EvidenceStatus
    pdf_path: str | None = None
    relative_posix: str | None = None
    section_heading: str | None = None
    page_numbers: list[int] = field(default_factory=list)  # 1-based PDF pages
    evidence_text: str = ""
    ku_id: str | None = None
    ku_summary: str | None = None
    ku_facts: list[str] = field(default_factory=list)
    detail: str | None = None

    @property
    def is_ready(self) -> bool:
        return self.status == "NCERT_EVIDENCE_READY"

    @property
    def requires_ncert(self) -> bool:
        return self.status != "NCERT_EVIDENCE_NOT_REQUIRED"


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\x00", " ")).strip()


def _pdf_page_texts(pdf_path: Path) -> list[tuple[int, str]]:
    import fitz

    doc = fitz.open(str(pdf_path))
    pages: list[tuple[int, str]] = []
    try:
        for i in range(doc.page_count):
            raw = doc.load_page(i).get_text("text") or ""
            pages.append((i + 1, _normalize_ws(raw)))
    finally:
        doc.close()
    return pages


def _keyword_set(*parts: str | None) -> set[str]:
    blob = " ".join(p for p in parts if p)
    words = _significant_words(blob)
    # Keep shorter domain tokens that still matter for page scoring.
    extras = {
        w.lower()
        for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", blob)
        if w.lower() not in {"the", "and", "for", "with", "from"}
    }
    return words | extras


def _score_page(text: str, keywords: set[str]) -> int:
    if not text or not keywords:
        return 0
    low = text.lower()
    return sum(1 for k in keywords if k in low)


def select_relevant_pdf_excerpt(
    pdf_path: Path,
    *,
    keywords: set[str],
    section_heading: str | None = None,
    max_pages: int = MAX_PAGES_SELECTED,
    max_chars: int = MAX_EVIDENCE_CHARS,
) -> tuple[str, list[int]]:
    """Pick relevant pages; for short chapter PDFs prefer broad coverage."""
    pages = _pdf_page_texts(pdf_path)
    if not pages:
        return "", []

    heading_key = None
    if section_heading:
        tail = section_heading.split("/")[-1].strip()
        heading_key = tail.lower() if tail else section_heading.lower()

    scored: list[tuple[int, int, str]] = []
    for page_no, text in pages:
        score = _score_page(text, keywords)
        if heading_key and heading_key[:48] in text.lower():
            score += 5
        scored.append((score, page_no, text))

    scored.sort(key=lambda t: (-t[0], t[1]))

    # Short chapter PDFs: include all pages until char budget (grounding needs breadth).
    if len(pages) <= 20:
        ordered = sorted(pages, key=lambda t: t[0])
        chunks: list[str] = []
        page_numbers: list[int] = []
        total = 0
        for page_no, text in ordered:
            block = f"[PDF page {page_no}]\n{text}"
            if total + len(block) > max_chars and chunks:
                break
            chunks.append(block)
            page_numbers.append(page_no)
            total += len(block) + 2
        return "\n\n".join(chunks).strip(), page_numbers

    chosen = [t for t in scored if t[0] > 0][:max_pages]
    if not chosen:
        chosen = [(0, p, t) for p, t in pages[: min(3, len(pages))]]

    chosen.sort(key=lambda t: t[1])
    chunks = []
    page_numbers = []
    total = 0
    for _score, page_no, text in chosen:
        block = f"[PDF page {page_no}]\n{text}"
        if total + len(block) > max_chars and chunks:
            break
        chunks.append(block)
        page_numbers.append(page_no)
        total += len(block) + 2
    return "\n\n".join(chunks).strip(), page_numbers


def assess_evidence_sufficiency(
    evidence_text: str,
    *,
    keywords: set[str],
    min_chars: int = MIN_EVIDENCE_CHARS,
    min_keyword_hits: int = MIN_KEYWORD_HITS,
) -> tuple[bool, str]:
    text = _normalize_ws(evidence_text)
    if len(text) < min_chars:
        return False, f"evidence too short ({len(text)} < {min_chars} chars)"
    hits = _score_page(text, keywords) if keywords else min_keyword_hits
    if keywords and hits < min_keyword_hits:
        return False, f"evidence keyword hits {hits} < {min_keyword_hits}"
    return True, f"ok chars={len(text)} keyword_hits={hits}"


def compose_evidence_text(
    *,
    pdf_excerpt: str,
    ku_summary: str | None = None,
    ku_facts: list[str] | None = None,
    max_chars: int = MAX_EVIDENCE_CHARS,
) -> str:
    parts: list[str] = []
    if ku_summary and ku_summary.strip():
        parts.append(f"[KU summary]\n{ku_summary.strip()}")
    facts = [f.strip() for f in (ku_facts or []) if f and str(f).strip()]
    if facts:
        bullets = "\n".join(f"- {f}" for f in facts[:24])
        parts.append(f"[KU structured facts]\n{bullets}")
    if pdf_excerpt.strip():
        parts.append(f"[NCERT PDF excerpt]\n{pdf_excerpt.strip()}")
    text = "\n\n".join(parts).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].strip()
    return text


def resolve_ncert_evidence_pack(
    constraints: dict[str, Any] | None,
    *,
    provenance_tier: str | None = None,
    concept_name: str | None = None,
    chapter_name: str | None = None,
    topic_name: str | None = None,
    ku_id: str | None = None,
    ku_summary: str | None = None,
    ku_facts: list[str] | None = None,
    validated_source: ValidatedNcertSource | None = None,
    pdf_excerpt_override: str | None = None,
) -> NcertEvidencePack:
    """Resolve evidence for a blueprint. Pure / sync — no DB, no provider calls."""
    constraints = constraints or {}
    if not blueprint_declares_ncert_source(constraints, provenance_tier):
        return NcertEvidencePack(status="NCERT_EVIDENCE_NOT_REQUIRED", detail="non-NCERT blueprint")

    source = validated_source
    if source is None:
        try:
            source = assert_blueprint_ncert_source(constraints, provenance_tier=provenance_tier)
        except Exception as exc:  # noqa: BLE001 — typed NcertSourceError or AppError
            return NcertEvidencePack(
                status="NCERT_EVIDENCE_INSUFFICIENT",
                detail=f"source validation failed: {exc}",
                ku_id=ku_id or (str(constraints.get("ku_id")) if constraints.get("ku_id") else None),
            )
    if source is None:
        return NcertEvidencePack(
            status="NCERT_EVIDENCE_INSUFFICIENT",
            detail="NCERT blueprint missing validated PDF source",
            ku_id=ku_id or (str(constraints.get("ku_id")) if constraints.get("ku_id") else None),
        )

    section = constraints.get("ncert_section_heading")
    section_s = str(section).strip() if section else None
    resolved_ku_id = ku_id or (str(constraints["ku_id"]) if constraints.get("ku_id") else None)

    keywords = _keyword_set(
        concept_name,
        chapter_name,
        topic_name,
        section_s,
        ku_summary,
        " ".join(ku_facts or []),
    )

    if pdf_excerpt_override is not None:
        pdf_excerpt = pdf_excerpt_override
        page_numbers: list[int] = []
    else:
        pdf_excerpt, page_numbers = select_relevant_pdf_excerpt(
            source.resolved_path,
            keywords=keywords,
            section_heading=section_s,
        )

    evidence_text = compose_evidence_text(
        pdf_excerpt=pdf_excerpt,
        ku_summary=ku_summary,
        ku_facts=ku_facts,
    )
    ok, detail = assess_evidence_sufficiency(evidence_text, keywords=keywords)
    status: EvidenceStatus = "NCERT_EVIDENCE_READY" if ok else "NCERT_EVIDENCE_INSUFFICIENT"
    return NcertEvidencePack(
        status=status,
        pdf_path=str(source.resolved_path),
        relative_posix=source.relative_posix,
        section_heading=section_s,
        page_numbers=page_numbers,
        evidence_text=evidence_text,
        ku_id=resolved_ku_id,
        ku_summary=(ku_summary.strip() if ku_summary else None),
        ku_facts=list(ku_facts or []),
        detail=detail,
    )


def parse_ku_id(constraints: dict[str, Any] | None) -> uuid.UUID | None:
    raw = (constraints or {}).get("ku_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def blueprint_ncert_path_for_logs(constraints: dict[str, Any] | None) -> str | None:
    return extract_blueprint_ncert_path(constraints)
