"""Build compact pack from verify-002 scratch for review."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
scratch = json.loads((ROOT / "docs/audits/_mcq_ncert_verify_002_scratch.json").read_text(encoding="utf-8"))
compact = []
for i, it in enumerate(scratch["items"], 1):
    m = it["mcq"]
    opts = {o["key"]: o["text"] for o in m["options"]}
    pages = it.get("ncert_excerpt", {}).get("pages", {})
    excerpt_parts = []
    for k in sorted(pages, key=lambda x: int(x)):
        excerpt_parts.append(f"---PDF p.{k}---\n{pages[k]}")
    excerpt = "\n".join(excerpt_parts)
    compact.append(
        {
            "idx": i,
            "candidate_id": it["candidate_id"],
            "content_item_id": it["content_item_id"],
            "subject": it["subject"],
            "concept": it["concept"],
            "chapter": it["chapter"],
            "topic": it["topic"],
            "syllabus": it["syllabus_mapping"],
            "pdf": it["ncert_relative"],
            "ncert_source_path": it["ncert_source_path"],
            "pages": it["evidence_pages"],
            "stem": m["stem"],
            "options": opts,
            "correct": m["correct_option"],
            "explanation": m["explanation"],
            "excerpt": excerpt[:12000],
        }
    )

out = ROOT / "docs/audits/_mcq_ncert_verify_002_compact.json"
out.write_text(json.dumps(compact, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {out} items={len(compact)}")
for c in compact:
    print(f"{c['idx']:02d} {c['subject']} ans={c['correct']} concept={c['concept']}")
