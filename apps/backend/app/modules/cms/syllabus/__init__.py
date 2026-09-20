"""NEET-UG-2026 syllabus gate package."""

from app.modules.cms.syllabus.neet_2026_parser import (
    EXPECTED_UNIT_COUNTS,
    NeetSyllabusRegistry,
    SyllabusParseError,
    default_syllabus_path,
    normalize_syllabus_text,
    parse_neet_syllabus_file,
    parse_neet_syllabus_text,
)
from app.modules.cms.syllabus.neet_2026_registry import (
    clear_neet_2026_registry_cache,
    load_neet_2026_registry,
)
from app.modules.cms.syllabus.neet_2026_scope import (
    ACADEMIC_TO_SYLLABUS_SUBJECT,
    SCOPE_BLOCK_KEY,
    SyllabusScopeResult,
    assert_blueprint_neet_syllabus_scope,
    extract_neet_ug_2026_scope,
)

__all__ = [
    "ACADEMIC_TO_SYLLABUS_SUBJECT",
    "EXPECTED_UNIT_COUNTS",
    "SCOPE_BLOCK_KEY",
    "NeetSyllabusRegistry",
    "SyllabusParseError",
    "SyllabusScopeResult",
    "assert_blueprint_neet_syllabus_scope",
    "clear_neet_2026_registry_cache",
    "default_syllabus_path",
    "extract_neet_ug_2026_scope",
    "load_neet_2026_registry",
    "normalize_syllabus_text",
    "parse_neet_syllabus_file",
    "parse_neet_syllabus_text",
]
