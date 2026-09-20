"""STEP 1 — local NCERT corpus inventory.

Subject/class are derived from the verified on-disk directory structure
(NCERT Books/Class <11|12>/<Physics|Chemistry|Biology>/...), not from
filename prefixes alone — a stronger, independently-checkable signal than
"keph101.pdf looks like physics". page_count/checksum come from opening
the actual PDF (PyMuPDF), so "verified" reflects a real, local file open,
not a guess.
"""

from __future__ import annotations

import hashlib
import json

from .config import MANIFEST_PATH, NCERT_ROOT, SUBJECT_DIR_MAP


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest() -> dict:
    import fitz  # local import — PDF parsing only, no network

    files = []
    for pdf_path in sorted(NCERT_ROOT.rglob("*.pdf")):
        rel = pdf_path.relative_to(NCERT_ROOT)
        parts = rel.parts
        class_level = None
        subject = None
        for part in parts:
            if part.lower().startswith("class "):
                class_level = part.split()[-1].strip()
            low = part.lower()
            # "Chemistry 1" / "Chemistry 2" (Class 12's two-volume split) are
            # still just "Chemistry" — strip a trailing " <digit>" before
            # matching rather than requiring an exact directory-name match.
            low_base = low.rsplit(" ", 1)[0] if low.rsplit(" ", 1)[-1].isdigit() else low
            if low_base in SUBJECT_DIR_MAP:
                subject = SUBJECT_DIR_MAP[low_base]
        verified = subject is not None and class_level is not None

        try:
            doc = fitz.open(str(pdf_path))
            page_count = doc.page_count
            doc.close()
            extractable = page_count > 0
        except Exception:  # noqa: BLE001
            page_count = 0
            extractable = False

        files.append(
            {
                "path": str(pdf_path),
                "filename": pdf_path.name,
                "subject": subject,
                "class": class_level,
                "book_chapter_id": pdf_path.stem,
                "page_count": page_count,
                "extraction_method": "pymupdf_local",
                "text_extractable": extractable,
                "checksum_sha256": _sha256(pdf_path),
                "verified": verified,
            }
        )

    manifest = {
        "generated_by": "pyq_subject_classifier.ncert_manifest",
        "ncert_root": str(NCERT_ROOT),
        "file_count": len(files),
        "verified_count": sum(1 for f in files if f["verified"]),
        "unverified_count": sum(1 for f in files if not f["verified"]),
        "files": files,
    }
    return manifest


def load_or_build_manifest(force: bool = False) -> dict:
    if MANIFEST_PATH.exists() and not force:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    manifest = build_manifest()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest
