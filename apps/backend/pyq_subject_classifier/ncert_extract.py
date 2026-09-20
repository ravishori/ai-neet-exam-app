"""STEP 2 — extract NCERT text once, cache per-book page text to disk.

Each NCERT file in this corpus is already split one-file-per-chapter, so
"book" == "chapter" for indexing purposes here; page numbers are preserved
for evidence citations.
"""

from __future__ import annotations

import json

from .config import INDEX_DIR


def extract_book_text(pdf_path: str, cache_key: str, force: bool = False) -> list[str]:
    """Returns a list of page texts (index 0 = page 1). Cached to
    data/ncert/index/<cache_key>.json so PDFs are parsed at most once."""
    cache_path = INDEX_DIR / f"{cache_key}.json"
    if cache_path.exists() and not force:
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)["pages"]

    import fitz

    doc = fitz.open(pdf_path)
    pages = [doc[i].get_text("text") or "" for i in range(doc.page_count)]
    doc.close()

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"pdf_path": pdf_path, "pages": pages}, f)
    return pages
