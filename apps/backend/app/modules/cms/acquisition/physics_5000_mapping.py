"""Explicit legacy Physics 5000 → TALOS field and academic mapping.

Do not infer mappings beyond what is documented here. Unresolved legacy
chapters stay flagged; concept_id is never guessed from chapter alone.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal

BATCH_ID = "legacy-physics-5000-import-20260902"
MODEL_USED = "legacy-physics-bank-algorithmic"
PROMPT_VERSION = "physics-11-5000-v1"
LEGACY_SOURCE_REF = "physics-question-bank/output/physics_11_5000_mcqs.json"

MappingConfidence = Literal["HIGH", "MEDIUM", "LOW", "UNRESOLVED"]


@dataclass(frozen=True)
class LegacyChapterMap:
    legacy_chapter_id: int
    legacy_title: str
    talos_chapter_code: str | None
    talos_topic_code: str | None
    confidence: MappingConfidence
    note: str


# Legacy PHY11-CH01..CH10 → TALOS academic.chapters (code). Topic/concept unset.
LEGACY_CHAPTER_MAP: dict[int, LegacyChapterMap] = {
    1: LegacyChapterMap(1, "Units and Measurement", None, None, "UNRESOLVED", "No TALOS chapter"),
    2: LegacyChapterMap(
        2,
        "Motion in a Straight Line",
        "kinematics",
        None,
        "LOW",
        "Chapter-level only; no topic/concept match",
    ),
    3: LegacyChapterMap(
        3,
        "Motion in a Plane",
        "kinematics",
        None,
        "LOW",
        "Chapter-level only; no topic/concept match",
    ),
    4: LegacyChapterMap(4, "Laws of Motion", "laws-of-motion", None, "MEDIUM", "Chapter-level only"),
    5: LegacyChapterMap(5, "Work, Energy and Power", "work-energy-power", None, "MEDIUM", "Chapter-level only"),
    6: LegacyChapterMap(
        6,
        "Systems of Particles and Rotational Motion",
        None,
        None,
        "UNRESOLVED",
        "No TALOS chapter",
    ),
    7: LegacyChapterMap(
        7,
        "Mechanical Properties of Solids",
        None,
        None,
        "UNRESOLVED",
        "No TALOS chapter",
    ),
    8: LegacyChapterMap(
        8,
        "Mechanical Properties of Fluids",
        None,
        None,
        "UNRESOLVED",
        "No TALOS chapter",
    ),
    9: LegacyChapterMap(9, "Thermodynamics", "thermodynamics-physics", None, "MEDIUM", "Chapter-level only"),
    10: LegacyChapterMap(10, "Kinetic Theory", None, None, "UNRESOLVED", "No TALOS chapter"),
}


def legacy_slug(legacy_id: str) -> str:
    """Idempotency key — immutable per PHY11 source id."""
    return f"legacy-phy11-{legacy_id.lower()}"


def normalize_stem(stem: str) -> str:
    return re.sub(r"\s+", " ", stem.strip().lower())


def stem_hash(stem: str) -> str:
    return hashlib.sha256(normalize_stem(stem).encode()).hexdigest()


def diagram_sha256(svg: str) -> str:
    return hashlib.sha256((svg or "").encode("utf-8")).hexdigest()


def legacy_to_question_body(record: dict[str, Any]) -> dict[str, Any]:
    """Map legacy JSON row → TALOS QuestionBody dict (no diagram fields on body)."""
    opts = record["options"]
    return {
        "stem": record["question"].strip(),
        "options": [
            {"label": "A", "text": str(opts["A"]).strip()},
            {"label": "B", "text": str(opts["B"]).strip()},
            {"label": "C", "text": str(opts["C"]).strip()},
            {"label": "D", "text": str(opts["D"]).strip()},
        ],
        "correct_option": str(record["correct_answer"]).strip().upper(),
        "explanation": record["explanation"].strip(),
        "difficulty": record["difficulty"],
    }


def build_provenance_tags(record: dict[str, Any], *, diagram_status: str, diagram_hash: str | None) -> list[str]:
    chapter_id = int(record["chapter_id"])
    chap = LEGACY_CHAPTER_MAP.get(chapter_id)
    tags = [
        BATCH_ID,
        f"legacy_id:{record['id']}",
        f"source:algorithmic",
        f"legacy_chapter_id:{chapter_id}",
        f"legacy_chapter_title:{record['chapter_title']}",
        f"legacy_topic:{record['topic']}",
        f"legacy_question_type:{record.get('question_type', '')}",
        "class:11",
        "subject:physics",
        "alignment:ncert-class-11-physics-legacy-bank",
        "ecaep:intake-draft-only",
        f"legacy_source_ref:{LEGACY_SOURCE_REF}",
    ]
    if chap:
        tags.append(f"mapping_confidence:{chap.confidence}")
        if chap.talos_chapter_code:
            tags.append(f"talos_chapter:{chap.talos_chapter_code}")
        else:
            tags.append("talos_chapter:UNRESOLVED")
    if record.get("generation_seed") is not None:
        tags.append(f"generation_seed:{record['generation_seed']}")
    tags.append(f"legacy_diagram_status:{diagram_status}")
    if diagram_hash:
        tags.append(f"legacy_diagram_sha256:{diagram_hash}")
    if record.get("diagram_subtype"):
        tags.append(f"legacy_diagram_subtype:{record['diagram_subtype']}")
    return tags
