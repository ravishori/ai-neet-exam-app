"""Pre-generation syllabus-boundary gate.

Reuses the existing deterministic NEET-UG-2026 syllabus registry
(``app.modules.cms.syllabus.neet_2026_scope`` /
``neet_2026_parser``/``neet_2026_registry``) rather than re-parsing
``NEETSyllabus.txt`` in this package. Must be called and must return
``is_in_scope`` True BEFORE any generation call is made for a topic —
callers that skip this and generate anyway are violating the pipeline
contract documented in
docs/quality/neet_mcq_factory_implementation_20261011.md.
"""

from __future__ import annotations

from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry
from app.modules.cms.syllabus.neet_2026_scope import (
    SyllabusScopeResult,
    assert_blueprint_neet_syllabus_scope,
)


def check_generation_topic_in_syllabus(
    *,
    subject: str,
    unit_number: int,
    topic: str | None = None,
    topic_id: str | None = None,
    unit_name: str | None = None,
    academic_subject_code: str | None = None,
    registry: NeetSyllabusRegistry | None = None,
    syllabus_path: str | None = None,
) -> SyllabusScopeResult:
    """Deterministic, exact-match syllabus authorization for one requested
    generation topic. Returns a ``SyllabusScopeResult`` whose
    ``is_in_scope`` MUST be checked by the caller before any generation
    call — never generate for a topic whose scope check did not return
    ``IN_SYLLABUS``.
    """
    constraints = {
        "neet_ug_2026": {
            "subject": subject,
            "unit_number": unit_number,
            "unit_name": unit_name,
            "topic": topic,
            "topic_id": topic_id,
        }
    }
    return assert_blueprint_neet_syllabus_scope(
        constraints,
        academic_subject_code=academic_subject_code,
        registry=registry,
        syllabus_path=syllabus_path,
    )


__all__ = ["check_generation_topic_in_syllabus"]
