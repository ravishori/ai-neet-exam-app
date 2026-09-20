"""Resolve registered SourceDocument paths under Settings.study_material_dir."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.modules.ingestion.models.source_document import SourceDocument
from app.modules.ingestion.services.pdf_extraction_service import compute_checksum
from app.modules.ingestion.services.study_material_path_parser import StudyMaterialPathError, resolve_under_root


def resolve_source_document_path(source: SourceDocument) -> Path:
    root = Path(get_settings().study_material_dir).resolve()
    try:
        resolved = resolve_under_root(root, source.relative_source_path)
    except StudyMaterialPathError as exc:
        raise AppError(str(exc), code="INVALID_SOURCE_PATH", status_code=400) from exc
    if not resolved.is_file():
        raise NotFoundError(f"Registered source file not found: {source.relative_source_path}")
    return resolved


def verify_source_checksum(source: SourceDocument, *, file_path: Path | None = None) -> str:
    """Return current SHA-256; raise if it no longer matches the registry."""
    path = file_path or resolve_source_document_path(source)
    current = compute_checksum(str(path))
    if current != source.checksum_sha256:
        raise AppError(
            "Registered source checksum does not match file on disk — rediscover before ingesting",
            code="SOURCE_CHECKSUM_MISMATCH",
            status_code=409,
        )
    return current
