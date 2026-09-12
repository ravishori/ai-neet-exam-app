"""factory_sample_v2 — representative, seed-stable sampling for Seed V2 cohorts.

Does NOT modify factory_sample_v1. Avoids UUID-order subject starvation by
round-robin across subjects first, then filling secondary strata.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class V2SampleItem:
    id: str
    subject: str
    difficulty: str
    archetype: str
    visual_required: bool
    numerical: bool
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class V2SampleResult:
    policy_version: str
    seed: int
    requested_sample_size: int
    actual_sample_size: int
    sampled_ids: list[str]
    subject_distribution: dict[str, int]
    difficulty_distribution: dict[str, int]
    archetype_distribution: dict[str, int]
    visual_distribution: dict[str, int]
    numerical_distribution: dict[str, int]
    notes: list[str] = field(default_factory=list)


POLICY_V2 = "factory_sample_v2"


def default_target(n_population: int, *, k: float = 2.0, n_min: int = 5) -> int:
    if n_population <= 0:
        return 0
    return min(n_population, max(n_min, int(math.ceil(k * math.sqrt(n_population)))))


def sample_v2(
    items: list[V2SampleItem],
    *,
    seed: int,
    target: int | None = None,
) -> V2SampleResult:
    """Deterministic representative sample.

    Strategy:
    1. Round-robin across subjects until each subject has ≥1 (if target permits).
    2. Prefer including visual_required items when present.
    3. Prefer including numerical items when present.
    4. Fill remaining slots by round-robin across subject|difficulty|archetype buckets.
    """
    n = len(items)
    tgt = default_target(n) if target is None else max(0, min(int(target), n))
    notes: list[str] = []
    if tgt == 0 or n == 0:
        return V2SampleResult(
            policy_version=POLICY_V2,
            seed=seed,
            requested_sample_size=tgt,
            actual_sample_size=0,
            sampled_ids=[],
            subject_distribution={},
            difficulty_distribution={},
            archetype_distribution={},
            visual_distribution={"visual_required": 0, "non_visual": 0},
            numerical_distribution={"numerical": 0, "non_numerical": 0},
            notes=["empty_population_or_target"],
        )

    rng = random.Random(seed)
    by_id = {it.id: it for it in items}
    remaining = {it.id for it in items}
    selected: list[str] = []

    # Shuffle within subject pools for seed stability without UUID bias.
    by_subject: dict[str, list[str]] = defaultdict(list)
    for it in items:
        by_subject[it.subject].append(it.id)
    for subj in by_subject:
        rng.shuffle(by_subject[subj])

    subjects = sorted(by_subject.keys())  # alphabetical subject names — stable, not UUID
    # Phase 1: one per subject
    if tgt >= len(subjects):
        for subj in subjects:
            if by_subject[subj]:
                pick = by_subject[subj].pop()
                if pick in remaining:
                    selected.append(pick)
                    remaining.discard(pick)
        notes.append("subject_floor_applied")
    else:
        notes.append("target_smaller_than_subject_count_subject_floor_partial")
        for subj in subjects:
            if len(selected) >= tgt:
                break
            if by_subject[subj]:
                pick = by_subject[subj].pop()
                if pick in remaining:
                    selected.append(pick)
                    remaining.discard(pick)

    # Phase 2: ensure ≥1 visual_required if any exist and room remains
    visual_pool = [i for i in remaining if by_id[i].visual_required]
    if visual_pool and not any(by_id[i].visual_required for i in selected) and len(selected) < tgt:
        rng.shuffle(visual_pool)
        pick = visual_pool[0]
        selected.append(pick)
        remaining.discard(pick)
        notes.append("visual_representation_applied")
    elif not any(it.visual_required for it in items):
        notes.append("no_visual_required_in_population")

    # Phase 3: ensure ≥1 numerical if any exist and room remains
    num_pool = [i for i in remaining if by_id[i].numerical]
    if num_pool and not any(by_id[i].numerical for i in selected) and len(selected) < tgt:
        rng.shuffle(num_pool)
        pick = num_pool[0]
        selected.append(pick)
        remaining.discard(pick)
        notes.append("numerical_representation_applied")

    # Phase 4: fill via subject|difficulty|archetype round-robin
    buckets: dict[str, list[str]] = defaultdict(list)
    for iid in list(remaining):
        it = by_id[iid]
        key = f"{it.subject}|{it.difficulty}|{it.archetype}"
        buckets[key].append(iid)
    for key in buckets:
        rng.shuffle(buckets[key])
    keys = sorted(buckets.keys())
    while len(selected) < tgt and keys:
        progressed = False
        for key in keys:
            if len(selected) >= tgt:
                break
            if buckets[key]:
                pick = buckets[key].pop()
                if pick in remaining:
                    selected.append(pick)
                    remaining.discard(pick)
                    progressed = True
        if not progressed:
            break

    # Trim if somehow over (should not happen)
    selected = selected[:tgt]
    picked = [by_id[i] for i in selected]
    return V2SampleResult(
        policy_version=POLICY_V2,
        seed=seed,
        requested_sample_size=tgt,
        actual_sample_size=len(selected),
        sampled_ids=selected,
        subject_distribution=dict(Counter(p.subject for p in picked)),
        difficulty_distribution=dict(Counter(p.difficulty for p in picked)),
        archetype_distribution=dict(Counter(p.archetype for p in picked)),
        visual_distribution={
            "visual_required": sum(1 for p in picked if p.visual_required),
            "non_visual": sum(1 for p in picked if not p.visual_required),
        },
        numerical_distribution={
            "numerical": sum(1 for p in picked if p.numerical),
            "non_numerical": sum(1 for p in picked if not p.numerical),
        },
        notes=notes,
    )


def result_to_dict(result: V2SampleResult) -> dict[str, Any]:
    return {
        "policy_version": result.policy_version,
        "seed": result.seed,
        "requested_sample_size": result.requested_sample_size,
        "actual_sample_size": result.actual_sample_size,
        "sampled_ids": list(result.sampled_ids),
        "subject_distribution": dict(result.subject_distribution),
        "difficulty_distribution": dict(result.difficulty_distribution),
        "archetype_distribution": dict(result.archetype_distribution),
        "visual_distribution": dict(result.visual_distribution),
        "numerical_distribution": dict(result.numerical_distribution),
        "notes": list(result.notes),
    }


def factory_sample_v2(
    rows: list[dict[str, Any]],
    *,
    sample_size: int,
    seed: int,
) -> dict[str, Any]:
    """Convenience wrapper: dict rows → seed-stable representative sample report.

    Expected row keys (flexible aliases accepted):
      id, subject|subject_name, difficulty, question_archetype|archetype,
      visual_required, is_numerical|numerical
    """
    items: list[V2SampleItem] = []
    for r in rows:
        rid = str(r.get("id") or r.get("content_item_id") or "")
        if not rid:
            continue
        items.append(
            V2SampleItem(
                id=rid,
                subject=str(r.get("subject_name") or r.get("subject") or "Unknown"),
                difficulty=str(r.get("difficulty") or "unknown"),
                archetype=str(r.get("question_archetype") or r.get("archetype") or "unknown"),
                visual_required=bool(r.get("visual_required")),
                numerical=bool(r.get("is_numerical") if "is_numerical" in r else r.get("numerical")),
                meta=dict(r),
            )
        )
    result = sample_v2(items, seed=seed, target=sample_size)
    return result_to_dict(result)
