"""Step 6 of FACTORY-PYQPDF-20261018: split each full extraction output
into incremental batch files (never overwriting the full-run JSON
produced by the extractors themselves).

Batching choice (documented, not arbitrary):
  - 33-years-Biology (3331 records across 38 chapters, ~485 pages): one
    batch file PER CHAPTER. Chapters are this book's own natural content
    boundary (each is independently a complete question+answer set, 12
    to 188 questions / roughly 10-20 pages each), which reads far more
    usefully as a resumable unit than an arbitrary "every 50 pages" cut
    that would sometimes split a chapter's questions from its own
    answer key.
  - neet_pyp_2025 (179 records, one 34-page exam paper): a SINGLE batch
    file, "per book" granularity -- the whole file is one coherent exam
    paper with global 1-180 numbering; there is no natural sub-boundary
    smaller than the whole paper worth splitting on.

No AI/LLM calls. No database writes. Read-only except for writing the
batch files themselves under data/extracted_mcqs/.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.pyq_pdf_extract.common import now_iso, write_json

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BOOK1_DIR = BACKEND_ROOT / "data" / "extracted_mcqs" / "33years_biology_2020"
BOOK2_DIR = BACKEND_ROOT / "data" / "extracted_mcqs" / "neet_pyp_2025"


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return s[:60]


def split_book1() -> dict:
    records = json.loads((BOOK1_DIR / "questions_full.json").read_text(encoding="utf-8"))
    manifest = json.loads((BOOK1_DIR / "manifest_full.json").read_text(encoding="utf-8"))
    toc_order = manifest["toc_chapter_names"]
    by_chapter: dict[str, list[dict]] = {}
    for r in records:
        by_chapter.setdefault(r["chapter"], []).append(r)

    batch_dir = BOOK1_DIR / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for i, chapter_name in enumerate(toc_order, start=1):
        chapter_records = by_chapter.get(chapter_name, [])
        fname = f"chapter_{i:02d}_{_slug(chapter_name)}.json"
        write_json(batch_dir / fname, chapter_records)
        index.append({
            "batch_number": i,
            "chapter": chapter_name,
            "file": f"batches/{fname}",
            "question_count": len(chapter_records),
            "answer_known": sum(1 for r in chapter_records if r["answer_raw"]),
            "needs_review": sum(1 for r in chapter_records if r["extraction_status"] == "NEEDS_REVIEW"),
        })
    index_doc = {
        "generated_at": now_iso(),
        "source_questions_file": "questions_full.json",
        "batching_strategy": "one batch file per chapter (this book's own natural content boundary)",
        "total_batches": len(index),
        "total_questions": sum(b["question_count"] for b in index),
        "batches": index,
    }
    write_json(batch_dir / "batch_index.json", index_doc)
    return index_doc


def split_book2() -> dict:
    records = json.loads((BOOK2_DIR / "questions_full.json").read_text(encoding="utf-8"))
    batch_dir = BOOK2_DIR / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    fname = "batch_001_full_paper.json"
    write_json(batch_dir / fname, records)
    index_doc = {
        "generated_at": now_iso(),
        "source_questions_file": "questions_full.json",
        "batching_strategy": "single batch, per-book granularity (one coherent 180-question exam paper)",
        "total_batches": 1,
        "total_questions": len(records),
        "batches": [{
            "batch_number": 1, "file": f"batches/{fname}", "question_count": len(records),
            "answer_known": sum(1 for r in records if r["answer_raw"]),
            "needs_review": sum(1 for r in records if r["extraction_status"] == "NEEDS_REVIEW"),
        }],
    }
    write_json(batch_dir / "batch_index.json", index_doc)
    return index_doc


def main() -> None:
    b1 = split_book1()
    b2 = split_book2()
    print(f"book1: {b1['total_batches']} batches, {b1['total_questions']} questions")
    print(f"book2: {b2['total_batches']} batches, {b2['total_questions']} questions")


if __name__ == "__main__":
    main()
