"""Calibration clustering for MMF semantic deduplication (analysis overlays only)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from app.modules.cms.acquisition.mmf.normalize import candidate_fingerprint
from app.modules.cms.acquisition.mmf.semantic_dedupe import cosine_similarity

Relationship = Literal["EXACT_DUPLICATE", "SEMANTIC_DUPLICATE", "VALID_VARIANT", "UNCERTAIN"]

DEFAULT_THRESHOLDS = (0.80, 0.85, 0.90, 0.92, 0.95)


@dataclass
class ScoredPair:
    candidate_a: str
    candidate_b: str
    provider_a: str
    provider_b: str
    similarity_score: float
    exact_fingerprint_match: bool
    cross_provider: bool


@dataclass
class ClusterProposal:
    cluster_id: str
    threshold: float
    member_ids: list[str]
    representative_candidate_id: str
    relationship: Relationship
    pair_evidence: list[dict[str, Any]] = field(default_factory=list)
    representative_rationale: list[str] = field(default_factory=list)
    note: str = "representative_is_proposal_only"


def classify_pair(
    score: float,
    *,
    threshold: float,
    exact: bool,
) -> Relationship:
    if exact:
        return "EXACT_DUPLICATE"
    if score >= threshold:
        # Proposed semantic duplicate — NOT scientifically calibrated
        return "SEMANTIC_DUPLICATE"
    # Near-threshold band for variants / uncertainty
    if score >= threshold - 0.03:
        return "UNCERTAIN"
    if score >= threshold - 0.08:
        return "VALID_VARIANT"
    return "VALID_VARIANT"  # unused when edge filtered


def compute_pairwise_scores(
    *,
    candidate_ids: list[str],
    providers: list[str],
    vectors: list[list[float]],
    fingerprints: list[str],
    min_score_to_keep: float = 0.72,
) -> list[ScoredPair]:
    n = len(candidate_ids)
    pairs: list[ScoredPair] = []
    for i in range(n):
        for j in range(i + 1, n):
            exact = bool(fingerprints[i] and fingerprints[i] == fingerprints[j])
            score = 1.0 if exact else cosine_similarity(vectors[i], vectors[j])
            if not exact and score < min_score_to_keep:
                continue
            pairs.append(
                ScoredPair(
                    candidate_a=candidate_ids[i],
                    candidate_b=candidate_ids[j],
                    provider_a=providers[i],
                    provider_b=providers[j],
                    similarity_score=round(float(score), 6),
                    exact_fingerprint_match=exact,
                    cross_provider=providers[i] != providers[j],
                )
            )
    pairs.sort(key=lambda p: -p.similarity_score)
    return pairs


def clusters_at_threshold(
    pairs: Sequence[ScoredPair],
    *,
    threshold: float,
    all_ids: Sequence[str],
    scores: dict[str, float] | None = None,
) -> list[ClusterProposal]:
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    edge_meta: dict[tuple[str, str], ScoredPair] = {}
    for p in pairs:
        rel = classify_pair(p.similarity_score, threshold=threshold, exact=p.exact_fingerprint_match)
        if rel in {"SEMANTIC_DUPLICATE", "EXACT_DUPLICATE"} or (
            rel == "UNCERTAIN" and p.similarity_score >= threshold - 0.02
        ):
            # Cluster only on strong edges (>= threshold or exact); uncertain near-threshold
            # included only if very close to threshold for review clusters
            if p.similarity_score >= threshold or p.exact_fingerprint_match:
                union(p.candidate_a, p.candidate_b)
                key = (p.candidate_a, p.candidate_b) if p.candidate_a < p.candidate_b else (p.candidate_b, p.candidate_a)
                edge_meta[key] = p

    groups: dict[str, list[str]] = defaultdict(list)
    for cid in all_ids:
        if cid in parent:
            groups[find(cid)].append(cid)

    clusters: list[ClusterProposal] = []
    for idx, (_root, members) in enumerate(sorted(groups.items(), key=lambda x: (-len(x[1]), x[0]))):
        if len(members) < 2:
            continue
        members = sorted(set(members))
        evidence = []
        best_rel: Relationship = "SEMANTIC_DUPLICATE"
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                key = (a, b) if a < b else (b, a)
                p = edge_meta.get(key)
                if not p:
                    continue
                rel = classify_pair(
                    p.similarity_score, threshold=threshold, exact=p.exact_fingerprint_match
                )
                if rel == "EXACT_DUPLICATE":
                    best_rel = "EXACT_DUPLICATE"
                evidence.append(
                    {
                        "candidate_a": p.candidate_a,
                        "candidate_b": p.candidate_b,
                        "similarity_score": p.similarity_score,
                        "relationship": rel,
                        "cross_provider": p.cross_provider,
                    }
                )
        # Representative: highest score if provided, else first id
        rep = members[0]
        if scores:
            rep = max(members, key=lambda m: (scores.get(m, 0.0), m))
        clusters.append(
            ClusterProposal(
                cluster_id=f"T{threshold:.2f}-C{idx+1:04d}",
                threshold=threshold,
                member_ids=members,
                representative_candidate_id=rep,
                relationship=best_rel,
                pair_evidence=evidence,
            )
        )
    return clusters


def cross_provider_stats(pairs: Sequence[ScoredPair], *, threshold: float) -> dict[str, Any]:
    combos = {
        "gemini_anthropic": ("gemini", "anthropic"),
        "gemini_openai": ("gemini", "openai"),
        "anthropic_openai": ("anthropic", "openai"),
    }
    out: dict[str, Any] = {}
    for label, (pa, pb) in combos.items():
        subset = [
            p
            for p in pairs
            if {p.provider_a, p.provider_b} == {pa, pb}
        ]
        high = [p for p in subset if p.similarity_score >= threshold]
        counts = {"SEMANTIC_DUPLICATE": 0, "VALID_VARIANT": 0, "UNCERTAIN": 0, "EXACT_DUPLICATE": 0}
        for p in subset:
            if p.similarity_score < threshold - 0.08 and not p.exact_fingerprint_match:
                continue
            rel = classify_pair(p.similarity_score, threshold=threshold, exact=p.exact_fingerprint_match)
            if p.similarity_score >= threshold - 0.08 or p.exact_fingerprint_match:
                counts[rel] = counts.get(rel, 0) + 1
        out[label] = {
            "pair_count_ge_0.72": len(subset),
            "high_similarity_pair_count_ge_threshold": len(high),
            "relationship_counts_near_band": counts,
        }
    return out


def representative_score(
    *,
    candidate_id: str,
    grounding_hint: str | None,
    structural_codes: list[str],
    type_mismatch: bool,
    difficulty_disagree: bool,
    concept_unresolved: bool,
    explanation_fail: bool,
    provider_rarity_bonus: float = 0.0,
) -> tuple[float, list[str]]:
    score = 1.0
    reasons: list[str] = ["base=1.0"]
    if grounding_hint == "DIRECT":
        score += 0.5
        reasons.append("+0.5 DIRECT grounding")
    elif grounding_hint == "SUPPORTED_INFERENCE":
        score += 0.25
        reasons.append("+0.25 SUPPORTED_INFERENCE")
    elif grounding_hint == "WEAK/UNCLEAR":
        score -= 0.25
        reasons.append("-0.25 WEAK/UNCLEAR")
    if structural_codes:
        score -= 0.4 * min(3, len(structural_codes))
        reasons.append(f"-structural:{structural_codes}")
    if type_mismatch:
        score -= 0.05
        reasons.append("-0.05 type_mismatch")
    if difficulty_disagree:
        score -= 0.05
        reasons.append("-0.05 difficulty_disagree")
    if concept_unresolved:
        score -= 0.1
        reasons.append("-0.1 concept_unresolved")
    if explanation_fail:
        score -= 0.5
        reasons.append("-0.5 explanation_fail")
    if provider_rarity_bonus:
        score += provider_rarity_bonus
        reasons.append(f"+provider_diversity={provider_rarity_bonus}")
    return score, reasons


def fingerprint_for_raw(raw: dict[str, Any]) -> str:
    opts = raw.get("options") or {}
    return candidate_fingerprint(
        stem=str(raw.get("stem") or ""),
        options={k: str(opts.get(k) or "") for k in ("A", "B", "C", "D")},
        correct_answer=str(raw.get("correct_answer") or ""),
    )


__all__ = [
    "ClusterProposal",
    "DEFAULT_THRESHOLDS",
    "Relationship",
    "ScoredPair",
    "classify_pair",
    "clusters_at_threshold",
    "compute_pairwise_scores",
    "cross_provider_stats",
    "fingerprint_for_raw",
    "representative_score",
]
