"""Reusable NEET StudyMaterial discovery + registry (ADR-0030).

Walks only Physics / Chemistry / Biology under Settings.study_material_dir.
Ignores Maths and Uploads at enumeration time. SHA-256 is the canonical
content identity — repeated discovery is idempotent.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import fitz
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.ingestion.models.source_document import SourceDocument
from app.modules.ingestion.repositories.source_document_repository import SourceDocumentRepository
from app.modules.ingestion.services.pdf_extraction_service import compute_checksum
from app.modules.ingestion.services.study_material_path_parser import (
    NEET_SUBJECT_ROOTS,
    StudyMaterialPathError,
    parse_study_material_path,
    resolve_under_root,
)

logger = get_logger("ingestion.discovery")

SUPPORTED_SUFFIXES = frozenset({".pdf"})


class StudyMaterialSettings(Protocol):
    study_material_dir: str


@dataclass
class DiscoveryErrorItem:
    relative_path: str | None
    message: str


@dataclass
class DiscoveryReport:
    discovered: int = 0
    registered: int = 0
    duplicates: int = 0
    skipped: int = 0
    errors: int = 0
    by_subject_class: dict[str, dict[str, int]] = field(default_factory=dict)
    page_count_total: int = 0
    error_details: list[DiscoveryErrorItem] = field(default_factory=list)
    dry_run: bool = False

    def to_api_dict(self) -> dict:
        """Public API shape — no absolute filesystem paths."""
        return {
            "discovered": self.discovered,
            "registered": self.registered,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "errors": self.errors,
            "by_subject_class": self.by_subject_class,
            "page_count_total": self.page_count_total,
            "dry_run": self.dry_run,
            "error_details": [{"relative_path": e.relative_path, "message": e.message} for e in self.error_details[:50]],
        }


def _infer_publisher(file_name: str) -> str | None:
    return "NCERT" if "ncert" in file_name.lower() else None


def _pdf_page_count(path: Path) -> int | None:
    try:
        doc = fitz.open(path)
        try:
            return int(doc.page_count)
        finally:
            doc.close()
    except Exception:  # noqa: BLE001 — discovery must continue on corrupt PDFs
        return None


class StudyMaterialDiscoveryService:
    def __init__(self, session: AsyncSession, settings: StudyMaterialSettings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.repo = SourceDocumentRepository(session)

    def resolve_root(self) -> Path:
        root = Path(self.settings.study_material_dir).resolve()
        if not root.exists():
            raise AppError(
                f"Study material directory does not exist: {root}",
                code="STUDY_MATERIAL_DIR_MISSING",
                status_code=500,
            )
        if not root.is_dir():
            raise AppError(
                f"Study material path is not a directory: {root}",
                code="STUDY_MATERIAL_DIR_INVALID",
                status_code=500,
            )
        return root

    def _neet_subject_dirs(self, root: Path) -> list[tuple[str, Path]]:
        """Return only Physics/Chemistry/Biology directories that exist under root."""
        found: list[tuple[str, Path]] = []
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not entry.is_dir():
                continue
            # Resolve to catch junctions/symlinks that escape the root.
            try:
                resolved = resolve_under_root(root, entry)
            except StudyMaterialPathError:
                logger.warning("discovery_skip_escaped_dir", path=str(entry))
                continue
            code = NEET_SUBJECT_ROOTS.get(entry.name.strip().lower())
            if code is None:
                # Maths, Uploads, and any other top-level dirs are ignored here.
                continue
            found.append((code, resolved))
        return found

    def enumerate_neet_pdfs(self, root: Path | None = None) -> list[Path]:
        """Recursively list NEET PDFs under the three subject roots only."""
        root = root or self.resolve_root()
        pdfs: list[Path] = []
        for _subject_code, subject_dir in self._neet_subject_dirs(root):
            for path in sorted(subject_dir.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                    continue
                try:
                    resolved = resolve_under_root(root, path)
                except StudyMaterialPathError:
                    logger.warning("discovery_skip_escaped_file", path=str(path))
                    continue
                # Extra guard: never accept Uploads nested oddly under a subject.
                rel_parts = resolved.relative_to(root).parts
                if any(p.strip().lower() == "uploads" for p in rel_parts):
                    continue
                pdfs.append(resolved)
        return pdfs

    async def discover(self, *, dry_run: bool = False) -> DiscoveryReport:
        root = self.resolve_root()
        report = DiscoveryReport(dry_run=dry_run)
        counts: dict[str, Counter[str]] = defaultdict(Counter)

        for absolute in self.enumerate_neet_pdfs(root):
            rel = absolute.relative_to(root).as_posix()
            try:
                parsed = parse_study_material_path(rel)
            except StudyMaterialPathError as exc:
                report.skipped += 1
                report.errors += 1
                report.error_details.append(DiscoveryErrorItem(rel, str(exc)))
                continue

            report.discovered += 1
            try:
                checksum = compute_checksum(str(absolute))
                file_size = absolute.stat().st_size
                page_count = _pdf_page_count(absolute)
            except OSError as exc:
                report.errors += 1
                report.error_details.append(DiscoveryErrorItem(rel, f"unreadable: {exc}"))
                continue

            if page_count is not None:
                report.page_count_total += page_count

            existing = await self.repo.get_by_checksum(checksum)
            if existing is not None:
                report.duplicates += 1
                counts[parsed.subject_code][parsed.class_level] += 1
                continue

            counts[parsed.subject_code][parsed.class_level] += 1

            if dry_run:
                report.registered += 1  # would-register count for dry-run UX
                continue

            doc = SourceDocument(
                relative_source_path=parsed.relative_source_path,
                file_name=parsed.file_name,
                file_type="pdf",
                file_size=file_size,
                checksum_sha256=checksum,
                absolute_source_path_dev=str(absolute),
                storage_key=None,
                class_level=parsed.class_level,
                subject_code=parsed.subject_code,
                title=Path(parsed.file_name).stem,
                publisher=_infer_publisher(parsed.file_name),
                edition=None,
                page_count=page_count,
                ingestion_status="DISCOVERED",
            )
            self.repo.add(doc)
            report.registered += 1

        if not dry_run and report.registered:
            await self.repo.commit()

        report.by_subject_class = {
            subject: dict(sorted(class_counts.items())) for subject, class_counts in sorted(counts.items())
        }
        logger.info(
            "study_material_discovery_complete",
            discovered=report.discovered,
            registered=report.registered,
            duplicates=report.duplicates,
            skipped=report.skipped,
            errors=report.errors,
            dry_run=dry_run,
        )
        return report
