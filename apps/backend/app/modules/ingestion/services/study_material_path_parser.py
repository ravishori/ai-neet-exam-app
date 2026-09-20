"""Parse NEET StudyMaterial relative paths into subject + class metadata.

Handles real-tree irregularities (e.g. ``Class 11- Chemistry`` with a space
after the hyphen) via whitespace/case normalization. Maths and Uploads are
rejected — they are outside the NEET discovery corpus (ADR-0030).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

# Only these three subject roots are accepted at discovery time.
NEET_SUBJECT_ROOTS = {
    "physics": "PHYSICS",
    "chemistry": "CHEMISTRY",
    "biology": "BIOLOGY",
}

EXCLUDED_ROOTS = frozenset({"maths", "uploads"})

_CLASS_RE = re.compile(r"class\s*(11|12)\b", re.IGNORECASE)
_SUPPORTED_EXTENSIONS = frozenset({".pdf"})


@dataclass(frozen=True)
class ParsedStudyMaterialPath:
    subject_code: str
    class_level: str
    relative_source_path: str
    file_name: str


class StudyMaterialPathError(ValueError):
    """Path is outside the NEET StudyMaterial corpus or cannot be parsed."""


def _normalize_rel_parts(relative: str) -> tuple[str, ...]:
    """Normalize to forward-slash POSIX parts without leading ``./`` noise."""
    cleaned = relative.replace("\\", "/").strip()
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("/")
    if not cleaned:
        raise StudyMaterialPathError("empty relative path")
    pure = PurePosixPath(cleaned)
    parts = tuple(p for p in pure.parts if p not in (".", ""))
    if ".." in parts:
        raise StudyMaterialPathError("path traversal is not allowed")
    if not parts:
        raise StudyMaterialPathError("empty relative path")
    return parts


def _normalize_token(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def parse_study_material_path(relative_path: str) -> ParsedStudyMaterialPath:
    """Parse a path relative to ``Settings.study_material_dir``.

    Expected shapes (whitespace/case tolerant)::

        Physics/Class 11-Physics/foo.pdf
        Chemistry/Class 11- Chemistry/foo.pdf
        Biology/Class 12-Biology/foo.pdf

    Raises ``StudyMaterialPathError`` for Maths, Uploads, unknown subjects,
    missing class level, unsupported extensions, or traversal.
    """
    parts = _normalize_rel_parts(relative_path)
    root = _normalize_token(parts[0])

    if root in EXCLUDED_ROOTS:
        raise StudyMaterialPathError(f"excluded root: {parts[0]}")

    subject_code = NEET_SUBJECT_ROOTS.get(root)
    if subject_code is None:
        raise StudyMaterialPathError(f"unsupported subject root: {parts[0]}")

    if len(parts) < 3:
        raise StudyMaterialPathError("expected Subject/Class folder/file.pdf — path too short")

    class_folder = _normalize_token(parts[1])
    class_match = _CLASS_RE.search(class_folder)
    if not class_match:
        raise StudyMaterialPathError(f"could not parse class level from: {parts[1]}")
    class_level = class_match.group(1)

    # Class folder should also mention the subject (tolerant of "Class 11- Chemistry").
    subject_token = subject_code.lower()
    if subject_token not in class_folder.replace("-", " ").replace("_", " "):
        # Still accept if subject root already established the subject — the
        # class folder naming is irregular; do not invent Maths/etc.
        pass

    file_name = parts[-1]
    suffix = Path(file_name).suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise StudyMaterialPathError(f"unsupported file type: {suffix or '(none)'}")

    relative_source_path = "/".join(parts)
    return ParsedStudyMaterialPath(
        subject_code=subject_code,
        class_level=class_level,
        relative_source_path=relative_source_path,
        file_name=file_name,
    )


def is_under_excluded_root(relative_path: str) -> bool:
    """True when the first path segment is Maths or Uploads (case-insensitive)."""
    try:
        parts = _normalize_rel_parts(relative_path)
    except StudyMaterialPathError:
        return False
    return _normalize_token(parts[0]) in EXCLUDED_ROOTS


def resolve_under_root(root: Path, candidate: Path | str) -> Path:
    """Resolve ``candidate`` and require it to stay inside ``root``.

    Rejects absolute paths outside root, ``..`` escape, and symlink/junction
    targets that resolve outside the configured StudyMaterial directory.
    """
    root_resolved = root.resolve()
    raw = Path(candidate)
    # Absolute Windows/POSIX paths that aren't under root must fail even before join.
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        # Disallow PureWindowsPath drive/UNC tricks smuggled as "relative".
        if isinstance(candidate, str) and PureWindowsPath(candidate).drive:
            raise StudyMaterialPathError("absolute path outside study material root")
        resolved = (root_resolved / raw).resolve()

    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise StudyMaterialPathError("path escapes study material root") from exc
    return resolved
