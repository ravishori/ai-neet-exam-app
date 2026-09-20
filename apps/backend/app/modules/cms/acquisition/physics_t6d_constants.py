"""T6-D Physics content pilot constants — NEW questions only; never touch legacy-5000."""

from __future__ import annotations

BATCH_ID = "physics-t6d-pilot-20260902"
MODEL_USED = "t6d-ncert-curated"  # ≤20 chars (cms.content_versions.model_used)
PROMPT_VERSION = "t6d-20260902-v1"  # ≤20 chars
LEGACY_BATCH = "legacy-physics-5000-import-20260902"
# Soft ceiling — quality > quantity; do not pad to fill (T6-E-FIX)
MAX_CANDIDATES = 100
TARGET_CANDIDATES = MAX_CANDIDATES  # back-compat alias

STUDY_MATERIAL_PHYSICS_XI = "StudyMaterial/Physics/Class 11-Physics"

# NCERT XI chapter number → PDF filename under STUDY_MATERIAL_PHYSICS_XI
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
    return f"{BATCH_ID}-q{seq:03d}"


def pilot_id(seq: int) -> str:
    return f"t6d-{seq:03d}"
