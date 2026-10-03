#!/usr/bin/env python3
"""NCERT relaxed-retrieval enablement for the project owner's accepted
8,159-question candidate pool (FACTORY-PYQ-P6).

Computes and (only with --apply) persists `pyq.questions.retrieval_match_tier`
and `pyq.questions.ncert_owner_accepted` for every ANSWER_PENDING question,
using compute_retrieval_tier() from resolve_pyq_answers.py (STRICT_MATCH ==
existing 0.5-threshold matcher, unchanged; RELAXED_MATCH == feature-flagged
0.25-threshold, subject-constrained-when-known matcher against the SAME
PASSED-only knowledge_units corpus -- no new knowledge units are created or
duplicated).

This script NEVER:
  - writes to pyq.answer_assertions (no answer is resolved or verified here)
  - changes pyq.questions.state (ANSWER_PENDING stays ANSWER_PENDING)
  - calls any AI/LLM provider
  - overwrites raw_stem/raw_options or any source/provenance field
  - touches a question whose state is not ANSWER_PENDING (independently
    verified / disputed / conflicted questions are read-only to this script)

`ncert_owner_accepted` is set True only for questions landing in
RELAXED_MATCH tier -- it records the owner's launch-prioritization
acceptance of the relaxed-retrieval candidate pool, and is NOT itself an
answer-verification status; it must never be interpreted as
VERIFIED/AI_RESOLVED.

Idempotent: reruns with the same flag/threshold config recompute the same
tier for the same question set (deterministic), and the UPDATE is a plain
overwrite of these two new columns only -- safe to rerun any number of times.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from scripts.resolve_pyq_answers import KnowledgeUnitIndex, _load_ku_index, compute_retrieval_tier

logger = get_logger("pyq.retrieval_enablement")

BATCH_SIZE = 1000


async def _snapshot(session: AsyncSession) -> dict:
    total = (await session.execute(text("SELECT count(*) FROM pyq.questions"))).scalar()
    by_state = dict(
        (row[0], row[1])
        for row in (
            await session.execute(text("SELECT state, count(*) FROM pyq.questions GROUP BY state"))
        ).all()
    )
    by_tier = dict(
        (row[0] or "(null)", row[1])
        for row in (
            await session.execute(
                text("SELECT retrieval_match_tier, count(*) FROM pyq.questions GROUP BY retrieval_match_tier")
            )
        ).all()
    )
    owner_accepted = (
        await session.execute(text("SELECT count(*) FROM pyq.questions WHERE ncert_owner_accepted = true"))
    ).scalar()
    conflicted_or_disputed = (
        await session.execute(
            text(
                "SELECT count(*) FROM pyq.questions q "
                "WHERE EXISTS (SELECT 1 FROM pyq.answer_assertions a "
                "WHERE a.question_id = q.id AND a.verification_status = 'DISPUTED')"
            )
        )
    ).scalar()
    return {
        "total_pyqs": total,
        "by_state": by_state,
        "by_retrieval_match_tier": by_tier,
        "ncert_owner_accepted_count": owner_accepted,
        "questions_with_disputed_assertions": conflicted_or_disputed,
    }


async def run_with_session(
    session: AsyncSession, *, apply: bool, relaxed_enabled: bool, relaxed_threshold: float, subject_constrained: bool
) -> dict:
    """Session-injectable core (mirrors resolve_up_to's pattern) so tests
    using a single SAVEPOINT-isolated session can see both the seeded
    fixture data and this function's own reads/writes on one connection.
    The CLI entrypoint (run(), below) wraps this with a real
    AsyncSessionLocal() connection."""
    before = await _snapshot(session)

    idx: KnowledgeUnitIndex = await _load_ku_index(session)
    logger.info(
        "pyq_retrieval_enablement_index_loaded",
        knowledge_units=len(idx.unit_ids),
        relaxed_enabled=relaxed_enabled,
        relaxed_threshold=relaxed_threshold,
        subject_constrained=subject_constrained,
    )

    tier_counts = {"STRICT_MATCH": 0, "RELAXED_MATCH": 0, "NONE": 0}
    candidate_question_ids: list[str] = []  # RELAXED_MATCH tier only

    last_id = None
    while True:
        if last_id is None:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, subject, raw_stem FROM pyq.questions "
                        "WHERE state = 'ANSWER_PENDING' ORDER BY id LIMIT :lim"
                    ),
                    {"lim": BATCH_SIZE},
                )
            ).all()
        else:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, subject, raw_stem FROM pyq.questions "
                        "WHERE state = 'ANSWER_PENDING' AND id > :last_id ORDER BY id LIMIT :lim"
                    ),
                    {"last_id": last_id, "lim": BATCH_SIZE},
                )
            ).all()
        if not rows:
            break
        last_id = rows[-1][0]

        for qid, subject, stem in rows:
            tier, _matched_units = compute_retrieval_tier(
                idx,
                stem or "",
                subject,
                relaxed_enabled=relaxed_enabled,
                relaxed_threshold=relaxed_threshold,
                subject_constrained=subject_constrained,
            )
            tier_counts[tier] += 1
            if tier == "RELAXED_MATCH":
                candidate_question_ids.append(str(qid))

            if apply:
                await session.execute(
                    text(
                        "UPDATE pyq.questions SET "
                        "retrieval_match_tier = :tier, "
                        "ncert_owner_accepted = :accepted, "
                        "ncert_owner_accepted_at = CASE WHEN :accepted THEN now() ELSE NULL END "
                        "WHERE id = :id"
                    ),
                    {"tier": tier, "accepted": tier == "RELAXED_MATCH", "id": qid},
                )
        if apply:
            await session.commit()
        # Dry-run issues no writes in this loop at all, so there is nothing
        # to roll back here -- an explicit rollback() on a shared/injected
        # session (as tests use) would also unwind that caller's own
        # uncommitted fixture state, which this script must never do.

    after = await _snapshot(session) if apply else before

    return {
        "apply": apply,
        "config": {
            "relaxed_enabled": relaxed_enabled,
            "relaxed_threshold": relaxed_threshold,
            "subject_constrained": subject_constrained,
        },
        "tier_counts_computed_this_run": tier_counts,
        "relaxed_match_candidate_count": len(candidate_question_ids),
        "before_snapshot": before,
        "after_snapshot": after,
    }


async def run(*, apply: bool, relaxed_enabled: bool, relaxed_threshold: float, subject_constrained: bool) -> dict:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        return await run_with_session(
            session,
            apply=apply,
            relaxed_enabled=relaxed_enabled,
            relaxed_threshold=relaxed_threshold,
            subject_constrained=subject_constrained,
        )


async def main() -> int:
    parser = argparse.ArgumentParser(description="PYQ NCERT relaxed-retrieval-context enablement (never resolves answers)")
    parser.add_argument("--apply", action="store_true", help="Persist retrieval_match_tier/ncert_owner_accepted (default: dry-run)")
    parser.add_argument("--relaxed-enabled", action="store_true", help="Enable the relaxed-threshold path (default: off -> STRICT_MATCH/NONE only)")
    parser.add_argument("--relaxed-threshold", type=float, default=0.25)
    parser.add_argument("--no-subject-constrained", action="store_true", help="Disable the same-subject safeguard (NOT recommended; for diagnostic comparison only)")
    args = parser.parse_args()

    result = await run(
        apply=args.apply,
        relaxed_enabled=args.relaxed_enabled,
        relaxed_threshold=args.relaxed_threshold,
        subject_constrained=not args.no_subject_constrained,
    )
    print("APPLY" if args.apply else "DRY RUN (no writes persisted)")
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
