"""Duplicate classification for pastq staging (no deletes)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def classify_duplicates(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Assign duplicate_class on each record; preserve all provenance."""
    by_norm: dict[str, list[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        h = (rec.get("hashes") or {}).get("normalized_question_hash") or ""
        if h:
            by_norm[h].append(idx)

    counts = {
        "UNIQUE": 0,
        "DUPLICATE_WITHIN_IMPORT": 0,
        "POTENTIAL_DUPLICATE": 0,
        "DUPLICATE_EXISTING": 0,
    }
    for _, idxs in by_norm.items():
        if len(idxs) == 1:
            records[idxs[0]]["quality"]["duplicate_class"] = "UNIQUE"
            counts["UNIQUE"] += 1
            continue
        # Same hash across records — keep all; first UNIQUE-ish, rest within-import.
        papers = {(records[i].get("paper") or {}).get("paper_id") for i in idxs}
        for n, i in enumerate(idxs):
            if len(papers) > 1:
                records[i]["quality"]["duplicate_class"] = "POTENTIAL_DUPLICATE"
                counts["POTENTIAL_DUPLICATE"] += 1
            elif n == 0:
                records[i]["quality"]["duplicate_class"] = "UNIQUE"
                counts["UNIQUE"] += 1
            else:
                records[i]["quality"]["duplicate_class"] = "DUPLICATE_WITHIN_IMPORT"
                counts["DUPLICATE_WITHIN_IMPORT"] += 1
    # Records without hash
    for rec in records:
        if not (rec.get("hashes") or {}).get("normalized_question_hash"):
            if rec["quality"].get("duplicate_class") in (None, "UNIQUE"):
                rec["quality"]["duplicate_class"] = "UNIQUE"
                # already counted if set earlier — only count unset
    return counts


def mark_existing_cms_duplicates(
    records: list[dict[str, Any]],
    existing_stem_hashes: set[str],
    *,
    stem_hash_fn,
) -> int:
    """Mark DUPLICATE_EXISTING when stem_hash already in CMS (read-only check)."""
    marked = 0
    for rec in records:
        stem = ((rec.get("question") or {}).get("stem") or "").strip()
        if not stem:
            continue
        h = stem_hash_fn(stem)
        if h in existing_stem_hashes:
            rec["quality"]["duplicate_class"] = "DUPLICATE_EXISTING"
            rec["quality"]["warnings"] = list(rec["quality"].get("warnings") or []) + [
                "DUPLICATE_EXISTING_CMS_STEM"
            ]
            marked += 1
    return marked
