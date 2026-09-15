"""NEET-UG-2026 syllabus registry — reproducible cache from NEETSyllabus.txt."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.modules.cms.syllabus.neet_2026_parser import (
    NeetSyllabusRegistry,
    default_syllabus_path,
    parse_neet_syllabus_file,
)


@lru_cache(maxsize=4)
def load_neet_2026_registry(path: str | None = None) -> NeetSyllabusRegistry:
    """Load and memoize the authoritative syllabus registry.

    ``NEETSyllabus.txt`` remains the source of truth; the in-memory registry
    is a reproducible parse of that file (keyed by absolute path string).
    """
    syllabus_path = Path(path) if path else default_syllabus_path()
    return parse_neet_syllabus_file(syllabus_path.resolve())


def clear_neet_2026_registry_cache() -> None:
    load_neet_2026_registry.cache_clear()
