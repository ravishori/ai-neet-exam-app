"""Deterministic adaptive topic allocation inside one subject's quota.

Pure function — no DB, no ORM, no scoring, no attempt state. The caller
brings the eligible-question inventory and (optional) last-seen data
already gathered from the existing assessment/attempt repositories, and
the allocator turns it into a fixed list of question ids that add up to
the subject quota without duplicates.

Preference semantics:
    WEAK    - increased selection priority (bonus multiplier).
    NEUTRAL - baseline eligibility.
    STRONG  - baseline retention exposure (kept, never zeroed).

Guarantees:
    - Sum of allocated question counts across topics == min(requested
      subject_quota, total_available_across_topics). "Never exceed
      available inventory" is honoured.
    - No question id appears twice in the returned list.
    - STRONG topics collectively receive at least ``strong_floor_pct``
      of the subject quota when STRONG topics have inventory to fill it.
    - When a topic's allocation exceeds its inventory, the surplus is
      redistributed to other topics with remaining capacity, weighted by
      their preference multipliers.
    - Deterministic: same inputs → same output. Tie-breaks resolve by
      the caller-supplied topic ordering.
    - Where last-seen data is provided, unseen questions come first,
      then oldest-seen. If no last-seen data is provided, the caller's
      per-topic id ordering is preserved verbatim.

This module never mutates mastery state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

Preference = str  # STRONG | NEUTRAL | WEAK


class TopicAllocationError(ValueError):
    """Raised on invariant violations; callers turn into 422."""


# --------------------------------------------------------------------------- config

@dataclass(frozen=True)
class TopicAllocationConfig:
    """Configurable constants. Kept centralised so downstream tuning does
    not scatter magic numbers across the codebase."""

    weak_multiplier: float = 2.0
    """Selection weight for WEAK-marked topics."""

    neutral_multiplier: float = 1.0
    """Selection weight for NEUTRAL topics."""

    strong_multiplier: float = 0.5
    """Selection weight for STRONG topics — non-zero so retention practice
    is preserved even when the student has marked the topic as strong."""

    strong_floor_pct: float = 10.0
    """When STRONG topics exist and have inventory, collectively they must
    receive at least this % of the subject quota (0..100). Set to 0 to
    disable the floor."""


DEFAULT_CONFIG = TopicAllocationConfig()


PREFERENCE_VALUES = frozenset({"STRONG", "NEUTRAL", "WEAK"})


# --------------------------------------------------------------------------- inputs

@dataclass(frozen=True)
class TopicInput:
    """One topic within a subject.

    ``available_ids`` is the caller-collected inventory of eligible
    (published, non-duplicate, syllabus-in-scope) question ids for this
    student × topic. Duplicates across topics or inside a topic are
    rejected explicitly so an upstream bug can never produce a shared
    paper with the same question twice.

    ``last_seen_by_id`` is optional. When present, unseen ids (missing
    key) sort first, then oldest last_seen_at first. Absent → caller
    ordering is preserved verbatim.
    """

    topic_id: str
    preference: Preference = "NEUTRAL"
    available_ids: tuple[str, ...] = ()
    last_seen_by_id: dict[str, datetime] = field(default_factory=dict)


# --------------------------------------------------------------------------- output

@dataclass(frozen=True)
class TopicQuota:
    topic_id: str
    preference: Preference
    requested_share: int
    allocated: int
    picked_ids: tuple[str, ...]


@dataclass(frozen=True)
class SubjectTopicAllocation:
    subject_quota_requested: int
    subject_quota_fulfilled: int
    per_topic: tuple[TopicQuota, ...]
    picked_ids: tuple[str, ...]


# --------------------------------------------------------------------------- allocator


def allocate_topics_within_subject(
    subject_quota: int,
    topics: list[TopicInput],
    config: TopicAllocationConfig | None = None,
) -> SubjectTopicAllocation:
    cfg = config or DEFAULT_CONFIG
    _validate_inputs(subject_quota, topics, cfg)

    total_available = sum(len(t.available_ids) for t in topics)
    if total_available == 0:
        return SubjectTopicAllocation(
            subject_quota_requested=subject_quota,
            subject_quota_fulfilled=0,
            per_topic=tuple(
                TopicQuota(t.topic_id, t.preference, 0, 0, ()) for t in topics
            ),
            picked_ids=(),
        )
    # Fulfill at most what the total pool holds — never invent items.
    target = min(subject_quota, total_available)

    multiplier_of = {
        "WEAK": cfg.weak_multiplier,
        "NEUTRAL": cfg.neutral_multiplier,
        "STRONG": cfg.strong_multiplier,
    }
    weights = [multiplier_of[t.preference] for t in topics]

    # Initial largest-remainder split, capped by each topic's inventory.
    allocated = _weighted_largest_remainder(
        target=target,
        weights=weights,
        caps=[len(t.available_ids) for t in topics],
    )

    # STRONG floor: if any STRONG topics have inventory, they collectively
    # must receive >= strong_floor_pct of the ORIGINAL subject_quota.
    if cfg.strong_floor_pct > 0:
        strong_indices = [
            i for i, t in enumerate(topics)
            if t.preference == "STRONG" and len(t.available_ids) > 0
        ]
        strong_capacity = sum(len(topics[i].available_ids) for i in strong_indices)
        floor = int(math.floor(subject_quota * cfg.strong_floor_pct / 100.0))
        floor = min(floor, strong_capacity, target)
        strong_current = sum(allocated[i] for i in strong_indices)
        while strong_current < floor:
            # Give one to the STRONG topic with most remaining capacity
            donor_ok = _pick_donor(allocated, topics, exclude=strong_indices)
            receiver = _pick_strong_receiver(allocated, topics, strong_indices)
            if donor_ok is None or receiver is None:
                break
            allocated[donor_ok] -= 1
            allocated[receiver] += 1
            strong_current += 1

    # Compose picked ids per topic, respecting last-seen preference within a topic.
    per_topic: list[TopicQuota] = []
    picked_all: list[str] = []
    seen: set[str] = set()
    for i, t in enumerate(topics):
        share_want = _proportional_share(target, weights[i], sum(weights))
        take_n = allocated[i]
        ordered = _order_available_ids(t)
        picked: list[str] = []
        for qid in ordered:
            if take_n == 0:
                break
            if qid in seen:
                # Cross-topic duplicate ids are already rejected in
                # validation; this path is defensive.
                continue
            seen.add(qid)
            picked.append(qid)
            take_n -= 1
        picked_all.extend(picked)
        per_topic.append(
            TopicQuota(
                topic_id=t.topic_id,
                preference=t.preference,
                requested_share=share_want,
                allocated=len(picked),
                picked_ids=tuple(picked),
            )
        )

    fulfilled = sum(q.allocated for q in per_topic)
    return SubjectTopicAllocation(
        subject_quota_requested=subject_quota,
        subject_quota_fulfilled=fulfilled,
        per_topic=tuple(per_topic),
        picked_ids=tuple(picked_all),
    )


# --------------------------------------------------------------------------- helpers


def _weighted_largest_remainder(
    *, target: int, weights: list[float], caps: list[int]
) -> list[int]:
    """Weighted Hare-quota allocation with per-slot caps.

    Runs iterative rounds so that (a) overflow beyond each cap is
    redistributed to remaining slots, and (b) each round is itself
    deterministic largest-remainder.
    """
    n = len(weights)
    allocation = [0] * n
    remaining = target
    active = set(range(n))
    # Cap zero-cap slots immediately.
    active = {i for i in active if caps[i] > 0}
    while remaining > 0 and active:
        total_w = sum(weights[i] for i in active) or 1.0
        exact = {i: remaining * (weights[i] / total_w) for i in active}
        floors = {i: min(caps[i] - allocation[i], math.floor(exact[i])) for i in active}
        for i in active:
            allocation[i] += floors[i]
        given = sum(floors.values())
        remaining -= given
        remainders = sorted(
            (
                ((exact[i] - math.floor(exact[i])), i)
                for i in active
                if allocation[i] < caps[i]
            ),
            key=lambda pair: (-pair[0], pair[1]),
        )
        # If floors gave nothing but capacity exists, hand out one at a time.
        if given == 0 and remainders:
            _, idx = remainders[0]
            allocation[idx] += 1
            remaining -= 1
        else:
            for _, idx in remainders:
                if remaining <= 0:
                    break
                if allocation[idx] < caps[idx]:
                    allocation[idx] += 1
                    remaining -= 1
        active = {i for i in active if allocation[i] < caps[i]}
    return allocation


def _proportional_share(target: int, w: float, total_w: float) -> int:
    if total_w <= 0:
        return 0
    return int(round(target * (w / total_w)))


def _pick_donor(allocated: list[int], topics: list[TopicInput], exclude: list[int]) -> int | None:
    """Choose the non-STRONG topic that can spare a slot (has >=1
    allocated and >0 inventory), preferring the one with the largest
    current allocation — smallest topic index breaks ties."""
    best: int | None = None
    best_value = -1
    for i in range(len(topics)):
        if i in exclude:
            continue
        if allocated[i] <= 0:
            continue
        if allocated[i] > best_value:
            best_value = allocated[i]
            best = i
    return best


def _pick_strong_receiver(
    allocated: list[int], topics: list[TopicInput], strong_indices: list[int]
) -> int | None:
    """STRONG topic with the most remaining capacity gets the +1."""
    best: int | None = None
    best_capacity = 0
    for i in strong_indices:
        cap = len(topics[i].available_ids) - allocated[i]
        if cap > best_capacity:
            best_capacity = cap
            best = i
    return best


def _order_available_ids(topic: TopicInput) -> list[str]:
    if not topic.last_seen_by_id:
        return list(topic.available_ids)
    # Unseen first (missing key), then oldest last_seen_at first.
    # Stable secondary sort preserves the caller's given ordering.
    indexed = list(enumerate(topic.available_ids))
    def sort_key(pair: tuple[int, str]):
        idx, qid = pair
        ts = topic.last_seen_by_id.get(qid)
        # (has_been_seen, last_seen, caller_index) — False < True.
        return (ts is not None, ts or datetime.min, idx)
    indexed.sort(key=sort_key)
    return [qid for _idx, qid in indexed]


# --------------------------------------------------------------------------- validation


def _validate_inputs(
    subject_quota: int, topics: list[TopicInput], cfg: TopicAllocationConfig
) -> None:
    if not isinstance(subject_quota, int) or isinstance(subject_quota, bool):
        raise TopicAllocationError("subject_quota must be an int")
    if subject_quota < 0:
        raise TopicAllocationError("subject_quota must be >= 0")
    if not isinstance(topics, list):
        raise TopicAllocationError("topics must be a list")
    for cfg_field, val in (
        ("weak_multiplier", cfg.weak_multiplier),
        ("neutral_multiplier", cfg.neutral_multiplier),
        ("strong_multiplier", cfg.strong_multiplier),
    ):
        if val < 0:
            raise TopicAllocationError(f"config.{cfg_field} must be >= 0")
    if not (0 <= cfg.strong_floor_pct <= 100):
        raise TopicAllocationError("config.strong_floor_pct must be in [0, 100]")

    seen_ids: set[str] = set()
    seen_topic_ids: set[str] = set()
    for t in topics:
        if t.topic_id in seen_topic_ids:
            raise TopicAllocationError(f"duplicate topic_id: {t.topic_id!r}")
        seen_topic_ids.add(t.topic_id)
        if t.preference not in PREFERENCE_VALUES:
            raise TopicAllocationError(
                f"topic {t.topic_id!r}: preference {t.preference!r} not in {sorted(PREFERENCE_VALUES)}"
            )
        for qid in t.available_ids:
            if qid in seen_ids:
                raise TopicAllocationError(
                    f"duplicate question id across topics: {qid!r}"
                )
            seen_ids.add(qid)
