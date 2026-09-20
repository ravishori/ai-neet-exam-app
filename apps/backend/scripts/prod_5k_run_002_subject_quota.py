#!/usr/bin/env python3
"""Production 5,000-MCQ resumable driver — subject-quota round-robin selection.

Supersedes the scratchpad `prod_5k_run.py` driver, which selected blueprints
via a concept-keyed interleave that degenerated into pure subject-alphabetical
order for any subject with a 1:1 concept:blueprint ratio (Botany, Chemistry,
Zoology all qualified). That let Botany-11/12 consume an entire wall-clock
budget before the driver ever reached Chemistry/Physics/Zoology — see
docs/audits (5K generation diagnosis, 2026-09-18) for the full root-cause
analysis.

This driver groups blueprints into 8 fixed queues (Physics/Chemistry/Botany/
Zoology x class 11/12) and rotates across non-empty queues one blueprint per
queue per lap, via `app.modules.cms.services.subject_quota_round_robin`.

Same safety posture as the superseded driver:
- One stable batch (batch_key=prod-5k-YYYYMMDD), idempotent create_batch.
- Reuses ContentFactoryGenerationService — the exact code path the HTTP
  endpoint and every prior pilot used. No gates are bypassed or duplicated.
- Provider fallback stays disabled (MCQ_ALLOW_FALLBACK_CHAIN=false asserted
  at startup).
- DB is the source of truth for resume — no local progress file.

--dry-run (default: on unless --live is passed) does not touch the DB or
call any provider. It loads the real blueprint pool, builds the 8 queues,
runs the round-robin selector, and prints the first N queue labels so the
cross-subject rotation can be inspected before any live run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.modules.cms.schemas.content_factory import (
    BatchStatusTransitionRequest,
    ContentBatchCreateRequest,
)
from app.modules.cms.services.content_factory_service import ContentFactoryService
from app.modules.cms.services.content_factory_generation_service import (
    ContentFactoryGenerationService,
)
from app.modules.cms.services.subject_quota_round_robin import (
    build_queues,
    round_robin_order,
)

TARGET = 5000
PER_CALL = 100
CHECKPOINT_EVERY = 500
WALL_S = float(os.environ.get("PROD5K_WALL_S", "36000"))
BATCH_KEY = os.environ.get("PROD5K_BATCH_KEY") or f"prod-5k-{date.today():%Y%m%d}"
DSN_ASYNC = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
LOG_PATH = os.environ.get(
    "PROD5K_LOG",
    str(Path(__file__).resolve().parents[1] / "scratchpad" / "prod_5k_run_002.log.jsonl"),
)

# Same eligibility filter as the superseded driver — unchanged, not the fix.
BLUEPRINT_POOL_SQL = """
    SELECT bp.id::text AS id,
           bp.blueprint_key AS key,
           s.name AS subject,
           ch.class_level AS class_level,
           ch.code AS chapter_code,
           co.name AS concept,
           co.id::text AS concept_id,
           COALESCE(qf.family_key, 'unknown') AS family,
           bp.difficulty AS difficulty,
           bp.subject_id, bp.chapter_id, bp.topic_id, bp.concept_id AS concept_id_uuid
    FROM cms.question_blueprints bp
    JOIN academic.subjects s ON s.id = bp.subject_id
    JOIN academic.chapters ch ON ch.id = bp.chapter_id
    JOIN academic.concepts co ON co.id = bp.concept_id
    LEFT JOIN cms.question_families qf ON qf.id = bp.question_family_id
    WHERE bp.status='ACTIVE' AND bp.is_active AND bp.generation_eligible
      AND bp.constraints ? 'ncert_source_path'
      AND (bp.constraints->>'ncert_derived')::boolean IS TRUE
    ORDER BY s.name, ch.class_level, ch.code, co.name,
             COALESCE(qf.family_key,'unknown'), bp.difficulty
"""


@dataclass
class RunStats:
    passes: int = 0
    provider_calls: int = 0
    generated: int = 0
    accepted_now: int = 0
    accepted_start: int = 0
    rejected_validation: int = 0
    duplicate: int = 0
    diversity_rejected: int = 0
    failed_provider: int = 0
    failed_parse: int = 0
    cost_usd: float = 0.0
    fallbacks: int = 0
    stop_reasons: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.perf_counter)


def _log(record: dict, *, log_path: str = LOG_PATH) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(UTC).isoformat(), **record}
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


async def _accepted_count(session: AsyncSession, batch_id: uuid.UUID) -> int:
    tag = f"batch:{batch_id}"
    row = (
        await session.execute(
            text("SELECT count(*) FROM cms.content_items WHERE :t = ANY(tags) AND deleted_at IS NULL"),
            {"t": tag},
        )
    ).first()
    return int(row[0] if row else 0)


async def _load_blueprint_pool(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(text(BLUEPRINT_POOL_SQL))).mappings().all()
    return [dict(r) for r in rows]


async def mark_batch_complete_if_target_reached(
    factory: ContentFactoryService,
    *,
    batch_id: uuid.UUID,
    actor_id: uuid.UUID,
    accepted_now: int,
    target: int,
) -> bool:
    """Terminal batch-state fix: on reaching target, advance GENERATING → QA
    — the project's canonical "generation phase complete" state (there is
    no separate COMPLETED status in BATCH_TRANSITIONS). Returns True if a
    transition was made. Leaves the batch untouched on timeout/under-target
    exit, preserving prior failure/timeout semantics exactly. Reuses the
    existing validated ContentFactoryService.transition_batch — no new
    state-machine logic."""
    if accepted_now < target:
        return False
    await factory.transition_batch(
        batch_id,
        BatchStatusTransitionRequest(to_status="QA"),
        actor_id=actor_id,
    )
    return True


def build_round_robin_order(rows: list[dict]) -> list:
    """Pure, DB-free composition of build_queues + round_robin_order —
    the actual selection fix. Exposed at module level so both the CLI
    and tests exercise the same code path."""
    queues = build_queues(rows)
    return round_robin_order(queues)


async def dry_run(preview_n: int) -> int:
    """Load the real blueprint pool, build the round-robin order, print the
    first `preview_n` queue labels. Never touches content_items, jobs, runs,
    or any provider. Safe to run anytime."""
    engine = create_async_engine(DSN_ASYNC, pool_pre_ping=True)
    async with AsyncSession(bind=engine, expire_on_commit=False) as session:
        rows = await _load_blueprint_pool(session)
    await engine.dispose()

    if not rows:
        print("DRY RUN: no eligible blueprints found.")
        return 1

    order = build_round_robin_order(rows)
    labels = [r.label for r in order]

    print(f"DRY RUN: {len(rows)} eligible blueprints across {len(set(labels))} queues.")
    print(f"First {preview_n} selected queue labels (round-robin order):")
    for i, label in enumerate(labels[:preview_n]):
        print(f"  [{i:02d}] {label}")

    distinct_in_first_n = len(set(labels[:preview_n]))
    print(f"\nDistinct subjects x classes covered in first {preview_n}: {distinct_in_first_n}")
    return 0


async def live_run(
    *,
    target: int = TARGET,
    per_call: int = PER_CALL,
    wall_s: float = WALL_S,
    batch_key: str = BATCH_KEY,
    bulk_mode: bool = False,
) -> int:
    settings = get_settings()
    if settings.factory_provider != "openai" or (settings.openai_model or "").strip() != "gpt-5.6-luna":
        _log({"level": "FATAL", "msg": "wrong provider/model", "provider": settings.factory_provider, "model": settings.openai_model})
        print("STOP: provider/model misconfigured; expected openai/gpt-5.6-luna", file=sys.stderr)
        return 2
    if settings.mcq_allow_fallback_chain:
        _log({"level": "FATAL", "msg": "MCQ_ALLOW_FALLBACK_CHAIN must be false"})
        print("STOP: MCQ_ALLOW_FALLBACK_CHAIN is true; refusing to run.", file=sys.stderr)
        return 2
    if not settings.openai_api_key:
        _log({"level": "FATAL", "msg": "OPENAI_API_KEY missing"})
        return 2

    engine = create_async_engine(DSN_ASYNC, pool_pre_ping=True, pool_size=4, max_overflow=2)
    stats = RunStats()
    deadline = time.perf_counter() + wall_s

    async with AsyncSession(bind=engine, expire_on_commit=False) as session:
        actor = (
            await session.execute(text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at ASC LIMIT 1"))
        ).first()
        if actor is None:
            _log({"level": "FATAL", "msg": "no actor user"})
            return 2
        actor_id: uuid.UUID = actor[0]

        rows = await _load_blueprint_pool(session)
        if not rows:
            _log({"level": "FATAL", "msg": "no eligible blueprints"})
            return 2
        order = build_round_robin_order(rows)

        seed = order[0].item
        factory = ContentFactoryService(session)
        batch, _ = await factory.create_batch(
            ContentBatchCreateRequest(
                batch_key=batch_key,
                name=f"Subject-quota round-robin MCQ run — {batch_key}",
                description="Resumable generation, subject-quota round-robin blueprint selection",
                subject_id=seed["subject_id"],
                chapter_id=seed["chapter_id"],
                topic_id=seed["topic_id"],
                concept_id=seed["concept_id_uuid"],
                source_type="AI",
                source_tier="ai",
                target_count=target,
            ),
            actor_id=actor_id,
        )
        batch_id: uuid.UUID = batch.id
        await session.commit()

        stats.accepted_start = await _accepted_count(session, batch_id)
        stats.accepted_now = stats.accepted_start
        _log({
            "level": "INFO", "event": "start",
            "batch_id": str(batch_id), "batch_key": batch_key,
            "target": target, "already_accepted": stats.accepted_start,
            "blueprint_pool": len(order), "wall_s": wall_s, "per_call": per_call,
            "selector": "subject_quota_round_robin",
        })

        gen = ContentFactoryGenerationService(session)
        next_checkpoint_at = ((stats.accepted_now // CHECKPOINT_EVERY) + 1) * CHECKPOINT_EVERY

        idx = 0
        while stats.accepted_now < target and time.perf_counter() < deadline:
            entry = order[idx % len(order)]
            bp = entry.item
            idx += 1

            remaining = target - stats.accepted_now
            call_size = min(remaining, per_call)

            stats.passes += 1
            call_start = time.perf_counter()
            try:
                result = await gen.generate_for_batch(
                    batch_id,
                    blueprint_id=uuid.UUID(bp["id"]),
                    target_count=call_size,
                    actor_id=actor_id,
                    job_key=f"{batch_key}-{uuid.uuid4().hex[:10]}",
                    sync_cap=False,
                    bulk_mode=bulk_mode,
                )
                created = int(result.get("created", 0))
                stats.generated += int(result.get("attempted", 0))
                stats.rejected_validation += int(result.get("rejected_validation", 0))
                stats.duplicate += int(result.get("duplicate", 0))
                stats.diversity_rejected += int(result.get("diversity_rejected", 0))
                stats.failed_provider += int(result.get("failed_provider", 0))
                stats.failed_parse += int(result.get("failed_parse", 0))
                stats.cost_usd += float(result.get("cost_usd", 0.0))
                sr = str(result.get("stop_reason", ""))
                stats.stop_reasons[sr] = stats.stop_reasons.get(sr, 0) + 1
                for pa in (result.get("provider_attempts") or []):
                    stats.provider_calls += 1
                    if isinstance(pa, dict) and pa.get("is_fallback"):
                        stats.fallbacks += 1
                stats.accepted_now = await _accepted_count(session, batch_id)
                _log({
                    "level": "INFO", "event": "call",
                    "queue": entry.label,
                    "bp": bp["key"], "concept": bp["concept"], "subject": bp["subject"],
                    "class": bp["class_level"], "family": bp["family"], "difficulty": bp["difficulty"],
                    "target": call_size, "created": created,
                    "rejected_validation": result.get("rejected_validation"),
                    "duplicate": result.get("duplicate"),
                    "stop_reason": sr,
                    "cost_usd": float(result.get("cost_usd", 0.0)),
                    "latency_s": round(time.perf_counter() - call_start, 1),
                    "accepted_now": stats.accepted_now,
                })
            except Exception as exc:  # noqa: BLE001
                msg = f"{type(exc).__name__}: {str(exc)[:400]}"
                stats.stop_reasons[msg[:80]] = stats.stop_reasons.get(msg[:80], 0) + 1
                _log({"level": "ERROR", "event": "call_exception", "queue": entry.label, "bp": bp["key"], "error": msg})
                try:
                    await session.rollback()
                except Exception:  # noqa: BLE001
                    pass
                continue

            if stats.accepted_now >= next_checkpoint_at or stats.accepted_now >= target:
                elapsed = time.perf_counter() - stats.started_at
                _log({
                    "level": "CHECKPOINT",
                    "accepted": stats.accepted_now,
                    "target": target,
                    "delta_since_start": stats.accepted_now - stats.accepted_start,
                    "generated": stats.generated,
                    "rejected_validation": stats.rejected_validation,
                    "duplicate": stats.duplicate,
                    "diversity_rejected": stats.diversity_rejected,
                    "failed_provider": stats.failed_provider,
                    "failed_parse": stats.failed_parse,
                    "provider_calls": stats.provider_calls,
                    "fallbacks": stats.fallbacks,
                    "cost_usd": round(stats.cost_usd, 4),
                    "elapsed_s": round(elapsed, 1),
                })
                next_checkpoint_at = ((stats.accepted_now // CHECKPOINT_EVERY) + 1) * CHECKPOINT_EVERY

        try:
            transitioned = await mark_batch_complete_if_target_reached(
                factory,
                batch_id=batch_id,
                actor_id=actor_id,
                accepted_now=stats.accepted_now,
                target=target,
            )
            if transitioned:
                await session.commit()
                _log({"level": "INFO", "event": "batch_transitioned", "batch_id": str(batch_id), "to_status": "QA"})
        except Exception as exc:  # noqa: BLE001
            # Never let a state-transition failure mask a successful generation run.
            _log({"level": "ERROR", "event": "batch_transition_failed", "batch_id": str(batch_id), "error": f"{type(exc).__name__}: {str(exc)[:300]}"})

    elapsed_total = time.perf_counter() - stats.started_at
    final = {
        "level": "FINAL",
        "batch_key": batch_key,
        "accepted_start": stats.accepted_start,
        "accepted_end": stats.accepted_now,
        "delta": stats.accepted_now - stats.accepted_start,
        "target": target,
        "reached_target": stats.accepted_now >= target,
        "stats": asdict(stats),
        "elapsed_s": round(elapsed_total, 1),
    }
    _log(final)
    print(json.dumps({
        "batch_key": batch_key,
        "accepted_now": stats.accepted_now,
        "target": target,
        "reached": stats.accepted_now >= target,
        "cost_usd": round(stats.cost_usd, 4),
        "elapsed_s": round(elapsed_total, 1),
        "log": LOG_PATH,
    }))
    return 0 if stats.accepted_now >= target else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Run live generation (default: dry-run only).")
    parser.add_argument("--preview", type=int, default=32, help="Dry-run: number of queue labels to print (default 32).")
    parser.add_argument("--target", type=int, default=TARGET, help=f"Total accepted-DRAFT target (default {TARGET}).")
    parser.add_argument("--per-call", type=int, default=PER_CALL, help=f"MCQs requested per generate_for_batch call, <=100 pilot cap (default {PER_CALL}).")
    parser.add_argument("--wall-s", type=float, default=WALL_S, help=f"Wall-clock budget in seconds (default {WALL_S}).")
    parser.add_argument("--batch-key", type=str, default=None, help="Batch key; must be new/distinct to avoid attaching to an existing batch (e.g. prod-5k-*).")
    parser.add_argument(
        "--bulk-mode",
        action="store_true",
        help=(
            "Skip the synchronous NCERT-evidence-sufficiency gate and the claim-level "
            "NCERT grounding check for cheap bulk DRAFT candidate generation. Does NOT "
            "weaken SYLLABUS-GATE-001, structural validation, duplicate detection, or "
            "retrieval-leakage filtering — those remain fully active. No NCERT evidence "
            "is ever fabricated."
        ),
    )
    args = parser.parse_args()

    if not args.live:
        return asyncio.run(dry_run(args.preview))

    if args.per_call > 100:
        print("STOP: --per-call exceeds the factory_max_pilot_generation_count cap (100).", file=sys.stderr)
        return 2
    if not args.batch_key:
        print("STOP: --batch-key is required for --live (must be a new, distinct key).", file=sys.stderr)
        return 2
    if args.batch_key.startswith("prod-5k-"):
        print("STOP: --batch-key must not reuse the prod-5k-* prefix — this would attach to the existing 1,236-item batches.", file=sys.stderr)
        return 2

    print("LIVE RUN requested — this will call the generation provider and write DRAFT rows.", file=sys.stderr)
    if args.bulk_mode:
        print("BULK MODE — NCERT evidence-sufficiency and claim-grounding gates are deferred for this run.", file=sys.stderr)
    return asyncio.run(live_run(
        target=args.target, per_call=args.per_call, wall_s=args.wall_s,
        batch_key=args.batch_key, bulk_mode=args.bulk_mode,
    ))


if __name__ == "__main__":
    sys.exit(main())
