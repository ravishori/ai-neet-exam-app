"""Deterministic parser for NEET (UG)-2026 syllabus text.

Authority: repo-root ``NEETSyllabus.txt`` (NMC/UGMEB).
Does not expand from NCERT, PYQ, StudyMaterial, web, or model knowledge.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

EXPECTED_UNIT_COUNTS = {"PHYSICS": 20, "CHEMISTRY": 20, "BIOLOGY": 10}

_SUBJECT_RE = re.compile(
    r"^##\s+\d+\.\s+(PHYSICS|CHEMISTRY|BIOLOGY)\s+SYLLABUS\s*$",
    re.IGNORECASE,
)
_UNIT_RE = re.compile(r"^\*\s*\*\*UNIT\s+(\d+)\s*:\s*(.+?)\*\*\s*$", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\*\s+(?!\*\*)(.+)$")
_NUMBERED_RE = re.compile(r"^(\d+)\.\s+(.+)$")


class SyllabusParseError(ValueError):
    """Loud failure when the authoritative syllabus cannot be parsed completely."""


@dataclass(frozen=True)
class NeetSyllabusTopic:
    subject: str
    unit_number: int
    unit_name: str
    topic_index: int
    topic: str
    subtopic: str | None
    topic_id: str
    source_line: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NeetSyllabusUnit:
    subject: str
    unit_number: int
    unit_name: str
    unit_id: str
    source_line: int
    topics: list[NeetSyllabusTopic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "unit_number": self.unit_number,
            "unit_name": self.unit_name,
            "unit_id": self.unit_id,
            "source_line": self.source_line,
            "topics": [t.to_dict() for t in self.topics],
        }


@dataclass
class NeetSyllabusRegistry:
    source_path: str
    source_sha256: str
    units: list[NeetSyllabusUnit]
    topics_by_id: dict[str, NeetSyllabusTopic]
    units_by_id: dict[str, NeetSyllabusUnit]

    def unit_counts(self) -> dict[str, int]:
        counts = {"PHYSICS": 0, "CHEMISTRY": 0, "BIOLOGY": 0}
        for u in self.units:
            counts[u.subject] = counts.get(u.subject, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "unit_counts": self.unit_counts(),
            "units": [u.to_dict() for u in self.units],
        }


def default_syllabus_path() -> Path:
    # .../app/modules/cms/syllabus/neet_2026_parser.py → repo root (parents[6])
    return Path(__file__).resolve().parents[6] / "NEETSyllabus.txt"


def normalize_syllabus_text(value: str) -> str:
    """Deterministic comparison key — casefold + whitespace collapse only."""
    text = (value or "").replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


def _unit_id(subject: str, unit_number: int) -> str:
    return f"{subject}:U{unit_number:02d}"


def _topic_id(subject: str, unit_number: int, topic_index: int) -> str:
    return f"{subject}:U{unit_number:02d}:T{topic_index:02d}"


def parse_neet_syllabus_text(
    text: str,
    *,
    source_path: str = "<memory>",
    source_sha256: str | None = None,
) -> NeetSyllabusRegistry:
    """Parse full syllabus text. Fails if expected 20/20/10 structure is missing."""
    if not (text or "").strip():
        raise SyllabusParseError("syllabus text is empty")

    digest = source_sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest()
    units: list[NeetSyllabusUnit] = []
    current_subject: str | None = None
    current_unit: NeetSyllabusUnit | None = None
    seen_unit_numbers: dict[str, set[int]] = {
        "PHYSICS": set(),
        "CHEMISTRY": set(),
        "BIOLOGY": set(),
    }

    lines = text.splitlines()
    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line == "---":
            continue

        sm = _SUBJECT_RE.match(line)
        if sm:
            current_subject = sm.group(1).upper()
            current_unit = None
            continue

        um = _UNIT_RE.match(line)
        if um:
            if current_subject is None:
                raise SyllabusParseError(f"unit before subject at line {line_no}")
            unit_number = int(um.group(1))
            unit_name = um.group(2).strip()
            if unit_number in seen_unit_numbers[current_subject]:
                raise SyllabusParseError(
                    f"duplicate unit {unit_number} for {current_subject} at line {line_no}"
                )
            seen_unit_numbers[current_subject].add(unit_number)
            current_unit = NeetSyllabusUnit(
                subject=current_subject,
                unit_number=unit_number,
                unit_name=unit_name,
                unit_id=_unit_id(current_subject, unit_number),
                source_line=line_no,
            )
            units.append(current_unit)
            continue

        if current_subject is None or current_unit is None:
            continue

        # Subsection headers like "### PHYSICAL CHEMISTRY" are structural, not topics.
        if line.startswith("#"):
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            topic_text = bullet.group(1).strip()
            if not topic_text:
                continue
            idx = len(current_unit.topics) + 1
            current_unit.topics.append(
                NeetSyllabusTopic(
                    subject=current_subject,
                    unit_number=current_unit.unit_number,
                    unit_name=current_unit.unit_name,
                    topic_index=idx,
                    topic=topic_text,
                    subtopic=None,
                    topic_id=_topic_id(current_subject, current_unit.unit_number, idx),
                    source_line=line_no,
                )
            )
            continue

        numbered = _NUMBERED_RE.match(line)
        if numbered:
            topic_text = f"{numbered.group(1)}. {numbered.group(2).strip()}"
            idx = len(current_unit.topics) + 1
            current_unit.topics.append(
                NeetSyllabusTopic(
                    subject=current_subject,
                    unit_number=current_unit.unit_number,
                    unit_name=current_unit.unit_name,
                    topic_index=idx,
                    topic=topic_text,
                    subtopic=None,
                    topic_id=_topic_id(current_subject, current_unit.unit_number, idx),
                    source_line=line_no,
                )
            )

    counts = {"PHYSICS": 0, "CHEMISTRY": 0, "BIOLOGY": 0}
    for u in units:
        counts[u.subject] = counts.get(u.subject, 0) + 1

    for subject, expected in EXPECTED_UNIT_COUNTS.items():
        actual = counts.get(subject, 0)
        if actual != expected:
            raise SyllabusParseError(
                f"{subject} unit count {actual} != expected {expected}"
            )
        expected_nums = set(range(1, expected + 1))
        if seen_unit_numbers[subject] != expected_nums:
            missing = sorted(expected_nums - seen_unit_numbers[subject])
            extra = sorted(seen_unit_numbers[subject] - expected_nums)
            raise SyllabusParseError(
                f"{subject} unit numbers incomplete; missing={missing} extra={extra}"
            )

    # Every unit must have at least one topic/bullet (or numbered item).
    empty = [u.unit_id for u in units if not u.topics]
    if empty:
        raise SyllabusParseError(f"units with no topics: {empty}")

    topics_by_id = {t.topic_id: t for u in units for t in u.topics}
    units_by_id = {u.unit_id: u for u in units}
    return NeetSyllabusRegistry(
        source_path=source_path,
        source_sha256=digest,
        units=units,
        topics_by_id=topics_by_id,
        units_by_id=units_by_id,
    )


def parse_neet_syllabus_file(path: Path | None = None) -> NeetSyllabusRegistry:
    syllabus_path = Path(path) if path is not None else default_syllabus_path()
    if not syllabus_path.exists():
        raise SyllabusParseError(f"syllabus file missing: {syllabus_path}")
    raw = syllabus_path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SyllabusParseError(f"syllabus file not utf-8: {syllabus_path}") from exc
    return parse_neet_syllabus_text(
        text,
        source_path=str(syllabus_path.resolve()),
        source_sha256=hashlib.sha256(raw).hexdigest(),
    )
