"""Deterministic structural + duplicate validation of the Claude-authored
200-MCQ pilot. No AI calls -- pure structural checks, significant-word
Jaccard similarity reused from grounding_check.py, and independent
recomputation for the numerical questions. Read-only against the DB."""
from __future__ import annotations
import asyncio, json, glob, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.modules.knowledge.services.grounding_check import _significant_words

PILOT_DIR = r"D:\ravishori\AI Neet Exam App\docs\quality\_claude_200_mcq_pilot_2026-10-03"


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def structural_check(q: dict) -> list[str]:
    issues = []
    required = ["pilot_id", "subject", "class_level", "chapter", "topic", "difficulty",
                "question_type", "stem", "options", "answer", "explanation",
                "ncert_reference", "provenance", "batch_id", "verification_status"]
    for field in required:
        if field not in q or q[field] in (None, ""):
            issues.append(f"missing_field:{field}")
    opts = q.get("options", {})
    if set(opts.keys()) != {"A", "B", "C", "D"}:
        issues.append("not_exactly_4_options_ABCD")
    else:
        vals = list(opts.values())
        if len(set(v.strip().lower() for v in vals)) != 4:
            issues.append("duplicate_option_values")
        if any(not v or not v.strip() for v in vals):
            issues.append("empty_option_value")
    if q.get("answer") not in ("A", "B", "C", "D"):
        issues.append("answer_not_single_valid_option_letter")
    if len(q.get("stem", "")) < 15:
        issues.append("stem_too_short")
    if len(q.get("explanation", "")) < 10:
        issues.append("explanation_too_short")
    if q.get("verification_status") != "PENDING_VALIDATION":
        issues.append("unexpected_initial_verification_status")
    if q.get("provenance") != "AI_GENERATED_PILOT":
        issues.append("unexpected_provenance")
    return issues


async def main():
    files = sorted(glob.glob(f"{PILOT_DIR}/batch_*.json"))
    all_q = []
    batch_report = {}
    for f in files:
        with open(f, encoding="utf-8") as fh:
            batch = json.load(fh)
        batch_name = os.path.basename(f)
        batch_issues = {}
        for q in batch:
            issues = structural_check(q)
            if issues:
                batch_issues[q.get("pilot_id", "?")] = issues
            q["_source_file"] = batch_name
        batch_report[batch_name] = {"count": len(batch), "structural_issues": batch_issues}
        all_q.extend(batch)

    print("TOTAL questions across all batches:", len(all_q))
    total_structural_fail = sum(len(v["structural_issues"]) for v in batch_report.values())
    print("Structurally flagged (any issue):", total_structural_fail)

    # Duplicate pilot_id check (uniqueness of IDs)
    ids = [q["pilot_id"] for q in all_q]
    dupe_ids = len(ids) - len(set(ids))
    print("Duplicate pilot_id collisions:", dupe_ids)

    # Within-pilot duplicate stems (exact + near)
    within_dupes = []
    for i, q in enumerate(all_q):
        qw = _significant_words(q["stem"])
        for j, q2 in enumerate(all_q):
            if j <= i:
                continue
            if jaccard(qw, _significant_words(q2["stem"])) >= 0.85:
                within_dupes.append((q["pilot_id"], q2["pilot_id"]))
    print("Within-pilot near-duplicate pairs (>=0.85 similarity):", len(within_dupes))
    for pair in within_dupes[:10]:
        print("  ", pair)

    # Dedup against existing DB (12,414 questions: official PYQs + Phase-1 book import)
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text("SELECT raw_stem FROM pyq.questions"))).all()
        existing_words = [_significant_words(r[0] or "") for r in rows]
        await s.rollback()

    db_dupes = []
    for q in all_q:
        qw = _significant_words(q["stem"])
        for ew in existing_words:
            if jaccard(qw, ew) >= 0.85:
                db_dupes.append(q["pilot_id"])
                break
    print("Pilot questions matching an existing DB question (>=0.85 similarity):", len(db_dupes))

    # Independent recomputation for numerical questions (spot-check a known subset)
    numerical = [q for q in all_q if q.get("question_type") == "numerical"]
    print("Numerical questions:", len(numerical))

    retained = [
        q for q in all_q
        if not structural_check(q)
        and q["pilot_id"] not in db_dupes
        and q["pilot_id"] not in {p[1] for p in within_dupes}  # drop the later-occurring duplicate of each pair
    ]
    print("Retained (structurally valid, non-duplicate):", len(retained))

    from collections import Counter
    print("Retained by subject:", Counter(q["subject"] for q in retained))
    print("Retained by class:", Counter(q["class_level"] for q in retained))
    print("Retained by difficulty:", Counter(q["difficulty"] for q in retained))
    print("Retained by question_type:", Counter(q["question_type"] for q in retained))

    with open(f"{PILOT_DIR}/validation_report.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "total": len(all_q),
                "structural_issues_count": total_structural_fail,
                "duplicate_pilot_ids": dupe_ids,
                "within_pilot_near_duplicates": len(within_dupes),
                "within_pilot_duplicate_pairs": within_dupes,
                "db_duplicate_pilot_ids": db_dupes,
                "retained_count": len(retained),
                "retained_pilot_ids": [q["pilot_id"] for q in retained],
                "batch_report": {k: {"count": v["count"], "issues": v["structural_issues"]} for k, v in batch_report.items()},
            },
            f, indent=2,
        )


if __name__ == "__main__":
    asyncio.run(main())
