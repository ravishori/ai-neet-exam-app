"""T6-F1 validation gates — reuses T6-E-FIX gate logic; F1 bank + extended dedupe."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.cms.acquisition.physics_t6d_gates import (
    audit_answer_position,
    audit_difficulty,
    validate_candidate,
)
from app.modules.cms.acquisition.physics_t6f1_bank import build_bank
from app.modules.cms.acquisition.physics_t6f1_constants import TARGET_CANDIDATES
from app.modules.cms.acquisition.physics_t6f1_distribution import (
    chapter_distribution_from_plan,
    distribution_plan,
    topic_distribution_from_plan,
)


def audit_bank(existing_hashes: set[str] | None = None, *, repo_root: Path | None = None, requested: int = TARGET_CANDIDATES) -> dict[str, Any]:
    bank = build_bank(requested)
    assert len(bank) == requested, len(bank)
    seen: dict[str, str] = {}
    seen_stems: list[tuple[str, str]] = []
    reports = [
        validate_candidate(
            c,
            seen_hashes=seen,
            existing_hashes=existing_hashes or set(),
            seen_stems=seen_stems,
            repo_root=repo_root,
            fast_near_dup=len(bank) >= 200,
        )
        for c in bank
    ]
    accepted = [r for r in reports if r.accepted]
    rejected = [r for r in reports if r.result == "REJECT"]
    held = [r for r in reports if r.result == "HOLD"]
    accepted_bank = [c for c, r in zip(bank, reports, strict=True) if r.accepted]

    by_chapter: dict[str, int] = {}
    by_topic: dict[str, int] = {}
    by_concept: dict[str, int] = {}
    by_diff: dict[str, int] = {}
    by_qtype: dict[str, int] = {}
    for c in accepted_bank:
        by_chapter[c.chapter_code] = by_chapter.get(c.chapter_code, 0) + 1
        by_topic[c.topic_code] = by_topic.get(c.topic_code, 0) + 1
        by_concept[c.concept_code] = by_concept.get(c.concept_code, 0) + 1
        by_diff[c.difficulty] = by_diff.get(c.difficulty, 0) + 1
        by_qtype[c.question_type] = by_qtype.get(c.question_type, 0) + 1

    plan = distribution_plan(requested)
    num_complete = sum(1 for r in reports if r.numerical_status == "NUMERICAL_COMPLETE")
    num_incomplete = sum(1 for r in reports if r.numerical_status == "NUMERICAL_INCOMPLETE")
    num_invalid = sum(1 for r in reports if r.numerical_status == "NUMERICAL_INVALID")
    near_dup = sum(1 for r in reports if r.similarity_band in ("NEAR_DUPLICATE", "DUPLICATE") and not r.duplicate_ok)

    failure_register = []
    for r in rejected + held:
        failure_register.append(
            {
                "candidate": r.pilot_qid,
                "stage": "gates",
                "severity": "HIGH" if not r.scientific_ok or not r.ncert_ok else "MEDIUM",
                "result": r.result,
                "reason": "; ".join(r.reasons[:3]),
                "evidence": r.pilot_qid,
            }
        )

    return {
        "candidates": len(bank),
        "requested": requested,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "held": len(held),
        "acceptance_rate": round(len(accepted) / len(bank), 4) if bank else 0,
        "rejection_rate": round(len(rejected) / len(bank), 4) if bank else 0,
        "duplicate_rate": round(sum(1 for r in reports if not r.duplicate_ok) / len(bank), 4) if bank else 0,
        "near_duplicate_count": near_dup,
        "reports": reports,
        "bank": bank,
        "distribution_plan": plan,
        "chapter_distribution_plan": chapter_distribution_from_plan(plan),
        "topic_distribution_plan": topic_distribution_from_plan(plan),
        "chapter_distribution_accepted": by_chapter,
        "topic_distribution_accepted": by_topic,
        "concept_distribution_accepted": by_concept,
        "difficulty_distribution_accepted": by_diff,
        "question_type_distribution_accepted": by_qtype,
        "answer_position_audit": audit_answer_position(accepted_bank),
        "answer_position_all_candidates": audit_answer_position(bank),
        "difficulty_audit": audit_difficulty(accepted_bank),
        "difficulty_audit_all": audit_difficulty(bank),
        "numerical": {
            "candidates_with_calc": num_complete + num_incomplete + num_invalid,
            "complete": num_complete,
            "incomplete": num_incomplete,
            "invalid": num_invalid,
        },
        "ncert_page_level_capability": "NOT AVAILABLE",
        "failure_register_sample": failure_register[:200],
        "failure_register_total": len(failure_register),
        "rejected_reasons": {r.pilot_qid: r.reasons for r in rejected},
        "held_reasons": {r.pilot_qid: r.reasons for r in held},
        "quality_over_quantity": True,
        "no_padding": True,
        "publication_allowed": False,
    }
