"""Stratified calibration-pair sampling for MMF semantic dedup (human review).

Does not assign DUPLICATE/VALID_VARIANT/UNCERTAIN — those fields stay blank.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

SelectionBucket = Literal[
    "VERY_HIGH_SIMILARITY",
    "THRESHOLD_REGION",
    "CROSS_PROVIDER",
    "SAME_PROVIDER",
    "FILL",
]

ProviderRel = Literal[
    "same_gemini",
    "same_anthropic",
    "same_openai",
    "gemini_anthropic",
    "gemini_openai",
    "anthropic_openai",
    "other",
]


@dataclass(frozen=True)
class PairKey:
    a: str
    b: str

    @staticmethod
    def of(x: str, y: str) -> "PairKey":
        return PairKey(x, y) if x < y else PairKey(y, x)


@dataclass
class CandidatePairScore:
    candidate_a: str
    candidate_b: str
    provider_a: str
    provider_b: str
    similarity_score: float
    cross_provider: bool


@dataclass
class SampledPair:
    pair_id: str
    candidate_id_a: str
    candidate_id_b: str
    provider_a: str
    provider_b: str
    cosine_similarity: float
    selection_buckets: list[str]
    provider_relationship: ProviderRel
    display_order_swapped: bool = False


@dataclass
class StratifiedSampleResult:
    pairs: list[SampledPair]
    quotas: dict[str, int]
    filled: dict[str, int]
    shortfalls: dict[str, int]
    pool_stats: dict[str, Any] = field(default_factory=dict)


def provider_relationship(pa: str, pb: str) -> ProviderRel:
    s = {pa, pb}
    if pa == pb:
        if pa == "gemini":
            return "same_gemini"
        if pa == "anthropic":
            return "same_anthropic"
        if pa == "openai":
            return "same_openai"
        return "other"
    if s == {"gemini", "anthropic"}:
        return "gemini_anthropic"
    if s == {"gemini", "openai"}:
        return "gemini_openai"
    if s == {"anthropic", "openai"}:
        return "anthropic_openai"
    return "other"


def pair_id_for(a: str, b: str, score: float) -> str:
    k = PairKey.of(a, b)
    key = f"{k.a}|{k.b}|{score:.6f}"
    return "PAIR-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12].upper()


def blank_review_fields() -> dict[str, Any]:
    return {
        "human_label": "",
        "human_reason": "",
        "reviewer": "",
        "reviewed_at": "",
        "reviewer_1_label": "",
        "reviewer_2_label": "",
        "adjudicated_label": "",
    }


def stratified_calibration_sample(
    pairs: Sequence[CandidatePairScore],
    *,
    target_total: int = 80,
    n_very_high: int = 20,
    n_threshold: int = 20,
    n_cross: int = 20,
    n_same: int = 20,
    very_high_min: float = 0.95,
    threshold_low: float = 0.90,
    threshold_high: float = 0.95,
    seed: int = 20260912,
) -> StratifiedSampleResult:
    """Select ~80 pairs with deliberate strata. Human labels are NOT assigned."""
    rng = random.Random(seed)
    quotas = {
        "VERY_HIGH_SIMILARITY": n_very_high,
        "THRESHOLD_REGION": n_threshold,
        "CROSS_PROVIDER": n_cross,
        "SAME_PROVIDER": n_same,
    }

    best: dict[PairKey, CandidatePairScore] = {}
    for p in pairs:
        if p.candidate_a == p.candidate_b:
            continue
        k = PairKey.of(p.candidate_a, p.candidate_b)
        prev = best.get(k)
        if prev is None or p.similarity_score > prev.similarity_score:
            best[k] = p
    universe = list(best.values())

    pools: dict[str, list[CandidatePairScore]] = {
        "VERY_HIGH_SIMILARITY": [p for p in universe if p.similarity_score >= very_high_min],
        "THRESHOLD_REGION": [
            p for p in universe if threshold_low <= p.similarity_score < threshold_high
        ],
        "CROSS_PROVIDER": [p for p in universe if p.cross_provider and p.similarity_score >= 0.85],
        "SAME_PROVIDER": [
            p for p in universe if (not p.cross_provider) and p.similarity_score >= 0.85
        ],
    }

    selected: dict[PairKey, SampledPair] = {}
    bucket_members: dict[str, set[PairKey]] = {b: set() for b in quotas}
    bucket_members["FILL"] = set()

    def ensure_selected(p: CandidatePairScore) -> PairKey:
        k = PairKey.of(p.candidate_a, p.candidate_b)
        if k in selected:
            return k
        swap = rng.random() < 0.5
        ca, cb = (p.candidate_b, p.candidate_a) if swap else (p.candidate_a, p.candidate_b)
        pa, pb = (p.provider_b, p.provider_a) if swap else (p.provider_a, p.provider_b)
        selected[k] = SampledPair(
            pair_id=pair_id_for(p.candidate_a, p.candidate_b, p.similarity_score),
            candidate_id_a=ca,
            candidate_id_b=cb,
            provider_a=pa,
            provider_b=pb,
            cosine_similarity=round(p.similarity_score, 6),
            selection_buckets=[],
            provider_relationship=provider_relationship(pa, pb),
            display_order_swapped=swap,
        )
        return k

    def tag(p: CandidatePairScore, bucket: str) -> None:
        k = ensure_selected(p)
        if bucket not in selected[k].selection_buckets:
            selected[k].selection_buckets.append(bucket)
        bucket_members[bucket].add(k)

    def fill_bucket(bucket: str, n: int, pool: list[CandidatePairScore]) -> None:
        items = list(pool)
        rng.shuffle(items)
        if bucket == "CROSS_PROVIDER":
            groups = {
                "gemini_anthropic": [],
                "gemini_openai": [],
                "anthropic_openai": [],
            }
            for p in items:
                rel = provider_relationship(p.provider_a, p.provider_b)
                if rel in groups:
                    groups[rel].append(p)
            for g in groups.values():
                rng.shuffle(g)
            # round-robin until quota or exhausted
            while len(bucket_members[bucket]) < n:
                progressed = False
                for g in groups.values():
                    if len(bucket_members[bucket]) >= n:
                        break
                    while g:
                        p = g.pop()
                        k = PairKey.of(p.candidate_a, p.candidate_b)
                        if k in bucket_members[bucket]:
                            continue
                        if len(selected) >= target_total and k not in selected:
                            continue
                        tag(p, bucket)
                        progressed = True
                        break
                if not progressed:
                    break
            return

        for p in items:
            if len(bucket_members[bucket]) >= n:
                break
            k = PairKey.of(p.candidate_a, p.candidate_b)
            if k in bucket_members[bucket]:
                continue
            if len(selected) >= target_total and k not in selected:
                # can still tag existing selected pairs into this bucket
                if k not in selected:
                    continue
            tag(p, bucket)

    # Pass 1: fill each stratum (may overlap; new pairs stop at target_total)
    for bucket, n in quotas.items():
        fill_bucket(bucket, n, pools[bucket])

    # Pass 2: if under target, FILL from remaining high-sim pairs
    if len(selected) < target_total:
        remainder = [
            p
            for p in universe
            if PairKey.of(p.candidate_a, p.candidate_b) not in selected
            and p.similarity_score >= 0.85
        ]
        remainder.sort(key=lambda x: (-x.similarity_score, x.candidate_a, x.candidate_b))
        # shuffle among top candidates for bias control
        top = remainder[: max(200, target_total * 4)]
        rng.shuffle(top)
        for p in top:
            if len(selected) >= target_total:
                break
            tag(p, "FILL")

    filled = {b: len(bucket_members[b]) for b in list(quotas.keys()) + ["FILL"]}
    shortfalls = {b: max(0, quotas[b] - filled[b]) for b in quotas}

    out = list(selected.values())
    # Ensure every pair has at least one bucket tag
    for p in out:
        if not p.selection_buckets:
            p.selection_buckets = ["FILL"]
            bucket_members["FILL"].add(PairKey.of(p.candidate_id_a, p.candidate_id_b))
    filled["FILL"] = len(bucket_members["FILL"])
    rng.shuffle(out)

    return StratifiedSampleResult(
        pairs=out,
        quotas=quotas,
        filled=filled,
        shortfalls=shortfalls,
        pool_stats={
            "universe_unique_pairs": len(universe),
            "very_high_pool": len(pools["VERY_HIGH_SIMILARITY"]),
            "threshold_pool": len(pools["THRESHOLD_REGION"]),
            "cross_provider_pool_ge_0.85": len(pools["CROSS_PROVIDER"]),
            "same_provider_pool_ge_0.85": len(pools["SAME_PROVIDER"]),
            "selected_total": len(out),
            "multi_bucket_pairs": sum(1 for p in out if len(p.selection_buckets) > 1),
            "target_total": target_total,
        },
    )


def validate_sample(
    sample: StratifiedSampleResult,
    *,
    valid_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    seen_keys: set[PairKey] = set()
    seen_pair_ids: set[str] = set()
    for p in sample.pairs:
        if p.candidate_id_a not in valid_ids or p.candidate_id_b not in valid_ids:
            errors.append(f"unknown_id:{p.pair_id}")
        if p.candidate_id_a == p.candidate_id_b:
            errors.append(f"self_pair:{p.pair_id}")
        k = PairKey.of(p.candidate_id_a, p.candidate_id_b)
        if k in seen_keys:
            errors.append(f"duplicate_pair:{p.pair_id}")
        seen_keys.add(k)
        if p.pair_id in seen_pair_ids:
            errors.append(f"duplicate_pair_id:{p.pair_id}")
        seen_pair_ids.add(p.pair_id)
    return errors


__all__ = [
    "CandidatePairScore",
    "PairKey",
    "SampledPair",
    "StratifiedSampleResult",
    "blank_review_fields",
    "pair_id_for",
    "provider_relationship",
    "stratified_calibration_sample",
    "validate_sample",
]
