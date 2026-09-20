"""Probe resegmentation yield on existing OCR text (no re-OCR, no writes)."""
from __future__ import annotations

import json
from pathlib import Path

from app.modules.cms.pyq.pyq_p2_1 import extract_questions_from_ocr

ROOT = Path(r"D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025\papers")


def main() -> None:
    totals_old = 0
    totals_new = 0
    samples = []
    for d in sorted(ROOT.iterdir()):
        qp = d / "questions.p2_1.jsonl"
        pages = d / "ocr.pages.p2_1.jsonl"
        if not qp.exists() or not pages.exists():
            continue
        meta = json.loads((d / "paper.json").read_text(encoding="utf-8"))
        old = sum(1 for line in qp.open(encoding="utf-8") if line.strip())
        chunks = []
        for line in pages.open(encoding="utf-8"):
            p = json.loads(line)
            chunks.append("<<<PAGE:%s>>>\n%s" % (p["page_number"], p.get("raw_text") or ""))
        corpus = "\n".join(chunks)
        new = extract_questions_from_ocr(
            corpus=corpus,
            meta=meta,
            ocr_meta={"dpi": 200, "tesseract_version": "probe"},
        )
        totals_old += old
        totals_new += len(new)
        samples.append((Path(meta["source_file"]).name, old, len(new)))

    print("papers", len(samples))
    print("old_total", totals_old, "new_total", totals_new, "delta", totals_new - totals_old)
    for name, old, new in sorted(samples, key=lambda x: -(x[2] - x[1]))[:8]:
        print(f"gain {new-old:+d}  old={old} new={new}  {name}")
    for name, old, new in sorted(samples, key=lambda x: (x[2] - x[1]))[:5]:
        print(f"flat/loss {new-old:+d}  old={old} new={new}  {name}")


if __name__ == "__main__":
    main()
