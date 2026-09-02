"""T6-F1 Physics 1,000-candidate pilot — staging only; never touch legacy-5000."""

from __future__ import annotations

BATCH_ID = "physics-t6f1-pilot-20260902"
T6D_BATCH_ID = "physics-t6d-pilot-20260902"
MODEL_USED = "t6f1-parametric"  # ≤20 chars
PROMPT_VERSION = "t6f1-20260902-v1"  # ≤20 chars
LEGACY_BATCH = "legacy-physics-5000-import-20260902"
TARGET_CANDIDATES = 1000
CHUNK_SIZE = 50  # persistence chunk size

STUDY_MATERIAL_PHYSICS_XI = "StudyMaterial/Physics/Class 11-Physics"

NCERT_XI_CHAPTER_PDF: dict[int, str] = {
    1: "ncert-books-class-11-physics-chapter-1.pdf",
    2: "ncert-books-class-11-physics-chapter-2.pdf",
    3: "ncert-books-class-11-physics-chapter-3.pdf",
    4: "ncert-books-class-11-physics-chapter-4.pdf",
    5: "ncert-books-class-11-physics-chapter-5.pdf",
    6: "ncert-books-class-11-physics-chapter-6.pdf",
    8: "ncert-books-class-11-physics-chapter-8.pdf",
    9: "ncert-books-class-11-physics-chapter-9.pdf",
    11: "ncert-books-class-11-physics-chapter-11.pdf",
    12: "ncert-books-class-11-physics-chapter-12.pdf",
}


def pilot_slug(seq: int) -> str:
    return f"{BATCH_ID}-q{seq:04d}"


def pilot_id(seq: int) -> str:
    return f"t6f1-{seq:04d}"
