"""Chapter content markers for StudyMaterial → academic mapping preflight.

Filename/NCERT chapter numbers in the on-disk corpus can drift from the
academic chapter they are mapped to. Before marking a source pilot-ready
(or starting pilot generation), the PDF body must contain markers for the
mapped academic chapter. This is a mechanical text check — not AI.

Markers are OR'd within a chapter: any one match is enough.
"""

from __future__ import annotations

from pathlib import Path

from app.modules.ingestion.services.pdf_extraction_service import extract_pages

# Preview enough early pages to catch chapter titles without scanning full PDFs.
_CONTENT_PREVIEW_PAGES = 8

# Academic chapter_code → distinctive phrases that must appear in the PDF body.
CHAPTER_CONTENT_MARKERS: dict[str, tuple[str, ...]] = {
    "current-electricity": ("ELECTRIC CURRENT", "CURRENT ELECTRICITY"),
    "chemical-bonding": ("CHEMICAL BOND", "ELECTROVALENT", "OCTET RULE"),
    "photosynthesis": ("PHOTOSYNTHESIS IN HIGHER PLANTS",),
    "body-fluids-circulation": ("BODY FLUIDS AND CIRCULATION", "BLOOD", "CIRCULATORY SYSTEM"),
}


def pdf_content_matches_chapter(file_path: str | Path, chapter_code: str) -> bool:
    """True when the PDF body matches the mapped academic chapter markers."""
    markers = CHAPTER_CONTENT_MARKERS.get(chapter_code)
    if not markers:
        # No markers configured — do not invent a pass; caller treats as not content-verified.
        return False
    path = Path(file_path)
    if not path.is_file():
        return False
    preview = " ".join(extract_pages(str(path))[:_CONTENT_PREVIEW_PAGES]).upper()
    return any(marker.upper() in preview for marker in markers)


def content_mismatch_detail(file_path: str | Path, chapter_code: str) -> str:
    markers = CHAPTER_CONTENT_MARKERS.get(chapter_code) or ()
    return (
        f"PDF content does not match academic chapter '{chapter_code}' "
        f"(required markers: {', '.join(markers) or 'none configured'}): {file_path}"
    )
