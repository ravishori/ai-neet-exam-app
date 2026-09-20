"""Validator V2 + semantic triage-only for BIO11-CH04-MMF-GEN-V2-B001.

Does NOT mutate PostgreSQL. Does NOT overwrite POC artifacts.
Does NOT auto-collapse candidates (production threshold remains NOT_CALIBRATED).

Usage (from apps/backend):
  python scripts/run_mmf_gen_v2_postprocess.py --authorize-embeddings
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
from app.modules.cms.acquisition.mmf.config import DEFAULT_POC_BATCH_ID, redact_secrets
from app.modules.cms.acquisition.mmf.contract_v2 import CONTRACT_VERSION, PROMPT_VERSION_V2, contract_v2_document
from app.modules.cms.acquisition.mmf.embedding_backends import (
    EmbeddingConfigurationError,
    embedding_status_from_settings,
    select_production_embedding_backend,
)
from app.modules.cms.acquisition.mmf.live_generation import EXPECTED_NCERT_SHA, GEN_V2_BATCH_ID
from app.modules.cms.acquisition.mmf.semantic_calibration import (
    classify_pair,
    clusters_at_threshold,
    compute_pairwise_scores,
    cross_provider_stats,
    fingerprint_for_raw,
)
from app.modules.cms.acquisition.mmf.semantic_input import (
    SEMANTIC_INPUT_VERSION,
    EmbeddingDiskCache,
    build_semantic_input,
    cache_key_for_embedding,
    semantic_input_hash,
)
from app.modules.cms.acquisition.mmf.validation_v2 import validate_candidate_list_v2
from app.modules.cms.models import ContentItem

REPO = BACKEND.parents[1]
BATCH = GEN_V2_BATCH_ID
CAND_DIR = REPO / "docs" / "acquisition" / "candidates" / BATCH
POC_DIR = REPO / "docs" / "acquisition" / "candidates" / DEFAULT_POC_BATCH_ID
POC_SEM = POC_DIR / "semantic_dedup_v1"
TRIAGE_DIR = CAND_DIR / "semantic_triage_v1"

POC_IMMUTABLE = {
    "candidates_normalized.jsonl": "c46181039a967666acc432a348833f942f9eee02dc44b455e79132efa95c04ea",
    "gemini_raw.jsonl": "640bc661c2db1c06ce74451ad87f40cd1cb00013840574a31c93062a30f6dace",
    "anthropic_raw.jsonl": "67c46a6dc82569c14236abe752ea11afdba2f0fa5d6a977302c11d17e78213f5",
    "openai_raw.jsonl": "cf5b6b89a5b840277cf37717d24d2867eab0b121b11e763f51f355655925e567",
    "candidates_raw_combined.jsonl": "92deedd6dd7dec93a9225e17a234a6213dd1111966d73f88e56671c11b71a943",
}
POC_CALIB = {
    "semantic_calibration_review.csv": "5b0d72ae06753e5b156e581a9be36a693dc1d8ee99290b64cb55f4025356f0d8",
    "semantic_calibration_sample.jsonl": "ce42369c2f37e85bf3691647e9187528c92e6aa9057b276622f8c1711fc8d3f7",
    "semantic_calibration_second_rater_review.csv": "3a6b0aa0fa0ca09cb296792a9a9b6625926b5e2aa05f0d27ee5ee4e8178f82da",
    "semantic_calibration_adjudication.json": "3a444a03c643ca126cec8453a0f3b222f0e9c528447b7043cb2fbf0c50285c1b",
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


async def embed_with_cache(rows, backend, cache):
    manifest_rows = []
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
        new_vecs: list[list[float]] = []
        # Respect backend safety cap (POC default 919) by chunking larger batches.
        chunk = max(1, int(getattr(backend, "max_texts", 919) or 919))
        for start in range(0, len(to_embed_texts), chunk):
            piece = to_embed_texts[start : start + chunk]
            new_vecs.extend(await backend.embed_texts(piece))
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
        "actual_candidates": len(rows),
    }
    return [v for v in vectors if v is not None], manifest_rows, stats


def verify_poc_immutable() -> dict[str, Any]:
    out = {"candidates": {}, "calibration": {}, "embedding_cache_count": None, "ok": True}
    for name, exp in POC_IMMUTABLE.items():
        got = sha256_file(POC_DIR / name)
        row = {"expected": exp, "actual": got, "unchanged": got == exp}
        out["candidates"][name] = row
        if not row["unchanged"]:
            out["ok"] = False
    for name, exp in POC_CALIB.items():
        p = POC_SEM / name
        if not p.exists():
            out["calibration"][name] = {"unchanged": False, "missing": True}
            out["ok"] = False
            continue
        got = sha256_file(p)
        row = {"expected": exp, "actual": got, "unchanged": got == exp}
        out["calibration"][name] = row
        if not row["unchanged"]:
            out["ok"] = False
    cache = POC_SEM / "embedding_cache"
    if cache.exists():
        out["embedding_cache_count"] = len(list(cache.glob("*.json")))
        if out["embedding_cache_count"] != 919:
            out["ok"] = False
    return out


async def amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize-embeddings", action="store_true")
    parser.add_argument("--skip-embeddings", action="store_true")
    args = parser.parse_args()
    if not args.skip_embeddings and not args.authorize_embeddings:
        print("Refusing embeddings: pass --authorize-embeddings or --skip-embeddings")
        return 2

    started = datetime.now(UTC).isoformat()
    CAND_DIR.mkdir(parents=True, exist_ok=True)
    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)

    poc_check = verify_poc_immutable()
    if not poc_check["ok"]:
        print(json.dumps({"verdict": "RED", "reason": "poc_immutable_changed", "poc_check": poc_check}, indent=2))
        return 1

    pre = await db_snapshot()
    if not db_ok(pre):
        print(json.dumps({"verdict": "RED", "reason": "pre_db_control_mismatch", "pre": pre}, indent=2))
        return 1

    raw_path = CAND_DIR / "candidates_raw_combined.jsonl"
    norm_path = CAND_DIR / "candidates_normalized.jsonl"
    if not raw_path.exists() or not norm_path.exists():
        print(json.dumps({"verdict": "RED", "reason": "missing_generation_artifacts"}, indent=2))
        return 1

    raw_rows = load_jsonl(raw_path)
    norm_rows = load_jsonl(norm_path)
    unique_rows = [r for r in norm_rows if str(r.get("status", "")).upper() != "EXACT_DUPLICATE"]
    exact_dups = [r for r in norm_rows if str(r.get("status", "")).upper() == "EXACT_DUPLICATE"]

    # Validator V2 (independent audit; no silent repair)
    full = validate_candidate_list_v2(norm_rows, expected_source_sha=EXPECTED_NCERT_SHA)
    sample_mismatch = [r for r in full["results"] if r["metadata_audit"].get("question_type_status") == "MISMATCH"][:40]
    sample_struct = [r for r in full["results"] if r["structural_reason_codes"]][:40]
    sample_unresolved = [r for r in full["results"] if r["concept_status"] == "UNRESOLVED"][:40]

    # Approximate NEET relevance / NCERT grounding from V2 reason codes + evidence presence
    grounding = {
        "source_sha_match": sum(1 for r in raw_rows if r.get("source_sha256") == EXPECTED_NCERT_SHA),
        "source_evidence_present": sum(1 for r in raw_rows if str(r.get("source_evidence") or "").strip()),
        "explanation_present": sum(1 for r in raw_rows if str(r.get("explanation") or "").strip()),
    }
    struct_reasons = Counter(full.get("structural_reason_counts") or {})

    contract = contract_v2_document()
    (CAND_DIR / "generation_contract_v2.json").write_text(
        json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    validation_payload = {
        "batch_id": BATCH,
        "gate": "VALIDATOR_V2_GEN_V2",
        "executed_at": started,
        "contract_version": CONTRACT_VERSION,
        "prompt_version": PROMPT_VERSION_V2,
        "input": {
            "raw_count": len(raw_rows),
            "normalized_count": len(norm_rows),
            "exact_duplicates": len(exact_dups),
            "unique_candidates": len(unique_rows),
        },
        "validator_v2_summary": {
            "count": full["count"],
            "schema_ok": full["schema_ok"],
            "schema_fail": full["schema_fail"],
            "question_type_MATCH": full["question_type_MATCH"],
            "question_type_MISMATCH": full["question_type_MISMATCH"],
            "difficulty_agree": full["difficulty_agree"],
            "difficulty_disagree": full["difficulty_disagree"],
            "concept_RESOLVED": full["concept_RESOLVED"],
            "concept_UNRESOLVED": full["concept_UNRESOLVED"],
            "structural_reason_counts": full["structural_reason_counts"],
            "mutated_any": full["mutated_any"],
        },
        "ncert_grounding": grounding,
        "neet_relevance_note": (
            "Experimental heuristic from structural/NCERT-grounding signals only; "
            "not a certification or publication gate."
        ),
        "samples": {
            "question_type_mismatch": sample_mismatch,
            "structural_findings": sample_struct,
            "concept_unresolved": sample_unresolved,
        },
        "silent_repair": False,
        "production_threshold_status": "NOT_CALIBRATED",
    }
    (CAND_DIR / "validator_v2_report.json").write_text(
        json.dumps(redact_secrets(validation_payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (CAND_DIR / "validator_v2_report.md").write_text(
        "\n".join(
            [
                f"# Validator V2 report — {BATCH}",
                "",
                f"- Contract: `{CONTRACT_VERSION}`",
                f"- Prompt: `{PROMPT_VERSION_V2}`",
                f"- Normalized audited: **{full['count']}**",
                f"- Schema OK/Fail: {full['schema_ok']} / {full['schema_fail']}",
                f"- Type MATCH/MISMATCH: {full['question_type_MATCH']} / {full['question_type_MISMATCH']}",
                f"- Difficulty agree/disagree: {full['difficulty_agree']} / {full['difficulty_disagree']}",
                f"- Concept RESOLVED/UNRESOLVED: {full['concept_RESOLVED']} / {full['concept_UNRESOLVED']}",
                f"- Silent repair: **false**",
                f"- Structural reasons: `{dict(struct_reasons)}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    triage_summary: dict[str, Any] = {
        "status": "SKIPPED",
        "production_threshold_status": "NOT_CALIBRATED",
        "automatic_collapse_enabled": False,
        "candidates_deleted": 0,
    }
    quality_pass = full["schema_ok"]  # experimental: schema-ok count as quality-pass proxy

    if not args.skip_embeddings:
        status = embedding_status_from_settings()
        backend = select_production_embedding_backend()
        cache = EmbeddingDiskCache(TRIAGE_DIR / "embedding_cache")
        # Triage on unique normalized candidates only
        vectors, manifest_rows, emb_stats = await embed_with_cache(unique_rows, backend, cache)
        ids = [r["candidate_id"] for r in unique_rows]
        providers = [str(r.get("provider") or "") for r in unique_rows]
        fingerprints = [fingerprint_for_raw(r) for r in unique_rows]
        pairs = compute_pairwise_scores(
            candidate_ids=ids,
            providers=providers,
            vectors=vectors,
            fingerprints=fingerprints,
            min_score_to_keep=0.85,
        )
        # Record triage pairs only — no collapse decisions
        triage_pairs = []
        band_counts: Counter[str] = Counter()
        observe_threshold = 0.92
        for p in pairs:
            # Band labels for reporting only (NOT production decisions)
            if p.similarity_score >= 0.95:
                band = "GE_0_95"
            elif p.similarity_score >= 0.92:
                band = "GE_0_92_LT_0_95"
            elif p.similarity_score >= 0.90:
                band = "GE_0_90_LT_0_92"
            elif p.similarity_score >= 0.88:
                band = "GE_0_88_LT_0_90"
            else:
                band = "GE_0_85_LT_0_88"
            band_counts[band] += 1
            # classify_pair used only as observe-only annotation; threshold NOT calibrated
            observe_rel = classify_pair(
                p.similarity_score, threshold=observe_threshold, exact=p.exact_fingerprint_match
            )
            triage_pairs.append(
                {
                    "pair_id": f"{p.candidate_a}::{p.candidate_b}",
                    "candidate_a_id": p.candidate_a,
                    "candidate_b_id": p.candidate_b,
                    "provider_a": p.provider_a,
                    "provider_b": p.provider_b,
                    "cosine_similarity": p.similarity_score,
                    "triage_band": band,
                    "observe_only_relationship_at_0_92": observe_rel,
                    "decision": "TRIAGE_ONLY",
                    "collapsed": False,
                }
            )
        triage_pairs.sort(key=lambda x: -x["cosine_similarity"])
        clusters = clusters_at_threshold(
            pairs, threshold=0.92, all_ids=ids
        )
        xprov = cross_provider_stats(pairs, threshold=0.92)

        (TRIAGE_DIR / "embedding_manifest.json").write_text(
            json.dumps(
                {
                    "batch_id": BATCH,
                    "semantic_input_version": SEMANTIC_INPUT_VERSION,
                    "backend": backend.config_manifest(),
                    "stats": emb_stats,
                    "rows": manifest_rows,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (TRIAGE_DIR / "semantic_triage_pairs.jsonl").write_text(
            "\n".join(json.dumps(p, ensure_ascii=False) for p in triage_pairs) + ("\n" if triage_pairs else ""),
            encoding="utf-8",
        )
        triage_summary = {
            "status": "TRIAGE_COMPLETE",
            "production_threshold_status": "NOT_CALIBRATED",
            "automatic_collapse_enabled": False,
            "candidates_deleted": 0,
            "unique_candidates_embedded": len(unique_rows),
            "embedding_stats": emb_stats,
            "triage_pair_count_ge_0_85": len(triage_pairs),
            "band_counts": dict(band_counts),
            "cluster_count_at_0_92_observe_only": len(clusters),
            "cross_provider": xprov,
            "top_pairs_sample": triage_pairs[:25],
            "note": "Pairs are triage signals only; no automatic DUPLICATE collapse.",
        }
        (TRIAGE_DIR / "semantic_triage_report.json").write_text(
            json.dumps(redact_secrets(triage_summary), indent=2, default=str) + "\n", encoding="utf-8"
        )
        (TRIAGE_DIR / "semantic_triage_report.md").write_text(
            "\n".join(
                [
                    f"# Semantic triage report — {BATCH}",
                    "",
                    "- Mode: **TRIAGE ONLY**",
                    "- Production threshold: **NOT_CALIBRATED**",
                    "- Automatic collapse: **false**",
                    f"- Unique candidates embedded: **{len(unique_rows)}**",
                    f"- Triage pairs ≥0.85: **{len(triage_pairs)}**",
                    f"- Band counts: `{dict(band_counts)}`",
                    f"- Observe-only clusters @0.92: **{len(clusters)}**",
                    f"- Candidates deleted: **0**",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    post = await db_snapshot()
    if pre != post or not db_ok(post):
        print(json.dumps({"verdict": "RED", "reason": "db_changed", "pre": pre, "post": post}, indent=2))
        return 1

    # Yield funnel (experimental)
    gen_manifest = {}
    gm = CAND_DIR / "generation_manifest.json"
    if gm.exists():
        gen_manifest = json.loads(gm.read_text(encoding="utf-8"))
    provider_stats = gen_manifest.get("provider_stats") or {}
    requested = 1000
    generated = len(raw_rows)
    valid_struct = full["schema_ok"]
    exact_unique = len(unique_rows)
    semantically_triaged = triage_summary.get("triage_pair_count_ge_0_85", 0)
    funnel = {
        "requested": requested,
        "generated": generated,
        "valid_schema_ok": valid_struct,
        "exact_unique": exact_unique,
        "semantic_triage_pairs_ge_0_85": semantically_triaged,
        "quality_pass_schema_ok": quality_pass,
        "note": "Not publishable; ECAEP/NCERT certification/publication not executed.",
    }

    # Provider comparison (experimental)
    by_provider = {}
    for prow in raw_rows:
        p = prow.get("provider") or "unknown"
        by_provider.setdefault(p, {"generated": 0, "with_evidence": 0})
        by_provider[p]["generated"] += 1
        if str(prow.get("source_evidence") or "").strip():
            by_provider[p]["with_evidence"] += 1
    for p, st in provider_stats.items():
        by_provider.setdefault(p, {})
        by_provider[p].update(
            {
                "requested": st.get("requested"),
                "generated_reported": st.get("generated"),
                "failed": st.get("failed"),
                "empty_response": st.get("empty_response"),
                "model": st.get("model"),
            }
        )

    artifact_hashes = {name: sha256_file(CAND_DIR / name) for name in [
        "gemini_raw.jsonl",
        "anthropic_raw.jsonl",
        "openai_raw.jsonl",
        "candidates_raw_combined.jsonl",
        "candidates_normalized.jsonl",
        "validator_v2_report.json",
    ] if (CAND_DIR / name).exists()}
    if (TRIAGE_DIR / "semantic_triage_report.json").exists():
        artifact_hashes["semantic_triage_v1/semantic_triage_report.json"] = sha256_file(
            TRIAGE_DIR / "semantic_triage_report.json"
        )

    experiment = {
        "batch_id": BATCH,
        "gate": "MMF_GENERATION_V2_COMPLETE",
        "executed_at": started,
        "contract_version": CONTRACT_VERSION,
        "prompt_version": PROMPT_VERSION_V2,
        "source_sha256": EXPECTED_NCERT_SHA,
        "requested_total": requested,
        "generated_total": generated,
        "provider_stats": provider_stats,
        "provider_comparison_experimental": by_provider,
        "valid_total_structural_at_generation": None,
        "exact_duplicates": len(exact_dups),
        "unique_candidates": exact_unique,
        "validator_v2": validation_payload["validator_v2_summary"],
        "ncert_grounding": grounding,
        "semantic_triage": {
            "status": triage_summary.get("status"),
            "pairs_ge_0_85": triage_summary.get("triage_pair_count_ge_0_85"),
            "band_counts": triage_summary.get("band_counts"),
            "automatic_collapse_enabled": False,
            "production_threshold_status": "NOT_CALIBRATED",
            "candidates_deleted": 0,
        },
        "empirical_yield_funnel": funnel,
        "artifact_hashes": artifact_hashes,
        "poc_immutability": poc_check,
        "database": {"pre": pre, "post": post, "unchanged": pre == post, "mutation_count": 0},
        "provider_api_generation_already_executed": True,
        "content_items_created": 0,
        "recommendation": (
            "Keep automatic semantic collapse disabled. Next: human review / quality sampling "
            "of GEN-V2 unique candidates, then separately authorize DRAFT import — not now."
        ),
    }
    (CAND_DIR / "experiment_summary.json").write_text(
        json.dumps(redact_secrets(experiment), indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    (CAND_DIR / "experiment_summary.md").write_text(
        "\n".join(
            [
                f"# MMF Generation V2 experiment summary — {BATCH}",
                "",
                f"- Requested: **{requested}**",
                f"- Generated: **{generated}**",
                f"- Exact duplicates: **{len(exact_dups)}**",
                f"- Unique: **{exact_unique}**",
                f"- Validator V2 schema OK/Fail: {full['schema_ok']} / {full['schema_fail']}",
                f"- Type MATCH/MISMATCH: {full['question_type_MATCH']} / {full['question_type_MISMATCH']}",
                f"- Difficulty agree/disagree: {full['difficulty_agree']} / {full['difficulty_disagree']}",
                f"- Concept RESOLVED/UNRESOLVED: {full['concept_RESOLVED']} / {full['concept_UNRESOLVED']}",
                f"- Semantic triage pairs ≥0.85: **{triage_summary.get('triage_pair_count_ge_0_85', 'n/a')}**",
                "- Production semantic threshold: **NOT_CALIBRATED**",
                "- Automatic collapse: **false**",
                "- ContentItem import / ECAEP / publication: **NOT EXECUTED**",
                f"- POC immutable: **{poc_check['ok']}**",
                f"- DB unchanged: **{pre == post}**",
                "",
                "## Yield funnel (experimental)",
                "",
                "```json",
                json.dumps(funnel, indent=2),
                "```",
                "",
                "## Provider comparison (experimental)",
                "",
                "```json",
                json.dumps(by_provider, indent=2),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "verdict": "GREEN" if poc_check["ok"] and pre == post else "RED",
                "batch_id": BATCH,
                "generated": generated,
                "unique": exact_unique,
                "validator_v2": validation_payload["validator_v2_summary"],
                "semantic_triage_status": triage_summary.get("status"),
                "poc_immutable": poc_check["ok"],
                "db_unchanged": pre == post,
                "dest": str(CAND_DIR),
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
