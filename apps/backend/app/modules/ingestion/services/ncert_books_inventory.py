"""CF-SOURCE-001 — deterministic inventory for ``NCERT Books`` layout.

Expected tree (tolerant of Part I/II nesting and Chemistry 1/2 folders)::

    NCERT Books/
      Class 11/
        Physics|Chemistry|Biology/
          <zip-folder>/.../<code><part><chapter>.pdf
      Class 12/
        ...

Chapter identity prefers PDF title/text over filename patterns.
Supplemental files (prelims, answers, appendices) are inventoried but not
treated as chapter sources for generation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.modules.ingestion.services.ncert_canonical_source import (
    NCERT_SOURCE_AMBIGUOUS,
    get_ncert_source_root,
    is_allowed_ncert_source,
)

logger = logging.getLogger(__name__)

SourceKind = Literal["chapter", "prelims", "answers", "appendix", "other", "unexpected"]
SourceStatus = Literal[
    "ok",
    "unreadable",
    "outside_structure",
    "duplicate_chapter",
    "ambiguous",
    "supplemental",
]

_CLASS_DIR_RE = re.compile(r"^class\s*(11|12)$", re.IGNORECASE)
_SUBJECT_DIR_RE = re.compile(
    r"^(physics|chemistry|biology)(?:\s*[12])?$",
    re.IGNORECASE,
)
# NCERT textbook filename: kebo101.pdf, leph208.pdf, kech1a1.pdf, kebo1ps.pdf
_NCERT_FILE_RE = re.compile(
    r"^(?P<code>[a-z]{4})(?P<part>\d)(?P<rest>[a-z0-9]+)\.pdf$",
    re.IGNORECASE,
)
_CHAPTER_TITLE_RE = re.compile(
    r"chapter\s*(?P<num>\d{1,2})\s*[\n\r:.\-–—]*\s*(?P<title>[^\n\r]{3,120})",
    re.IGNORECASE,
)
_EDITION_HINT_RE = re.compile(
    r"\b(rationalis(?:e|z)d|revised\s+edition|old\s+edition|new\s+edition|"
    r"reprint|first\s+edition|second\s+edition)\b",
    re.IGNORECASE,
)

SUBJECT_CODES = {
    "physics": "PHYSICS",
    "chemistry": "CHEMISTRY",
    "biology": "BIOLOGY",
}


@dataclass(frozen=True)
class NcertInventoryEntry:
    class_level: str
    subject_code: str
    part_number: int | None
    chapter_number: int | None
    chapter_title: str | None
    file_name: str
    relative_path: str
    resolved_path: str
    file_size: int
    checksum_sha256: str | None
    readable: bool
    kind: SourceKind
    status: SourceStatus
    edition_hints: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NcertInventoryReport:
    root: str
    entries: list[NcertInventoryEntry] = field(default_factory=list)
    anomalies: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        by_matrix: dict[str, dict[str, Any]] = {}
        for cls in ("11", "12"):
            for subj in ("PHYSICS", "CHEMISTRY", "BIOLOGY"):
                key = f"Class {cls}/{subj.title()}"
                bucket = [e for e in self.entries if e.class_level == cls and e.subject_code == subj]
                chapters = [e for e in bucket if e.kind == "chapter"]
                by_matrix[key] = {
                    "total_pdfs": len(bucket),
                    "chapters": len(chapters),
                    "readable_chapters": sum(1 for e in chapters if e.readable),
                    "duplicates": sum(1 for e in chapters if e.status == "duplicate_chapter"),
                    "ambiguous": sum(1 for e in chapters if e.status == "ambiguous"),
                    "supplemental": sum(1 for e in bucket if e.kind != "chapter"),
                    "entries": [e.to_dict() for e in sorted(bucket, key=_entry_sort_key)],
                }
        return {
            "root": self.root,
            "total_pdfs": len(self.entries),
            "readable": sum(1 for e in self.entries if e.readable),
            "duplicates": sum(1 for e in self.entries if e.status == "duplicate_chapter"),
            "ambiguous": sum(1 for e in self.entries if e.status == "ambiguous"),
            "unreadable": sum(1 for e in self.entries if e.status == "unreadable"),
            "unexpected": sum(1 for e in self.entries if e.status == "outside_structure"),
            "anomalies": self.anomalies,
            "matrix": by_matrix,
        }


def _entry_sort_key(entry: NcertInventoryEntry) -> tuple:
    return (
        entry.class_level,
        entry.subject_code,
        entry.part_number if entry.part_number is not None else 0,
        entry.chapter_number if entry.chapter_number is not None else 999,
        entry.file_name.lower(),
    )


def _sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _classify_filename(file_name: str) -> tuple[SourceKind, int | None, int | None]:
    """Return kind, part_number, chapter_number_within_part."""
    m = _NCERT_FILE_RE.match(file_name)
    if not m:
        return "other", None, None
    part = int(m.group("part"))
    rest = m.group("rest").lower()
    if rest == "ps":
        return "prelims", part, None
    if rest == "an":
        return "answers", part, None
    if rest.startswith("a") and rest[1:].isdigit():
        return "appendix", part, None
    if rest.isdigit() and len(rest) == 2:
        return "chapter", part, int(rest)
    return "other", part, None


def _parse_class_subject(rel_parts: tuple[str, ...]) -> tuple[str | None, str | None, list[str]]:
    notes: list[str] = []
    if len(rel_parts) < 3:
        return None, None, ["path too short for Class/Subject/file"]
    class_m = _CLASS_DIR_RE.match(rel_parts[0].strip())
    if not class_m:
        return None, None, [f"unexpected class folder: {rel_parts[0]}"]
    class_level = class_m.group(1)
    subject_m = _SUBJECT_DIR_RE.match(rel_parts[1].strip())
    if not subject_m:
        return class_level, None, [f"unexpected subject folder: {rel_parts[1]}"]
    subject_token = subject_m.group(1).lower()
    subject_code = SUBJECT_CODES[subject_token]
    if re.search(r"[12]\s*$", rel_parts[1].strip()):
        notes.append(f"subject part folder retained: {rel_parts[1]}")
    return class_level, subject_code, notes


def _extract_pdf_identity(path: Path) -> tuple[bool, int | None, str | None, tuple[str, ...]]:
    """Return readable, chapter_number, title, edition_hints from PDF content."""
    try:
        import fitz
    except ImportError:
        return False, None, None, ()

    try:
        doc = fitz.open(path)
    except Exception:
        return False, None, None, ()

    try:
        if doc.page_count < 1:
            return False, None, None, ()
        # Sample early pages for chapter banner (covers/TOC often precede body).
        sample_pages = min(8, doc.page_count)
        text_parts: list[str] = []
        meta_title = (doc.metadata or {}).get("title") or ""
        for i in range(sample_pages):
            text_parts.append(doc.load_page(i).get_text("text") or "")
        blob = "\n".join(text_parts)
        edition = tuple(sorted({m.group(0) for m in _EDITION_HINT_RE.finditer(blob + " " + meta_title)}))
        # Prefer explicit "Chapter N Title" near start of a line.
        chapter_num: int | None = None
        chapter_title: str | None = None
        for m in _CHAPTER_TITLE_RE.finditer(blob):
            num = int(m.group("num"))
            title = re.sub(r"\s+", " ", m.group("title")).strip(" .-–—:\t")
            # Skip TOC-like very long concatenated titles and filesystem metadata.
            if len(title) > 80:
                continue
            if re.search(r"[\\/]:|Textbook\\|Source Files|\\\\|Reprint\s+\d{4}", title, re.I):
                continue
            if title.lower().startswith(("e:\\", "c:\\", "d:\\")):
                continue
            chapter_num = num
            chapter_title = title or None
            break
        if chapter_title is None and meta_title.strip():
            mt = meta_title.strip()[:120]
            if not re.search(r"[\\/]|Textbook", mt, re.I):
                chapter_title = mt
        return True, chapter_num, chapter_title, edition
    finally:
        doc.close()


def scan_ncert_books(*, root: Path | None = None, compute_hashes: bool = True) -> NcertInventoryReport:
    """Deterministically scan the canonical NCERT Books tree."""
    source_root = (root or get_ncert_source_root()).resolve()
    report = NcertInventoryReport(root=str(source_root))

    if not source_root.is_dir():
        report.anomalies.append(
            {
                "code": "NCERT_SOURCE_MISSING",
                "message": f"NCERT source root is not a directory: {source_root}",
            }
        )
        return report

    pdfs = sorted(source_root.rglob("*.pdf"), key=lambda p: p.as_posix().lower())
    # Track chapter collisions: (class, subject, chapter_number) -> entries
    chapter_index: dict[tuple[str, str, int], list[NcertInventoryEntry]] = {}

    for pdf in pdfs:
        if not is_allowed_ncert_source(pdf, root=source_root):
            report.anomalies.append(
                {
                    "code": NCERT_SOURCE_AMBIGUOUS,
                    "message": "PDF resolved outside root during scan (ignored)",
                    "path": str(pdf),
                }
            )
            continue

        rel = pdf.relative_to(source_root)
        rel_posix = rel.as_posix()
        parts = rel.parts
        class_level, subject_code, structure_notes = _parse_class_subject(parts)
        kind, part_number, file_chapter = _classify_filename(pdf.name)
        readable, pdf_chapter, pdf_title, edition_hints = _extract_pdf_identity(pdf)

        notes = list(structure_notes)
        status: SourceStatus = "ok"
        # Filename chapter is authoritative for NCERT code PDFs (part-relative).
        # PDF text is used for title; TOC mismatches are notes, not identity flips.
        chapter_number = file_chapter
        chapter_title = pdf_title

        if class_level is None or subject_code is None:
            status = "outside_structure"
            kind = "unexpected"
            notes.append("PDF outside expected Class/Subject structure")
            class_level = class_level or "?"
            subject_code = subject_code or "UNKNOWN"
        elif not readable:
            status = "unreadable"
            notes.append("PDF could not be opened or has no pages")
        elif kind == "chapter":
            if pdf_chapter is not None and file_chapter is not None and pdf_chapter != file_chapter:
                notes.append(
                    f"PDF text chapter {pdf_chapter} differs from filename chapter "
                    f"{file_chapter} (filename kept; likely TOC noise)"
                )
            if chapter_number is None and pdf_chapter is not None:
                chapter_number = pdf_chapter
                status = "ambiguous"
                notes.append("chapter number taken from PDF text only")
            if edition_hints:
                notes.append("edition hints present — do not auto-select curriculum baseline")
        else:
            status = "supplemental"

        checksum = _sha256_file(pdf) if compute_hashes else None
        try:
            size = pdf.stat().st_size
        except OSError:
            size = 0
            status = "unreadable"
            readable = False

        entry = NcertInventoryEntry(
            class_level=class_level,
            subject_code=subject_code,
            part_number=part_number,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            file_name=pdf.name,
            relative_path=rel_posix,
            resolved_path=str(pdf.resolve()),
            file_size=size,
            checksum_sha256=checksum,
            readable=readable,
            kind=kind,
            status=status,
            edition_hints=edition_hints,
            notes=tuple(notes),
        )
        report.entries.append(entry)

        if (
            kind == "chapter"
            and chapter_number is not None
            and part_number is not None
            and subject_code != "UNKNOWN"
        ):
            chapter_index.setdefault(
                (class_level, subject_code, part_number, chapter_number),
                [],
            ).append(entry)

    # Mark duplicates without mutating frozen entries — rebuild with status.
    dup_keys = {k for k, v in chapter_index.items() if len(v) > 1}
    if dup_keys:
        revised: list[NcertInventoryEntry] = []
        for entry in report.entries:
            if (
                entry.kind == "chapter"
                and entry.chapter_number is not None
                and entry.part_number is not None
                and (entry.class_level, entry.subject_code, entry.part_number, entry.chapter_number)
                in dup_keys
            ):
                revised.append(
                    NcertInventoryEntry(
                        class_level=entry.class_level,
                        subject_code=entry.subject_code,
                        part_number=entry.part_number,
                        chapter_number=entry.chapter_number,
                        chapter_title=entry.chapter_title,
                        file_name=entry.file_name,
                        relative_path=entry.relative_path,
                        resolved_path=entry.resolved_path,
                        file_size=entry.file_size,
                        checksum_sha256=entry.checksum_sha256,
                        readable=entry.readable,
                        kind=entry.kind,
                        status="duplicate_chapter",
                        edition_hints=entry.edition_hints,
                        notes=tuple(
                            list(entry.notes)
                            + ["duplicate chapter number under same class/subject/part"]
                        ),
                    )
                )
                report.anomalies.append(
                    {
                        "code": NCERT_SOURCE_AMBIGUOUS,
                        "message": "duplicate chapter mapping",
                        "class_level": entry.class_level,
                        "subject_code": entry.subject_code,
                        "part_number": entry.part_number,
                        "chapter_number": entry.chapter_number,
                        "relative_path": entry.relative_path,
                    }
                )
            else:
                revised.append(entry)
        report.entries = revised

    # Non-PDF noise under root (zips, shortcuts) — report only.
    for path in sorted(source_root.rglob("*"), key=lambda p: p.as_posix().lower()):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".pdf":
            continue
        if path.suffix.lower() in {".zip", ".lnk", ".txt", ".md"}:
            if is_allowed_ncert_source(path, root=source_root):
                report.anomalies.append(
                    {
                        "code": "UNEXPECTED_NON_PDF",
                        "message": f"non-PDF artifact under NCERT root: {path.suffix}",
                        "relative_path": path.relative_to(source_root).as_posix(),
                    }
                )

    report.entries.sort(key=_entry_sort_key)
    return report


def write_inventory_report(report: NcertInventoryReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def detect_ambiguous_mappings(report: NcertInventoryReport) -> list[dict[str, Any]]:
    """Return anomaly rows for duplicates / ambiguous chapter identities."""
    return [
        a
        for a in report.anomalies
        if a.get("code") == NCERT_SOURCE_AMBIGUOUS or "duplicate" in str(a.get("message", "")).lower()
    ]
