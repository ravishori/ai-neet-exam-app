"""EXECUTE real embedding-backed semantic dedup calibration (read-only analysis).

Usage (from apps/backend):
  .venv/Scripts/python.exe scripts/run_mmf_semantic_dedup_calibration.py --authorize-embeddings

Does NOT mutate candidate JSONL, ContentItems, taxonomy, or ECAEP.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, text

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.cms.acquisition.mmf.config import redact_secrets
from app.modules.cms.acquisition.mmf.embedding_backends import (
    EmbeddingConfigurationError,
    embedding_status_from_settings,
    select_production_embedding_backend,
)
from app.modules.cms.acquisition.mmf.semantic_calibration import (
    DEFAULT_THRESHOLDS,
    classify_pair,
    clusters_at_threshold,
    compute_pairwise_scores,
    cross_provider_stats,
    fingerprint_for_raw,
    representative_score,
)
from app.modules.cms.acquisition.mmf.semantic_input import (
    SEMANTIC_INPUT_VERSION,
    EmbeddingDiskCache,
    build_semantic_input,
    cache_key_for_embedding,
    semantic_input_hash,
)
from app.modules.cms.acquisition.mmf.validation_v2 import validate_candidate_v2
from app.modules.cms.models import ContentItem

REPO = BACKEND.parents[1]
BATCH = "BIO11-CH04-MMF-POC-B001"
CAND_DIR = REPO / "docs" / "acquisition" / "candidates" / BATCH
OUT_DIR = CAND_DIR / "semantic_dedup_v1"
EXPECTED_SHA = "2c092dd3d16cf15f2d3bcaf0636653c6e7b370c9b2159ffad73df3601643ba87"
NORMALIZED_SHA = "c46181039a967666acc432a348833f942f9eee02dc44b455e79132efa95c04ea"
IMMUTABLE = {
    "candidates_normalized.jsonl": NORMALIZED_SHA,
    "gemini_raw.jsonl": "640bc661c2db1c06ce74451ad87f40cd1cb00013840574a31c93062a30f6dace",
    "anthropic_raw.jsonl": "67c46a6dc82569c14236abe752ea11afdba2f0fa5d6a977302c11d17e78213f5",
    "openai_raw.jsonl": "cf5b6b89a5b840277cf37717d24d2867eab0b121b11e763f51f355655925e567",
    "candidates_raw_combined.jsonl": "92deedd6dd7dec93a9225e17a234a6213dd1111966d73f88e56671c11b71a943",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


async def db_snapshot() -> dict[str, Any]:
    batches = {
        "CH01": ("20260911-BIO11-CH01-B001", "bio11-ch01-b001"),
        "CH02": ("20260911-BIO11-CH02-B001", "bio11-ch02-b001"),
        "CH03": ("20260912-BIO11-CH03-B001", "bio11-ch03-b001"),
        "CH04": ("20260912-BIO11-CH04-B001", "bio11-ch04-b001"),
        "PHY02": ("20260911-PHY11-CH02-B001", "phy11-ch02-b001"),
    }

    def is_batch(item: ContentItem, batch: str, slug_bit: str) -> bool:
        tags = item.tags or []
        if batch in tags or any(batch in str(t) for t in tags):
            return True
        return bool(item.slug and slug_bit in (item.slug or "").lower())

    async with AsyncSessionLocal() as session:
        tax = (
            await session.execute(
                text(
                    "SELECT (SELECT count(*) FROM academic.subjects WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.chapters WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.topics WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.concepts WHERE deleted_at IS NULL)"
                )
            )
        ).one()
        items = (await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))).scalars().all()

        def bucket(key: str) -> dict[str, int]:
            batch, slug = batches[key]
            subset = [i for i in items if is_batch(i, batch, slug)]
            return {**dict(Counter(i.status for i in subset)), "_total": len(subset)}

        return {
            "taxonomy": {"subjects": tax[0], "chapters": tax[1], "topics": tax[2], "concepts": tax[3]},
            "CH01": bucket("CH01"),
            "CH02": bucket("CH02"),
            "CH03": bucket("CH03"),
            "CH04": bucket("CH04"),
            "PHY02": bucket("PHY02"),
        }


def db_ok(snap: dict[str, Any]) -> bool:
    return (
        snap["CH01"].get("PUBLISHED") == 100
        and snap["CH02"].get("PUBLISHED") == 100
        and snap["CH03"].get("PUBLISHED") == 100
        and snap["CH04"].get("IN_REVIEW") == 100
        and snap["PHY02"].get("DRAFT") == 24
        and [
            snap["taxonomy"]["subjects"],
            snap["taxonomy"]["chapters"],
            snap["taxonomy"]["topics"],
            snap["taxonomy"]["concepts"],
        ]
        == [4, 36, 125, 192]
    )


async def embed_with_cache(
    rows: list[dict[str, Any]],
    backend,
    cache: EmbeddingDiskCache,
) -> tuple[list[list[float]], list[dict[str, Any]], dict[str, Any]]:
    manifest_rows: list[dict[str, Any]] = []
    vectors: list[list[float] | None] = [None] * len(rows)
    to_embed_idx: list[int] = []
    to_embed_texts: list[str] = []
    cfg = backend.config_manifest()

    for i, raw in enumerate(rows):
        sem = build_semantic_input(raw)
        sem_hash = hashlib.sha256(sem.encode("utf-8")).hexdigest()
        assert sem_hash == semantic_input_hash(raw)
        key = cache_key_for_embedding(
            semantic_input_sha256=sem_hash,
            embedding_provider=cfg["embedding_provider"],
            embedding_model=cfg["embedding_model"],
            embedding_dimension=cfg["embedding_dimension"],
            embedding_configuration_version=cfg["embedding_configuration_version"],
        )
        meta = {
            "candidate_id": raw["candidate_id"],
            "provider": raw["provider"],
            "semantic_input_version": SEMANTIC_INPUT_VERSION,
            "semantic_input_sha256": sem_hash,
            "cache_key": key,
            "fingerprint": fingerprint_for_raw(raw),
        }
        cached = cache.get(key)
        if cached is not None:
            if len(cached) != cfg["embedding_dimension"]:
                raise EmbeddingConfigurationError("cached_vector_dimension_mismatch")
            vectors[i] = cached
            meta["cache"] = "HIT"
        else:
            to_embed_idx.append(i)
            to_embed_texts.append(sem)
            meta["cache"] = "MISS"
        manifest_rows.append(meta)

    if to_embed_texts:
        new_vecs = await backend.embed_texts(to_embed_texts)
        for j, idx in enumerate(to_embed_idx):
            vec = new_vecs[j]
            vectors[idx] = vec
            m = manifest_rows[idx]
            cache.put(
                m["cache_key"],
                vec,
                candidate_id=m["candidate_id"],
                semantic_input_sha256=m["semantic_input_sha256"],
                embedding_provider=cfg["embedding_provider"],
                embedding_model=cfg["embedding_model"],
                embedding_dimension=cfg["embedding_dimension"],
            )

    if any(v is None for v in vectors):
        raise RuntimeError("incomplete_embeddings")

    stats = {
        "embedded_live": len(to_embed_texts),
        "cache_hits": cache.hits,
        "cache_misses": cache.misses,
        "http_calls": getattr(backend, "http_calls", 0),
        "tokens_estimated": getattr(backend, "tokens_estimated", 0),
        "max_candidates": 919,
        "actual_candidates": len(rows),
    }
    return [v for v in vectors if v is not None], manifest_rows, stats


async def amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize-embeddings", action="store_true")
    args = parser.parse_args()
    if not args.authorize_embeddings:
        print("Refusing: pass --authorize-embeddings to run paid/network embedding calls")
        return 2

    started = datetime.now(UTC).isoformat()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = OUT_DIR / "embedding_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Immutable check
    immutable_check = {}
    for name, exp in IMMUTABLE.items():
        got = sha256_file(CAND_DIR / name)
        immutable_check[name] = {"expected": exp, "actual": got, "unchanged": got == exp}
    if not all(v["unchanged"] for v in immutable_check.values()):
        print(json.dumps({"verdict": "RED", "reason": "immutable_artifact_hash_mismatch", "immutable_check": immutable_check}, indent=2))
        return 1

    pre = await db_snapshot()
    if not db_ok(pre):
        print(json.dumps({"verdict": "RED", "reason": "pre_db_control_mismatch", "pre": pre}, indent=2))
        return 1

    status = embedding_status_from_settings()
    try:
        backend = select_production_embedding_backend()
    except EmbeddingConfigurationError as exc:
        payload = {
            "verdict": "AMBER",
            "reason": str(exc),
            "embedding_status": redact_secrets(status),
            "component_status": {
                "embedding_backend": "STUB_OR_UNAVAILABLE",
                "semantic_dedup_execution": "NOT_EXECUTED",
                "calibration": "NOT_CALIBRATED",
            },
        }
        (OUT_DIR / "semantic_dedup_results.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(payload, indent=2))
        return 0

    rows = load_jsonl(CAND_DIR / "candidates_normalized.jsonl")
    if len(rows) != 919:
        print(json.dumps({"verdict": "RED", "reason": f"expected_919_got_{len(rows)}"}, indent=2))
        return 1

    # Validator V2 overlays (read-only, in-memory)
    v2_by_id: dict[str, Any] = {}
    for raw in rows:
        r = validate_candidate_v2(raw, expected_source_sha=EXPECTED_SHA)
        v2_by_id[raw["candidate_id"]] = {
            "structural_reason_codes": [f.reason_code for f in r.structural_findings],
            "question_type_status": r.metadata_audit.get("question_type_status"),
            "difficulty_agreement": r.metadata_audit.get("difficulty_agreement"),
            "concept_status": r.concept_status,
        }

    cache = EmbeddingDiskCache(cache_dir)
    vectors, manifest_rows, embed_stats = await embed_with_cache(rows, backend, cache)

    ids = [r["candidate_id"] for r in rows]
    providers = [r["provider"] for r in rows]
    fps = [m["fingerprint"] for m in manifest_rows]

    pairs = compute_pairwise_scores(
        candidate_ids=ids,
        providers=providers,
        vectors=vectors,
        fingerprints=fps,
        min_score_to_keep=0.72,
    )

    # Representative scores
    provider_counts = Counter(providers)
    rep_scores: dict[str, float] = {}
    rep_reasons: dict[str, list[str]] = {}
    for raw in rows:
        cid = raw["candidate_id"]
        v2 = v2_by_id[cid]
        rarity = 0.05 if provider_counts[raw["provider"]] < 350 else 0.0
        sc, reasons = representative_score(
            candidate_id=cid,
            grounding_hint=None,  # quality analysis grounding not reloaded; optional
            structural_codes=v2["structural_reason_codes"],
            type_mismatch=v2["question_type_status"] == "MISMATCH",
            difficulty_disagree=v2["difficulty_agreement"] is False,
            concept_unresolved=v2["concept_status"] == "UNRESOLVED",
            explanation_fail="EXPLANATION_CONTRADICTS_ANSWER_LETTER" in v2["structural_reason_codes"],
            provider_rarity_bonus=rarity,
        )
        rep_scores[cid] = sc
        rep_reasons[cid] = reasons

    threshold_results: dict[str, Any] = {}
    all_clusters: dict[str, Any] = {}
    for thr in DEFAULT_THRESHOLDS:
        clusters = clusters_at_threshold(pairs, threshold=thr, all_ids=ids, scores=rep_scores)
        for c in clusters:
            c.representative_rationale = rep_reasons.get(c.representative_candidate_id, [])
        # Counts
        sem_pairs = [
            p
            for p in pairs
            if classify_pair(p.similarity_score, threshold=thr, exact=p.exact_fingerprint_match)
            == "SEMANTIC_DUPLICATE"
        ]
        unc_pairs = [
            p
            for p in pairs
            if classify_pair(p.similarity_score, threshold=thr, exact=p.exact_fingerprint_match)
            == "UNCERTAIN"
            and p.similarity_score >= thr - 0.03
        ]
        var_pairs = [
            p
            for p in pairs
            if thr - 0.08 <= p.similarity_score < thr - 0.03 and not p.exact_fingerprint_match
        ]
        clustered_ids = set()
        for c in clusters:
            clustered_ids.update(c.member_ids)
        unique_est = len(ids) - sum(len(c.member_ids) - 1 for c in clusters)
        threshold_results[f"{thr:.2f}"] = {
            "threshold": thr,
            "threshold_authoritative": False,
            "calibration_status": "NOT_CALIBRATED",
            "high_similarity_pair_count": len(sem_pairs),
            "uncertain_pair_count": len(unc_pairs),
            "valid_variant_pair_count": len(var_pairs),
            "cluster_count": len(clusters),
            "candidates_in_clusters": len(clustered_ids),
            "potential_duplicates_extra_members": sum(len(c.member_ids) - 1 for c in clusters),
            "projected_unique_yield_estimate": unique_est,
            "cross_provider": cross_provider_stats(pairs, threshold=thr),
            "note": "embedding similarity ≠ automatically proven duplicate",
        }
        all_clusters[f"{thr:.2f}"] = [
            {
                "cluster_id": c.cluster_id,
                "threshold": c.threshold,
                "candidate_ids": c.member_ids,
                "representative_candidate": c.representative_candidate_id,
                "representative_is_proposal": True,
                "representative_rationale": c.representative_rationale,
                "relationship": c.relationship,
                "similarity_evidence": c.pair_evidence,
                "validator_v2_overlay": {
                    mid: v2_by_id.get(mid) for mid in c.member_ids
                },
            }
            for c in clusters
        ]

    # Calibration review sample — top cross-provider + top overall high scores
    review = []
    for p in pairs[:80]:
        review.append(
            {
                "candidate_a": p.candidate_a,
                "candidate_b": p.candidate_b,
                "provider_a": p.provider_a,
                "provider_b": p.provider_b,
                "similarity_score": p.similarity_score,
                "cross_provider": p.cross_provider,
                "exact_fingerprint_match": p.exact_fingerprint_match,
                "label": "CANDIDATE_FOR_MANUAL_REVIEW",
                "not_auto_duplicate": True,
            }
        )

    post = await db_snapshot()
    # Re-check immutable
    immutable_after = {}
    for name, exp in IMMUTABLE.items():
        got = sha256_file(CAND_DIR / name)
        immutable_after[name] = {"expected": exp, "actual": got, "unchanged": got == exp}

    artifacts_ok = all(v["unchanged"] for v in immutable_after.values())
    database_ok = db_ok(post) and post == pre

    cfg = backend.config_manifest()
    embedding_manifest = {
        "batch_id": BATCH,
        "executed_at": started,
        "semantic_input_version": SEMANTIC_INPUT_VERSION,
        "semantic_input_document": {
            "fields": ["stem", "options.A", "options.B", "options.C", "options.D", "correct_answer"],
            "excluded": ["explanation", "provider_metadata", "generated_at", "timestamps"],
            "normalization": "normalize_text NFKC/casefold/whitespace",
        },
        "embedding": redact_secrets(cfg),
        "provider_status": redact_secrets(status),
        "embed_stats": embed_stats,
        "candidates": len(rows),
        "per_candidate": manifest_rows,
    }

    similarity_results = {
        "pair_count_ge_0.72": len(pairs),
        "top_pairs": [
            {
                "candidate_a": p.candidate_a,
                "candidate_b": p.candidate_b,
                "provider_a": p.provider_a,
                "provider_b": p.provider_b,
                "similarity_score": p.similarity_score,
                "exact_fingerprint_match": p.exact_fingerprint_match,
                "cross_provider": p.cross_provider,
            }
            for p in pairs[:500]
        ],
        "calibration_review_sample": review,
        "note": "Full pair list truncated in artifact; clusters carry threshold evidence",
    }

    # Provider-specific overlap at 0.92 (illustrative, not calibrated)
    thr_ref = 0.92
    same_provider = Counter()
    for p in pairs:
        if p.similarity_score >= thr_ref and not p.cross_provider:
            same_provider[p.provider_a] += 1

    results = {
        "batch_id": BATCH,
        "gate": "SEMANTIC_DEDUPLICATION_CALIBRATION",
        "executed_at": started,
        "final_verdict": None,  # filled below
        "component_status": {
            "embedding_backend": "IMPLEMENTED",
            "embedding_execution": "EXECUTED",
            "threshold_calibration": "NOT_CALIBRATED",
            "null_backend_used": False,
            "candidate_jsonl_mutation": "NOT_EXECUTED",
            "contentitem_mutation": "NOT_EXECUTED",
            "generation": "NOT_EXECUTED",
            "ecaep": "NOT_EXECUTED",
            "publication": "NOT_EXECUTED",
        },
        "candidates_analyzed": 919,
        "embedding": redact_secrets(cfg),
        "embed_stats": embed_stats,
        "threshold_sweep": threshold_results,
        "provider_same_overlap_at_0.92": dict(same_provider),
        "cross_provider_at_0.92": threshold_results["0.92"]["cross_provider"],
        "semantic_duplicate_rate_at_0.92": round(
            threshold_results["0.92"]["potential_duplicates_extra_members"] / 919, 4
        ),
        "projected_unique_yield_at_0.92": threshold_results["0.92"]["projected_unique_yield_estimate"],
        "calibration_limitations": [
            "Thresholds are exploratory sweep values only — NOT scientifically validated",
            "High cosine similarity is a review signal, not automatic proof of duplication",
            "VALID_VARIANT / UNCERTAIN bands are heuristic near-threshold rules",
            "Representative selection is a proposal for human review",
            "Do not treat survivors as publishable questions",
        ],
        "immutable_poc_artifacts": immutable_after,
        "database_safety": {
            "pre": pre,
            "post": post,
            "unchanged": database_ok,
            "mutations": {
                "content_items": 0,
                "taxonomy": 0,
                "ecaep": 0,
                "certification": 0,
                "publication": 0,
                "student_visibility": 0,
            },
        },
        "mandatory_stop": True,
    }

    if not artifacts_ok or not database_ok:
        verdict = "RED"
        reason = "Integrity failure after embedding run"
    else:
        verdict = "GREEN"
        reason = (
            "Real OpenAI embedding backend executed on 919 candidates; "
            "threshold sweep complete; calibration NOT_CALIBRATED; "
            "no DB/content/JSONL mutation"
        )
    results["final_verdict"] = f"{verdict} — {reason}"

    # Write artifacts
    (OUT_DIR / "embedding_manifest.json").write_text(
        json.dumps(embedding_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "semantic_similarity_results.json").write_text(
        json.dumps(similarity_results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "semantic_clusters.json").write_text(
        json.dumps(all_clusters, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    report = f"""# Semantic Deduplication Calibration — {BATCH}

**Verdict:** `{verdict}` — {reason}

**Executed at:** {started}

## Component status

| Item | Status |
|------|--------|
| Embedding backend (OpenAI via MMF EmbeddingBackend) | IMPLEMENTED |
| Embedding run on 919 candidates | EXECUTED |
| Threshold scientifically calibrated | NOT_CALIBRATED |
| NullEmbeddingBackend | NOT USED |
| Candidate JSONL mutation | NOT_EXECUTED |
| ContentItem / ECAEP / publish | NOT_EXECUTED |

## Embedding configuration (no secrets)

```json
{json.dumps(redact_secrets(cfg), indent=2)}
```

## Semantic input

Version `{SEMANTIC_INPUT_VERSION}`: stem + options A–D + correct answer letter.
Excluded: explanation, provider metadata, timestamps.

## Embed stats

```json
{json.dumps(embed_stats, indent=2)}
```

## Threshold sweep (NOT authoritative)

| Threshold | Clusters | High-sim pairs | Extra members | Unique yield est. |
|----------:|--------:|---------------:|--------------:|------------------:|
"""
    for thr in DEFAULT_THRESHOLDS:
        key = f"{thr:.2f}"
        t = threshold_results[key]
        report += (
            f"| {thr:.2f} | {t['cluster_count']} | {t['high_similarity_pair_count']} | "
            f"{t['potential_duplicates_extra_members']} | {t['projected_unique_yield_estimate']} |\n"
        )

    report += f"""
### Cross-provider at 0.92 (illustrative)

```json
{json.dumps(threshold_results['0.92']['cross_provider'], indent=2)}
```

Same-provider high-sim pairs @0.92: {dict(same_provider)}

Semantic duplicate rate @0.92 (extra clustered members / 919): {results['semantic_duplicate_rate_at_0.92']}

## Calibration warning

**Embedding similarity ≠ automatically proven duplicate.**  
High-score pairs are candidates for manual review. Thresholds are **NOT_CALIBRATED**.

## Database safety

Unchanged: **{database_ok}**

POC JSONL immutable: **{artifacts_ok}**

## Mandatory stop

No generation, repair, import, ECAEP, certification, or publish.
"""
    (OUT_DIR / "semantic_dedup_report.md").write_text(report, encoding="utf-8")
    results_path = OUT_DIR / "semantic_dedup_results.json"
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    hashes = {p.name: sha256_file(OUT_DIR / p.name) for p in OUT_DIR.iterdir() if p.is_file()}
    results["artifact_hashes"] = hashes
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    results["artifact_hashes"]["semantic_dedup_results.json"] = sha256_file(results_path)
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "candidates": 919,
                "embed_stats": embed_stats,
                "threshold_0.92": threshold_results["0.92"],
                "db_ok": database_ok,
                "artifacts_ok": artifacts_ok,
                "out_dir": str(OUT_DIR),
            },
            indent=2,
        )
    )
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
