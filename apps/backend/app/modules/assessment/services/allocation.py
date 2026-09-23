"""Deterministic largest-remainder allocation for subject weightage.

Pure function. No DB, no ORM, no assessment/attempt side effects. The
caller (quiz-generation entry points) is responsible for mapping the
returned per-subject quotas onto the existing question-selection engine
— this module never touches scoring, published-question eligibility, or
attempt state.

Contract:
    - Weightages MUST sum to exactly 100 (±0.01 float tolerance).
    - Weightages MUST be finite, non-negative, non-NaN, non-infinite.
    - `total_questions` MUST be a positive integer.
    - Output preserves input key order (Python dict insertion order).
    - Sum of allocated integers ALWAYS equals `total_questions`.
    - Tie-breaking among equal fractional remainders is deterministic:
      earlier insertion order wins. Two calls with the same inputs
      always return the same result.

Validation is strict server-side. Client-supplied totals are re-checked
here — never trusted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

TOTAL_TOLERANCE_PCT = 0.01
"""How far the sum of weightages may drift from 100 before we reject."""


class WeightageError(ValueError):
    """Raised on any invariant violation. Callers turn this into a 422."""


@dataclass(frozen=True)
class Allocation:
    """Result of one call. `quotas` is ordered like the input map."""

    total_questions: int
    quotas: dict[str, int]
    weightages: dict[str, float]


def allocate_by_weightage(
    total_questions: int,
    weightages: dict[str, float],
) -> Allocation:
    """Deterministic largest-remainder (Hare quota) allocation.

    Example:
        >>> allocate_by_weightage(30, {"Physics": 40, "Chemistry": 30, "Biology": 30}).quotas
        {'Physics': 12, 'Chemistry': 9, 'Biology': 9}
    """
    _validate_total(total_questions)
    _validate_weightages(weightages)

    # Exact quotas as floats, then split into integer floor + fractional
    # remainder. Awarding the leftover units to the largest remainders is
    # the Hare / largest-remainder method — same rule used by many
    # parliamentary seat allocations. It preserves the total exactly and
    # is stable under tie-breaks (we sort by remainder desc, then by
    # insertion index asc).
    keys = list(weightages.keys())
    exact = [total_questions * (weightages[k] / 100.0) for k in keys]
    floors = [math.floor(x) for x in exact]
    remainders = [(exact[i] - floors[i], i) for i in range(len(keys))]

    remaining = total_questions - sum(floors)
    if remaining < 0:  # unreachable when validators fire, defensive only
        raise WeightageError("Internal: negative remainder from floor allocation")

    # Largest remainder first, then earliest insertion index (deterministic).
    remainders.sort(key=lambda pair: (-pair[0], pair[1]))
    allocation = list(floors)
    for _, idx in remainders[:remaining]:
        allocation[idx] += 1

    if sum(allocation) != total_questions:  # invariant guard
        raise WeightageError(
            f"Internal: allocation sum {sum(allocation)} != requested {total_questions}"
        )

    return Allocation(
        total_questions=total_questions,
        quotas={k: allocation[i] for i, k in enumerate(keys)},
        weightages=dict(weightages),
    )


# --------------------------------------------------------------------------- validators

def _validate_total(total_questions: int) -> None:
    if not isinstance(total_questions, int) or isinstance(total_questions, bool):
        raise WeightageError("total_questions must be an int")
    if total_questions < 1:
        raise WeightageError("total_questions must be >= 1")


def _validate_weightages(weightages: dict[str, float]) -> None:
    if not weightages:
        raise WeightageError("weightages is empty")
    seen: set[str] = set()
    for key, value in weightages.items():
        if not isinstance(key, str) or not key:
            raise WeightageError(f"weightage key must be a non-empty string: {key!r}")
        if key in seen:
            raise WeightageError(f"duplicate weightage key: {key!r}")
        seen.add(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise WeightageError(f"weightage[{key!r}] must be numeric")
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            raise WeightageError(f"weightage[{key!r}] is not finite")
        if v < 0:
            raise WeightageError(f"weightage[{key!r}] must be >= 0: got {v}")
        if v > 100:
            raise WeightageError(f"weightage[{key!r}] must be <= 100: got {v}")
    total = sum(float(v) for v in weightages.values())
    if abs(total - 100.0) > TOTAL_TOLERANCE_PCT:
        raise WeightageError(
            f"weightages must sum to 100 (tolerance ±{TOTAL_TOLERANCE_PCT}); got {total}"
        )
