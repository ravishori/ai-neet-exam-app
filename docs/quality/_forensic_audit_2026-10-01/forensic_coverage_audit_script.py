"""Read-only, in-memory-only forensic coverage diagnostic. No DB writes, no
Gemini calls, no changes to any persistent config. Reuses the exact
production word-significance function; only the overlap threshold is varied
locally as a diagnostic (never written back to grounding_check.py)."""

from __future__ import annotations

import asyncio
import json
import re

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.modules.knowledge.services.grounding_check import _significant_words

MIN_SIG_LEN = 4
_STOPWORDS = frozenset(
    {
        "this", "that", "these", "those", "with", "from", "into", "onto",
        "have", "has", "had", "were", "was", "are", "is", "be", "been",
        "being", "will", "would", "could", "should", "shall", "must",
        "than", "then", "when", "where", "which", "while", "about",
        "there", "their", "they", "them", "such", "each", "some", "more",
        "most", "other", "only", "also", "both", "same", "very", "just",
        "over", "under", "between", "across", "through", "within", "without",
        "does", "did", "not", "and", "for", "the", "its", "it's",
    }
)


def overlap_ratio(stem_words: set[str], unit_words: set[str]) -> float:
    if not stem_words:
        return 0.0
    return len(stem_words & unit_words) / len(stem_words)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        # Load ALL non-deleted KUs (reproduces the exact production index),
        # tagged with validation_status and chapter code for breakdown.
        rows = (
            await session.execute(
                text(
                    """
                    SELECT ku.id, ku.summary, ku.structured_facts, ku.validation_status,
                           c.code AS chapter_code, s.code AS subject_code
                    FROM knowledge.knowledge_units ku
                    LEFT JOIN academic.concepts co ON co.id = ku.concept_id
                    LEFT JOIN academic.topics t ON t.id = co.topic_id
                    LEFT JOIN academic.chapters c ON c.id = t.chapter_id
                    LEFT JOIN academic.subjects s ON s.id = c.subject_id
                    WHERE ku.deleted_at IS NULL
                    """
                )
            )
        ).all()

        units = []
        for uid, summary, facts, status, chapter_code, subject_code in rows:
            facts_list = facts if isinstance(facts, list) else (json.loads(facts) if facts else [])
            combined = " ".join([summary or "", *[str(f) for f in facts_list]])
            words = _significant_words(combined)
            units.append(
                {
                    "id": str(uid), "words": words, "status": status,
                    "chapter_code": chapter_code, "subject_code": subject_code,
                }
            )
        print("total_units_in_index", len(units))
        print("passed_units", sum(1 for u in units if u["status"] == "PASSED"))
        print("failed_units", sum(1 for u in units if u["status"] == "FAILED"))

        # Candidate word index (mirrors production _load_ku_index / candidates_for)
        word_to_units_all: dict[str, list[int]] = {}
        word_to_units_passed: dict[str, list[int]] = {}
        for i, u in enumerate(units):
            for w in u["words"]:
                word_to_units_all.setdefault(w, []).append(i)
                if u["status"] == "PASSED":
                    word_to_units_passed.setdefault(w, []).append(i)

        pending = (
            await session.execute(
                text("SELECT id, subject, raw_stem FROM pyq.questions WHERE state='ANSWER_PENDING'")
            )
        ).all()
        print("total_pending", len(pending))

        STRICT = 0.5  # production threshold (grounding_check.OVERLAP_THRESHOLD)
        RELAXED = 0.25  # diagnostic only, never written to any config

        current_covered = 0  # ALL units, strict threshold — must reproduce 3868
        passed_only_covered = 0  # PASSED units only, strict threshold
        relaxed_passed_covered = 0  # PASSED units only, relaxed threshold (diagnostic)
        zero_overlap_at_all = 0  # not even one shared significant word, strict current-logic uncovered set
        current_by_subject: dict[str, list[int]] = {}
        current_chapter_hits: dict[str, int] = {}
        uncovered_ids = []

        for qid, subject, stem in pending:
            stem_words = _significant_words(stem or "")
            key = subject or "(null)"
            current_by_subject.setdefault(key, [0, 0])
            current_by_subject[key][1] += 1

            if not stem_words:
                uncovered_ids.append(str(qid))
                continue

            candidate_idx_all = set()
            for w in stem_words:
                candidate_idx_all.update(word_to_units_all.get(w, []))
            matched_all = [i for i in candidate_idx_all if overlap_ratio(stem_words, units[i]["words"]) >= STRICT]

            if matched_all:
                current_covered += 1
                current_by_subject[key][0] += 1
                for i in matched_all:
                    cc = units[i]["chapter_code"] or "(no chapter)"
                    current_chapter_hits[cc] = current_chapter_hits.get(cc, 0) + 1
            else:
                uncovered_ids.append(str(qid))
                if not candidate_idx_all:
                    zero_overlap_at_all += 1

            candidate_idx_passed = set()
            for w in stem_words:
                candidate_idx_passed.update(word_to_units_passed.get(w, []))
            matched_passed_strict = [
                i for i in candidate_idx_passed if overlap_ratio(stem_words, units[i]["words"]) >= STRICT
            ]
            if matched_passed_strict:
                passed_only_covered += 1

            matched_passed_relaxed = [
                i for i in candidate_idx_passed if overlap_ratio(stem_words, units[i]["words"]) >= RELAXED
            ]
            if matched_passed_relaxed:
                relaxed_passed_covered += 1

        print("=== CURRENT (ALL units, strict 0.5) ===")
        print("covered", current_covered, "of", len(pending))
        print("by_subject", current_by_subject)
        print("=== PASSED-ONLY (strict 0.5) ===")
        print("covered", passed_only_covered, "of", len(pending))
        print("delta_vs_current (coverage relying on FAILED units)", current_covered - passed_only_covered)
        print("=== PASSED-ONLY, RELAXED 0.25 (diagnostic only) ===")
        print("covered", relaxed_passed_covered, "of", len(pending))
        print("=== ZERO OVERLAP (not even 1 shared significant word with any ingested unit) ===")
        print("zero_overlap_at_all", zero_overlap_at_all, "of", len(pending) - current_covered, "uncovered")
        print("=== TOP CHAPTER HITS for currently-covered questions ===")
        for cc, n in sorted(current_chapter_hits.items(), key=lambda x: -x[1])[:15]:
            print(f"  {cc}: {n}")

        with open("forensic_uncovered_ids.json", "w") as f:
            json.dump(uncovered_ids, f)
        print("uncovered_count_saved", len(uncovered_ids))

        await session.rollback()


if __name__ == "__main__":
    asyncio.run(main())
