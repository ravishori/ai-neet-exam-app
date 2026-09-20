"""CF-SOURCE-001 — canonical NCERT source root + hard path guard.

All future NCERT-derived MCQ generation must resolve PDFs inside
``Settings.ncert_source_root`` (env ``NCERT_SOURCE_ROOT``). Legacy
``StudyMaterial/`` paths are rejected for NCERT generation.

This module is path-policy only — it does not mutate content rows,
call AI providers, or rewrite provenance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# Domain error codes (backend/internal diagnostics — not student-facing copy).
NCERT_SOURCE_NOT_ALLOWED = "NCERT_SOURCE_NOT_ALLOWED"
NCERT_SOURCE_MISSING = "NCERT_SOURCE_MISSING"
NCERT_SOURCE_UNREADABLE = "NCERT_SOURCE_UNREADABLE"
NCERT_SOURCE_AMBIGUOUS = "NCERT_SOURCE_AMBIGUOUS"
NCERT_SOURCE_IDENTITY_MISMATCH = "NCERT_SOURCE_IDENTITY_MISMATCH"
NCERT_SOURCE_NOT_PDF = "NCERT_SOURCE_NOT_PDF"
NCERT_SOURCE_ROOT_UNCONFIGURED = "NCERT_SOURCE_ROOT_UNCONFIGURED"

# Constraint keys that bind a blueprint to a canonical NCERT PDF.
NCERT_SOURCE_CONSTRAINT_KEYS = (
    "ncert_source_path",
    "canonical_ncert_pdf",
    "source_pdf_path",
)


class NcertSourceError(AppError):
    """Typed failure for canonical NCERT source validation (fail-closed)."""

    def __init__(self, message: str, *, code: str = NCERT_SOURCE_NOT_ALLOWED, status_code: int = 400):
        super().__init__(message, code=code, status_code=status_code)


@dataclass(frozen=True)
class ValidatedNcertSource:
    """Resolved, containment-checked NCERT PDF identity."""

    resolved_path: Path
    relative_posix: str
    root: Path


def get_ncert_source_root() -> Path:
    """Single canonical accessor for the configured NCERT Books root."""
    raw = (get_settings().ncert_source_root or "").strip()
    if not raw:
        raise NcertSourceError(
            "NCERT_SOURCE_ROOT is empty",
            code=NCERT_SOURCE_ROOT_UNCONFIGURED,
        )
    return Path(raw).expanduser().resolve()


def _resolve_inside_root(root: Path, candidate: Path | str) -> Path:
    """Resolve ``candidate`` and require it to stay inside ``root``.

    Uses pathlib containment (``relative_to``), not string-prefix checks, so
    ``.../NCERT Books2/...`` cannot pass against ``.../NCERT Books``.
    """
    root_resolved = root.resolve()
    raw = Path(candidate)

    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        if isinstance(candidate, str) and PureWindowsPath(candidate).drive:
            raise NcertSourceError(
                "absolute path outside NCERT source root",
                code=NCERT_SOURCE_NOT_ALLOWED,
            )
        # Reject explicit traversal segments before join/resolve.
        parts = Path(str(candidate).replace("\\", "/")).parts
        if ".." in parts:
            raise NcertSourceError(
                "path traversal is not allowed",
                code=NCERT_SOURCE_NOT_ALLOWED,
            )
        resolved = (root_resolved / raw).resolve()

    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise NcertSourceError(
            "path escapes NCERT source root",
            code=NCERT_SOURCE_NOT_ALLOWED,
        ) from exc
    return resolved


def is_allowed_ncert_source(path: Path | str, *, root: Path | None = None) -> bool:
    """True only when the resolved path is contained in the canonical root.

    Does not require the file to exist — use ``validate_ncert_generation_source``
    for generation-time existence/PDF checks.
    """
    try:
        source_root = root.resolve() if root is not None else get_ncert_source_root()
        _resolve_inside_root(source_root, path)
        return True
    except (NcertSourceError, OSError, RuntimeError):
        return False


def assert_allowed_ncert_source(path: Path | str, *, root: Path | None = None) -> Path:
    """Return resolved path inside the canonical root, or raise ``NcertSourceError``."""
    source_root = root.resolve() if root is not None else get_ncert_source_root()
    return _resolve_inside_root(source_root, path)


def validate_ncert_generation_source(
    path: Path | str,
    *,
    root: Path | None = None,
) -> ValidatedNcertSource:
    """Fail-closed generation gate: inside root, exists, is a readable PDF."""
    source_root = root.resolve() if root is not None else get_ncert_source_root()
    resolved = assert_allowed_ncert_source(path, root=source_root)

    if not resolved.exists():
        logger.warning("ncert_source_missing path=%s", resolved.name)
        raise NcertSourceError(
            "NCERT source PDF does not exist",
            code=NCERT_SOURCE_MISSING,
        )
    if not resolved.is_file():
        raise NcertSourceError(
            "NCERT source path is not a file",
            code=NCERT_SOURCE_NOT_PDF,
        )
    if resolved.suffix.lower() != ".pdf":
        raise NcertSourceError(
            "NCERT source must be a PDF",
            code=NCERT_SOURCE_NOT_PDF,
        )
    try:
        with resolved.open("rb") as fh:
            header = fh.read(5)
        if header != b"%PDF-":
            raise NcertSourceError(
                "NCERT source is not a readable PDF",
                code=NCERT_SOURCE_UNREADABLE,
            )
    except OSError as exc:
        raise NcertSourceError(
            "NCERT source PDF cannot be read",
            code=NCERT_SOURCE_UNREADABLE,
        ) from exc

    rel = resolved.relative_to(source_root).as_posix()
    return ValidatedNcertSource(resolved_path=resolved, relative_posix=rel, root=source_root)


def blueprint_declares_ncert_source(constraints: dict | None, provenance_tier: str | None = None) -> bool:
    """True when a blueprint is NCERT-derived / binds a canonical PDF."""
    c = constraints or {}
    if c.get("ncert_derived") is True:
        return True
    if any(c.get(k) for k in NCERT_SOURCE_CONSTRAINT_KEYS):
        return True
    # Authoritative tier implies NCERT/textbook grounding for factory policy.
    if (provenance_tier or "").strip().lower() == "authoritative":
        return True
    return False


def extract_blueprint_ncert_path(constraints: dict | None) -> str | None:
    c = constraints or {}
    for key in NCERT_SOURCE_CONSTRAINT_KEYS:
        value = c.get(key)
        if value:
            return str(value).strip()
    return None


def assert_blueprint_ncert_source(
    constraints: dict | None,
    *,
    provenance_tier: str | None = None,
    root: Path | None = None,
) -> ValidatedNcertSource | None:
    """Validate blueprint NCERT binding.

    - Non-NCERT blueprints → ``None`` (AI/derived generation may proceed).
    - NCERT-derived without path → ``NCERT_SOURCE_MISSING``.
    - Path outside root / StudyMaterial / missing → typed rejection.
    """
    if not blueprint_declares_ncert_source(constraints, provenance_tier):
        return None

    path = extract_blueprint_ncert_path(constraints)
    if not path:
        raise NcertSourceError(
            "NCERT-derived blueprint is missing ncert_source_path",
            code=NCERT_SOURCE_MISSING,
        )
    return validate_ncert_generation_source(path, root=root)


def assert_ncert_generation_root(study_dir: Path | str | None = None) -> Path:
    """Require a generation scan root to be the canonical NCERT root (or inside it).

    Blocks legacy ``StudyMaterial/`` and any other directory as NCERT corpus.
    """
    source_root = get_ncert_source_root()
    if study_dir is None:
        return source_root
    candidate = Path(study_dir).expanduser().resolve()
    if candidate == source_root:
        return candidate
    # Allow a subdirectory of the canonical root (e.g. Class 11 only).
    try:
        candidate.relative_to(source_root)
        return candidate
    except ValueError as exc:
        logger.warning(
            "ncert_source_not_allowed requested_root=%s canonical=%s",
            candidate.name,
            source_root.name,
        )
        raise NcertSourceError(
            "NCERT generation root must be inside NCERT_SOURCE_ROOT "
            "(StudyMaterial and other directories are not allowed)",
            code=NCERT_SOURCE_NOT_ALLOWED,
        ) from exc
