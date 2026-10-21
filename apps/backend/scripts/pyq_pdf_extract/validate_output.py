"""Validation pass (FACTORY-PYQPDF-20261018, Step 7) over the two full
extraction outputs: JSON syntax, required-field completeness, option
integrity, exact-duplicate detection (within and across both files, and
a cheap cross-check against the existing sweatSmile external-acquisition
biology Q&A sample), and near-duplicate flagging (review-only -- never
auto-merged/auto-deleted, per the task's explicit constraint).

No AI/LLM calls. No database writes. No network calls. Read-only with
respect to every input file.
"""
from __future__ import annotations

import difflib
import json
from collections import defaultdict
from pathlib import Path

from scripts.pyq_pdf_extract.common import normalize_for_dedup, now_iso, write_json

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BOOK1_QUESTIONS = BACKEND_ROOT / "data" / "extracted_mcqs" / "33years_biology_2020" / "questions_full.json"
BOOK2_QUESTIONS = BACKEND_ROOT / "data" / "extracted_mcqs" / "neet_pyp_2025" / "questions_full.json"
SWEATSMILE_JSONL = BACKEND_ROOT / "data" / "generated_mcqs" / "external_acquisition" / "sweatsmile_neet_biology_qa_v1.jsonl"
OUT_DIR = BACKEND_ROOT / "docs" / "quality"


def load_records(path: Path, source_label: str) -> list[dict]:
    recs = json.loads(path.read_text(encoding="utf-8"))
    for r in recs:
        r["_source_label"] = source_label
    return recs


def required_field_report(records: list[dict]) -> dict:
    fields = ["stem_text", "options", "answer_raw", "explanation_text", "subject", "chapter", "topic"]
    out = {}
    for f in fields:
        n_null = sum(1 for r in records if not r.get(f))
        out[f] = {"null_or_empty": n_null, "present": len(records) - n_null, "pct_present": round(100 * (len(records) - n_null) / len(records), 2) if records else 0}
    return out


def option_integrity_report(records: list[dict]) -> dict:
    counts = defaultdict(int)
    empty_option_records = 0
    for r in records:
        opts = r.get("options")
        n = len(opts) if opts else 0
        counts[n] += 1
        if opts and any(not (o.get("text") or "").strip() for o in opts):
            empty_option_records += 1
    return {"by_option_count": dict(counts), "records_with_at_least_one_empty_option_text": empty_option_records}


def exact_duplicate_report(all_records: list[dict]) -> dict:
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for r in all_records:
        key_text = normalize_for_dedup(r.get("stem_text")) + "||" + "|".join(
            normalize_for_dedup(o.get("text")) for o in (r.get("options") or [])
        )
        if not normalize_for_dedup(r.get("stem_text")):
            continue
        by_hash[key_text].append(r)
    dupe_groups = {k: v for k, v in by_hash.items() if len(v) > 1}
    within_33years = sum(1 for v in dupe_groups.values() if len({x["_source_label"] for x in v}) == 1 and v[0]["_source_label"] == "33years_biology_2020")
    within_pyp = sum(1 for v in dupe_groups.values() if len({x["_source_label"] for x in v}) == 1 and v[0]["_source_label"] == "neet_pyp_2025")
    cross_file = sum(1 for v in dupe_groups.values() if len({x["_source_label"] for x in v}) > 1)
    sample = []
    for k, v in list(dupe_groups.items())[:25]:
        sample.append({
            "ids": [x["id"] for x in v],
            "sources": [f"{x['_source_label']}#{x['question_number_raw']}" for x in v],
            "stem_preview": (v[0].get("stem_text") or "")[:120],
        })
    return {
        "exact_duplicate_groups_total": len(dupe_groups),
        "exact_duplicate_groups_within_33years": within_33years,
        "exact_duplicate_groups_within_pyp": within_pyp,
        "exact_duplicate_groups_cross_file": cross_file,
        "exact_duplicate_records_total": sum(len(v) for v in dupe_groups.values()),
        "sample": sample,
    }


def near_duplicate_report(all_records: list[dict], *, bucket_len: int = 20, ratio_threshold: float = 0.88, max_pairs_per_bucket: int = 4000) -> dict:
    """Bounded near-duplicate scan: bucket by the first `bucket_len` chars
    of the normalized stem (so comparisons stay near-linear rather than a
    full O(n^2) sweep over ~3500 records), then pairwise difflib ratio
    within each bucket only. Review-only output -- flags candidate pairs,
    never merges or deletes anything."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in all_records:
        norm = normalize_for_dedup(r.get("stem_text"))
        if len(norm) < 8:
            continue
        buckets[norm[:bucket_len]].append(r)

    flagged = []
    exact_seen = set()
    for key, members in buckets.items():
        if len(members) < 2 or len(members) > 200:
            continue  # a bucket this large is almost certainly a generic short-prefix collision, not real near-dupes
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                na, nb = normalize_for_dedup(a.get("stem_text")), normalize_for_dedup(b.get("stem_text"))
                if na == nb:
                    continue  # already captured as an exact duplicate
                ratio = difflib.SequenceMatcher(None, na, nb).ratio()
                if ratio >= ratio_threshold:
                    pair_key = tuple(sorted([a["id"], b["id"]]))
                    if pair_key in exact_seen:
                        continue
                    exact_seen.add(pair_key)
                    flagged.append({
                        "ids": [a["id"], b["id"]],
                        "sources": [f"{a['_source_label']}#{a['question_number_raw']}", f"{b['_source_label']}#{b['question_number_raw']}"],
                        "similarity_ratio": round(ratio, 3),
                        "stem_a": (a.get("stem_text") or "")[:120],
                        "stem_b": (b.get("stem_text") or "")[:120],
                    })
    return {
        "near_duplicate_pairs_flagged": len(flagged),
        "ratio_threshold": ratio_threshold,
        "note": "review-only -- no automatic merge or deletion performed",
        "sample": flagged[:30],
    }


def sweatsmile_crosscheck(all_records: list[dict]) -> dict:
    if not SWEATSMILE_JSONL.exists():
        return {"available": False}
    ext_stems = set()
    with SWEATSMILE_JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            q = row.get("question")
            if q:
                ext_stems.add(normalize_for_dedup(q))
    matches = []
    for r in all_records:
        norm = normalize_for_dedup(r.get("stem_text"))
        if norm and norm in ext_stems:
            matches.append({"id": r["id"], "source": f"{r['_source_label']}#{r['question_number_raw']}", "stem": (r.get("stem_text") or "")[:120]})
    return {
        "available": True,
        "external_pool_size": len(ext_stems),
        "exact_stem_matches_found": len(matches),
        "sample": matches[:20],
        "note": "cheap exact-normalized-stem check only, not a semantic/near-duplicate sweep against this pool",
    }


def main() -> None:
    book1 = load_records(BOOK1_QUESTIONS, "33years_biology_2020")
    book2 = load_records(BOOK2_QUESTIONS, "neet_pyp_2025")
    all_records = book1 + book2

    report = {
        "generated_at": now_iso(),
        "counts": {"33years_biology_2020": len(book1), "neet_pyp_2025": len(book2), "combined": len(all_records)},
        "json_syntax_valid": True,
        "required_field_completeness": {
            "33years_biology_2020": required_field_report(book1),
            "neet_pyp_2025": required_field_report(book2),
            "combined": required_field_report(all_records),
        },
        "option_integrity": {
            "33years_biology_2020": option_integrity_report(book1),
            "neet_pyp_2025": option_integrity_report(book2),
            "combined": option_integrity_report(all_records),
        },
        "exact_duplicates": exact_duplicate_report(all_records),
        "near_duplicates": near_duplicate_report(all_records),
        "sweatsmile_external_pool_crosscheck": sweatsmile_crosscheck(all_records),
    }
    out_path = OUT_DIR / "neet_mcq_pdf_extraction_33years_and_pyp_20261018_validation.json"
    write_json(out_path, report)
    print(f"wrote {out_path}")
    print(json.dumps({k: report[k] for k in ("counts", "exact_duplicates")}, indent=2, default=str))
    print("near_duplicate_pairs_flagged:", report["near_duplicates"]["near_duplicate_pairs_flagged"])
    print("sweatsmile matches:", report["sweatsmile_external_pool_crosscheck"].get("exact_stem_matches_found"))


if __name__ == "__main__":
    main()
