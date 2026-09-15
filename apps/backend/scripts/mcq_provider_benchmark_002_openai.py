"""MCQ-PROVIDER-BENCHMARK-002 — OpenAI 5-candidate NCERT smoke benchmark.

Exactly 5 NEW candidates via MCQ_PROVIDER=openai / gpt-5-mini.
NOT part of the 400 pilot; does not resume 271; excludes prior smoke candidate/BP.
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
os.environ["FACTORY_PROVIDER"] = "openai"
os.environ["MCQ_PROVIDER"] = "openai"
os.environ["FACTORY_PROVIDER_FALLBACK_CHAIN"] = ""
os.environ["MCQ_ALLOW_FALLBACK_CHAIN"] = "false"
os.environ.setdefault("FACTORY_MAX_PILOT_COST_USD", "10.0")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

import app.modules.cms.services.content_factory_generation_service as gen_mod  # noqa: E402
import app.modules.knowledge.models  # noqa: E402, F401
from app.modules.ai.gateway.registry import build_registry_from_settings  # noqa: E402
from app.modules.cms.schemas.content_factory import ContentBatchCreateRequest  # noqa: E402
from app.modules.cms.services.content_factory_generation_service import (  # noqa: E402
    ContentFactoryGenerationService,
)
from app.modules.cms.services.content_factory_service import ContentFactoryService  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    assert_blueprint_ncert_source,
    extract_blueprint_ncert_path,
    get_ncert_source_root,
)

REPORT_STEM = "mcq_provider_benchmark_002_20260914"
CAMPAIGN = "mcq-provider-benchmark-002-20260914"
PILOT_CAMPAIGN = "mcq-pilot-001-20260913"
SMOKE_CAMPAIGN = "openai-adapter-fix-001-20260914"
SMOKE_CANDIDATE_ID = "aa41982d-8b25-4dfd-81ce-87c3297d9d49"
SMOKE_BLUEPRINT_KEY = "bp-create-002-20260913-bp-physics-drift-velocity-mcq"
TARGET = 5

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
        "sv2c-botany-15",
    }
)
EXCLUDED_CHAPTERS = frozenset({"digestion-absorption"})

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


def snapshot(conn) -> dict:
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
    hard = {
        "PUBLISHED": status.get("PUBLISHED", 0),
        "IN_REVIEW": status.get("IN_REVIEW", 0),
        "SUPERSEDED": status.get("SUPERSEDED", 0),
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
    return {
        "status_counts": status,
        "protected_hard": hard,
        "ok": all(hard.get(k) == v for k, v in PROTECTED_HARD.items()),
    }


def pilot_created(conn) -> int:
    return conn.execute(
        text(
            """
            SELECT COUNT(*)::int
            FROM cms.generation_candidates cand
            JOIN cms.content_batches b ON b.id = cand.batch_id
            WHERE cand.deleted_at IS NULL AND cand.status = 'CREATED'
              AND b.batch_key LIKE :pfx
            """
        ),
        {"pfx": f"%{PILOT_CAMPAIGN}%"},
    ).scalar()


def smoke_candidate_intact(conn) -> dict:
    row = conn.execute(
        text(
            """
            SELECT cand.id::text, cand.status, cand.provider, cand.model_used, cand.deleted_at
            FROM cms.generation_candidates cand
            WHERE cand.id = :id
            """
        ),
        {"id": SMOKE_CANDIDATE_ID},
    ).mappings().first()
    return {
        "id": SMOKE_CANDIDATE_ID,
        "found": row is not None,
        "status": row["status"] if row else None,
        "unchanged_created": bool(row and row["status"] == "CREATED" and row["deleted_at"] is None),
        "provider": row["provider"] if row else None,
        "model_used": row["model_used"] if row else None,
    }


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
                JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
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
        if r["blueprint_key"] == SMOKE_BLUEPRINT_KEY:
            continue
        cons = parse_constraints(r.get("constraints"))
        if r["concept_code"] in TAXONOMY_REVIEW_CODES:
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


def select_five(bps: list[dict]) -> list[dict]:
    """Physics, Chemistry, Botany, Zoology + one extra (prefer second Physics chapter)."""
    by_subj: dict[str, list[dict]] = defaultdict(list)
    for bp in bps:
        by_subj[bp["subject"]].append(bp)

    def pick(subj: str, *, prefer_index: int | None = None) -> dict | None:
        pool = by_subj.get(subj) or []
        if not pool:
            return None
        if prefer_index is not None and len(pool) > prefer_index:
            return pool[prefer_index]
        return pool[len(pool) // 3] if len(pool) >= 3 else pool[0]

    selected: list[dict] = []
    seen: set[str] = set()
    for subj in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY"):
        bp = pick(subj)
        if bp and bp["blueprint_id"] not in seen:
            selected.append(bp)
            seen.add(bp["blueprint_id"])

    # Fifth: another Physics chapter if possible, else Chemistry, else any
    for subj, idx in (("PHYSICS", -1), ("CHEMISTRY", -1), ("BOTANY", -2), ("ZOOLOGY", -2)):
        pool = by_subj.get(subj) or []
        if not pool:
            continue
        bp = pool[idx]
        if bp["blueprint_id"] not in seen:
            selected.append(bp)
            seen.add(bp["blueprint_id"])
            break

    if len(selected) < TARGET:
        for bp in bps:
            if bp["blueprint_id"] in seen:
                continue
            selected.append(bp)
            seen.add(bp["blueprint_id"])
            if len(selected) >= TARGET:
                break
    return selected[:TARGET]


async def run() -> dict:
    settings = get_settings()
    gen_mod.settings = settings
    model = settings.openai_model
    if model != "gpt-5-mini":
        print(json.dumps({"warn": "unexpected_openai_model", "model": model}))

    registry = build_registry_from_settings(settings)
    entry = registry.get("openai")
    if entry is None or entry.status != "AVAILABLE":
        raise SystemExit(f"ABORT: openai not AVAILABLE ({entry.status if entry else None})")

    try:
        ncert_root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        ncert_root = ROOT / "NCERT Books"

    sync = create_engine(settings.database_url_sync)
    with sync.connect() as conn:
        before = snapshot(conn)
        pilot_before = pilot_created(conn)
        smoke_before = smoke_candidate_intact(conn)
        if not before["ok"]:
            raise SystemExit(f"ABORT: protected freeze before: {before['protected_hard']}")
        if pilot_before != PILOT_CREATED_EXPECTED:
            print(json.dumps({"warn": "pilot_created_unexpected", "count": pilot_before}))
        if not smoke_before["unchanged_created"]:
            raise SystemExit(f"ABORT: prior smoke candidate not intact: {smoke_before}")
        eligible = load_canonical_bps(conn, ncert_root)
        sample = select_five(eligible)
        if len(sample) != TARGET:
            raise SystemExit(f"ABORT: need {TARGET} blueprints, got {len(sample)}")
        if any(bp["blueprint_key"] == SMOKE_BLUEPRINT_KEY for bp in sample):
            raise SystemExit("ABORT: smoke blueprint must be excluded")

    engine = create_async_engine(settings.database_url)
    totals = Counter()
    runs = []
    latency_samples: list[int] = []
    batch_keys: list[str] = []

    async with AsyncSession(engine, expire_on_commit=False) as session:
        actor_id = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()
        factory = ContentFactoryService(session)
        gen = ContentFactoryGenerationService(session)
        if gen.mcq_provider.provider_name != "openai":
            raise SystemExit(f"ABORT: provider={gen.mcq_provider.provider_name}")

        for bp in sample:
            assert_blueprint_ncert_source(
                bp["constraints"],
                provenance_tier=bp["provenance_tier"],
                root=ncert_root,
            )
            batch_key = f"{CAMPAIGN}-{bp['subject'].lower()}-{bp['concept_code'][:36]}-{uuid.uuid4().hex[:8]}"
            batch_keys.append(batch_key)
            batch, _ = await factory.create_batch(
                ContentBatchCreateRequest(
                    batch_key=batch_key,
                    name=f"MCQ-PROVIDER-BENCHMARK-002 {bp['subject']} {bp['concept_code']}",
                    description=(
                        "OpenAI 5-candidate benchmark — NOT part of 400 pilot; "
                        "DRAFT only; no publish/ECAEP; does not count toward 271"
                    ),
                    subject_id=uuid.UUID(bp["subject_id"]),
                    target_count=1,
                    source_type="AI",
                    source_tier="ai",
                ),
                actor_id=actor_id,
            )
            t0 = time.perf_counter()
            try:
                result = await gen.generate_for_batch(
                    batch.id,
                    blueprint_id=uuid.UUID(bp["blueprint_id"]),
                    target_count=1,
                    actor_id=actor_id,
                    job_key=f"{CAMPAIGN}-{uuid.uuid4().hex[:8]}",
                    sync_cap=False,
                )
            except Exception as exc:  # noqa: BLE001
                latency = int((time.perf_counter() - t0) * 1000)
                latency_samples.append(latency)
                totals["provider_failures"] += 1
                totals["attempted"] += 1
                runs.append(
                    {
                        "blueprint_id": bp["blueprint_id"],
                        "blueprint_key": bp["blueprint_key"],
                        "batch_key": batch_key,
                        "error": f"{type(exc).__name__}: {exc}"[:500],
                        "latency_ms": latency,
                    }
                )
                continue

            latency = int((time.perf_counter() - t0) * 1000)
            latency_samples.append(latency)
            s = result if isinstance(result, dict) else {}
            if "stats" in s and isinstance(s["stats"], dict):
                s = s["stats"]
            created = int(s.get("created") or 0)
            attempted = int(s.get("attempted") or 0)
            totals["created"] += created
            totals["attempted"] += attempted
            totals["parse_failures"] += int(s.get("failed_parse") or 0)
            totals["validation_failures"] += int(s.get("rejected_validation") or 0)
            totals["duplicate_failures"] += int(s.get("duplicate") or 0)
            totals["provider_failures"] += int(s.get("failed_provider") or 0)
            totals["cost_usd"] += float(s.get("cost_usd") or 0.0)
            if created:
                totals["structured_output_success"] += created
            # Approximate retries as extra attempts beyond first per BP
            if attempted > 1:
                totals["retries"] += attempted - 1
            runs.append(
                {
                    "blueprint_id": bp["blueprint_id"],
                    "blueprint_key": bp["blueprint_key"],
                    "batch_key": batch_key,
                    "subject": bp["subject"],
                    "class_level": bp["class_level"],
                    "chapter": bp["chapter_name"],
                    "topic": bp["topic_name"],
                    "concept": bp["concept_name"],
                    "concept_code": bp["concept_code"],
                    "difficulty": bp["difficulty"],
                    "ncert_source_path": bp["ncert_source_path"],
                    "provenance_tier": bp["provenance_tier"],
                    "requested": 1,
                    "created": created,
                    "attempted": attempted,
                    "failed_parse": int(s.get("failed_parse") or 0),
                    "rejected_validation": int(s.get("rejected_validation") or 0),
                    "duplicate": int(s.get("duplicate") or 0),
                    "failed_provider": int(s.get("failed_provider") or 0),
                    "stop_reason": s.get("stop_reason"),
                    "latency_ms": latency,
                    "cost_usd": s.get("cost_usd"),
                    "content_item_ids": s.get("content_item_ids") or result.get("content_item_ids"),
                }
            )
            print(
                json.dumps(
                    {
                        "event": "bp_done",
                        "subject": bp["subject"],
                        "blueprint_key": bp["blueprint_key"],
                        "created": created,
                        "attempted": attempted,
                        "latency_ms": latency,
                    }
                )
            )

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
                           cand.cost_usd,
                           cand.cost_status,
                           cand.content_item_id::text,
                           cand.routing_policy,
                           cand.stem_hash,
                           bp.id::text AS blueprint_id,
                           bp.blueprint_key,
                           s.code AS subject,
                           ch.class_level,
                           ch.name AS chapter_name,
                           t.name AS topic_name,
                           c.name AS concept_name,
                           bp.constraints,
                           bp.provenance_tier,
                           ci.status AS content_item_status
                    FROM cms.generation_candidates cand
                    JOIN cms.content_batches b ON b.id = cand.batch_id
                    JOIN cms.question_blueprints bp ON bp.id = cand.blueprint_id
                    JOIN academic.concepts c ON c.id = cand.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    LEFT JOIN cms.content_items ci ON ci.id = cand.content_item_id
                    WHERE cand.deleted_at IS NULL
                      AND b.batch_key LIKE :pfx
                    ORDER BY cand.created_at
                    """
                ),
                {"pfx": f"{CAMPAIGN}%"},
            )
        ).mappings().all()

    await engine.dispose()

    candidates = []
    for row in cand_rows:
        cons = parse_constraints(row["constraints"])
        path = extract_blueprint_ncert_path(cons) or cons.get("ncert_source_path")
        candidates.append(
            {
                "candidate_id": row["candidate_id"],
                "status": row["status"],
                "error_code": row["error_code"],
                "provider": row["provider"],
                "model": row["model_used"],
                "subject": row["subject"],
                "class_level": row["class_level"],
                "chapter": row["chapter_name"],
                "topic": row["topic_name"],
                "concept": row["concept_name"],
                "blueprint_id": row["blueprint_id"],
                "blueprint_key": row["blueprint_key"],
                "content_item_id": row["content_item_id"],
                "content_item_status": row["content_item_status"],
                "routing_policy": row["routing_policy"],
                "cost_usd": float(row["cost_usd"]) if row["cost_usd"] is not None else None,
                "cost_status": row["cost_status"],
                "source_metadata": {
                    "ncert_source_path": path,
                    "ncert_derived": cons.get("ncert_derived"),
                    "provenance_tier": row["provenance_tier"],
                },
                "ncert_verification_status": "NOT PERFORMED",
                "is_prior_smoke_candidate": row["candidate_id"] == SMOKE_CANDIDATE_ID,
            }
        )

    if any(c["candidate_id"] == SMOKE_CANDIDATE_ID for c in candidates):
        raise SystemExit("ABORT: prior smoke candidate appeared in benchmark-002 set")

    with sync.connect() as conn:
        after = snapshot(conn)
        pilot_after = pilot_created(conn)
        smoke_after = smoke_candidate_intact(conn)

    py = str(BACKEND / ".venv" / "Scripts" / "python.exe")
    test_cmd = [
        py,
        "-m",
        "pytest",
        "tests/test_openai_adapter_fix_001.py",
        "tests/test_mcq_provider_abstraction_001.py::test_provider_blocked_must_stop_and_not_retry",
        "tests/test_mcq_provider_abstraction_001.py::test_rate_limit_retries_with_bounded_backoff",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(test_cmd, cwd=str(BACKEND), capture_output=True, text=True)
    test_tail = "\n".join(((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-20:])

    created = int(totals["created"])
    requested = TARGET
    attempted = int(totals["attempted"]) or 1
    rates = {
        "created_pct": round(100.0 * created / requested, 1),
        "parse_fail_pct": round(100.0 * totals["parse_failures"] / attempted, 1),
        "validation_fail_pct": round(100.0 * totals["validation_failures"] / attempted, 1),
        "duplicate_pct": round(100.0 * totals["duplicate_failures"] / attempted, 1),
        "provider_fail_pct": round(100.0 * totals["provider_failures"] / attempted, 1),
        "structured_output_success_pct": round(100.0 * totals["structured_output_success"] / requested, 1),
    }

    pilot_ok = pilot_after == pilot_before
    smoke_ok = smoke_after["unchanged_created"]
    hard_ok = before["ok"] and after["ok"]
    if created == TARGET and pilot_ok and smoke_ok and hard_ok and proc.returncode == 0:
        final = f"GREEN — OPENAI BENCHMARK-002 COMPLETE ({created}/{TARGET} CREATED)"
    elif created > 0 and pilot_ok and smoke_ok and hard_ok:
        final = f"YELLOW — OPENAI BENCHMARK-002 PARTIAL ({created}/{TARGET} CREATED)"
    else:
        final = f"RED — OPENAI BENCHMARK-002 FAILED ({created}/{TARGET} CREATED)"

    shared_sample = [
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
            "provenance_tier": bp["provenance_tier"],
        }
        for bp in sample
    ]

    payload = {
        "campaign": CAMPAIGN,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "provider": "openai",
        "model": model,
        "routing_policy": "fixed:openai",
        "ncert_root": str(ncert_root),
        "ncert_verification_status": "NOT PERFORMED",
        "requested": requested,
        "created": created,
        "attempted": int(totals["attempted"]),
        "parse_failures": int(totals["parse_failures"]),
        "validation_failures": int(totals["validation_failures"]),
        "duplicate_failures": int(totals["duplicate_failures"]),
        "provider_failures": int(totals["provider_failures"]),
        "retries": int(totals["retries"]),
        "structured_output_success": int(totals["structured_output_success"]),
        "latency_ms_samples": latency_samples,
        "latency_ms_avg": round(sum(latency_samples) / len(latency_samples), 1) if latency_samples else None,
        "latency_ms_total": sum(latency_samples),
        "cost_usd_sum": round(float(totals["cost_usd"]), 6),
        "rates": rates,
        "shared_sample_blueprints": shared_sample,
        "blueprint_ids": [bp["blueprint_id"] for bp in sample],
        "candidate_ids": [c["candidate_id"] for c in candidates if c["status"] == "CREATED"],
        "all_candidate_ids": [c["candidate_id"] for c in candidates],
        "runs": runs,
        "candidates": candidates,
        "batch_keys": batch_keys,
        "exclusions": {
            "prior_smoke_candidate_id": SMOKE_CANDIDATE_ID,
            "prior_smoke_blueprint_key": SMOKE_BLUEPRINT_KEY,
            "smoke_excluded_from_sample": True,
            "smoke_not_counted_in_five": True,
        },
        "database_safety": {
            "pilot_created_before": pilot_before,
            "pilot_created_after": pilot_after,
            "pilot_created_ok": pilot_ok,
            "prior_smoke": {"before": smoke_before, "after": smoke_after, "ok": smoke_ok},
            "protected_hard_before": before["protected_hard"],
            "protected_hard_after": after["protected_hard"],
            "protected_hard_ok": hard_ok,
            "status_counts_before": before["status_counts"],
            "status_counts_after": after["status_counts"],
            "counted_toward_271": False,
            "part_of_400_pilot": False,
            "published": False,
            "certified": False,
        },
        "tests": {
            "command": " ".join(test_cmd),
            "exit_code": proc.returncode,
            "tail": test_tail,
        },
        "confirmation": {
            "did_not_resume_271": True,
            "did_not_run_400_pilot": True,
            "did_not_include_prior_smoke": True,
            "did_not_publish": True,
            "did_not_certify": True,
            "did_not_commit": True,
            "did_not_push": True,
        },
    }

    out = ROOT / "docs" / "audits"
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{REPORT_STEM}.json"
    md_path = out / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# MCQ-PROVIDER-BENCHMARK-002",
        "",
        f"**Status:** `{final}`",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "Controlled OpenAI 5-candidate NCERT benchmark. **Not** the 400-pilot resume. "
        "Prior smoke candidate excluded. 271 remaining **not** resumed.",
        "",
        "## Provider / model",
        "",
        f"- Provider: `openai`",
        f"- Model: `{model}`",
        f"- Routing: `fixed:openai`",
        "",
        "## Blueprints (5 distinct)",
        "",
        "| # | Subject | Class | Chapter | Concept | Blueprint ID | Blueprint key |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, bp in enumerate(shared_sample, 1):
        lines.append(
            f"| {i} | {bp['subject']} | {bp['class_level']} | {bp['chapter_name']} | "
            f"{bp['concept_name']} | `{bp['blueprint_id']}` | `{bp['blueprint_key']}` |"
        )

    lines += [
        "",
        "## Metrics",
        "",
        f"- Requested: `{requested}`",
        f"- Created: `{created}`",
        f"- Attempted: `{totals['attempted']}`",
        f"- Parse failures: `{totals['parse_failures']}` ({rates['parse_fail_pct']}%)",
        f"- Validation failures: `{totals['validation_failures']}` ({rates['validation_fail_pct']}%)",
        f"- Duplicate failures: `{totals['duplicate_failures']}` ({rates['duplicate_pct']}%)",
        f"- Provider failures: `{totals['provider_failures']}` ({rates['provider_fail_pct']}%)",
        f"- Retries (extra attempts): `{totals['retries']}`",
        f"- Structured-output success: `{totals['structured_output_success']}` ({rates['structured_output_success_pct']}%)",
        f"- Avg latency ms: `{payload['latency_ms_avg']}`",
        f"- Cost USD (estimated sum): `{payload['cost_usd_sum']}`",
        "",
        "## Candidates",
        "",
        "| Candidate ID | Status | Subject | Chapter | Concept | Blueprint | Source path | NCERT verify |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in candidates:
        src = (c.get("source_metadata") or {}).get("ncert_source_path") or ""
        src_short = str(src).replace("\\", "/").split("NCERT Books/")[-1][:70]
        lines.append(
            f"| `{c['candidate_id']}` | {c['status']} | {c['subject']} | {c['chapter']} | "
            f"{c['concept']} | `{c['blueprint_key']}` | `{src_short}` | NOT PERFORMED |"
        )

    lines += [
        "",
        f"- CREATED candidate IDs: `{payload['candidate_ids']}`",
        "",
        "## NCERT verification",
        "",
        "**NCERT verification status = NOT PERFORMED**",
        "",
        "Source/provenance metadata is recorded for subsequent independent verification.",
        "",
        "## Database safety",
        "",
        f"- Pilot CREATED: `{pilot_before}` → `{pilot_after}` (ok=`{pilot_ok}`)",
        f"- Prior smoke CREATED intact: `{smoke_ok}` (`{SMOKE_CANDIDATE_ID}`)",
        f"- Hard freeze OK: `{hard_ok}`",
        f"- Counted toward 271: `False`",
        f"- Published/certified: `False` / `False`",
        "",
        "## Tests",
        "",
        f"- Exit: `{proc.returncode}`",
        "```",
        test_tail,
        "```",
        "",
        "## STOP",
        "",
        "Do not resume the 271. Do not generate the 400 pilot. Do not publish/certify/commit/push.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "final_status": final,
                "created": created,
                "candidate_ids": payload["candidate_ids"],
                "md": str(md_path),
                "json": str(json_path),
            },
            indent=2,
        )
    )
    return payload


if __name__ == "__main__":
    asyncio.run(run())
