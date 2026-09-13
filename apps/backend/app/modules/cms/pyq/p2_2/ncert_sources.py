"""NCERT source discovery and page-level text extraction for P2.2 Track B.

CF-SOURCE-001: generation/discovery pools must resolve under ``NCERT_SOURCE_ROOT``.
Legacy StudyMaterial layouts are rejected for NCERT MCQ generation.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from app.modules.ingestion.services.ncert_books_inventory import scan_ncert_books
from app.modules.ingestion.services.ncert_canonical_source import (
    assert_ncert_generation_root,
    validate_ncert_generation_source,
)
from app.modules.ingestion.services.study_material_path_parser import StudyMaterialPathError

_CLASS_DIR_RE = re.compile(r"^class\s*(11|12)$", re.IGNORECASE)
_SUBJECT_DIR_RE = re.compile(r"^(physics|chemistry|biology)(?:\s*[12])?$", re.IGNORECASE)
_SUBJECT_CODES = {"physics": "PHYSICS", "chemistry": "CHEMISTRY", "biology": "BIOLOGY"}
_NCERT_CHAPTER_FILE_RE = re.compile(
    r"^[a-z]{4}\d(\d{2})\.pdf$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NcertPageSource:
    source_id: str
    relative_path: str
    subject: str
    class_level: str
    chapter: int | None
    page: int
    text: str
    text_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "relative_path": self.relative_path,
            "subject": self.subject,
            "class": self.class_level,
            "chapter": self.chapter,
            "page": self.page,
            "text_hash": self.text_hash,
            "text_preview": self.text[:240],
        }


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chapter_from_ncert_filename(file_name: str) -> int | None:
    m = _NCERT_CHAPTER_FILE_RE.match(file_name)
    if not m:
        return None
    return int(m.group(1))


def _parse_ncert_books_rel(rel: str) -> tuple[str, str, int | None] | None:
    """Parse ``Class 11/Physics/.../kebo101.pdf`` relative paths."""
    parts = tuple(p for p in Path(rel.replace("\\", "/")).parts if p not in (".", ""))
    if len(parts) < 3:
        return None
    class_m = _CLASS_DIR_RE.match(parts[0].strip())
    subject_m = _SUBJECT_DIR_RE.match(parts[1].strip())
    if not class_m or not subject_m:
        return None
    subject = _SUBJECT_CODES[subject_m.group(1).lower()]
    class_level = class_m.group(1)
    chapter = _chapter_from_ncert_filename(parts[-1])
    return subject, class_level, chapter


def discover_ncert_pdfs(study_material_dir: Path) -> list[Path]:
    """Discover chapter PDFs for NCERT generation under the canonical root only.

    CF-SOURCE-001: ``study_material_dir`` must resolve inside ``NCERT_SOURCE_ROOT``.
    Legacy StudyMaterial subject-root layouts are not accepted for generation.
    """
    root = assert_ncert_generation_root(study_material_dir)
    report = scan_ncert_books(root=root, compute_hashes=False)
    chapter_pdfs = [
        Path(e.resolved_path)
        for e in report.entries
        if e.kind == "chapter" and e.readable and e.status in {"ok", "ambiguous", "duplicate_chapter"}
    ]
    if chapter_pdfs:
        return sorted(set(chapter_pdfs), key=lambda p: p.as_posix().lower())

    pdfs: list[Path] = []
    for pdf in sorted(root.rglob("*.pdf"), key=lambda p: p.as_posix().lower()):
        try:
            validate_ncert_generation_source(pdf, root=root)
        except Exception:
            continue
        rel = pdf.relative_to(root).as_posix()
        if _parse_ncert_books_rel(rel) is None:
            continue
        if _chapter_from_ncert_filename(pdf.name) is None:
            continue
        pdfs.append(pdf)
    return pdfs


def extract_page_sources(pdf_path: Path, *, study_root: Path) -> list[NcertPageSource]:
    root = assert_ncert_generation_root(study_root)
    validated = validate_ncert_generation_source(pdf_path, root=root)
    rel = validated.relative_posix
    parsed_books = _parse_ncert_books_rel(rel)
    if parsed_books is None:
        raise StudyMaterialPathError(
            "NCERT PDF is not under expected Class/Subject structure inside NCERT_SOURCE_ROOT"
        )
    subject, class_level, chapter = parsed_books
    sources: list[NcertPageSource] = []
    doc = fitz.open(validated.resolved_path)
    try:
        for page_idx in range(doc.page_count):
            text = (doc.load_page(page_idx).get_text("text") or "").strip()
            if len(text) < 120:
                continue
            sid = _text_hash(f"{rel}:{page_idx}:{text[:500]}")[:16]
            sources.append(
                NcertPageSource(
                    source_id=sid,
                    relative_path=rel,
                    subject=subject,
                    class_level=class_level,
                    chapter=chapter,
                    page=page_idx + 1,
                    text=text[:6000],
                    text_hash=_text_hash(text),
                )
            )
    finally:
        doc.close()
    return sources


def build_ncert_source_pool(study_material_dir: Path) -> list[NcertPageSource]:
    root = assert_ncert_generation_root(study_material_dir)
    pool: list[NcertPageSource] = []
    for pdf in discover_ncert_pdfs(root):
        pool.extend(extract_page_sources(pdf, study_root=root))
    return pool


def assign_sources_for_mcq(
    pool: list[NcertPageSource],
    count: int,
    *,
    seed: int = 42,
) -> list[NcertPageSource]:
    if not pool:
        return []
    rng = random.Random(seed)
    shuffled = pool[:]
    rng.shuffle(shuffled)
    if len(shuffled) >= count:
        return shuffled[:count]
    out: list[NcertPageSource] = []
    i = 0
    while len(out) < count:
        out.append(shuffled[i % len(shuffled)])
        i += 1
    return out
