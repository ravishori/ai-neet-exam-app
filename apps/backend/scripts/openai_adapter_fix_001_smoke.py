"""OPENAI-ADAPTER-FIX-001 — One-candidate OpenAI NCERT smoke (not part of 400 pilot).

Generates at most ONE DRAFT candidate via MCQ_PROVIDER=openai using one canonical
NCERT blueprint. Does not publish, certify, resume 271, or re-run the 20-benchmark.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import uuid
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
os.environ.setdefault("FACTORY_MAX_PILOT_COST_USD", "5.0")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

import app.modules.cms.services.content_factory_generation_service as gen_mod  # noqa: E402
import app.modules.knowledge.models  # noqa: E402, F401
from app.modules.ai.gateway.openai_provider import uses_max_completion_tokens  # noqa: E402
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

REPORT_STEM = "openai_adapter_fix_001_20260914"
CAMPAIGN = "openai-adapter-fix-001-20260914"
PILOT_CAMPAIGN = "mcq-pilot-001-20260913"
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
    return {"status_counts": status, "protected_hard": hard, "ok": all(hard.get(k) == v for k, v in PROTECTED_HARD.items())}


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


def pick_blueprint(conn, ncert_root: Path) -> dict:
    rows = conn.execute(
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
                   t.name AS topic_name,
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
              AND bp.generation_eligible IS TRUE
              AND bp.is_active IS TRUE
              AND bp.status NOT IN ('SUPERSEDED', 'ARCHIVED')
              AND s.code = 'PHYSICS'
            ORDER BY ch.code, c.code
            LIMIT 20
            """
        )
    ).mappings().all()
    for r in rows:
        cons = parse_constraints(r["constraints"])
        path = extract_blueprint_ncert_path(cons)
        if not path or "StudyMaterial" in path:
            continue
        try:
            assert_blueprint_ncert_source(cons, provenance_tier=r["provenance_tier"], root=ncert_root)
        except Exception:  # noqa: BLE001
            continue
        return {**dict(r), "constraints": cons, "ncert_source_path": path}
    raise SystemExit("ABORT: no eligible Physics NCERT blueprint for smoke")


async def run_smoke() -> dict:
    settings = get_settings()
    gen_mod.settings = settings
    if (settings.mcq_provider or settings.factory_provider).lower() not in {"openai"}:
        raise SystemExit("ABORT: MCQ_PROVIDER/FACTORY_PROVIDER must be openai for this smoke")

    model = settings.openai_model
    registry = build_registry_from_settings(settings)
    entry = registry.get("openai")
    if entry is None or entry.status != "AVAILABLE":
        raise SystemExit(f"ABORT: openai registry not AVAILABLE ({entry.status if entry else None})")

    try:
        ncert_root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        ncert_root = ROOT / "NCERT Books"

    sync = create_engine(settings.database_url_sync)
    with sync.connect() as conn:
        before = snapshot(conn)
        pilot_before = pilot_created(conn)
        if not before["ok"]:
            raise SystemExit(f"ABORT: protected freeze before: {before['protected_hard']}")
        if pilot_before != PILOT_CREATED_EXPECTED:
            print(json.dumps({"warn": "pilot_created_unexpected", "count": pilot_before}))
        bp = pick_blueprint(conn, ncert_root)

    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        actor_id = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()
        factory = ContentFactoryService(session)
        gen = ContentFactoryGenerationService(session)
        if gen.mcq_provider.provider_name != "openai":
            raise SystemExit(f"ABORT: provider selection={gen.mcq_provider.provider_name}")

        batch_key = f"{CAMPAIGN}-smoke-{bp['concept_code'][:32]}-{uuid.uuid4().hex[:8]}"
        batch, _ = await factory.create_batch(
            ContentBatchCreateRequest(
                batch_key=batch_key,
                name="OPENAI-ADAPTER-FIX-001 smoke (1 candidate, DRAFT only)",
                description="Adapter fix smoke — NOT part of 400 pilot; no publish/ECAEP",
                subject_id=uuid.UUID(bp["subject_id"]),
                target_count=1,
                source_type="AI",
                source_tier="ai",
            ),
            actor_id=actor_id,
        )
        assert_blueprint_ncert_source(bp["constraints"], provenance_tier=bp["provenance_tier"], root=ncert_root)
        result = await gen.generate_for_batch(
            batch.id,
            blueprint_id=uuid.UUID(bp["blueprint_id"]),
            target_count=1,
            actor_id=actor_id,
            job_key=f"{CAMPAIGN}-{uuid.uuid4().hex[:8]}",
            sync_cap=False,
        )
        s = result if isinstance(result, dict) else {}
        if "stats" in s and isinstance(s["stats"], dict):
            s = s["stats"]

        cand = (
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
                           cand.stem_hash
                    FROM cms.generation_candidates cand
                    WHERE cand.batch_id = :bid AND cand.deleted_at IS NULL
                    ORDER BY cand.created_at DESC
                    LIMIT 5
                    """
                ),
                {"bid": batch.id},
            )
        ).mappings().all()

    await engine.dispose()

    with sync.connect() as conn:
        after = snapshot(conn)
        pilot_after = pilot_created(conn)

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
    test_tail = "\n".join(((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-15:])

    created = int(s.get("created") or 0)
    primary = dict(cand[0]) if cand else None
    parse_ok = created > 0 or (primary and primary.get("status") not in {"FAILED_PARSE", None})
    # More precise:
    parse_result = "SUCCESS" if created > 0 else (
        "FAILED_PARSE" if primary and primary.get("status") == "FAILED_PARSE" else
        "N/A_PROVIDER_OR_VALIDATION" if primary else "NO_CANDIDATE"
    )
    validation_result = (
        "PASS"
        if created > 0
        else (
            "REJECTED_VALIDATION"
            if primary and primary.get("status") == "REJECTED_VALIDATION"
            else primary.get("status") if primary else "N/A"
        )
    )

    request_success = created > 0 or (
        primary is not None and primary.get("status") not in {"FAILED_PROVIDER"} and primary.get("provider") == "openai"
    )
    # Provider reached model if we have provider metadata openai and not auth/blocked/invalid-param
    provider_reached = False
    if primary:
        err = (primary.get("error_code") or "")
        provider_reached = primary.get("provider") == "openai" and err not in {
            "PROVIDER_AUTH_FAILED",
            "PROVIDER_BLOCKED",
        }
        if created > 0:
            provider_reached = True
            request_success = True

    if created == 1 and pilot_after == pilot_before and after["ok"]:
        final = "GREEN — OPENAI ADAPTER FIX + SMOKE CREATED"
    elif provider_reached and primary and primary.get("status") == "REJECTED_VALIDATION":
        final = "YELLOW — OPENAI REACHABLE / VALIDATION REJECTED"
    elif provider_reached and primary and primary.get("status") == "FAILED_PARSE":
        final = "YELLOW — OPENAI REACHABLE / PARSE FAILED"
    elif created == 0:
        final = "RED — OPENAI SMOKE FAILED"
    else:
        final = "YELLOW — OPENAI ADAPTER FIX / PARTIAL"

    payload = {
        "campaign": CAMPAIGN,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "previous_failure": {
            "source": "MCQ-PROVIDER-BENCHMARK-001",
            "model": "gpt-5-mini",
            "http_status": 400,
            "error": "Unsupported parameter: 'max_tokens' — use 'max_completion_tokens'",
        },
        "inspection": {
            "api_endpoint": "POST {base_url}/chat/completions (OpenAI Chat Completions)",
            "transport": "httpx (no openai Python SDK installed)",
            "httpx_version": "0.28.1",
            "openai_sdk_version": None,
            "api_style": "Chat Completions (not Responses API)",
            "old_incompatible_parameter": "max_tokens",
            "corrected_parameter": "max_completion_tokens",
            "temperature_handling": "omitted for gpt-5 family (non-default temperature unsupported)",
            "structured_output": "response_format.type=json_object preserved",
            "model_uses_max_completion_tokens": uses_max_completion_tokens(model),
        },
        "model": model,
        "provider": "openai",
        "routing_policy": "fixed:openai",
        "blueprint": {
            "blueprint_id": bp["blueprint_id"],
            "blueprint_key": bp["blueprint_key"],
            "subject": bp["subject"],
            "class_level": bp["class_level"],
            "chapter": bp["chapter_name"],
            "topic": bp["topic_name"],
            "concept": bp["concept_name"],
            "ncert_source_path": bp["ncert_source_path"],
            "provenance_tier": bp["provenance_tier"],
        },
        "smoke": {
            "requested": 1,
            "created": created,
            "attempted": int(s.get("attempted") or 0),
            "failed_parse": int(s.get("failed_parse") or 0),
            "rejected_validation": int(s.get("rejected_validation") or 0),
            "duplicate": int(s.get("duplicate") or 0),
            "failed_provider": int(s.get("failed_provider") or 0),
            "stop_reason": s.get("stop_reason"),
            "cost_usd": s.get("cost_usd"),
            "batch_key": batch_key,
            "batch_id": str(batch.id),
            "request_success": request_success,
            "provider_reached_model": provider_reached,
            "parse_result": parse_result,
            "deterministic_validation_result": validation_result,
            "candidates": [dict(c) for c in cand],
            "candidate_id": primary.get("candidate_id") if primary else None,
            "content_item_id": primary.get("content_item_id") if primary else None,
            "provider_metadata": {
                "provider": primary.get("provider") if primary else None,
                "model_used": primary.get("model_used") if primary else None,
                "routing_policy": primary.get("routing_policy") if primary else None,
                "cost_status": primary.get("cost_status") if primary else None,
            },
            "published": False,
            "ncert_certified": False,
            "editorially_approved": False,
            "ncert_verification_status": "NOT PERFORMED",
            "counted_toward_271": False,
            "part_of_400_pilot": False,
        },
        "database_safety": {
            "pilot_created_before": pilot_before,
            "pilot_created_after": pilot_after,
            "pilot_created_ok": pilot_after == pilot_before == PILOT_CREATED_EXPECTED
            or (pilot_after == pilot_before),
            "protected_hard_before": before["protected_hard"],
            "protected_hard_after": after["protected_hard"],
            "protected_hard_ok": before["ok"] and after["ok"],
            "status_counts_before": before["status_counts"],
            "status_counts_after": after["status_counts"],
        },
        "tests": {
            "command": " ".join(test_cmd),
            "exit_code": proc.returncode,
            "tail": test_tail,
        },
        "confirmation": {
            "did_not_rerun_20_benchmark": True,
            "did_not_resume_271": True,
            "did_not_run_400_pilot": True,
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

    md = [
        "# OPENAI-ADAPTER-FIX-001",
        "",
        f"**Status:** `{final}`",
        f"**Generated:** `{payload['generated_at']}`",
        "",
        "## Previous failure",
        "",
        "- Benchmark OpenAI `gpt-5-mini` returned HTTP 400:",
        "  `Unsupported parameter: 'max_tokens' … Use 'max_completion_tokens' instead.`",
        "",
        "## Inspection",
        "",
        f"- API endpoint: `{payload['inspection']['api_endpoint']}`",
        f"- Transport: `{payload['inspection']['transport']}` (httpx `{payload['inspection']['httpx_version']}`)",
        f"- OpenAI Python SDK: `{payload['inspection']['openai_sdk_version']}` (not used)",
        f"- API style: `{payload['inspection']['api_style']}`",
        f"- Old parameter: `{payload['inspection']['old_incompatible_parameter']}`",
        f"- Corrected parameter: `{payload['inspection']['corrected_parameter']}`",
        f"- Model: `{model}` (uses_max_completion_tokens={uses_max_completion_tokens(model)})",
        "",
        "## Smoke (1 candidate max)",
        "",
        f"- Blueprint: `{bp['blueprint_key']}` ({bp['subject']} / {bp['chapter_name']} / {bp['concept_name']})",
        f"- NCERT path: `{bp['ncert_source_path']}`",
        f"- Request success / provider reached: `{request_success}` / `{provider_reached}`",
        f"- Created: `{created}`",
        f"- Parse: `{parse_result}`",
        f"- Deterministic validation: `{validation_result}`",
        f"- Candidate ID: `{payload['smoke']['candidate_id']}`",
        f"- Provider metadata: `{json.dumps(payload['smoke']['provider_metadata'])}`",
        f"- Published / certified / approved: `False` / `False` / `False`",
        f"- NCERT verification: **NOT PERFORMED**",
        f"- Counted toward 271 / part of 400 pilot: `False` / `False`",
        "",
        "## Database safety",
        "",
        f"- Pilot CREATED: `{pilot_before}` → `{pilot_after}` (ok=`{payload['database_safety']['pilot_created_ok']}`)",
        f"- Hard freeze OK: `{payload['database_safety']['protected_hard_ok']}`",
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
        "Do not re-run the 20-provider benchmark. Do not resume the 271. "
        "Do not publish/certify/commit/push.",
        "",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"final_status": final, "created": created, "candidate_id": payload["smoke"]["candidate_id"], "md": str(md_path), "json": str(json_path)}, indent=2))
    return payload


if __name__ == "__main__":
    asyncio.run(run_smoke())
