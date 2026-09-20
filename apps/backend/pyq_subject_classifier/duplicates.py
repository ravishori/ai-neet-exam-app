"""Phase 4 — deterministic duplicate / near-duplicate detection.

Single local method for near-duplicates: token-Jaccard similarity over
significant words (reusing the project's existing _significant_words),
with an inverted-word-index for blocking so the full corpus (~12k rows)
stays tractable without external embeddings/AI. No merging/deletion —
detection only.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.modules.knowledge.services.grounding_check import _significant_words

from .quality_checks import normalize_for_dedup, options_hash, stem_hash

NEAR_DUP_JACCARD_THRESHOLD = 0.6
MIN_SHARED_WORDS_FOR_CANDIDATE = 4


@dataclass
class DuplicateFinding:
    question_id: str
    duplicate_group_id: str
    match_type: str  # EXACT_STEM | EXACT_STEM_AND_OPTIONS | NEAR_DUPLICATE
    similarity_score: float
    exam_year: str
    paper_code: str
    question_number: object


def find_exact_duplicates(rows: list[dict]) -> list[DuplicateFinding]:
    """rows: list of {question_id, raw_stem, raw_options, exam_year, paper_code, question_number}."""
    by_stem_hash: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_stem_hash[stem_hash(r["raw_stem"])].append(r)

    findings: list[DuplicateFinding] = []
    for h, group in sorted(by_stem_hash.items()):
        if len(group) < 2:
            continue
        group_id = f"exact-{h[:12]}"

        # Sub-split by options hash: any subgroup with >=2 rows shares both
        # stem AND options — a stronger duplicate signal than stem alone.
        by_opt: dict[str, list[dict]] = defaultdict(list)
        for r in group:
            by_opt[options_hash(r["raw_options"])].append(r)

        stem_and_options_ids: set[str] = set()
        for opt_h, sub in sorted(by_opt.items()):
            if len(sub) < 2:
                continue
            sub_group_id = f"{group_id}-{opt_h[:8]}"
            for r in sub:
                stem_and_options_ids.add(r["question_id"])
                findings.append(DuplicateFinding(
                    question_id=r["question_id"], duplicate_group_id=sub_group_id,
                    match_type="EXACT_STEM_AND_OPTIONS", similarity_score=1.0,
                    exam_year=r["exam_year"], paper_code=r["paper_code"], question_number=r["question_number"],
                ))

        # Remaining rows in this stem group (same stem, but options didn't
        # match anyone else's) are still same-stem duplicates.
        for r in group:
            if r["question_id"] in stem_and_options_ids:
                continue
            findings.append(DuplicateFinding(
                question_id=r["question_id"], duplicate_group_id=group_id,
                match_type="EXACT_STEM", similarity_score=1.0,
                exam_year=r["exam_year"], paper_code=r["paper_code"], question_number=r["question_number"],
            ))
    return findings


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def find_near_duplicates(rows: list[dict], exclude_ids: set[str]) -> list[DuplicateFinding]:
    """rows already excludes exact duplicates via `exclude_ids`."""
    word_sets: dict[str, set] = {}
    postings: dict[str, set] = defaultdict(set)
    meta = {r["question_id"]: r for r in rows}

    for r in rows:
        qid = r["question_id"]
        if qid in exclude_ids:
            continue
        words = _significant_words(normalize_for_dedup(r["raw_stem"]))
        word_sets[qid] = words
        for w in words:
            postings[w].add(qid)

    uf = _UnionFind()
    pair_scores: dict[tuple, float] = {}
    seen_pairs = set()
    ids_sorted = sorted(word_sets.keys())
    for qid in ids_sorted:
        words = word_sets[qid]
        candidates: dict[str, int] = defaultdict(int)
        for w in words:
            for other in postings[w]:
                if other != qid:
                    candidates[other] += 1
        for other, shared in candidates.items():
            if shared < MIN_SHARED_WORDS_FOR_CANDIDATE:
                continue
            pair = tuple(sorted((qid, other)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            w1, w2 = word_sets[pair[0]], word_sets[pair[1]]
            union_size = len(w1 | w2)
            if union_size == 0:
                continue
            jaccard = len(w1 & w2) / union_size
            if jaccard >= NEAR_DUP_JACCARD_THRESHOLD:
                pair_scores[pair] = jaccard
                uf.union(pair[0], pair[1])

    if not pair_scores:
        return []

    findings: list[DuplicateFinding] = []
    grouped_ids = {qid for pair in pair_scores for qid in pair}
    best_score: dict[str, float] = defaultdict(float)
    for (a, b), score in pair_scores.items():
        best_score[a] = max(best_score[a], score)
        best_score[b] = max(best_score[b], score)

    for qid in sorted(grouped_ids):
        root = uf.find(qid)
        r = meta[qid]
        findings.append(DuplicateFinding(
            question_id=qid, duplicate_group_id=f"near-{root[:8]}",
            match_type="NEAR_DUPLICATE", similarity_score=round(best_score[qid], 4),
            exam_year=r["exam_year"], paper_code=r["paper_code"], question_number=r["question_number"],
        ))
    return findings
