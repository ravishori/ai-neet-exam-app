"""Semantic duplicate detection — provider-neutral interface.

Physical deletion is forbidden. Thresholds are configurable and require
manual calibration; this module does not claim a scientifically validated cutoff.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from app.modules.cms.acquisition.mmf.normalize import normalize_text
from app.modules.cms.acquisition.mmf.schemas import CandidateRecord, CandidateStatus

DuplicateKind = Literal["EXACT_DUPLICATE", "SEMANTIC_DUPLICATE", "VALID_VARIANT"]


@dataclass(frozen=True)
class SemanticDedupConfig:
    """Configurable threshold — NOT scientifically validated by default."""

    similarity_threshold: float
    calibrated: bool = False
    calibration_note: str = (
        "Threshold requires calibration against manually reviewed examples. "
        "Do not treat the configured value as scientifically validated."
    )

    def __post_init__(self) -> None:
        if not 0.0 < self.similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be in (0, 1]")


@dataclass
class CandidateEmbedding:
    candidate_id: str
    vector: list[float]
    backend: str


@dataclass
class SimilarityPair:
    candidate_a: str
    candidate_b: str
    similarity_score: float
    relationship_type: DuplicateKind
    above_threshold: bool


@dataclass
class DuplicateCluster:
    cluster_id: str
    kind: DuplicateKind
    representative_candidate_id: str
    member_candidate_ids: list[str]
    similarity: float | None = None
    reason: str = ""
    pair_scores: list[SimilarityPair] = field(default_factory=list)


@dataclass
class SemanticDedupResult:
    clusters: list[DuplicateCluster] = field(default_factory=list)
    updated_candidates: list[CandidateRecord] = field(default_factory=list)
    pair_scores: list[SimilarityPair] = field(default_factory=list)
    embeddings: list[CandidateEmbedding] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class EmbeddingBackend(ABC):
    """Provider-neutral embedding boundary — no vendor lock-in."""

    name: str = "abstract"

    @abstractmethod
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class NullEmbeddingBackend(EmbeddingBackend):
    """Explicit no-op boundary — semantic detection NOT_EXECUTED."""

    name = "null"

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [[] for _ in texts]


class HashBagEmbeddingBackend(EmbeddingBackend):
    """Deterministic bag-of-tokens vector for tests — NOT a production embedder."""

    name = "hash_bag_test_only"

    def __init__(self, dims: int = 64):
        self.dims = dims

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dims
            for tok in normalize_text(text).split():
                idx = hash(tok) % self.dims
                vec[idx] += 1.0
            # L2 normalize
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))


class SemanticDuplicateDetector(ABC):
    """Provider-independent semantic duplicate detector."""

    @abstractmethod
    async def detect(
        self,
        candidates: list[CandidateRecord],
        *,
        config: SemanticDedupConfig | None = None,
        similarity_threshold: float | None = None,
    ) -> SemanticDedupResult:
        ...


class StubSemanticDuplicateDetector(SemanticDuplicateDetector):
    """Deterministic stub: no embeddings, no network.

    Preserves VALID / EXACT_DUPLICATE from prior exact dedupe.
    Does not invent semantic duplicates without embeddings.
    """

    async def detect(
        self,
        candidates: list[CandidateRecord],
        *,
        config: SemanticDedupConfig | None = None,
        similarity_threshold: float | None = None,
    ) -> SemanticDedupResult:
        thr = (
            config.similarity_threshold
            if config is not None
            else (similarity_threshold if similarity_threshold is not None else 0.92)
        )
        cfg = config or SemanticDedupConfig(similarity_threshold=thr, calibrated=False)
        clusters: list[DuplicateCluster] = []
        by_fp: dict[str, list[CandidateRecord]] = {}
        for c in candidates:
            if c.fingerprint:
                by_fp.setdefault(c.fingerprint, []).append(c)
        for i, (_fp, members) in enumerate(sorted(by_fp.items())):
            if len(members) < 2:
                continue
            rep = members[0].candidate_id
            clusters.append(
                DuplicateCluster(
                    cluster_id=f"exact-cluster-{i+1}",
                    kind="EXACT_DUPLICATE",
                    representative_candidate_id=rep,
                    member_candidate_ids=[m.candidate_id for m in members],
                    similarity=1.0,
                    reason="deterministic_exact_fingerprint_cluster",
                )
            )
        return SemanticDedupResult(
            clusters=clusters,
            updated_candidates=list(candidates),
            pair_scores=[],
            embeddings=[],
            metadata={
                "mode": "stub_no_embeddings",
                "semantic_deduplication_status": "NOT_EXECUTED",
                "similarity_threshold": cfg.similarity_threshold,
                "threshold_calibrated": cfg.calibrated,
                "calibration_note": cfg.calibration_note,
                "external_embedding_calls": 0,
                "note": "Semantic embeddings deferred; use ConfigurableSemanticDuplicateDetector with a backend.",
            },
        )


class ConfigurableSemanticDuplicateDetector(SemanticDuplicateDetector):
    """Production interface: embeddings + pair scores + clusters; never deletes."""

    def __init__(self, backend: EmbeddingBackend | None = None):
        self.backend = backend or NullEmbeddingBackend()

    async def detect(
        self,
        candidates: list[CandidateRecord],
        *,
        config: SemanticDedupConfig | None = None,
        similarity_threshold: float | None = None,
    ) -> SemanticDedupResult:
        thr = (
            config.similarity_threshold
            if config is not None
            else (similarity_threshold if similarity_threshold is not None else 0.92)
        )
        cfg = config or SemanticDedupConfig(similarity_threshold=thr, calibrated=False)

        if isinstance(self.backend, NullEmbeddingBackend) or self.backend.name == "null":
            stub = await StubSemanticDuplicateDetector().detect(candidates, config=cfg)
            stub.metadata["backend"] = self.backend.name
            return stub

        texts = [
            f"{c.stem} " + " ".join(c.options.model_dump()[k] for k in ("A", "B", "C", "D"))
            for c in candidates
        ]
        vectors = await self.backend.embed_texts(texts)
        embeddings = [
            CandidateEmbedding(candidate_id=c.candidate_id, vector=v, backend=self.backend.name)
            for c, v in zip(candidates, vectors, strict=True)
        ]

        pairs: list[SimilarityPair] = []
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

        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                score = cosine_similarity(vectors[i], vectors[j])
                # Exact fingerprint short-circuit
                if (
                    candidates[i].fingerprint
                    and candidates[i].fingerprint == candidates[j].fingerprint
                ):
                    rel: DuplicateKind = "EXACT_DUPLICATE"
                    score = 1.0
                elif score >= cfg.similarity_threshold:
                    rel = "SEMANTIC_DUPLICATE"
                else:
                    # Near-miss as variant annotation only when moderately close
                    rel = "VALID_VARIANT"
                    if score < cfg.similarity_threshold * 0.85:
                        continue
                above = score >= cfg.similarity_threshold or rel == "EXACT_DUPLICATE"
                pair = SimilarityPair(
                    candidate_a=candidates[i].candidate_id,
                    candidate_b=candidates[j].candidate_id,
                    similarity_score=round(score, 6),
                    relationship_type=rel if above or rel == "EXACT_DUPLICATE" else "VALID_VARIANT",
                    above_threshold=above,
                )
                pairs.append(pair)
                if above or rel == "EXACT_DUPLICATE":
                    union(candidates[i].candidate_id, candidates[j].candidate_id)

        # Build clusters; mark non-representatives without deleting
        groups: dict[str, list[CandidateRecord]] = {}
        for c in candidates:
            if c.candidate_id in parent or any(
                p.candidate_a == c.candidate_id or p.candidate_b == c.candidate_id for p in pairs if p.above_threshold
            ):
                if any(p.above_threshold and (p.candidate_a == c.candidate_id or p.candidate_b == c.candidate_id) for p in pairs):
                    groups.setdefault(find(c.candidate_id), []).append(c)

        clusters: list[DuplicateCluster] = []
        updated: list[CandidateRecord] = []
        clustered_ids: set[str] = set()
        for idx, (_root, members) in enumerate(sorted(groups.items(), key=lambda x: x[0])):
            if len(members) < 2:
                continue
            rep = members[0].candidate_id
            kind: DuplicateKind = "SEMANTIC_DUPLICATE"
            if all(m.fingerprint and m.fingerprint == members[0].fingerprint for m in members):
                kind = "EXACT_DUPLICATE"
            member_ids = [m.candidate_id for m in members]
            cluster_pairs = [
                p
                for p in pairs
                if p.candidate_a in member_ids and p.candidate_b in member_ids and p.above_threshold
            ]
            clusters.append(
                DuplicateCluster(
                    cluster_id=f"sem-cluster-{idx+1}",
                    kind=kind,
                    representative_candidate_id=rep,
                    member_candidate_ids=member_ids,
                    similarity=max((p.similarity_score for p in cluster_pairs), default=None),
                    reason="embedding_similarity_above_configured_threshold",
                    pair_scores=cluster_pairs,
                )
            )
            for m in members:
                clustered_ids.add(m.candidate_id)
                data = m.model_dump(by_alias=True)
                if m.candidate_id == rep:
                    updated.append(m)
                    continue
                data["status"] = (
                    CandidateStatus.EXACT_DUPLICATE
                    if kind == "EXACT_DUPLICATE"
                    else CandidateStatus.SEMANTIC_DUPLICATE
                )
                data["duplicate_of"] = rep
                data["duplicate_reason"] = kind.lower()
                updated.append(CandidateRecord.model_validate(data))

        for c in candidates:
            if c.candidate_id not in clustered_ids:
                updated.append(c)

        return SemanticDedupResult(
            clusters=clusters,
            updated_candidates=updated,
            pair_scores=pairs,
            embeddings=embeddings,
            metadata={
                "mode": "configurable_embedding_backend",
                "semantic_deduplication_status": "EXECUTED",
                "backend": self.backend.name,
                "similarity_threshold": cfg.similarity_threshold,
                "threshold_calibrated": cfg.calibrated,
                "calibration_note": cfg.calibration_note,
                "external_embedding_calls": 1,
                "candidates_deleted": 0,
                "note": "Candidates are marked, never physically deleted.",
            },
        )


def mark_valid_variants(
    candidates: list[CandidateRecord],
    *,
    shared_concept: str | None = None,
) -> list[CandidateRecord]:
    """Example helper: same concept alone does not imply semantic duplicate."""
    out: list[CandidateRecord] = []
    for c in candidates:
        data = c.model_dump(by_alias=True)
        if (
            shared_concept
            and c.concept == shared_concept
            and c.status == CandidateStatus.VALID
            and c.duplicate_of is None
        ):
            data["status"] = CandidateStatus.VALID_VARIANT
            data["duplicate_reason"] = "shared_concept_not_duplicate"
        out.append(CandidateRecord.model_validate(data))
    return out


__all__ = [
    "CandidateEmbedding",
    "ConfigurableSemanticDuplicateDetector",
    "DuplicateCluster",
    "DuplicateKind",
    "EmbeddingBackend",
    "HashBagEmbeddingBackend",
    "NullEmbeddingBackend",
    "SemanticDedupConfig",
    "SemanticDedupResult",
    "SemanticDuplicateDetector",
    "SimilarityPair",
    "StubSemanticDuplicateDetector",
    "cosine_similarity",
    "mark_valid_variants",
]
