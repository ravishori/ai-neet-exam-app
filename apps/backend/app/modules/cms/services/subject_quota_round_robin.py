"""Deterministic subject x class round-robin blueprint selector.

Fixes the 5K MCQ driver defect where a concept-keyed interleave degenerated
into pure subject-alphabetical order whenever a subject had a 1:1
concept:blueprint ratio (Botany, Chemistry, Zoology all did). That let a
single slow-to-exhaust subject (Botany) consume an entire wall-clock budget
before the driver ever reached Chemistry/Physics/Zoology.

This selector groups blueprints into exactly 8 queues — one per
(subject, class_level) cell — and rotates across the non-empty queues in a
fixed canonical order, taking exactly one item per queue per lap. Skewed
per-subject blueprint counts (e.g. Physics-12 having far more rows than
Zoology-12) no longer starve later subjects: a subject with more blueprints
just keeps appearing in more laps after the smaller queues are exhausted,
but every subject appears at least once in the first lap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

CANONICAL_QUEUE_ORDER: tuple[str, ...] = (
    "Physics-11",
    "Physics-12",
    "Chemistry-11",
    "Chemistry-12",
    "Botany-11",
    "Botany-12",
    "Zoology-11",
    "Zoology-12",
)


def queue_label(subject: str, class_level: str | int) -> str:
    """Canonical queue label for a (subject, class_level) pair."""
    return f"{subject.strip().title()}-{str(class_level).strip()}"


@dataclass
class RoundRobinResult(Generic[T]):
    label: str
    item: T


def round_robin_order(
    queues: dict[str, list[T]],
    *,
    canonical_order: tuple[str, ...] = CANONICAL_QUEUE_ORDER,
) -> list[RoundRobinResult[T]]:
    """Deterministically interleave items from `queues` one-per-queue-per-lap.

    `queues` maps a queue label (see `queue_label`) to an ordered list of
    items (blueprints). Items within a queue keep their given order and are
    consumed from the front. Queue labels not present in `canonical_order`
    are appended after it, in sorted order, so nothing is silently dropped
    if the input ever contains an unexpected label.

    Deterministic and pure — no I/O, no randomness, no DB/network access.
    """
    # Work on shallow copies so we never mutate the caller's lists.
    work: dict[str, list[T]] = {k: list(v) for k, v in queues.items()}

    order = list(canonical_order)
    extra = sorted(k for k in work if k not in canonical_order)
    order.extend(extra)

    out: list[RoundRobinResult[T]] = []
    while any(work.get(label) for label in order):
        for label in order:
            bucket = work.get(label)
            if bucket:
                out.append(RoundRobinResult(label=label, item=bucket.pop(0)))
    return out


def build_queues(
    rows: list[dict],
    *,
    subject_key: str = "subject",
    class_level_key: str = "class_level",
) -> dict[str, list[dict]]:
    """Group flat blueprint rows into the 8 canonical (subject, class) queues.

    Rows keep their incoming relative order within their queue — callers
    that want a specific in-queue ordering (e.g. by concept, then family,
    then difficulty) should sort `rows` before calling this.
    """
    queues: dict[str, list[dict]] = {}
    for row in rows:
        label = queue_label(row[subject_key], row[class_level_key])
        queues.setdefault(label, []).append(row)
    return queues
