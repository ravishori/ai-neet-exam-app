"""Hard NEET-UG-2026 syllabus scope gate for generation blueprints.

Authorization is exact/deterministic against the parsed syllabus registry.
Fuzzy matching is never used to authorize generation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.modules.cms.syllabus.neet_2026_parser import (
    NeetSyllabusRegistry,
    normalize_syllabus_text,
)
from app.modules.cms.syllabus.neet_2026_registry import load_neet_2026_registry

SyllabusScopeStatus = Literal[
    "IN_SYLLABUS",
    "SYLLABUS_OUT_OF_SCOPE",
    "SYLLABUS_MAPPING_REVIEW_REQUIRED",
]

VALID_SYLLABUS_SUBJECTS = frozenset({"PHYSICS", "CHEMISTRY", "BIOLOGY"})
ACADEMIC_TO_SYLLABUS_SUBJECT = {
    "PHYSICS": "PHYSICS",
    "CHEMISTRY": "CHEMISTRY",
    "BIOLOGY": "BIOLOGY",
    "BOTANY": "BIOLOGY",
    "ZOOLOGY": "BIOLOGY",
}

# Constraint keys (explicit binding required for authorization)
SCOPE_BLOCK_KEY = "neet_ug_2026"


@dataclass(frozen=True)
class SyllabusScopeResult:
    status: SyllabusScopeStatus
    subject: str | None = None
    unit_number: int | None = None
    unit_name: str | None = None
    topic: str | None = None
    topic_id: str | None = None
    unit_id: str | None = None
    source_line: int | None = None
    detail: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def is_in_scope(self) -> bool:
        return self.status == "IN_SYLLABUS"

    @property
    def blocks_provider(self) -> bool:
        return self.status != "IN_SYLLABUS"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_neet_ug_2026_scope(constraints: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the explicit syllabus scope block from blueprint constraints, if any."""
    c = constraints or {}
    block = c.get(SCOPE_BLOCK_KEY)
    if isinstance(block, dict) and block:
        return block
    # Flat aliases (still explicit — not inferred from chapter names)
    flat_keys = (
        "neet_2026_subject",
        "neet_2026_unit",
        "neet_2026_unit_number",
        "neet_2026_unit_name",
        "neet_2026_topic",
        "neet_2026_topic_id",
        "syllabus_unit",
        "syllabus_topic",
    )
    if any(c.get(k) is not None for k in flat_keys):
        return {
            "subject": c.get("neet_2026_subject") or c.get("syllabus_subject"),
            "unit_number": c.get("neet_2026_unit_number")
            if c.get("neet_2026_unit_number") is not None
            else c.get("neet_2026_unit", c.get("syllabus_unit")),
            "unit_name": c.get("neet_2026_unit_name") or c.get("syllabus_unit_name"),
            "topic": c.get("neet_2026_topic") or c.get("syllabus_topic"),
            "topic_id": c.get("neet_2026_topic_id") or c.get("syllabus_topic_id"),
            "subtopic": c.get("neet_2026_subtopic") or c.get("syllabus_subtopic"),
        }
    return None


def assert_blueprint_neet_syllabus_scope(
    constraints: dict[str, Any] | None,
    *,
    academic_subject_code: str | None = None,
    registry: NeetSyllabusRegistry | None = None,
    syllabus_path: str | None = None,
) -> SyllabusScopeResult:
    """Deterministic syllabus membership check.

    Requires an explicit ``constraints.neet_ug_2026`` (or flat neet_2026_*) binding
    that exactly matches a parsed registry entry. Missing/ambiguous bindings do not
    authorize generation.
    """
    reg = registry or load_neet_2026_registry(syllabus_path)
    scope = extract_neet_ug_2026_scope(constraints)

    if not scope:
        return SyllabusScopeResult(
            status="SYLLABUS_MAPPING_REVIEW_REQUIRED",
            detail="missing explicit neet_ug_2026 syllabus binding on blueprint",
            reasons=["missing_neet_ug_2026_scope"],
        )

    raw_subject = str(scope.get("subject") or "").strip().upper()
    if not raw_subject:
        return SyllabusScopeResult(
            status="SYLLABUS_MAPPING_REVIEW_REQUIRED",
            detail="syllabus subject missing in binding",
            reasons=["missing_subject"],
        )
    if raw_subject not in VALID_SYLLABUS_SUBJECTS:
        return SyllabusScopeResult(
            status="SYLLABUS_OUT_OF_SCOPE",
            subject=raw_subject,
            detail=f"invalid syllabus subject: {raw_subject}",
            reasons=["invalid_subject"],
        )

    # If academic subject is provided, it must be compatible (Botany/Zoology → Biology).
    if academic_subject_code:
        mapped = ACADEMIC_TO_SYLLABUS_SUBJECT.get(academic_subject_code.strip().upper())
        if mapped and mapped != raw_subject:
            return SyllabusScopeResult(
                status="SYLLABUS_OUT_OF_SCOPE",
                subject=raw_subject,
                detail=(
                    f"academic subject {academic_subject_code} incompatible with "
                    f"syllabus subject {raw_subject}"
                ),
                reasons=["subject_mismatch"],
            )

    unit_number_raw = scope.get("unit_number")
    if unit_number_raw is None:
        return SyllabusScopeResult(
            status="SYLLABUS_MAPPING_REVIEW_REQUIRED",
            subject=raw_subject,
            detail="unit_number missing in binding",
            reasons=["missing_unit_number"],
        )
    try:
        unit_number = int(unit_number_raw)
    except (TypeError, ValueError):
        return SyllabusScopeResult(
            status="SYLLABUS_OUT_OF_SCOPE",
            subject=raw_subject,
            detail=f"invalid unit_number: {unit_number_raw!r}",
            reasons=["invalid_unit_number"],
        )

    unit_id = f"{raw_subject}:U{unit_number:02d}"
    unit = reg.units_by_id.get(unit_id)
    if unit is None:
        return SyllabusScopeResult(
            status="SYLLABUS_OUT_OF_SCOPE",
            subject=raw_subject,
            unit_number=unit_number,
            unit_id=unit_id,
            detail=f"unit not in NEET-UG-2026 syllabus: {unit_id}",
            reasons=["unit_not_in_syllabus"],
        )

    declared_unit_name = scope.get("unit_name")
    if declared_unit_name:
        if normalize_syllabus_text(str(declared_unit_name)) != normalize_syllabus_text(unit.unit_name):
            return SyllabusScopeResult(
                status="SYLLABUS_OUT_OF_SCOPE",
                subject=raw_subject,
                unit_number=unit_number,
                unit_name=unit.unit_name,
                unit_id=unit_id,
                detail="declared unit_name does not match syllabus unit",
                reasons=["unit_name_mismatch"],
            )

    topic_id = scope.get("topic_id")
    topic_text = scope.get("topic")
    subtopic = scope.get("subtopic")

    if topic_id:
        topic_id_s = str(topic_id).strip()
        topic = reg.topics_by_id.get(topic_id_s)
        if topic is None:
            return SyllabusScopeResult(
                status="SYLLABUS_OUT_OF_SCOPE",
                subject=raw_subject,
                unit_number=unit_number,
                unit_name=unit.unit_name,
                unit_id=unit_id,
                topic_id=topic_id_s,
                detail=f"topic_id not in syllabus registry: {topic_id_s}",
                reasons=["topic_id_not_in_syllabus"],
            )
        if f"{topic.subject}:U{topic.unit_number:02d}" != unit_id:
            return SyllabusScopeResult(
                status="SYLLABUS_OUT_OF_SCOPE",
                subject=raw_subject,
                unit_number=unit_number,
                unit_name=unit.unit_name,
                unit_id=unit_id,
                topic_id=topic_id_s,
                detail="topic_id does not belong to declared unit",
                reasons=["topic_unit_mismatch"],
            )
        if topic_text and normalize_syllabus_text(str(topic_text)) != normalize_syllabus_text(topic.topic):
            return SyllabusScopeResult(
                status="SYLLABUS_OUT_OF_SCOPE",
                subject=raw_subject,
                unit_number=unit_number,
                unit_name=unit.unit_name,
                unit_id=unit_id,
                topic=topic.topic,
                topic_id=topic.topic_id,
                detail="declared topic text does not match topic_id entry",
                reasons=["topic_text_mismatch"],
            )
        if subtopic is not None and topic.subtopic is not None:
            if normalize_syllabus_text(str(subtopic)) != normalize_syllabus_text(topic.subtopic):
                return SyllabusScopeResult(
                    status="SYLLABUS_OUT_OF_SCOPE",
                    subject=raw_subject,
                    unit_number=unit_number,
                    unit_name=unit.unit_name,
                    unit_id=unit_id,
                    topic=topic.topic,
                    topic_id=topic.topic_id,
                    detail="subtopic mismatch",
                    reasons=["subtopic_mismatch"],
                )
        return SyllabusScopeResult(
            status="IN_SYLLABUS",
            subject=raw_subject,
            unit_number=unit_number,
            unit_name=unit.unit_name,
            topic=topic.topic,
            topic_id=topic.topic_id,
            unit_id=unit_id,
            source_line=topic.source_line,
            detail="exact topic_id match",
            reasons=[],
        )

    if not topic_text:
        return SyllabusScopeResult(
            status="SYLLABUS_MAPPING_REVIEW_REQUIRED",
            subject=raw_subject,
            unit_number=unit_number,
            unit_name=unit.unit_name,
            unit_id=unit_id,
            detail="topic or topic_id required for deterministic authorization",
            reasons=["missing_topic"],
        )

    needle = normalize_syllabus_text(str(topic_text))
    matches = [t for t in unit.topics if normalize_syllabus_text(t.topic) == needle]
    if len(matches) == 1:
        topic = matches[0]
        return SyllabusScopeResult(
            status="IN_SYLLABUS",
            subject=raw_subject,
            unit_number=unit_number,
            unit_name=unit.unit_name,
            topic=topic.topic,
            topic_id=topic.topic_id,
            unit_id=unit_id,
            source_line=topic.source_line,
            detail="exact topic text match within unit",
            reasons=[],
        )
    if len(matches) > 1:
        return SyllabusScopeResult(
            status="SYLLABUS_MAPPING_REVIEW_REQUIRED",
            subject=raw_subject,
            unit_number=unit_number,
            unit_name=unit.unit_name,
            unit_id=unit_id,
            detail="ambiguous exact topic matches within unit",
            reasons=["ambiguous_topic_match"],
        )

    # No exact topic match — out of scope (invented / old / wrong topic)
    return SyllabusScopeResult(
        status="SYLLABUS_OUT_OF_SCOPE",
        subject=raw_subject,
        unit_number=unit_number,
        unit_name=unit.unit_name,
        unit_id=unit_id,
        topic=str(topic_text),
        detail="topic not found in NEET-UG-2026 unit (exact match required)",
        reasons=["topic_not_in_unit"],
    )
