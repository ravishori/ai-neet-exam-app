"""P2.2 MCQ safeguard — never regenerate Track B structural cohort."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.modules.cms.pyq.p2_2.r1_validation.loader import EXPECTED_STRUCTURAL, load_gemini_structural_candidates

P2_2_ORIGIN = "p2_2_track_b"
P2_2_MCQ_ID_PREFIXES = ("mcq-",)


def load_p2_2_protected_ids(mcq_results_path: Path) -> set[str]:
    rows = load_gemini_structural_candidates(mcq_results_path)
    return {r["mcq_id"] for r in rows}


def load_p2_2_protected_stems(mcq_results_path: Path) -> list[str]:
    rows = load_gemini_structural_candidates(mcq_results_path)
    return [r.get("question") or "" for r in rows if r.get("question")]


def assert_p2_2_not_regenerated(*, question_ids: list[str], protected: set[str]) -> None:
    overlap = set(question_ids) & protected
    if overlap:
        raise RuntimeError(
            f"P2.2 SAFEGUARD: would regenerate {len(overlap)} protected Track-B MCQs. STOP."
        )


def assert_not_p2_2_origin(record: dict[str, Any]) -> None:
    if record.get("origin") == P2_2_ORIGIN:
        raise RuntimeError("P2.2 SAFEGUARD: p2_2_track_b records must not be overwritten by P2.3 generation.")


def is_p2_2_mcq_id(mcq_id: str) -> bool:
    return any(mcq_id.startswith(p) for p in P2_2_MCQ_ID_PREFIXES) and not mcq_id.startswith("p3-")


def verify_p2_2_population(mcq_results_path: Path) -> dict[str, Any]:
    if not mcq_results_path.exists():
        raise FileNotFoundError(f"P2.2 MCQ results missing: {mcq_results_path}")
    rows = load_gemini_structural_candidates(mcq_results_path)
    return {
        "protected_count": len(rows),
        "expected": EXPECTED_STRUCTURAL,
        "path": str(mcq_results_path),
    }
