"""Phase 3 — page-level NCERT index, reusing the SAME cached page-text
JSON files Phase 1 already produced (data/ncert/index/<chapter>.json).
Never re-opens a PDF. This adds real page numbers to evidence (PART G) —
previously Phase 2 only tracked whole-chapter provenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .config import INDEX_DIR
from .normalize import normalize_text

PHASE3_PAGE_CACHE = INDEX_DIR / "phase3_page_index.json"


@dataclass
class PageEntry:
    chapter_id: str
    subject: str
    book: str
    page_number: int  # 1-based
    normalized_text: str


@dataclass
class Phase3Index:
    pages: list = field(default_factory=list)

    def pages_for_subject(self, subject: str):
        return [p for p in self.pages if p.subject == subject]


def build_phase3_index(manifest: dict, force: bool = False) -> Phase3Index:
    if PHASE3_PAGE_CACHE.exists() and not force:
        with open(PHASE3_PAGE_CACHE, encoding="utf-8") as f:
            raw = json.load(f)
        idx = Phase3Index()
        idx.pages = [PageEntry(**p) for p in raw]
        return idx

    idx = Phase3Index()
    cache_out = []
    for entry in manifest["files"]:
        if not entry["verified"] or not entry["text_extractable"]:
            continue
        cache_path = INDEX_DIR / f"{entry['book_chapter_id']}.json"
        if not cache_path.exists():
            continue  # reuse only — never re-extract
        with open(cache_path, encoding="utf-8") as f:
            pages = json.load(f)["pages"]
        for page_no, page_text in enumerate(pages, start=1):
            norm = normalize_text(page_text)
            if not norm:
                continue
            page_entry = PageEntry(
                chapter_id=entry["book_chapter_id"], subject=entry["subject"],
                book=entry["filename"], page_number=page_no, normalized_text=norm,
            )
            idx.pages.append(page_entry)
            cache_out.append(vars(page_entry))

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(PHASE3_PAGE_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache_out, f)
    return idx
