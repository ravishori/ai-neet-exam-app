"""Read-only inventory of PastQuestionPapers (PASTQ-IMPORT-001 Phase 1)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz

from app.modules.cms.pyq.pyq_discovery import sha256_file

DEFAULT_SOURCE_ROOT = Path(r"D:\ravishori\AI Neet Exam App\PastQuestionPapers")
SUPPORTED_EXTS = {".pdf", ".epub", ".docx", ".txt", ".zip", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


@dataclass
class SourceFileRecord:
    source_file_id: str
    filename: str
    relative_path: str
    absolute_path: str
    extension: str
    file_size: int
    sha256: str
    page_count: int | None
    readable: bool
    extraction_method: str
    extraction_status: str
    notes: list[str] = field(default_factory=list)
    sample_chars: int = 0
    image_page_hint: bool = False


@dataclass
class SourceInventory:
    source_root: str
    generated_at: str
    total_files: int
    by_extension: dict[str, int]
    files: list[SourceFileRecord]
    unreadable: list[str] = field(default_factory=list)
    excluded_non_paper: list[str] = field(default_factory=list)


def _probe_pdf(path: Path) -> tuple[int | None, bool, str, int, bool, list[str]]:
    notes: list[str] = []
    try:
        doc = fitz.open(path)
        try:
            n = doc.page_count
            chars = 0
            image_hint = False
            for i in range(n):
                page = doc.load_page(i)
                text = (page.get_text("text") or "").strip()
                chars += len(text)
                if len(text) < 40 and page.get_images():
                    image_hint = True
            if chars < 80 and image_hint:
                status = "SCANNED_OR_EMPTY_TEXT"
                method = "pymupdf_text+ocr_required"
                notes.append("little_or_no_extractable_text")
            elif chars < 80:
                status = "LOW_TEXT"
                method = "pymupdf_text"
                notes.append("low_text_density")
            else:
                status = "TEXT_EXTRACTABLE"
                method = "pymupdf_text"
            return n, True, status, chars, image_hint, notes
        finally:
            doc.close()
    except Exception as exc:  # noqa: BLE001
        return None, False, "UNREADABLE", 0, False, [f"open_failed:{exc}"]


def inventory_source_root(source_root: Path | str | None = None) -> SourceInventory:
    root = Path(source_root or DEFAULT_SOURCE_ROOT).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"PastQuestionPapers root missing: {root}")

    files: list[SourceFileRecord] = []
    by_ext: dict[str, int] = {}
    unreadable: list[str] = []
    excluded: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        ext = path.suffix.lower() or "(none)"
        by_ext[ext] = by_ext.get(ext, 0) + 1
        digest = sha256_file(path)
        source_file_id = digest[:16]

        page_count = None
        readable = True
        method = "binary_hash_only"
        status = "INVENTORIED"
        notes: list[str] = []
        sample_chars = 0
        image_hint = False

        lower_name = path.name.lower()
        if "syllabus" in lower_name:
            excluded.append(rel)
            notes.append("classified_non_paper_syllabus")
            status = "EXCLUDED_NON_PAPER"

        if ext == ".pdf":
            page_count, readable, status2, sample_chars, image_hint, pdf_notes = _probe_pdf(path)
            if status != "EXCLUDED_NON_PAPER":
                status = status2
            method = "pymupdf_text" if readable else "unreadable"
            notes.extend(pdf_notes)
            if not readable:
                unreadable.append(rel)
        elif ext not in SUPPORTED_EXTS:
            notes.append("unsupported_extension")
            status = "UNSUPPORTED"
        else:
            method = f"file_{ext.lstrip('.')}"
            status = "INVENTORIED_NON_PDF"

        files.append(
            SourceFileRecord(
                source_file_id=source_file_id,
                filename=path.name,
                relative_path=rel,
                absolute_path=str(path),
                extension=ext,
                file_size=path.stat().st_size,
                sha256=digest,
                page_count=page_count,
                readable=readable,
                extraction_method=method,
                extraction_status=status,
                notes=notes,
                sample_chars=sample_chars,
                image_page_hint=image_hint,
            )
        )

    return SourceInventory(
        source_root=str(root),
        generated_at=datetime.now(UTC).isoformat(),
        total_files=len(files),
        by_extension=dict(sorted(by_ext.items())),
        files=files,
        unreadable=unreadable,
        excluded_non_paper=excluded,
    )


def inventory_to_dict(inv: SourceInventory) -> dict[str, Any]:
    return {
        "source_root": inv.source_root,
        "generated_at": inv.generated_at,
        "total_files": inv.total_files,
        "by_extension": inv.by_extension,
        "unreadable": inv.unreadable,
        "excluded_non_paper": inv.excluded_non_paper,
        "files": [asdict(f) for f in inv.files],
    }


def write_inventory_reports(
    inv: SourceInventory,
    *,
    md_path: Path,
    json_path: Path,
) -> None:
    data = inventory_to_dict(inv)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    lines = [
        "# PASTQ-IMPORT-001 — Source Inventory",
        "",
        f"**Generated:** {inv.generated_at}",
        f"**Root:** `{inv.source_root}`",
        f"**Total files:** {inv.total_files}",
        "",
        "## By extension",
        "",
    ]
    for ext, count in inv.by_extension.items():
        lines.append(f"- `{ext}`: {count}")
    lines.extend(["", "## Files", ""])
    lines.append("| file | pages | size | status | sha256 |")
    lines.append("|---|---:|---:|---|---|")
    for f in inv.files:
        lines.append(
            f"| `{f.filename}` | {f.page_count if f.page_count is not None else '-'} | "
            f"{f.file_size} | {f.extraction_status} | `{f.sha256[:12]}…` |"
        )
    if inv.excluded_non_paper:
        lines.extend(["", "## Excluded non-paper", ""])
        for rel in inv.excluded_non_paper:
            lines.append(f"- `{rel}`")
    if inv.unreadable:
        lines.extend(["", "## Unreadable", ""])
        for rel in inv.unreadable:
            lines.append(f"- `{rel}`")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Source files were **not** modified.",
            "- PastQuestionPapers is **not** an NCERT source.",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
