"""Explicit, human-approved NCERT → academic chapter mappings (ADR-0031).

Keys use filesystem/source subject codes (PHYSICS/CHEMISTRY/BIOLOGY) plus
class level and NCERT chapter number. Values use academic subject codes
(PHYSICS/CHEMISTRY/BOTANY/ZOOLOGY) and existing chapter slugs from seed.

Do NOT add entries unless the academic chapter already exists in seed and the
mapping is auditable. Missing entries remain UNMAPPED — never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

# (source_subject_code, class_level, ncert_chapter_number)
RegistryKey = tuple[str, str, int]


@dataclass(frozen=True)
class AcademicChapterRef:
    academic_subject_code: str
    chapter_code: str
    note: str = ""


# Pilot + explicitly approved mappings only.
EXPLICIT_NCERT_MAPPINGS: dict[RegistryKey, AcademicChapterRef] = {
    # Physics pilot — Class 12 NCERT Ch 3 → current-electricity
    ("PHYSICS", "12", 3): AcademicChapterRef(
        "PHYSICS",
        "current-electricity",
        "Pilot Physics source (ADR-0022/0031)",
    ),
    # Chemistry pilot — Class 11 NCERT Ch 4 → chemical-bonding
    ("CHEMISTRY", "11", 4): AcademicChapterRef(
        "CHEMISTRY",
        "chemical-bonding",
        "Pilot Chemistry source",
    ),
    # Biology pilot — Class 11 NCERT file chapter-11.pdf contains
    # "PHOTOSYNTHESIS IN HIGHER PLANTS" (verified Phase B.1). Do NOT map
    # chapter-13.pdf (Plant Growth) to photosynthesis.
    ("BIOLOGY", "11", 11): AcademicChapterRef(
        "BOTANY",
        "photosynthesis",
        "Pilot Biology (Botany) — corpus chapter-11.pdf = Photosynthesis",
    ),
    # Biology pilot — explicit Zoology mapping (Class 11 NCERT Ch 18)
    ("BIOLOGY", "11", 18): AcademicChapterRef(
        "ZOOLOGY",
        "body-fluids-circulation",
        "Pilot Biology (Zoology) alternative source",
    ),
}

# Chapters with fully seeded topic/concept trees — used for pilot_ready flag.
# pilot_ready also requires PDF content preflight (see SourceAcademicMappingService).
PILOT_CHAPTER_CODES: frozenset[str] = frozenset(
    {
        "current-electricity",
        "chemical-bonding",
        "photosynthesis",
        "body-fluids-circulation",
    }
)

# Documented pilot source selection for Phase D (relative path suffixes).
PILOT_SOURCE_RELATIVE_PATHS: frozenset[str] = frozenset(
    {
        "Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf",
        "Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf",
        "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf",
    }
)


def lookup_explicit_mapping(
    *,
    source_subject_code: str,
    class_level: str,
    ncert_chapter_number: int | None,
) -> AcademicChapterRef | None:
    if ncert_chapter_number is None:
        return None
    return EXPLICIT_NCERT_MAPPINGS.get((source_subject_code, class_level, ncert_chapter_number))
