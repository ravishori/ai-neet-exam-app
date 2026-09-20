"""Phase 2 — chapter-level index built from the ALREADY-cached Phase 1 page
text (data/ncert/index/<book_chapter_id>.json). Never re-opens/re-parses a
PDF — reuses ncert_extract's on-disk cache directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.modules.knowledge.services.grounding_check import _significant_words

from .config import INDEX_DIR
from .normalize import normalize_text

PHASE2_CHAPTER_CACHE = INDEX_DIR / "phase2_chapter_index.json"


@dataclass
class ChapterEntry:
    chapter_id: str
    subject: str
    book: str
    class_level: str | None
    words: set  # significant words present anywhere in this chapter
    normalized_text: str  # concatenated normalized page text, for exact-phrase search


@dataclass
class Phase2Index:
    chapters: dict = field(default_factory=dict)  # chapter_id -> ChapterEntry

    def chapters_for_subject(self, subject: str):
        return [c for c in self.chapters.values() if c.subject == subject]


def build_phase2_index(manifest: dict, force: bool = False) -> Phase2Index:
    if PHASE2_CHAPTER_CACHE.exists() and not force:
        with open(PHASE2_CHAPTER_CACHE, encoding="utf-8") as f:
            raw = json.load(f)
        idx = Phase2Index()
        for cid, entry in raw.items():
            idx.chapters[cid] = ChapterEntry(
                chapter_id=cid, subject=entry["subject"], book=entry["book"],
                class_level=entry["class"], words=set(entry["words"]), normalized_text=entry["normalized_text"],
            )
        return idx

    idx = Phase2Index()
    cache_out = {}
    for entry in manifest["files"]:
        if not entry["verified"] or not entry["text_extractable"]:
            continue
        cache_path = INDEX_DIR / f"{entry['book_chapter_id']}.json"
        if not cache_path.exists():
            continue  # Phase 1 index missing for this file — skip, don't re-extract.
        with open(cache_path, encoding="utf-8") as f:
            pages = json.load(f)["pages"]
        full_text = normalize_text(" ".join(pages))
        words = _significant_words(full_text)
        chapter_id = entry["book_chapter_id"]
        idx.chapters[chapter_id] = ChapterEntry(
            chapter_id=chapter_id, subject=entry["subject"], book=entry["filename"],
            class_level=entry["class"], words=words, normalized_text=full_text,
        )
        cache_out[chapter_id] = {
            "subject": entry["subject"], "book": entry["filename"], "class": entry["class"],
            "words": sorted(words), "normalized_text": full_text,
        }

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(PHASE2_CHAPTER_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache_out, f)
    return idx
