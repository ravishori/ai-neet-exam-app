"""MCQ-PROVIDER-BENCHMARK-001 — Controlled multi-provider quality/cost benchmark.

Generates exactly 5 candidates per AVAILABLE provider using the SAME 5 canonical
NCERT blueprints. Separated from the 400-question pilot (does not resume 271).

Providers requested: gemini, openai, mistral, local (anthropic skipped — billing).
Max total CREATED target: 20. No publish / certify / approve / commit / push.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)
os.environ["FACTORY_PROVIDER_MODE"] = "fixed"
os.environ["FACTORY_PROVIDER_FALLBACK_CHAIN"] = ""
os.environ["MCQ_ALLOW_FALLBACK_CHAIN"] = "false"
os.environ.setdefault("FACTORY_MAX_PILOT_COST_USD", "15.0")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

import app.modules.cms.services.content_factory_generation_service as gen_mod  # noqa: E402
import app.modules.knowledge.models  # noqa: E402, F401
from app.modules.ai.gateway.base import (  # noqa: E402
    PROVIDER_BLOCKED,
    PROVIDER_RATE_LIMITED,
)
from app.modules.ai.gateway.registry import build_registry_from_settings  # noqa: E402
from app.modules.cms.schemas.content_factory import ContentBatchCreateRequest  # noqa: E402
from app.modules.cms.services.content_factory_generation_service import (  # noqa: E402
    ContentFactoryGenerationService,
)
from app.modules.cms.services.content_factory_service import ContentFactoryService  # noqa: E402
from app.modules.cms.services.mcq_llm_provider import report_error_alias  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    assert_blueprint_ncert_source,
    extract_blueprint_ncert_path,
    get_ncert_source_root,
)

REPORT_STEM = "mcq_provider_benchmark_001_20260914"
CAMPAIGN = "mcq-provider-benchmark-001-20260914"
PILOT_CAMPAIGN = "mcq-pilot-001-20260913"
PER_PROVIDER = 5
MAX_TOTAL_CREATED = 20

# Explicit skip: prior resume observed PROVIDER_BLOCKED billing — do not spend to retest.
BENCHMARK_PROVIDERS = ("gemini", "openai", "mistral", "local")
ANTHROPIC_POLICY = "SKIPPED_BILLING_BLOCK_DO_NOT_SPEND"

TAXONOMY_REVIEW_CODES = frozenset(
    {
        "sv2c-zoology-12",
        "sv2c-zoology-15",
        "sv2c-zoology-08",
        "sv2c-zoology-05",
        "sv2c-botany-14",
        "sv2c-botany-02",
        "sv2c-chemistry-04",
        "sv2c-chemistry-14",
        "sv2c-chemistry-34",
        "sv2c-chemistry-19",
    }
)
EXCLUDED_CHAPTERS = frozenset({"digestion-absorption"})
EXCLUDED_CONCEPTS = frozenset({"sv2c-botany-15"}) | TAXONOMY_REVIEW_CODES

PROTECTED_HARD = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "SUPERSEDED": 6,
    "chapters": 56,
    "topics": 192,
    "concepts": 318,
    "knowledge_units": 381,
    "blueprints": 445,
}
PILOT_CREATED_EXPECTED = 129


def parse_constraints(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def snapshot_sync(conn) -> dict:
    status = {
        r[0]: r[1]
        for r in conn.execute(
            text(
                """
                SELECT status, COUNT(*)::int FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
        )
    }
    unmapped = conn.execute(
        text(
            """
            SELECT COUNT(*)::int FROM cms.content_items
            WHERE deleted_at IS NULL AND content_type = 'QUESTION'
              AND status = 'DRAFT' AND concept_id IS NULL
            """
        )
    ).scalar()
    counts = {
        "chapters": conn.execute(text("SELECT COUNT(*)::int FROM academic.chapters WHERE deleted_at IS NULL")).scalar(),
        "topics": conn.execute(text("SELECT COUNT(*)::int FROM academic.topics WHERE deleted_at IS NULL")).scalar(),
        "concepts": conn.execute(text("SELECT COUNT(*)::int FROM academic.concepts WHERE deleted_at IS NULL")).scalar(),
        "knowledge_units": conn.execute(
            text("SELECT COUNT(*)::int FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*)::int FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
    }
    hard = {
        "PUBLISHED": status.get("PUBLISHED", 0),
        "IN_REVIEW": status.get("IN_REVIEW", 0),
        "SUPERSEDED": status.get("SUPERSEDED", 0),
        **counts,
    }
    return {
        "status_counts": status,
        "unmapped_draft_null_concept": unmapped,
        "protected_hard": hard,
        "protected_hard_ok": all(hard.get(k) == v for k, v in PROTECTED_HARD.items()),
    }


def pilot_created_count(conn) -> int:
    return conn.execute(
        text(
            """
            SELECT COUNT(*)::int
            FROM cms.generation_candidates cand
            JOIN cms.content_batches b ON b.id = cand.batch_id
            WHERE cand.deleted_at IS NULL
              AND cand.status = 'CREATED'
              AND b.batch_key LIKE :pfx
            """
        ),
        {"pfx": f"%{PILOT_CAMPAIGN}%"},
    ).scalar()


def load_canonical_bps(conn, ncert_root: Path) -> list[dict]:
    rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT bp.id::text AS blueprint_id,
                       bp.blueprint_key,
                       bp.blueprint_version,
                       bp.generation_eligible,
                       bp.is_active,
                       bp.status,
                       bp.provenance_tier,
                       bp.difficulty,
                       bp.constraints,
                       bp.subject_id::text AS subject_id,
                       bp.concept_id::text AS concept_id,
                       s.code AS subject,
                       c.code AS concept_code,
                       c.name AS concept_name,
                       t.code AS topic_code,
                       t.name AS topic_name,
                       ch.code AS chapter_code,
                       ch.name AS chapter_name,
                       ch.class_level
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                JOIN academic.concepts c ON c.id = bp.concept_id AND c.deleted_at IS NULL
                JOIN academic.topics t ON t.id = bp.topic_id AND t.deleted_at IS NULL
                JOIN academic.chapters ch ON ch.id = bp.chapter_id AND ch.deleted_at IS NULL
                WHERE bp.deleted_at IS NULL
                  AND bp.provenance_tier = 'authoritative'
                  AND coalesce(bp.constraints->>'ncert_derived', '') = 'true'
                  AND coalesce(bp.constraints->>'ncert_source_path', '') ILIKE '%NCERT Books%'
                ORDER BY s.code, ch.code, c.code
                """
            )
        ).mappings()
    ]
    eligible = []
    for r in rows:
        cons = parse_constraints(r.get("constraints"))
        if r["concept_code"] in EXCLUDED_CONCEPTS:
            continue
        if r["chapter_code"] in EXCLUDED_CHAPTERS:
            continue
        if not r["generation_eligible"] or not r["is_active"] or r["status"] in {"SUPERSEDED", "ARCHIVED"}:
            continue
        path = extract_blueprint_ncert_path(cons)
        if not path or "StudyMaterial" in path:
            continue
        try:
            assert_blueprint_ncert_source(cons, provenance_tier=r["provenance_tier"], root=ncert_root)
        except Exception:  # noqa: BLE001
            continue
        eligible.append({**r, "constraints": cons, "ncert_source_path": path})
    return eligible


def select_shared_sample(bps: list[dict], n: int = PER_PROVIDER) -> list[dict]:
    """One BP per subject first (Physics/Chemistry/Botany/Zoology), then fill to n.

    Prefer blueprints with zero pilot CREATED so comparison is not dominated by
    duplicate collisions; still keep subject diversity.
    """
    by_subj: dict[str, list[dict]] = defaultdict(list)
    for bp in bps:
        by_subj[bp["subject"]].append(bp)

    # Prefer mid-list entries (avoid always first chapter) for breadth
    def pick(subj: str) -> dict | None:
        pool = by_subj.get(subj) or []
        if not pool:
            return None
        return pool[len(pool) // 3] if len(pool) >= 3 else pool[0]

    order = ["PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY"]
    selected: list[dict] = []
    seen = set()
    for subj in order:
        bp = pick(subj)
        if bp and bp["blueprint_id"] not in seen:
            selected.append(bp)
            seen.add(bp["blueprint_id"])
        if len(selected) >= n:
            return selected[:n]

    # Fill remaining from other subjects / later chapters
    for subj in order:
        for bp in by_subj.get(subj, [])[::-1]:
            if bp["blueprint_id"] in seen:
                continue
            selected.append(bp)
            seen.add(bp["blueprint_id"])
            if len(selected) >= n:
                return selected[:n]
    return selected[:n]


def check_local_endpoint(base_url: str) -> dict[str, Any]:
    """Non-destructive reachability check (models list or root). No model download."""
    import httpx

    base = base_url.rstrip("/")
    result = {
        "configured": True,
        "base_url": base,
        "reachable": False,
        "probe": None,
        "status_code": None,
        "error": None,
    }
    probes = [f"{base}/models", base]
    for url in probes:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
            result["probe"] = url
            result["status_code"] = resp.status_code
            # 200/401/404 on /models still means endpoint is up
            if resp.status_code < 500:
                result["reachable"] = True
                return result
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"{type(exc).__name__}: {exc}"[:300]
    return result


def apply_provider_env(provider_alias: str) -> None:
    """Switch explicit MCQ provider and refresh cached settings."""
    os.environ["MCQ_PROVIDER"] = provider_alias
    os.environ["FACTORY_PROVIDER"] = "openai" if provider_alias == "local" else provider_alias
    if provider_alias == "google":
        os.environ["MCQ_PROVIDER"] = "google"
        os.environ["FACTORY_PROVIDER"] = "gemini"
    os.environ["FACTORY_PROVIDER_MODE"] = "fixed"
    os.environ["FACTORY_PROVIDER_FALLBACK_CHAIN"] = ""
    get_settings.cache_clear()
    gen_mod.settings = get_settings()


def preflight_providers(settings) -> dict[str, Any]:
    registry = build_registry_from_settings(settings)
    out: dict[str, Any] = {
        "anthropic": {
            "requested": False,
            "policy": ANTHROPIC_POLICY,
            "registry_status": registry.get("anthropic").status if registry.get("anthropic") else None,
            "model_configured": settings.anthropic_model or settings.ai_default_model,
            "availability": "SKIPPED",
            "reason": "Prior MCQ-PILOT-001R observed PROVIDER_BLOCKED (billing/credits); do not spend to benchmark",
        }
    }

    # gemini
    g = registry.get("gemini")
    out["gemini"] = {
        "requested": True,
        "alias": "google/gemini",
        "registry_name": "gemini",
        "model": settings.gemini_model,
        "enabled": settings.gemini_enabled,
        "key_configured": bool((settings.gemini_api_key or "").strip()),
        "registry_status": g.status if g else None,
        "availability": "AVAILABLE" if g and g.status == "AVAILABLE" else "PROVIDER_UNAVAILABLE",
        "reason": None if g and g.status == "AVAILABLE" else (g.detail if g else "missing"),
    }

    # openai cloud
    o = registry.get("openai")
    base = (settings.openai_base_url or "").strip()
    openai_cloud_ok = (
        o
        and o.status == "AVAILABLE"
        and settings.openai_enabled
        and bool((settings.openai_api_key or "").strip())
        and not base  # empty base_url → cloud default
    )
    # If base_url is set, openai registry points at local; cloud may still have key
    if base:
        openai_cloud_ok = bool((settings.openai_api_key or "").strip()) and settings.openai_enabled and not base
    # When openai_base_url empty, AVAILABLE means cloud
    if not base and o and o.status == "AVAILABLE" and settings.openai_enabled and (settings.openai_api_key or "").strip():
        openai_cloud_ok = True
    out["openai"] = {
        "requested": True,
        "alias": "openai",
        "registry_name": "openai",
        "model": settings.openai_model,
        "enabled": settings.openai_enabled,
        "key_configured": bool((settings.openai_api_key or "").strip()),
        "openai_base_url_set": bool(base),
        "registry_status": o.status if o else None,
        "availability": "AVAILABLE" if openai_cloud_ok else "PROVIDER_UNAVAILABLE",
        "reason": None
        if openai_cloud_ok
        else ("OPENAI_BASE_URL redirects adapter to local" if base else (o.detail if o else "not configured")),
    }

    # mistral
    m = registry.get("mistral")
    mistral_ok = m and m.status == "AVAILABLE" and settings.mistral_enabled and bool((settings.mistral_api_key or "").strip())
    out["mistral"] = {
        "requested": True,
        "alias": "mistral",
        "registry_name": "mistral",
        "model": settings.mistral_model,
        "enabled": settings.mistral_enabled,
        "key_configured": bool((settings.mistral_api_key or "").strip()),
        "registry_status": m.status if m else None,
        "availability": "AVAILABLE" if mistral_ok else "PROVIDER_UNAVAILABLE",
        "reason": None if mistral_ok else (m.detail if m else "not configured"),
    }

    # local
    local_info: dict[str, Any] = {
        "requested": True,
        "alias": "local",
        "registry_name": "openai",
        "model": settings.openai_model,
        "openai_base_url": base or None,
        "availability": "PROVIDER_UNAVAILABLE",
        "reason": None,
        "health_check": None,
    }
    if not base:
        local_info["reason"] = "OPENAI_BASE_URL not configured"
    else:
        health = check_local_endpoint(base)
        local_info["health_check"] = health
        if not health.get("reachable"):
            local_info["reason"] = f"endpoint not reachable: {health.get('error') or health.get('status_code')}"
        else:
            local_info["availability"] = "AVAILABLE"
            local_info["reason"] = None
    out["local"] = local_info
    return out


async def run_provider_benchmark(
    *,
    provider_alias: str,
    registry_name: str,
    model: str,
    sample: list[dict],
    actor_id: uuid.UUID,
    ncert_root: Path,
) -> dict[str, Any]:
    apply_provider_env(provider_alias)
    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    provider_result: dict[str, Any] = {
        "provider_alias": provider_alias,
        "registry_name": registry_name,
        "model": model,
        "routing_policy": f"fixed:{registry_name}",
        "requested": PER_PROVIDER,
        "created": 0,
        "attempted": 0,
        "parse_failures": 0,
        "validation_failures": 0,
        "duplicate_failures": 0,
        "provider_failures": 0,
        "rate_limit_failures": 0,
        "blocked_billing_failures": 0,
        "retries_observed": 0,
        "latency_ms_total": 0,
        "latency_ms_samples": [],
        "structured_output_success": 0,
        "cost_usd_sum": 0.0,
        "cost_status_counts": Counter(),
        "stop_reason": None,
        "batch_id": None,
        "batch_key": None,
        "runs": [],
        "candidates": [],
    }

    async with AsyncSession(engine, expire_on_commit=False) as session:
        factory = ContentFactoryService(session)
        gen = ContentFactoryGenerationService(session)
        # Confirm selection matches expected registry
        if gen.mcq_provider.provider_name != registry_name:
            provider_result["stop_reason"] = (
                f"provider_selection_mismatch expected={registry_name} got={gen.mcq_provider.provider_name}"
            )
            await engine.dispose()
            return provider_result

        batch_ids: list[str] = []
        for bp in sample:
            assert_blueprint_ncert_source(
                bp["constraints"],
                provenance_tier=bp["provenance_tier"],
                root=ncert_root,
            )
            subject_id = uuid.UUID(bp["subject_id"])
            batch_key = f"{CAMPAIGN}-{provider_alias}-{bp['subject'].lower()}-{bp['concept_code'][:40]}"
            # Truncate to safe key length
            batch_key = batch_key[:120]
            batch, _ = await factory.create_batch(
                ContentBatchCreateRequest(
                    batch_key=batch_key,
                    name=f"MCQ-PROVIDER-BENCHMARK-001 {provider_alias} {bp['concept_code']}",
                    description=(
                        "Controlled provider benchmark — NOT part of 400 pilot; "
                        "DRAFT only; no publish/ECAEP"
                    ),
                    subject_id=subject_id,
                    target_count=1,
                    source_type="AI",
                    source_tier="ai",
                ),
                actor_id=actor_id,
            )
            batch_ids.append(str(batch.id))
            provider_result["batch_id"] = batch_ids[0]
            provider_result.setdefault("batch_keys", []).append(batch_key)
            keys = provider_result["batch_keys"]
            provider_result["batch_key"] = ",".join(keys[:3]) + ("…" if len(keys) > 3 else "")

            job_key = f"{CAMPAIGN}-{provider_alias}-{bp['concept_code']}-{uuid.uuid4().hex[:8]}"
            t0 = time.perf_counter()
            try:
                result = await gen.generate_for_batch(
                    batch.id,
                    blueprint_id=uuid.UUID(bp["blueprint_id"]),
                    target_count=1,
                    actor_id=actor_id,
                    job_key=job_key,
                    sync_cap=False,
                )
            except Exception as exc:  # noqa: BLE001
                latency = int((time.perf_counter() - t0) * 1000)
                provider_result["provider_failures"] += 1
                provider_result["attempted"] += 1
                provider_result["latency_ms_samples"].append(latency)
                provider_result["runs"].append(
                    {
                        "blueprint_key": bp["blueprint_key"],
                        "batch_key": batch_key,
                        "error": f"{type(exc).__name__}: {exc}"[:500],
                        "latency_ms": latency,
                    }
                )
                msg = str(exc).lower()
                if "credit" in msg or "billing" in msg or PROVIDER_BLOCKED.lower() in msg:
                    provider_result["blocked_billing_failures"] += 1
                    provider_result["stop_reason"] = PROVIDER_BLOCKED
                    break
                continue

            latency = int((time.perf_counter() - t0) * 1000)
            provider_result["latency_ms_samples"].append(latency)
            s = result if isinstance(result, dict) else {}
            if "stats" in s and isinstance(s["stats"], dict):
                s = s["stats"]
            created = int(s.get("created") or 0)
            attempted = int(s.get("attempted") or 0)
            provider_result["created"] += created
            provider_result["attempted"] += attempted
            provider_result["parse_failures"] += int(s.get("failed_parse") or 0)
            provider_result["validation_failures"] += int(s.get("rejected_validation") or 0)
            provider_result["duplicate_failures"] += int(s.get("duplicate") or 0)
            provider_result["provider_failures"] += int(s.get("failed_provider") or 0)
            provider_result["cost_usd_sum"] += float(s.get("cost_usd") or 0.0)
            if created:
                provider_result["structured_output_success"] += created
            stop = s.get("stop_reason")
            provider_result["runs"].append(
                {
                    "blueprint_id": bp["blueprint_id"],
                    "blueprint_key": bp["blueprint_key"],
                    "batch_key": batch_key,
                    "subject": bp["subject"],
                    "chapter": bp["chapter_name"],
                    "concept": bp["concept_name"],
                    "class_level": bp["class_level"],
                    "ncert_source_path": bp["ncert_source_path"],
                    "requested": 1,
                    "created": created,
                    "attempted": attempted,
                    "failed_parse": int(s.get("failed_parse") or 0),
                    "rejected_validation": int(s.get("rejected_validation") or 0),
                    "duplicate": int(s.get("duplicate") or 0),
                    "failed_provider": int(s.get("failed_provider") or 0),
                    "stop_reason": stop,
                    "latency_ms": latency,
                    "cost_usd": s.get("cost_usd"),
                    "content_item_ids": s.get("content_item_ids") or result.get("content_item_ids"),
                }
            )
            if stop in {PROVIDER_BLOCKED, "PROVIDER_AUTH_FAILED"}:
                if stop == PROVIDER_BLOCKED:
                    provider_result["blocked_billing_failures"] += 1
                provider_result["stop_reason"] = stop
                break
            if stop == PROVIDER_RATE_LIMITED:
                provider_result["rate_limit_failures"] += 1

        # Collect candidate rows for this provider's benchmark batches
        cand_rows = (
            await session.execute(
                text(
                    """
                    SELECT cand.id::text AS candidate_id,
                           cand.status,
                           cand.error_code,
                           cand.error_summary,
                           cand.provider,
                           cand.model_used,
                           cand.stem_hash,
                           cand.cost_usd,
                           cand.cost_status,
                           cand.blueprint_id::text,
                           cand.content_item_id::text,
                           cand.routing_policy,
                           bp.blueprint_key,
                           s.code AS subject,
                           ch.name AS chapter_name,
                           ch.class_level,
                           t.name AS topic_name,
                           c.name AS concept_name,
                           bp.constraints
                    FROM cms.generation_candidates cand
                    JOIN cms.content_batches b ON b.id = cand.batch_id
                    JOIN cms.question_blueprints bp ON bp.id = cand.blueprint_id
                    JOIN academic.concepts c ON c.id = cand.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE cand.deleted_at IS NULL
                      AND b.batch_key LIKE :pfx
                    ORDER BY cand.created_at
                    """
                ),
                {"pfx": f"{CAMPAIGN}-{provider_alias}%"},
            )
        ).mappings().all()

        for row in cand_rows:
            cons = parse_constraints(row["constraints"])
            path = extract_blueprint_ncert_path(cons) or cons.get("ncert_source_path")
            validation_status = "PASS" if row["status"] == "CREATED" else row["status"]
            dup = row["status"] == "REJECTED_DUPLICATE" or (row["error_code"] or "") == "DUPLICATE_STEM"
            obs = []
            if row["status"] == "CREATED":
                obs.append("schema accepted by factory validators; DRAFT only")
            elif row["status"] == "FAILED_PARSE":
                obs.append(f"parse failure: {(row['error_summary'] or '')[:120]}")
            elif row["status"] == "REJECTED_VALIDATION":
                obs.append(f"validation: {(row['error_code'] or '')[:120]}")
            elif row["status"] == "FAILED_PROVIDER":
                obs.append(f"provider: {report_error_alias(row['error_code'] or '')} {(row['error_summary'] or '')[:80]}")
            provider_result["candidates"].append(
                {
                    "provider": row["provider"] or registry_name,
                    "model": row["model_used"] or model,
                    "subject": row["subject"],
                    "class_level": row["class_level"],
                    "chapter": row["chapter_name"],
                    "topic": row["topic_name"],
                    "concept": row["concept_name"],
                    "blueprint_key": row["blueprint_key"],
                    "candidate_id": row["candidate_id"],
                    "content_item_id": row["content_item_id"],
                    "status": row["status"],
                    "validation_status": validation_status,
                    "duplicate_status": "DUPLICATE" if dup else "NOT_DUPLICATE",
                    "error_code": row["error_code"],
                    "source_metadata": {
                        "ncert_source_path": path,
                        "ncert_derived": cons.get("ncert_derived"),
                        "provenance_tier": "authoritative",
                    },
                    "cost_usd": float(row["cost_usd"]) if row["cost_usd"] is not None else None,
                    "cost_status": row["cost_status"],
                    "quality_observations": "; ".join(obs) if obs else "n/a",
                    "ncert_verification_status": "NOT PERFORMED",
                }
            )
            if row["cost_status"]:
                provider_result["cost_status_counts"][row["cost_status"]] += 1
            # Count rate-limit / blocked from candidate errors
            if (row["error_code"] or "") == PROVIDER_RATE_LIMITED:
                provider_result["rate_limit_failures"] += 1
            if (row["error_code"] or "") == PROVIDER_BLOCKED:
                provider_result["blocked_billing_failures"] += 1

    await engine.dispose()
    samples = provider_result["latency_ms_samples"]
    provider_result["latency_ms_total"] = sum(samples)
    provider_result["latency_ms_avg"] = round(sum(samples) / len(samples), 1) if samples else None
    provider_result["cost_status_counts"] = dict(provider_result["cost_status_counts"])
    # rates
    req = provider_result["requested"] or 1
    att = provider_result["attempted"] or 1
    provider_result["rates"] = {
        "created_pct": round(100.0 * provider_result["created"] / req, 1),
        "parse_fail_pct": round(100.0 * provider_result["parse_failures"] / att, 1),
        "validation_fail_pct": round(100.0 * provider_result["validation_failures"] / att, 1),
        "duplicate_pct": round(100.0 * provider_result["duplicate_failures"] / att, 1),
        "provider_fail_pct": round(100.0 * provider_result["provider_failures"] / att, 1),
        "structured_output_success_pct": round(100.0 * provider_result["structured_output_success"] / req, 1),
    }
    return provider_result


def pct(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(100.0 * n / d, 1)


def build_recommendation(results: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    """Operator-facing recommendation — does NOT auto-switch production provider."""
    scored = []
    for alias, r in results.items():
        if r.get("availability") != "AVAILABLE":
            continue
        if r.get("skipped"):
            continue
        created = r.get("created") or 0
        avg_lat = r.get("latency_ms_avg")
        cost = r.get("cost_usd_sum")
        blocked = r.get("blocked_billing_failures") or 0
        scored.append(
            {
                "provider": alias,
                "model": r.get("model"),
                "created": created,
                "created_pct": (r.get("rates") or {}).get("created_pct"),
                "avg_latency_ms": avg_lat,
                "cost_usd_sum": cost,
                "blocked": blocked,
                "parse_failures": r.get("parse_failures"),
                "validation_failures": r.get("validation_failures"),
            }
        )
    scored.sort(key=lambda x: (-x["created"], x["avg_latency_ms"] if x["avg_latency_ms"] is not None else 1e9))
    return {
        "auto_selected": False,
        "note": (
            "Recommendation only — operator must explicitly set MCQ_PROVIDER before resuming the 271. "
            "No silent switch performed."
        ),
        "ranked_available": scored,
        "suggested_next_for_271": scored[0]["provider"] if scored and scored[0]["created"] > 0 else None,
        "caveats": [
            "NCERT verification NOT PERFORMED — editorial/NCERT gate still required before any publication claim",
            "n=5 per provider is indicative only",
            "Anthropic not benchmarked due to billing block",
            "Local unavailable in this environment",
        ],
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# MCQ-PROVIDER-BENCHMARK-001",
        "",
        f"**Status:** `{payload['final_status']}`",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "Controlled multi-provider benchmark (max 20 candidates). "
        "**Not** part of the 400-question pilot. Existing 129 CREATED untouched. "
        "271 remaining **not** resumed.",
        "",
        "## Provider availability",
        "",
        "| Provider | Model | Availability | Reason |",
        "|---|---|---|---|",
    ]
    for alias, pf in payload["preflight"].items():
        lines.append(
            f"| {alias} | `{pf.get('model') or pf.get('model_configured')}` | "
            f"{pf.get('availability')} | {pf.get('reason') or pf.get('policy') or ''} |"
        )

    lines += [
        "",
        "## Shared blueprint sample (fair comparison)",
        "",
        "| # | Subject | Class | Chapter | Concept | Blueprint key |",
        "|---|---|---|---|---|---|",
    ]
    for i, bp in enumerate(payload["shared_sample"], 1):
        lines.append(
            f"| {i} | {bp['subject']} | {bp['class_level']} | {bp['chapter_name']} | "
            f"{bp['concept_name']} | `{bp['blueprint_key']}` |"
        )

    lines += [
        "",
        "## Comparison table",
        "",
        "| Provider | Model | Req | Created | Parse fail | Valid fail | Dup | Prov fail | "
        "RL | Blocked | Avg latency ms | Struct OK % | Cost USD |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for alias in [*BENCHMARK_PROVIDERS, "anthropic"]:
        r = payload["provider_results"].get(alias) or {}
        if r.get("skipped") or r.get("availability") == "PROVIDER_UNAVAILABLE" or r.get("availability") == "SKIPPED":
            lines.append(
                f"| {alias} | `{r.get('model') or ''}` | — | — | — | — | — | — | — | — | — | — | — |"
            )
            continue
        rates = r.get("rates") or {}
        lines.append(
            f"| {alias} | `{r.get('model')}` | {r.get('requested')} | {r.get('created')} | "
            f"{r.get('parse_failures')} | {r.get('validation_failures')} | {r.get('duplicate_failures')} | "
            f"{r.get('provider_failures')} | {r.get('rate_limit_failures')} | {r.get('blocked_billing_failures')} | "
            f"{r.get('latency_ms_avg')} | {rates.get('structured_output_success_pct')} | "
            f"{round(float(r.get('cost_usd_sum') or 0), 6)} |"
        )

    lines += [
        "",
        "## NCERT verification",
        "",
        "**NCERT verification status = NOT PERFORMED**",
        "",
        "Deterministic factory validators ran (schema / options / single-answer / duplicate / source-path). "
        "Independent NCERT editorial verification is a later gate — do not treat CREATED as verified.",
        "",
        "## Quality sample (every generated candidate)",
        "",
        "| Provider | Model | Subject | Chapter | Concept | Candidate ID | Validation | Duplicate | Source | Observations |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for alias, r in payload["provider_results"].items():
        for c in r.get("candidates") or []:
            src = (c.get("source_metadata") or {}).get("ncert_source_path") or ""
            src_short = src.replace("\\", "/").split("NCERT Books/")[-1][:60] if src else ""
            lines.append(
                f"| {c.get('provider')} | `{c.get('model')}` | {c.get('subject')} | {c.get('chapter')} | "
                f"{c.get('concept')} | `{c.get('candidate_id')}` | {c.get('validation_status')} | "
                f"{c.get('duplicate_status')} | `{src_short}` | {c.get('quality_observations')} |"
            )

    rec = payload["recommendation"]
    lines += [
        "",
        "## Recommendation for next 271 (operator decision)",
        "",
        f"- Auto-selected: **{rec.get('auto_selected')}** (must remain false)",
        f"- Suggested next provider (manual): `{rec.get('suggested_next_for_271')}`",
        f"- Ranked: `{json.dumps(rec.get('ranked_available'), default=str)}`",
        "",
        "### Caveats",
        "",
    ]
    for c in rec.get("caveats") or []:
        lines.append(f"- {c}")

    saf = payload["database_safety"]
    lines += [
        "",
        "## Database safety",
        "",
        f"- Pilot CREATED unchanged: `{saf.get('pilot_created_ok')}` ({saf.get('pilot_created_after')})",
        f"- Hard protected freeze OK: `{saf.get('protected_hard_ok')}`",
        f"- Benchmark batches: `{saf.get('benchmark_batch_keys')}`",
        f"- Publication/certification: none",
        "",
        "## Tests",
        "",
        f"- Command: `{payload['tests'].get('command')}`",
        f"- Passed/Failed: `{payload['tests'].get('passed')}` / `{payload['tests'].get('failed')}`",
        "",
        "## STOP",
        "",
        "Do not resume the 271. Do not generate beyond this benchmark. "
        "Do not publish/certify/commit/push.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path, json_path


async def async_main() -> int:
    settings = get_settings()
    try:
        ncert_root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        ncert_root = ROOT / "NCERT Books"

    sync_engine = create_engine(settings.database_url_sync)
    with sync_engine.connect() as conn:
        before = snapshot_sync(conn)
        pilot_before = pilot_created_count(conn)
        if pilot_before != PILOT_CREATED_EXPECTED:
            print(json.dumps({"warn": "pilot_created_unexpected", "count": pilot_before}))
        if not before["protected_hard_ok"]:
            raise SystemExit(f"ABORT: hard protected freeze failed before: {before['protected_hard']}")
        eligible = load_canonical_bps(conn, ncert_root)
        if len(eligible) < 308:
            print(json.dumps({"warn": "canonical_eligible_lt_308", "count": len(eligible)}))
        sample = select_shared_sample(eligible, PER_PROVIDER)
        if len(sample) != PER_PROVIDER:
            raise SystemExit(f"ABORT: could not select {PER_PROVIDER} shared BPs (got {len(sample)})")

    preflight = preflight_providers(settings)
    print(json.dumps({"event": "preflight", "providers": {k: v.get("availability") for k, v in preflight.items()}}))

    shared_sample_meta = [
        {
            "blueprint_id": bp["blueprint_id"],
            "blueprint_key": bp["blueprint_key"],
            "subject": bp["subject"],
            "class_level": bp["class_level"],
            "chapter_name": bp["chapter_name"],
            "topic_name": bp["topic_name"],
            "concept_name": bp["concept_name"],
            "concept_code": bp["concept_code"],
            "difficulty": bp["difficulty"],
            "ncert_source_path": bp["ncert_source_path"],
        }
        for bp in sample
    ]

    # Resolve actor
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        actor_id = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()
    await engine.dispose()

    provider_results: dict[str, Any] = {
        "anthropic": {
            **preflight["anthropic"],
            "skipped": True,
            "requested": 0,
            "created": 0,
            "candidates": [],
            "model": preflight["anthropic"].get("model_configured"),
        }
    }

    total_created = 0
    for alias in BENCHMARK_PROVIDERS:
        pf = preflight[alias]
        if pf.get("availability") != "AVAILABLE":
            provider_results[alias] = {
                **pf,
                "skipped": True,
                "requested": 0,
                "created": 0,
                "candidates": [],
                "availability": "PROVIDER_UNAVAILABLE",
            }
            print(json.dumps({"event": "provider_skip", "provider": alias, "reason": pf.get("reason")}))
            continue

        if alias == "gemini":
            provider_alias = "google"
            registry_name = "gemini"
        elif alias == "local":
            provider_alias = "local"
            registry_name = "openai"
        else:
            provider_alias = alias
            registry_name = alias
        model = pf.get("model")
        print(json.dumps({"event": "provider_start", "provider": alias, "model": model}))
        result = await run_provider_benchmark(
            provider_alias=provider_alias,
            registry_name=registry_name,
            model=model,
            sample=sample,
            actor_id=actor_id,
            ncert_root=ncert_root,
        )
        result["provider_alias"] = provider_alias
        result["availability"] = "AVAILABLE"
        provider_results[alias] = result
        total_created += int(result.get("created") or 0)
        print(
            json.dumps(
                {
                    "event": "provider_done",
                    "provider": alias,
                    "created": result.get("created"),
                    "attempted": result.get("attempted"),
                    "stop": result.get("stop_reason"),
                    "cost_usd": result.get("cost_usd_sum"),
                }
            )
        )
        if total_created > MAX_TOTAL_CREATED:
            raise SystemExit("ABORT: exceeded max 20 benchmark CREATED")

    # Safety after
    with sync_engine.connect() as conn:
        after = snapshot_sync(conn)
        pilot_after = pilot_created_count(conn)
        bench_batches = [
            r[0]
            for r in conn.execute(
                text("SELECT batch_key FROM cms.content_batches WHERE batch_key LIKE :pfx ORDER BY created_at"),
                {"pfx": f"{CAMPAIGN}%"},
            )
        ]
        bench_created = conn.execute(
            text(
                """
                SELECT COUNT(*)::int FROM cms.generation_candidates cand
                JOIN cms.content_batches b ON b.id = cand.batch_id
                WHERE cand.deleted_at IS NULL AND cand.status = 'CREATED'
                  AND b.batch_key LIKE :pfx
                """
            ),
            {"pfx": f"{CAMPAIGN}%"},
        ).scalar()

    # Tests
    py = str(BACKEND / ".venv" / "Scripts" / "python.exe")
    test_cmd = [
        py,
        "-m",
        "pytest",
        "tests/test_mcq_provider_abstraction_001.py",
        "tests/test_content_factory_p3.py::test_provider_credit_blocked_stops",
        "tests/test_ai_gateway_multi_provider.py::test_provider_contract_success",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(test_cmd, cwd=str(BACKEND), capture_output=True, text=True)
    test_out = (proc.stdout or "") + (proc.stderr or "")
    passed = failed = None
    for token in test_out.strip().splitlines()[-5:]:
        if "passed" in token:
            # e.g. "18 passed"
            parts = token.replace(",", "").split()
            for i, p in enumerate(parts):
                if p == "passed" and i > 0:
                    passed = int(parts[i - 1])
                if p == "failed" and i > 0:
                    failed = int(parts[i - 1])

    recommendation = build_recommendation(provider_results, preflight)
    pilot_ok = pilot_after == PILOT_CREATED_EXPECTED == pilot_before
    hard_ok = after["protected_hard_ok"] and before["protected_hard_ok"]
    if total_created > MAX_TOTAL_CREATED:
        final = "RED — OVER GENERATION"
    elif not pilot_ok or not hard_ok:
        final = "YELLOW — BENCHMARK COMPLETE / SAFETY DRIFT"
    elif total_created == 0:
        final = "YELLOW — BENCHMARK COMPLETE / ZERO CREATED"
    else:
        final = f"GREEN — BENCHMARK COMPLETE ({total_created}/{MAX_TOTAL_CREATED} CREATED)"

    payload = {
        "campaign": CAMPAIGN,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "ncert_root": str(ncert_root),
        "ncert_verification_status": "NOT PERFORMED",
        "benchmark_size": {
            "per_provider": PER_PROVIDER,
            "providers_requested": list(BENCHMARK_PROVIDERS),
            "max_total_created": MAX_TOTAL_CREATED,
            "total_created": total_created,
            "benchmark_created_in_db": bench_created,
        },
        "preflight": preflight,
        "shared_sample": shared_sample_meta,
        "canonical_eligible_count": len(eligible),
        "provider_results": provider_results,
        "recommendation": recommendation,
        "database_safety": {
            "pilot_created_before": pilot_before,
            "pilot_created_after": pilot_after,
            "pilot_created_ok": pilot_ok,
            "protected_hard_before": before["protected_hard"],
            "protected_hard_after": after["protected_hard"],
            "protected_hard_ok": hard_ok,
            "unmapped_draft_null_concept_before": before["unmapped_draft_null_concept"],
            "unmapped_draft_null_concept_after": after["unmapped_draft_null_concept"],
            "status_counts_before": before["status_counts"],
            "status_counts_after": after["status_counts"],
            "benchmark_batch_keys": bench_batches,
            "did_not_resume_271": True,
            "did_not_modify_pilot_129": pilot_ok,
            "did_not_publish": True,
            "did_not_certify": True,
            "did_not_modify_blueprints_kus_taxonomy": hard_ok,
        },
        "tests": {
            "command": " ".join(test_cmd),
            "exit_code": proc.returncode,
            "passed": passed,
            "failed": failed or 0,
            "tail": "\n".join(test_out.strip().splitlines()[-20:]),
        },
        "confirmation": {
            "not_part_of_400_pilot": True,
            "anthropic_benchmarked": False,
            "auto_provider_switch": False,
            "commit": False,
            "push": False,
        },
    }
    md_path, json_path = write_reports(payload)
    print(json.dumps({"final_status": final, "md": str(md_path), "json": str(json_path), "created": total_created}, indent=2))
    return 0 if proc.returncode == 0 and hard_ok and pilot_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
