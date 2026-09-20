"""STEP 3 — build a deterministic per-subject term index from the local
NCERT corpus (built once, reused for every question — no re-parsing).

Subject-EXCLUSIVE vocabulary (present in one subject's NCERT text but not
the other two) is the core signal: a word like "energy" appears across
Physics AND Chemistry NCERT books, so it is correctly excluded from both
exclusive sets rather than counted as evidence for either — this is the
direct, mechanical fix for the "matches merely because a word appears"
failure mode called out in the task.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field

from app.modules.knowledge.services.grounding_check import _significant_words

from .config import INDEX_DIR
from .ncert_extract import extract_book_text

INDEX_CACHE_PATH = INDEX_DIR / "subject_term_index.json"


@dataclass
class SubjectTermIndex:
    # word -> subject -> count of (book,page) occurrences
    word_subject_counts: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    # subject -> set of words exclusive to that subject
    exclusive_words: dict[str, set[str]] = field(default_factory=dict)
    # word -> best evidence citation {subject, book, chapter, page}
    word_evidence: dict[str, dict] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "word_subject_counts": {w: dict(s) for w, s in self.word_subject_counts.items()},
            "exclusive_words": {s: sorted(w) for s, w in self.exclusive_words.items()},
            "word_evidence": self.word_evidence,
        }

    @classmethod
    def from_json(cls, data: dict) -> SubjectTermIndex:
        idx = cls()
        idx.word_subject_counts = defaultdict(lambda: defaultdict(int))
        for w, s in data["word_subject_counts"].items():
            for subj, c in s.items():
                idx.word_subject_counts[w][subj] = c
        idx.exclusive_words = {s: set(w) for s, w in data["exclusive_words"].items()}
        idx.word_evidence = data["word_evidence"]
        return idx


def build_index(manifest: dict, force: bool = False) -> SubjectTermIndex:
    if INDEX_CACHE_PATH.exists() and not force:
        with open(INDEX_CACHE_PATH, encoding="utf-8") as f:
            return SubjectTermIndex.from_json(json.load(f))

    idx = SubjectTermIndex()
    for entry in manifest["files"]:
        if not entry["verified"] or not entry["text_extractable"]:
            continue
        subject = entry["subject"]
        pages = extract_book_text(entry["path"], cache_key=entry["book_chapter_id"])
        for page_no, page_text in enumerate(pages, start=1):
            words = _significant_words(page_text)
            for w in words:
                idx.word_subject_counts[w][subject] += 1
                if w not in idx.word_evidence:
                    idx.word_evidence[w] = {
                        "subject": subject,
                        "book": entry["filename"],
                        "chapter": entry["book_chapter_id"],
                        "class": entry["class"],
                        "page": page_no,
                    }

    for subject in ("Physics", "Chemistry", "Biology"):
        idx.exclusive_words[subject] = {
            w for w, counts in idx.word_subject_counts.items()
            if counts.get(subject, 0) > 0 and all(
                counts.get(other, 0) == 0 for other in ("Physics", "Chemistry", "Biology") if other != subject
            )
        }

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(idx.to_json(), f)
    return idx
