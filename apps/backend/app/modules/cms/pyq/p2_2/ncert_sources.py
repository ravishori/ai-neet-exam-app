"""NCERT source discovery and page-level text extraction for P2.2 Track B."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from app.modules.ingestion.services.study_material_ncert_parser import extract_ncert_chapter_number
from app.modules.ingestion.services.study_material_path_parser import (
    NEET_SUBJECT_ROOTS,
    StudyMaterialPathError,
    parse_study_material_path,
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


def discover_ncert_pdfs(study_material_dir: Path) -> list[Path]:
    root = study_material_dir.resolve()
    pdfs: list[Path] = []
    for subject_dir in sorted(root.iterdir()):
        if not subject_dir.is_dir():
            continue
        if subject_dir.name.lower() not in NEET_SUBJECT_ROOTS:
            continue
        for pdf in sorted(subject_dir.rglob("*.pdf")):
            try:
                rel = pdf.relative_to(root).as_posix()
                parse_study_material_path(rel)
                pdfs.append(pdf)
            except (StudyMaterialPathError, ValueError):
                continue
    return pdfs


def extract_page_sources(pdf_path: Path, *, study_root: Path) -> list[NcertPageSource]:
    rel = pdf_path.relative_to(study_root).as_posix()
    parsed = parse_study_material_path(rel)
    chapter = extract_ncert_chapter_number(parsed.file_name)
    sources: list[NcertPageSource] = []
    doc = fitz.open(pdf_path)
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
                    subject=parsed.subject_code,
                    class_level=parsed.class_level,
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
    root = study_material_dir.resolve()
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
