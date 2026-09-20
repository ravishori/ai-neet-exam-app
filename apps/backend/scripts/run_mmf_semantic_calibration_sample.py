"""Build human-reviewable semantic-dedup calibration sample (READ-ONLY).

Reuses cached embeddings — no generation LLM calls, no human-label prefill.
"""

from __future__ import annotations

import asyncio
import csv
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
from app.modules.cms.acquisition.mmf.audit import audit_candidate_metadata
from app.modules.cms.acquisition.mmf.calibration_sample import (
    CandidatePairScore,
    blank_review_fields,
    stratified_calibration_sample,
    validate_sample,
)
from app.modules.cms.acquisition.mmf.semantic_dedupe import cosine_similarity
from app.modules.cms.models import ContentItem

REPO = BACKEND.parents[1]
BATCH = "BIO11-CH04-MMF-POC-B001"
CAND_DIR = REPO / "docs" / "acquisition" / "candidates" / BATCH
OUT_DIR = CAND_DIR / "semantic_dedup_v1"
CACHE_DIR = OUT_DIR / "embedding_cache"
MANIFEST_PATH = OUT_DIR / "embedding_manifest.json"
NORMALIZED = CAND_DIR / "candidates_normalized.jsonl"
EXPECTED_SHA = "2c092dd3d16cf15f2d3bcaf0636653c6e7b370c9b2159ffad73df3601643ba87"
NORMALIZED_SHA = "c46181039a967666acc432a348833f942f9eee02dc44b455e79132efa95c04ea"
IMMUTABLE = {
    "candidates_normalized.jsonl": NORMALIZED_SHA,
    "gemini_raw.jsonl": "640bc661c2db1c06ce74451ad87f40cd1cb00013840574a31c93062a30f6dace",
    "anthropic_raw.jsonl": "67c46a6dc82569c14236abe752ea11afdba2f0fa5d6a977302c11d17e78213f5",
    "openai_raw.jsonl": "cf5b6b89a5b840277cf37717d24d2867eab0b121b11e763f51f355655925e567",
    "candidates_raw_combined.jsonl": "92deedd6dd7dec93a9225e17a234a6213dd1111966d73f88e56671c11b71a943",
}
SEED = 20260912


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
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


def load_vectors_from_cache(manifest: dict[str, Any]) -> tuple[list[str], list[str], list[list[float]]]:
    ids: list[str] = []
    providers: list[str] = []
    vectors: list[list[float]] = []
    for row in manifest["per_candidate"]:
        path = CACHE_DIR / f"{row['cache_key']}.json"
        if not path.exists():
            raise FileNotFoundError(f"missing_cache:{row['cache_key']} for {row['candidate_id']}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if "api_key" in data or "authorization" in data:
            raise RuntimeError("cache_contains_secrets")
        vec = data["vector"]
        if len(vec) != 1536:
            raise RuntimeError(f"bad_dim:{len(vec)}")
        ids.append(row["candidate_id"])
        providers.append(row["provider"])
        vectors.append([float(x) for x in vec])
    return ids, providers, vectors


def compute_pairs(
    ids: list[str], providers: list[str], vectors: list[list[float]], *, min_score: float = 0.85
) -> list[CandidatePairScore]:
    n = len(ids)
    out: list[CandidatePairScore] = []
    for i in range(n):
        for j in range(i + 1, n):
            score = cosine_similarity(vectors[i], vectors[j])
            if score < min_score:
                continue
            out.append(
                CandidatePairScore(
                    candidate_a=ids[i],
                    candidate_b=ids[j],
                    provider_a=providers[i],
                    provider_b=providers[j],
                    similarity_score=float(score),
                    cross_provider=providers[i] != providers[j],
                )
            )
    return out


def cand_view(raw: dict[str, Any]) -> dict[str, Any]:
    audit = audit_candidate_metadata(raw)
    return {
        "candidate_id": raw["candidate_id"],
        "provider": raw["provider"],
        "model": raw.get("model"),
        "stem": raw.get("stem"),
        "options": raw.get("options"),
        "correct_answer": raw.get("correct_answer"),
        "topic": raw.get("topic"),
        "concept": raw.get("concept"),
        "declared_question_type": raw.get("declared_question_type") or raw.get("question_type"),
        "audited_question_type": audit.get("audited_question_type"),
        "question_type_status": audit.get("question_type_status"),
        "declared_difficulty": raw.get("declared_difficulty") or raw.get("difficulty"),
        "audited_difficulty": audit.get("audited_difficulty"),
        "difficulty_agreement": audit.get("difficulty_agreement"),
        "source_evidence": raw.get("source_evidence"),
        "source_sha256": raw.get("source_sha256"),
    }


REVIEW_GUIDE = """# Semantic Dedup Calibration — Reviewer Guide

## Purpose

Assign a **human** label to each pair so we can calibrate cosine thresholds later.
Do **not** use the similarity score alone to decide the label.

## Labels (required)

| Label | Meaning |
|-------|---------|
| `DUPLICATE` | The two questions substantially test the same formulation / knowledge retrieval such that retaining both adds little or no additional practice value. |
| `VALID_VARIANT` | Related material/concepts, but meaningfully different practice value, formulation, reasoning, comparison, or application. |
| `UNCERTAIN` | Cannot confidently distinguish duplicate from meaningful variant. |

## Rubric reminders

- Same concept ≠ duplicate
- Same answer ≠ duplicate
- Similar wording ≠ automatically duplicate
- Different wording ≠ automatically unique
- Cosine similarity is a **signal for review**, not a verdict

## How to record

Fill in the CSV or JSONL fields:

- `human_label` — one of DUPLICATE / VALID_VARIANT / UNCERTAIN
- `human_reason` — short free text
- `reviewer` — your initials or name
- `reviewed_at` — ISO timestamp

Optional inter-rater fields (leave blank if unused):

- `reviewer_1_label`
- `reviewer_2_label`
- `adjudicated_label`

## Bias controls

- Candidate A/B order was randomized (not provider-ordered)
- Sample is stratified (very-high / 0.90–0.95 / cross-provider / same-provider)
- System did **not** pre-fill human labels

## Out of scope

Do not change candidate content, import ContentItems, or pick an operational threshold in this step.
"""


async def amain() -> int:
    started = datetime.now(UTC).isoformat()
    # Immutable checks
    immutable_check = {}
    for name, exp in IMMUTABLE.items():
        got = sha256_file(CAND_DIR / name)
        immutable_check[name] = {"expected": exp, "actual": got, "unchanged": got == exp}
    if not all(v["unchanged"] for v in immutable_check.values()):
        print(json.dumps({"verdict": "RED", "reason": "immutable_mismatch", "immutable_check": immutable_check}, indent=2))
        return 1

    # Embedding cache fingerprint (prefer unchanged)
    cache_files = sorted(CACHE_DIR.glob("*.json"))
    cache_count_before = len(cache_files)
    cache_hash_before = hashlib.sha256(
        "".join(p.name + ":" + str(p.stat().st_size) for p in cache_files).encode()
    ).hexdigest()

    pre = await db_snapshot()
    if not db_ok(pre):
        print(json.dumps({"verdict": "RED", "reason": "pre_db", "pre": pre}, indent=2))
        return 1

    rows = load_jsonl(NORMALIZED)
    if len(rows) != 919:
        print(json.dumps({"verdict": "RED", "reason": f"expected_919_got_{len(rows)}"}, indent=2))
        return 1
    by_id = {r["candidate_id"]: r for r in rows}
    for r in rows:
        if r.get("source_sha256") != EXPECTED_SHA:
            print(json.dumps({"verdict": "RED", "reason": "source_sha_mismatch", "id": r["candidate_id"]}, indent=2))
            return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    ids, providers, vectors = load_vectors_from_cache(manifest)
    if len(ids) != 919:
        print(json.dumps({"verdict": "RED", "reason": "cache_count", "n": len(ids)}, indent=2))
        return 1

    # Recompute pairs from cache only (no embedding API)
    pair_scores = compute_pairs(ids, providers, vectors, min_score=0.85)
    sample = stratified_calibration_sample(pair_scores, target_total=80, seed=SEED)
    errors = validate_sample(sample, valid_ids=set(by_id))
    if errors:
        print(json.dumps({"verdict": "RED", "reason": "sample_validation", "errors": errors[:20]}, indent=2))
        return 1

    # Build review records
    jsonl_rows: list[dict[str, Any]] = []
    for sp in sample.pairs:
        a = by_id[sp.candidate_id_a]
        b = by_id[sp.candidate_id_b]
        rec = {
            "pair_id": sp.pair_id,
            "cosine_similarity": sp.cosine_similarity,
            "selection_bucket": sp.selection_buckets[0],
            "selection_buckets": sp.selection_buckets,
            "provider_relationship": sp.provider_relationship,
            "display_order_swapped": sp.display_order_swapped,
            "candidate_id_a": sp.candidate_id_a,
            "candidate_id_b": sp.candidate_id_b,
            "provider_a": sp.provider_a,
            "model_a": a.get("model"),
            "provider_b": sp.provider_b,
            "model_b": b.get("model"),
            "topic_a": a.get("topic"),
            "topic_b": b.get("topic"),
            "concept_a": a.get("concept"),
            "concept_b": b.get("concept"),
            "question_type_a": a.get("question_type"),
            "question_type_b": b.get("question_type"),
            "difficulty_a": a.get("difficulty"),
            "difficulty_b": b.get("difficulty"),
            "source_evidence_a": a.get("source_evidence"),
            "source_evidence_b": b.get("source_evidence"),
            "candidate_a": cand_view(a),
            "candidate_b": cand_view(b),
            **blank_review_fields(),
        }
        # Guard: human labels must be blank
        assert rec["human_label"] == ""
        jsonl_rows.append(rec)

    # Distributions (no human labels)
    sim_scores = [r["cosine_similarity"] for r in jsonl_rows]
    bucket_dist = Counter()
    for r in jsonl_rows:
        for b in r["selection_buckets"]:
            bucket_dist[b] += 1
    provider_rel_dist = Counter(r["provider_relationship"] for r in jsonl_rows)
    score_bands = {
        "ge_0.95": sum(1 for s in sim_scores if s >= 0.95),
        "0.90_to_0.95": sum(1 for s in sim_scores if 0.90 <= s < 0.95),
        "0.85_to_0.90": sum(1 for s in sim_scores if 0.85 <= s < 0.90),
        "lt_0.85": sum(1 for s in sim_scores if s < 0.85),
    }

    # Write artifacts (new files only)
    jsonl_path = OUT_DIR / "semantic_calibration_sample.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for rec in jsonl_rows:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    csv_path = OUT_DIR / "semantic_calibration_review.csv"
    csv_fields = [
        "pair_id",
        "cosine_similarity",
        "selection_bucket",
        "selection_buckets",
        "provider_relationship",
        "candidate_id_a",
        "provider_a",
        "model_a",
        "stem_a",
        "option_a_A",
        "option_a_B",
        "option_a_C",
        "option_a_D",
        "correct_answer_a",
        "topic_a",
        "concept_a",
        "declared_type_a",
        "audited_type_a",
        "declared_difficulty_a",
        "audited_difficulty_a",
        "source_evidence_a",
        "candidate_id_b",
        "provider_b",
        "model_b",
        "stem_b",
        "option_b_A",
        "option_b_B",
        "option_b_C",
        "option_b_D",
        "correct_answer_b",
        "topic_b",
        "concept_b",
        "declared_type_b",
        "audited_type_b",
        "declared_difficulty_b",
        "audited_difficulty_b",
        "source_evidence_b",
        "human_label",
        "human_reason",
        "reviewer",
        "reviewed_at",
        "reviewer_1_label",
        "reviewer_2_label",
        "adjudicated_label",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        for rec in jsonl_rows:
            ca, cb = rec["candidate_a"], rec["candidate_b"]
            oa, ob = ca["options"], cb["options"]
            w.writerow(
                {
                    "pair_id": rec["pair_id"],
                    "cosine_similarity": rec["cosine_similarity"],
                    "selection_bucket": rec["selection_bucket"],
                    "selection_buckets": "|".join(rec["selection_buckets"]),
                    "provider_relationship": rec["provider_relationship"],
                    "candidate_id_a": rec["candidate_id_a"],
                    "provider_a": rec["provider_a"],
                    "model_a": rec["model_a"],
                    "stem_a": ca["stem"],
                    "option_a_A": oa["A"],
                    "option_a_B": oa["B"],
                    "option_a_C": oa["C"],
                    "option_a_D": oa["D"],
                    "correct_answer_a": ca["correct_answer"],
                    "topic_a": ca["topic"],
                    "concept_a": ca["concept"],
                    "declared_type_a": ca["declared_question_type"],
                    "audited_type_a": ca["audited_question_type"],
                    "declared_difficulty_a": ca["declared_difficulty"],
                    "audited_difficulty_a": ca["audited_difficulty"],
                    "source_evidence_a": ca["source_evidence"],
                    "candidate_id_b": rec["candidate_id_b"],
                    "provider_b": rec["provider_b"],
                    "model_b": rec["model_b"],
                    "stem_b": cb["stem"],
                    "option_b_A": ob["A"],
                    "option_b_B": ob["B"],
                    "option_b_C": ob["C"],
                    "option_b_D": ob["D"],
                    "correct_answer_b": cb["correct_answer"],
                    "topic_b": cb["topic"],
                    "concept_b": cb["concept"],
                    "declared_type_b": cb["declared_question_type"],
                    "audited_type_b": cb["audited_question_type"],
                    "declared_difficulty_b": cb["declared_difficulty"],
                    "audited_difficulty_b": cb["audited_difficulty"],
                    "source_evidence_b": cb["source_evidence"],
                    "human_label": "",
                    "human_reason": "",
                    "reviewer": "",
                    "reviewed_at": "",
                    "reviewer_1_label": "",
                    "reviewer_2_label": "",
                    "adjudicated_label": "",
                }
            )

    guide_path = OUT_DIR / "semantic_calibration_review_guide.md"
    guide_path.write_text(REVIEW_GUIDE, encoding="utf-8")

    post = await db_snapshot()
    immutable_after = {}
    for name, exp in IMMUTABLE.items():
        got = sha256_file(CAND_DIR / name)
        immutable_after[name] = {"expected": exp, "actual": got, "unchanged": got == exp}
    cache_files_after = sorted(CACHE_DIR.glob("*.json"))
    cache_count_after = len(cache_files_after)
    cache_hash_after = hashlib.sha256(
        "".join(p.name + ":" + str(p.stat().st_size) for p in cache_files_after).encode()
    ).hexdigest()

    strata_ok = all(
        sample.filled.get(b, 0) > 0
        for b in ("VERY_HIGH_SIMILARITY", "THRESHOLD_REGION", "CROSS_PROVIDER", "SAME_PROVIDER")
    )
    shortfall_total = sum(sample.shortfalls.values())
    artifacts_ok = all(v["unchanged"] for v in immutable_after.values())
    database_ok = db_ok(post) and post == pre
    cache_ok = cache_count_before == cache_count_after == 919 and cache_hash_before == cache_hash_after
    human_blank = all(r["human_label"] == "" for r in jsonl_rows)

    if not artifacts_ok or not database_ok or not human_blank:
        verdict = "RED"
        reason = "Integrity failure or pre-filled human labels"
    elif len(jsonl_rows) < 60 or not strata_ok or shortfall_total > 20:
        verdict = "AMBER"
        reason = "Sample incomplete or materially short on strata"
    else:
        verdict = "GREEN"
        reason = (
            f"Calibration sample of {len(jsonl_rows)} pairs created with blank human labels; "
            "strata represented; cache/JSONL/DB unchanged"
        )

    results = {
        "batch_id": BATCH,
        "gate": "SEMANTIC_DEDUP_CALIBRATION_SAMPLE_ONLY",
        "executed_at": started,
        "final_verdict": f"{verdict} — {reason}",
        "seed": SEED,
        "sample_size": len(jsonl_rows),
        "target_size": 80,
        "quotas": sample.quotas,
        "filled": sample.filled,
        "shortfalls": sample.shortfalls,
        "pool_stats": sample.pool_stats,
        "pair_pool_ge_0.85": len(pair_scores),
        "distributions": {
            "selection_bucket_tags": dict(bucket_dist),
            "provider_relationship": dict(provider_rel_dist),
            "score_bands": score_bands,
            "similarity_min": min(sim_scores) if sim_scores else None,
            "similarity_max": max(sim_scores) if sim_scores else None,
            "similarity_mean": round(sum(sim_scores) / len(sim_scores), 6) if sim_scores else None,
        },
        "human_labels_prefilled": False,
        "precision_recall_computed": False,
        "threshold_decision": "NOT_EXECUTED",
        "embedding_api_calls": 0,
        "cache_unchanged": cache_ok,
        "cache_count": cache_count_after,
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
        "next_step": "Human reviewers assign DUPLICATE / VALID_VARIANT / UNCERTAIN",
    }

    manifest = {
        "batch_id": BATCH,
        "created_at": started,
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimension": 1536,
        "embedding_configuration_version": "mmf-embedding-config-v1",
        "semantic_input_version": "mmf-semantic-input-v1",
        "reused_cached_embeddings": True,
        "new_embedding_calls": 0,
        "sample_seed": SEED,
        "sample_size": len(jsonl_rows),
        "pair_ids": [r["pair_id"] for r in jsonl_rows],
        "artifacts": [
            "semantic_calibration_sample.jsonl",
            "semantic_calibration_review.csv",
            "semantic_calibration_review_guide.md",
            "semantic_calibration_manifest.json",
            "semantic_calibration_report.md",
            "semantic_calibration_results.json",
        ],
        "note": "No answer key — human labels intentionally blank",
    }

    report = f"""# Semantic Dedup Calibration Sample Report

**Verdict:** `{verdict}` — {reason}

**Executed:** {started}  
**Seed:** `{SEED}`  
**Sample size:** {len(jsonl_rows)} / 80 target

## Strata

| Bucket | Quota | Filled | Shortfall |
|--------|------:|-------:|----------:|
| VERY_HIGH_SIMILARITY (≥0.95) | {sample.quotas['VERY_HIGH_SIMILARITY']} | {sample.filled.get('VERY_HIGH_SIMILARITY',0)} | {sample.shortfalls.get('VERY_HIGH_SIMILARITY',0)} |
| THRESHOLD_REGION [0.90, 0.95) | {sample.quotas['THRESHOLD_REGION']} | {sample.filled.get('THRESHOLD_REGION',0)} | {sample.shortfalls.get('THRESHOLD_REGION',0)} |
| CROSS_PROVIDER | {sample.quotas['CROSS_PROVIDER']} | {sample.filled.get('CROSS_PROVIDER',0)} | {sample.shortfalls.get('CROSS_PROVIDER',0)} |
| SAME_PROVIDER | {sample.quotas['SAME_PROVIDER']} | {sample.filled.get('SAME_PROVIDER',0)} | {sample.shortfalls.get('SAME_PROVIDER',0)} |
| FILL | — | {sample.filled.get('FILL',0)} | — |

Multi-bucket tagged pairs: {sample.pool_stats.get('multi_bucket_pairs')}

## Distributions (no human labels)

- Provider relationships: {dict(provider_rel_dist)}
- Score bands: {score_bands}
- Similarity range: {min(sim_scores):.4f} – {max(sim_scores):.4f} (mean {sum(sim_scores)/len(sim_scores):.4f})

## Explicit non-claims

- Precision/recall: **NOT_EXECUTED** (no human labels yet)
- Operational threshold: **NOT selected**
- 0.92 remains exploratory only

## Safety

- Candidate JSONL unchanged: **{artifacts_ok}**
- Embedding cache unchanged (919 files): **{cache_ok}**
- Database unchanged: **{database_ok}**
- Human labels blank: **{human_blank}**
- Embedding API calls this gate: **0**

## Review files

- `semantic_calibration_sample.jsonl`
- `semantic_calibration_review.csv`
- `semantic_calibration_review_guide.md`

## Mandatory stop

Human review is the next step. Do not auto-decide thresholds or import candidates.
"""

    (OUT_DIR / "semantic_calibration_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "semantic_calibration_report.md").write_text(report, encoding="utf-8")
    results_path = OUT_DIR / "semantic_calibration_results.json"
    results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    new_artifacts = [
        "semantic_calibration_sample.jsonl",
        "semantic_calibration_review.csv",
        "semantic_calibration_review_guide.md",
        "semantic_calibration_manifest.json",
        "semantic_calibration_report.md",
        "semantic_calibration_results.json",
    ]
    hashes = {name: sha256_file(OUT_DIR / name) for name in new_artifacts}
    results["artifact_hashes"] = hashes
    results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    hashes["semantic_calibration_results.json"] = sha256_file(results_path)
    results["artifact_hashes"] = hashes
    results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "sample_size": len(jsonl_rows),
                "filled": sample.filled,
                "shortfalls": sample.shortfalls,
                "distributions": results["distributions"],
                "cache_ok": cache_ok,
                "db_ok": database_ok,
                "artifacts_ok": artifacts_ok,
                "hashes": hashes,
            },
            indent=2,
        )
    )
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
