"""Load and verify P2.2-R1 input population."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXPECTED_STRUCTURAL = 326


def is_structurally_valid(row: dict[str, Any]) -> bool:
    if row.get("provider") != "gemini":
        return False
    q = (row.get("question") or "").strip()
    opts = row.get("options") or {}
    if not q or set(opts.keys()) != {"A", "B", "C", "D"}:
        return False
    return all(str(opts.get(k) or "").strip() for k in "ABCD")


def load_gemini_structural_candidates(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"MCQ results not found: {path}")
    rows = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    candidates = [r for r in rows if is_structurally_valid(r)]
    if len(candidates) != EXPECTED_STRUCTURAL:
        raise ValueError(
            f"Expected exactly {EXPECTED_STRUCTURAL} Gemini structural MCQs, found {len(candidates)}. STOP."
        )
    return candidates
