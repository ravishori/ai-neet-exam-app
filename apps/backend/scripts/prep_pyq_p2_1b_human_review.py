"""P2.1B-HR: prepare human fidelity review pack (no DB/OCR/AI)."""
from __future__ import annotations

import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import fitz

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
STAGING = ROOT / "data" / "staging" / "pyq" / "2020-2025"
ZIP_PATH = ROOT / "NEET_PYQ_OFFICIAL.zip"
OUT = STAGING / "human_review_p2_1b"
OUT.mkdir(exist_ok=True)


def load_all_records() -> list[dict]:
    recs = []
    for d in sorted((STAGING / "papers").iterdir()):
        qp = d / "questions.p2_1_resegmented.jsonl"
        if not qp.exists():
            continue
        for line in qp.open(encoding="utf-8"):
            if line.strip():
                recs.append(json.loads(line))
    return recs


def is_fragment(r: dict) -> bool:
    stem = (r.get("stem") or "").strip()
    opts = any((r.get(k) or "").strip() for k in ("option_a", "option_b", "option_c", "option_d"))
    if len(stem) < 20 and not opts:
        return True
    if re.fullmatch(r"[\(\)\s1-4A-Dabcd\.\-]+", stem or ""):
        return True
    return False


def find_full_record(recs: list[dict], sample: dict) -> dict | None:
    sha = sample.get("source_sha256")
    qn = sample.get("question_number")
    page = sample.get("source_page")
    preview = (sample.get("stem_preview") or "")[:40]
    for r in recs:
        if r.get("source_sha256") != sha:
            continue
        if r.get("question_number") != qn:
            continue
        if page is not None and r.get("source_page") != page:
            continue
        if preview and preview not in (r.get("stem") or ""):
            # soft match
            if not (r.get("stem") or "").startswith(preview[:20]):
                continue
        return r
    # fallback by sha+qn only
    for r in recs:
        if r.get("source_sha256") == sha and r.get("question_number") == qn:
            return r
    return None


def main() -> None:
    samples = json.loads((STAGING / "samples.p2_1b.json").read_text(encoding="utf-8"))
    recs = load_all_records()
    by_sha = defaultdict(list)
    for r in recs:
        by_sha[r.get("source_sha256")].append(r)

    # Enrich samples with full fields
    enriched = {}
    render_jobs = []
    for bucket, items in samples.items():
        enriched[bucket] = []
        for it in items:
            full = find_full_record(recs, it) or {}
            row = {
                **it,
                "stem_full": (full.get("stem") or it.get("stem_preview") or "")[:500],
                "option_a": (full.get("option_a") or "")[:120],
                "option_b": (full.get("option_b") or "")[:120],
                "option_c": (full.get("option_c") or "")[:120],
                "option_d": (full.get("option_d") or "")[:120],
                "raw_preview": (full.get("raw_extracted_text") or "")[:300],
                "duplicate_within_paper": full.get("duplicate_within_paper"),
                "staging_id": full.get("staging_id"),
                "source_file": full.get("source_file") or it.get("source_file"),
            }
            enriched[bucket].append(row)
            if row.get("source_file") and row.get("source_page"):
                render_jobs.append(
                    (
                        row["source_file"],
                        row["source_sha256"],
                        row["source_page"],
                        f"{bucket}_q{row.get('question_number')}_p{row.get('source_page')}",
                    )
                )

    dups = [r for r in recs if r.get("duplicate_within_paper")]
    frags = [r for r in recs if is_fragment(r)]

    # Group duplicates by normalized hash within paper
    dup_groups = defaultdict(list)
    for r in dups:
        dup_groups[(r.get("source_sha256"), r.get("normalized_question_hash"))].append(r)

    dup_export = []
    for (sha, nh), items in dup_groups.items():
        dup_export.append(
            {
                "source_sha256": sha,
                "source_file": items[0].get("source_file"),
                "normalized_question_hash": nh,
                "count": len(items),
                "members": [
                    {
                        "question_number": x.get("question_number"),
                        "source_page": x.get("source_page"),
                        "stem_preview": (x.get("stem") or "")[:160],
                        "options_filled": sum(
                            1
                            for k in ("option_a", "option_b", "option_c", "option_d")
                            if (x.get(k) or "").strip()
                        ),
                        "quality": x.get("p2_1b_quality_status"),
                    }
                    for x in items
                ],
            }
        )

    frag_export = []
    for r in frags:
        stem = (r.get("stem") or "").strip()
        kind = "short_stem"
        if re.fullmatch(r"[\(\)\s1-4A-Dabcd\.\-]+", stem or ""):
            kind = "option_marker_only"
        elif not stem:
            kind = "empty_stem"
        frag_export.append(
            {
                "kind_heuristic": kind,
                "source_file": r.get("source_file"),
                "source_sha256": r.get("source_sha256"),
                "question_number": r.get("question_number"),
                "source_page": r.get("source_page"),
                "quality": r.get("p2_1b_quality_status"),
                "stem": stem[:200],
                "options_filled": sum(
                    1 for k in ("option_a", "option_b", "option_c", "option_d") if (r.get(k) or "").strip()
                ),
            }
        )

    (OUT / "samples_enriched.json").write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "hash_duplicates.json").write_text(json.dumps(dup_export, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "fragment_candidates.json").write_text(json.dumps(frag_export, indent=2, ensure_ascii=False), encoding="utf-8")

    # Render unique pages needed for sample review + first 15 dup pages + first 15 frag pages
    render_dir = OUT / "renders"
    render_dir.mkdir(exist_ok=True)
    jobs = []
    seen_pages = set()
    for job in render_jobs:
        key = (job[1], job[2])
        if key in seen_pages:
            continue
        seen_pages.add(key)
        jobs.append(job)
    for g in dup_export[:20]:
        for m in g["members"][:2]:
            key = (g["source_sha256"], m["source_page"])
            if key not in seen_pages and m["source_page"]:
                seen_pages.add(key)
                jobs.append((g["source_file"], g["source_sha256"], m["source_page"], f"dup_p{m['source_page']}"))
    for f in frag_export[:25]:
        key = (f["source_sha256"], f["source_page"])
        if key not in seen_pages and f["source_page"]:
            seen_pages.add(key)
            jobs.append((f["source_file"], f["source_sha256"], f["source_page"], f"frag_q{f['question_number']}_p{f['source_page']}"))

    print("render jobs", len(jobs))
    with zipfile.ZipFile(ZIP_PATH) as zf:
        cache = {}
        for i, (rel, sha, page, label) in enumerate(jobs[:80]):
            if rel not in cache:
                cache[rel] = zf.read(rel)
            doc = fitz.open(stream=cache[rel], filetype="pdf")
            if page < 1 or page > doc.page_count:
                doc.close()
                continue
            pix = doc.load_page(page - 1).get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
            name = f"{i:03d}_{sha[:8]}_p{page}_{label[:40]}.png"
            (render_dir / name).write_bytes(pix.tobytes("png"))
            # OCR page text snippet for side-by-side
            paper_dir = STAGING / "papers" / sha
            ocr_snip = ""
            pages_path = paper_dir / "ocr.pages.p2_1.jsonl"
            if pages_path.exists():
                for line in pages_path.open(encoding="utf-8"):
                    p = json.loads(line)
                    if p.get("page_number") == page:
                        ocr_snip = (p.get("raw_text") or "")[:1200]
                        break
            (render_dir / name.replace(".png", ".txt")).write_text(
                f"file={rel}\npage={page}\nlabel={label}\n\nOCR:\n{ocr_snip}\n",
                encoding="utf-8",
            )
            doc.close()

    print("dups groups", len(dup_export), "dup records", len(dups))
    print("frags", len(frags))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
