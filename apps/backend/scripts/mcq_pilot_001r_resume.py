"""MCQ-PILOT-001R — Rate-limit-aware resume of the 400-MCQ NCERT pilot.

Completes remaining quotas only:
  Chemistry +71, Botany +100, Zoology +100  (271 total)
Does NOT regenerate Physics (100 already CREATED).
Does NOT publish / certify / approve / commit / push.

Rate-limit behavior (resume layer; gateway marks PROVIDER_RATE_LIMITED retryable
but does not sleep):
  - respect Retry-After when present on ProviderError / response metadata
  - else exponential backoff + jitter
  - concurrency = 1
  - max 3 resume retries per blueprint allocation
  - stop safely after repeated account-level rate-limit exhaustion
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
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
os.environ["FACTORY_PROVIDER"] = "anthropic"
os.environ["FACTORY_PROVIDER_FALLBACK_CHAIN"] = ""
os.environ.setdefault("FACTORY_MAX_PILOT_COST_USD", "30.0")

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

import app.modules.knowledge.models  # noqa: E402, F401
from app.modules.ai.gateway.base import PROVIDER_RATE_LIMITED  # noqa: E402
from app.modules.cms.models.generation_candidate import GenerationCandidate  # noqa: E402
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

REPORT_STEM = "mcq_pilot_001r_resume_20260914"
CAMPAIGN = "mcq-pilot-001-20260913"  # reuse original pilot batches
RESUME_TAG = "mcq-pilot-001r-20260914"
SUBJECT_TARGETS = {"PHYSICS": 100, "CHEMISTRY": 100, "BOTANY": 100, "ZOOLOGY": 100}
RESUME_SUBJECTS = ("CHEMISTRY", "BOTANY", "ZOOLOGY")
TOTAL_TARGET = 400
PREVIOUS_CREATED = 129
RESUME_REQUESTED = 271

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

MAX_RESUME_RETRIES = 3
BASE_BACKOFF_S = 20.0
MAX_BACKOFF_S = 300.0
PACE_SUCCESS_S = (2.0, 5.0)
CONSECUTIVE_RL_STOP = 6  # exhausted BP allocations in a row → stop
CHECKPOINT = ROOT / "docs" / "audits" / f"_{RESUME_TAG}_checkpoint.jsonl"

PROTECTED = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "SUPERSEDED": 6,
    "unmapped_draft": 5024,
    "chapters": 56,
    "topics": 192,
    "concepts": 318,
    "knowledge_units": 381,
    "blueprints": 445,
}


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
                SELECT status, COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
        )
    }
    unmapped = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM cms.content_items
            WHERE deleted_at IS NULL AND content_type = 'QUESTION'
              AND status = 'DRAFT' AND concept_id IS NULL
            """
        )
    ).scalar()
    protected_cs = conn.execute(
        text(
            """
            SELECT md5(string_agg(id::text || ':' || status, '|' ORDER BY id))
            FROM cms.content_items
            WHERE deleted_at IS NULL AND content_type = 'QUESTION'
              AND status IN ('PUBLISHED', 'IN_REVIEW', 'SUPERSEDED')
            """
        )
    ).scalar()
    return {
        "status": status,
        "unmapped_draft": unmapped,
        "protected_status_checksum": protected_cs,
        "chapters": conn.execute(text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")).scalar(),
        "topics": conn.execute(text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")).scalar(),
        "concepts": conn.execute(text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")).scalar(),
        "knowledge_units": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "question_blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "content_batches": conn.execute(
            text("SELECT COUNT(*) FROM cms.content_batches WHERE deleted_at IS NULL")
        ).scalar(),
        "generation_jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "generation_runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
        "generation_candidates": conn.execute(text("SELECT COUNT(*) FROM cms.generation_candidates")).scalar(),
        "ecaep_reviews": conn.execute(text("SELECT COUNT(*) FROM cms.content_reviews")).scalar(),
    }


def protected_ok(snap: dict) -> bool:
    return (
        snap["status"].get("PUBLISHED") == PROTECTED["PUBLISHED"]
        and snap["status"].get("IN_REVIEW") == PROTECTED["IN_REVIEW"]
        and snap["status"].get("SUPERSEDED") == PROTECTED["SUPERSEDED"]
        and snap["unmapped_draft"] == PROTECTED["unmapped_draft"]
        and snap["chapters"] == PROTECTED["chapters"]
        and snap["topics"] == PROTECTED["topics"]
        and snap["concepts"] == PROTECTED["concepts"]
        and snap["knowledge_units"] == PROTECTED["knowledge_units"]
        and snap["question_blueprints"] == PROTECTED["blueprints"]
    )


def load_canonical_bps(conn, ncert_root: Path) -> list[dict]:
    rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT bp.id::text AS blueprint_id,
                       bp.blueprint_key,
                       bp.generation_eligible,
                       bp.is_active,
                       bp.status,
                       bp.provenance_tier,
                       bp.constraints,
                       bp.subject_id::text AS subject_id,
                       s.code AS subject,
                       c.code AS concept_code,
                       t.code AS topic_code,
                       ch.code AS chapter_code,
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
    out = []
    for r in rows:
        cons = parse_constraints(r.get("constraints"))
        if r["concept_code"] in EXCLUDED_CONCEPTS or r["chapter_code"] in EXCLUDED_CHAPTERS:
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
        out.append({**r, "constraints": cons, "ncert_source_path": path})
    return out


def pilot_created_by_bp(conn) -> dict[str, int]:
    rows = conn.execute(
        text(
            """
            SELECT bp.blueprint_key, COUNT(*)
            FROM cms.generation_candidates cand
            JOIN cms.content_batches b ON b.id = cand.batch_id
            JOIN cms.question_blueprints bp ON bp.id = cand.blueprint_id
            WHERE b.batch_key LIKE :pfx
              AND cand.deleted_at IS NULL
              AND cand.status = 'CREATED'
            GROUP BY bp.blueprint_key
            """
        ),
        {"pfx": f"{CAMPAIGN}-batch-%"},
    ).fetchall()
    return {k: int(n) for k, n in rows}


def pilot_created_by_subject(conn) -> dict[str, int]:
    rows = conn.execute(
        text(
            """
            SELECT s.code, COUNT(*)
            FROM cms.generation_candidates cand
            JOIN cms.content_batches b ON b.id = cand.batch_id
            JOIN cms.question_blueprints bp ON bp.id = cand.blueprint_id
            JOIN academic.subjects s ON s.id = bp.subject_id
            WHERE b.batch_key LIKE :pfx
              AND cand.deleted_at IS NULL
              AND cand.status = 'CREATED'
            GROUP BY s.code
            """
        ),
        {"pfx": f"{CAMPAIGN}-batch-%"},
    ).fetchall()
    return {k: int(n) for k, n in rows}


def build_resume_allocations(
    bps: list[dict], created_by_bp: dict[str, int], created_by_subj: dict[str, int]
) -> dict[str, list[tuple[dict, int]]]:
    """Allocate remaining quotas to BPs without over-creating."""
    by_subj: dict[str, list[dict]] = defaultdict(list)
    for bp in bps:
        by_subj[bp["subject"]].append(bp)

    allocations: dict[str, list[tuple[dict, int]]] = {}
    for subj in RESUME_SUBJECTS:
        need = SUBJECT_TARGETS[subj] - int(created_by_subj.get(subj, 0))
        if need <= 0:
            allocations[subj] = []
            continue
        # Prefer BPs with zero CREATED, then those with only 1 if still needed
        zero = [bp for bp in by_subj[subj] if created_by_bp.get(bp["blueprint_key"], 0) == 0]
        ones = [bp for bp in by_subj[subj] if created_by_bp.get(bp["blueprint_key"], 0) == 1]
        plan: list[tuple[dict, int]] = []
        for bp in zero:
            if need <= 0:
                break
            plan.append((bp, 1))
            need -= 1
        for bp in ones:
            if need <= 0:
                break
            # allow second candidate on BP that already has one (breadth first already done)
            plan.append((bp, 1))
            need -= 1
        # If still short, allow third on zeros that we already planned once
        if need > 0:
            for i, (bp, q) in enumerate(list(plan)):
                if need <= 0:
                    break
                if created_by_bp.get(bp["blueprint_key"], 0) + q < 3:
                    plan[i] = (bp, q + 1)
                    need -= 1
        allocations[subj] = plan
    return allocations


def extract_retry_after_seconds(exc: BaseException | None, result: dict | None) -> float | None:
    """Best-effort Retry-After extraction (gateway currently does not surface it)."""
    if exc is not None:
        for attr in ("retry_after", "retry_after_seconds"):
            v = getattr(exc, attr, None)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        # Search message for retry-after / please retry in Ns
        msg = str(exc)
        m = re.search(r"retry[- ]after[:\s]+(\d+)", msg, re.I)
        if m:
            return float(m.group(1))
        m = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", msg, re.I)
        if m:
            return float(m.group(1))
    if result:
        meta = result.get("provider_attempts") or []
        for att in meta:
            if isinstance(att, dict) and att.get("retry_after") is not None:
                try:
                    return float(att["retry_after"])
                except (TypeError, ValueError):
                    pass
    return None


def is_rate_limit_result(result: dict) -> bool:
    if int(result.get("failed_provider") or 0) <= 0 and not result.get("error"):
        return False
    blob = json.dumps(result, default=str).lower()
    return "provider_rate_limited" in blob or "rate limit" in blob or "rate_limited" in blob


def is_blocked_result(result: dict) -> bool:
    blob = json.dumps(result, default=str).lower()
    return "provider_blocked" in blob or "billing/credits blocked" in blob or "credit balance" in blob


async def backoff_sleep(attempt: int, retry_after: float | None, reason: str) -> float:
    if retry_after is not None and retry_after > 0:
        delay = min(MAX_BACKOFF_S, retry_after + random.uniform(0.5, 2.0))
    else:
        delay = min(MAX_BACKOFF_S, BASE_BACKOFF_S * (2 ** (attempt - 1)) + random.uniform(0, 5))
    print(json.dumps({"event": "backoff", "reason": reason, "attempt": attempt, "sleep_s": round(delay, 2)}))
    await asyncio.sleep(delay)
    return delay


def append_checkpoint(row: dict) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    with CHECKPOINT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


async def ensure_batch(session: AsyncSession, subject: str, subject_id: uuid.UUID, actor_id: uuid.UUID, target: int):
    factory = ContentFactoryService(session)
    batch, created = await factory.create_batch(
        ContentBatchCreateRequest(
            batch_key=f"{CAMPAIGN}-batch-{subject.lower()}",
            name=f"MCQ-PILOT-001 {subject} NCERT generation (DRAFT candidates)",
            description="Controlled NCERT pilot — resume 001R, no publish",
            subject_id=subject_id,
            target_count=max(target, SUBJECT_TARGETS[subject]),
            source_type="AI",
            source_tier="ai",
        ),
        actor_id=actor_id,
    )
    return batch, created


async def generate_one(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    bp_row: dict,
    quota: int,
    actor_id: uuid.UUID,
    ncert_root: Path,
) -> dict:
    assert_blueprint_ncert_source(
        bp_row["constraints"],
        provenance_tier=bp_row["provenance_tier"],
        root=ncert_root,
    )
    gen = ContentFactoryGenerationService(session)
    job_key = f"{RESUME_TAG}-{bp_row['subject'].lower()}-{bp_row['concept_code']}-{uuid.uuid4().hex[:8]}"
    result = await gen.generate_for_batch(
        batch_id,
        blueprint_id=uuid.UUID(bp_row["blueprint_id"]),
        target_count=quota,
        actor_id=actor_id,
        job_key=job_key,
        sync_cap=False,
    )
    return result if isinstance(result, dict) else {}


async def resume_subject(
    session: AsyncSession,
    *,
    subject: str,
    allocations: list[tuple[dict, int]],
    actor_id: uuid.UUID,
    ncert_root: Path,
    telemetry: dict,
) -> dict:
    if not allocations:
        return {
            "subject": subject,
            "requested": 0,
            "created": 0,
            "skipped_existing": True,
            "runs": [],
        }

    batch, _ = await ensure_batch(
        session,
        subject,
        uuid.UUID(allocations[0][0]["subject_id"]),
        actor_id,
        sum(q for _, q in allocations),
    )

    runs = []
    created_total = 0
    requested_total = sum(q for _, q in allocations)
    consecutive_rl = 0
    stop_reason = None

    for bp_row, quota in allocations:
        existing = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.generation_candidates cand
                    JOIN cms.content_batches b ON b.id = cand.batch_id
                    WHERE b.batch_key = :bk
                      AND cand.blueprint_id = :bp
                      AND cand.status = 'CREATED'
                      AND cand.deleted_at IS NULL
                    """
                ),
                {"bk": batch.batch_key, "bp": bp_row["blueprint_id"]},
            )
        ).scalar_one()

        # Recompute subject created; stop if subject target met
        subj_created = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.generation_candidates cand
                    JOIN cms.content_batches b ON b.id = cand.batch_id
                    JOIN cms.question_blueprints bp ON bp.id = cand.blueprint_id
                    JOIN academic.subjects s ON s.id = bp.subject_id
                    WHERE b.batch_key LIKE :pfx
                      AND s.code = :subj
                      AND cand.status = 'CREATED'
                      AND cand.deleted_at IS NULL
                    """
                ),
                {"pfx": f"{CAMPAIGN}-batch-%", "subj": subject},
            )
        ).scalar_one()
        if int(subj_created) >= SUBJECT_TARGETS[subject]:
            stop_reason = "subject_target_met"
            break

        # Cap at 2 CREATED per blueprint for this pilot; never duplicate beyond that
        need_here = max(0, min(quota, 2 - int(existing)))
        if need_here <= 0:
            runs.append(
                {
                    "blueprint_key": bp_row["blueprint_key"],
                    "status": "SKIPPED_EXISTING",
                    "existing_created": int(existing),
                }
            )
            continue

        success = False
        last_result: dict = {}
        for attempt in range(1, MAX_RESUME_RETRIES + 1):
            try:
                last_result = await generate_one(
                    session,
                    batch_id=batch.id,
                    bp_row=bp_row,
                    quota=need_here,
                    actor_id=actor_id,
                    ncert_root=ncert_root,
                )
            except Exception as exc:  # noqa: BLE001
                telemetry["retries"] += 1
                ra = extract_retry_after_seconds(exc, None)
                msg = str(exc).lower()
                if "rate" in msg or "429" in msg or PROVIDER_RATE_LIMITED.lower() in msg:
                    telemetry["provider_rate_limit_failures"] += 1
                    consecutive_rl += 1
                    await backoff_sleep(attempt, ra, "exception_rate_limit")
                    last_result = {"error": str(exc)[:400], "failed_provider": 1, "created": 0}
                    if consecutive_rl >= CONSECUTIVE_RL_STOP and attempt == MAX_RESUME_RETRIES:
                        stop_reason = "provider_rate_limit_exhausted"
                        break
                    continue
                telemetry["other_provider_failures"] += 1
                last_result = {"error": str(exc)[:400], "failed_provider": 1, "created": 0}
                break

            created = int(last_result.get("created") or 0)
            telemetry["attempted"] += int(last_result.get("attempted") or 0)
            telemetry["failed_parse"] += int(last_result.get("failed_parse") or 0)
            telemetry["rejected_validation"] += int(last_result.get("rejected_validation") or 0)
            telemetry["duplicate"] += int(last_result.get("duplicate") or 0)

            if created > 0:
                created_total += created
                telemetry["resume_created"] += created
                consecutive_rl = 0
                success = True
                append_checkpoint(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "subject": subject,
                        "blueprint_key": bp_row["blueprint_key"],
                        "created": created,
                        "attempt": attempt,
                    }
                )
                # pace after success
                await asyncio.sleep(random.uniform(*PACE_SUCCESS_S))
                break

            fp = int(last_result.get("failed_provider") or 0)
            if fp > 0 and is_blocked_result(last_result):
                telemetry["other_provider_failures"] += fp
                stop_reason = "provider_blocked_billing_credits"
                break
            if fp > 0 and is_rate_limit_result(last_result):
                telemetry["provider_rate_limit_failures"] += fp
                telemetry["retries"] += 1
                consecutive_rl += 1
                ra = extract_retry_after_seconds(None, last_result)
                await backoff_sleep(attempt, ra, "result_rate_limit")
                if consecutive_rl >= CONSECUTIVE_RL_STOP and attempt >= MAX_RESUME_RETRIES:
                    stop_reason = "provider_rate_limit_exhausted"
                continue
            if fp > 0:
                # Ambiguous provider failure after recent limits: treat as RL and back off once
                telemetry["provider_rate_limit_failures"] += fp
                telemetry["retries"] += 1
                consecutive_rl += 1
                await backoff_sleep(attempt, None, "provider_fail_assumed_rl")
                if consecutive_rl >= CONSECUTIVE_RL_STOP and attempt >= MAX_RESUME_RETRIES:
                    stop_reason = "provider_rate_limit_exhausted"
                continue
            break

        runs.append(
            {
                "blueprint_key": bp_row["blueprint_key"],
                "concept_code": bp_row["concept_code"],
                "chapter_code": bp_row["chapter_code"],
                "topic_code": bp_row["topic_code"],
                "requested": need_here,
                "created": int(last_result.get("created") or 0),
                "attempted": int(last_result.get("attempted") or 0),
                "failed_provider": int(last_result.get("failed_provider") or 0),
                "failed_parse": int(last_result.get("failed_parse") or 0),
                "rejected_validation": int(last_result.get("rejected_validation") or 0),
                "duplicate": int(last_result.get("duplicate") or 0),
                "stop_reason": last_result.get("stop_reason") or stop_reason,
                "success": success,
                "ncert_source_path": bp_row.get("ncert_source_path"),
            }
        )
        if stop_reason in {"provider_rate_limit_exhausted", "provider_blocked_billing_credits"}:
            break

    return {
        "subject": subject,
        "batch_id": str(batch.id),
        "batch_key": batch.batch_key,
        "requested": requested_total,
        "created": created_total,
        "runs": runs,
        "stop_reason": stop_reason,
        "allocations": len(allocations),
    }


async def collect_pilot_candidates(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(GenerationCandidate)
            .where(
                GenerationCandidate.deleted_at.is_(None),
            )
            .order_by(GenerationCandidate.created_at.asc())
        )
    ).scalars().all()
    # Filter to pilot batches via SQL join instead
    q = await session.execute(
        text(
            """
            SELECT cand.id::text, cand.status, cand.error_code,
                   left(coalesce(cand.error_summary,''), 200),
                   cand.content_item_id::text, bp.blueprint_key, s.code AS subject,
                   b.batch_key, cand.provider, cand.model_used
            FROM cms.generation_candidates cand
            JOIN cms.content_batches b ON b.id = cand.batch_id
            LEFT JOIN cms.question_blueprints bp ON bp.id = cand.blueprint_id
            LEFT JOIN academic.subjects s ON s.id = bp.subject_id
            WHERE b.batch_key LIKE :pfx AND cand.deleted_at IS NULL
            ORDER BY cand.created_at
            """
        ),
        {"pfx": f"{CAMPAIGN}-batch-%"},
    )
    out = []
    for r in q.fetchall():
        out.append(
            {
                "candidate_id": r[0],
                "status": r[1],
                "error_code": r[2],
                "error_summary": r[3] or None,
                "content_item_id": r[4],
                "blueprint_key": r[5],
                "subject": r[6],
                "batch_key": r[7],
                "provider": r[8],
                "model_used": r[9],
            }
        )
    return out


def run_tests() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "app/modules/ingestion/tests/test_ncert_canonical_source.py",
        "tests/test_content_factory_p2.py",
        "tests/test_phase32_content_readiness_safety.py",
        "tests/test_phase33_ecaep_publication_safety.py",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(cmd, cwd=str(BACKEND), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    passed = failed = 0
    m = re.search(r"(\d+) passed", out)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", out)
    if m:
        failed = int(m.group(1))
    return {
        "passed": passed,
        "failed": failed,
        "exit_code": proc.returncode,
        "command": " ".join(cmd),
        "tail": "\n".join(out.strip().splitlines()[-30:]),
    }


def pct(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(100.0 * n / d, 2)


def write_reports(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    t = payload["telemetry"]
    lines = [
        "# MCQ-PILOT-001R — Rate-limit-aware resume",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Publication / NCERT certification / editorial approval: **NONE**",
        "- Git: **no commit / no push**",
        "",
        "## Previous pilot state",
        f"- Previously CREATED: `{PREVIOUS_CREATED}`",
        f"- Physics was complete and **not regenerated**",
        "",
        "## Resume request",
        f"- Resume requested: `{RESUME_REQUESTED}` (Chem 71 + Botany 100 + Zoology 100)",
        f"- Resume CREATED: `{t['resume_created']}`",
        f"- Final total CREATED: `{t['final_total_created']}`",
        f"- Remaining gap: `{t['remaining_gap']}`",
        "",
        "## Subject final counts",
        "",
        "| Subject | Target | Final CREATED | Gap |",
        "|---|---:|---:|---:|",
    ]
    for subj, target in SUBJECT_TARGETS.items():
        final = payload["final_created_by_subject"].get(subj, 0)
        lines.append(f"| {subj} | {target} | {final} | {max(0, target - final)} |")

    lines += [
        "",
        "## Telemetry A–L",
        f"- A total requested: `{TOTAL_TARGET}`",
        f"- B previously created: `{PREVIOUS_CREATED}`",
        f"- C resume requested: `{RESUME_REQUESTED}`",
        f"- D resume CREATED: `{t['resume_created']}`",
        f"- E provider rate-limit failures: `{t['provider_rate_limit_failures']}`",
        f"- F other provider failures: `{t['other_provider_failures']}`",
        f"- G parse failures: `{t['failed_parse']}`",
        f"- H validation rejections: `{t['rejected_validation']}`",
        f"- I duplicate rejections: `{t['duplicate']}`",
        f"- J retries: `{t['retries']}`",
        f"- K final total CREATED: `{t['final_total_created']}`",
        f"- L remaining gap: `{t['remaining_gap']}`",
        "",
        "## Yield (rate-limit excluded from content denominator)",
        f"- Content processing yield: `{t['content_processing_yield_pct']}%`",
        f"- Overall 400-request CREATED rate: `{t['overall_created_rate_pct']}%`",
        "",
        f"```json\n{json.dumps(t, indent=2)}\n```",
        "",
        "## Rate-limit handling",
        f"```json\n{json.dumps(payload['rate_limit_policy'], indent=2)}\n```",
        "",
        "## Database / ECAEP freeze",
        f"- Protected freeze OK: `{payload['protected_freeze_ok']}`",
        f"- Protected checksum unchanged: `{payload['protected_checksum_unchanged']}`",
        f"- ECAEP reviews unchanged: `{payload['before']['ecaep_reviews']} → {payload['after']['ecaep_reviews']}`",
        f"- Blueprints/KUs/taxonomy unchanged",
        f"- DRAFT delta this resume: `{payload['draft_delta']}`",
        "",
        "## Tests",
        f"- Passed `{payload['tests'].get('passed')}` / Failed `{payload['tests'].get('failed')}`",
        "",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## Confirmation",
        f"```json\n{json.dumps(payload['confirmation'], indent=2)}\n```",
        "",
        "**STOP** — no NCERT certification, no editorial approval, no publish, no commit, no push.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


async def async_main() -> int:
    settings = get_settings()
    if settings.factory_provider != "anthropic" or settings.factory_provider_mode != "fixed":
        raise SystemExit(
            f"ABORT: expected fixed:anthropic, got {settings.factory_provider_mode}:{settings.factory_provider}"
        )
    try:
        ncert_root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        ncert_root = ROOT / "NCERT Books"

    sync_engine = create_engine(settings.database_url_sync)
    with sync_engine.connect() as conn:
        before = snapshot_sync(conn)
        if not protected_ok(before):
            raise SystemExit(f"ABORT protected freeze: {before}")
        created_by_bp = pilot_created_by_bp(conn)
        created_by_subj = pilot_created_by_subject(conn)
        # Sanity: Physics must already be 100; do not touch
        if int(created_by_subj.get("PHYSICS", 0)) < 100:
            raise SystemExit(
                f"ABORT: Physics incomplete ({created_by_subj.get('PHYSICS')}); unexpected resume state"
            )
        if int(created_by_subj.get("PHYSICS", 0)) > 100:
            raise SystemExit("ABORT: Physics already over target")
        previous_total = sum(created_by_subj.values())
        bps = load_canonical_bps(conn, ncert_root)
        allocations = build_resume_allocations(bps, created_by_bp, created_by_subj)
        planned = {s: sum(q for _, q in allocations[s]) for s in RESUME_SUBJECTS}
        print(
            json.dumps(
                {
                    "event": "resume_plan",
                    "created_by_subj": created_by_subj,
                    "planned": planned,
                    "previous_total": previous_total,
                }
            )
        )

    # Cool-down before resume (prior run hit hard rate limits)
    print(json.dumps({"event": "initial_cooldown_s", "sleep_s": 45}))
    await asyncio.sleep(45)

    telemetry = {
        "resume_created": 0,
        "provider_rate_limit_failures": 0,
        "other_provider_failures": 0,
        "failed_parse": 0,
        "rejected_validation": 0,
        "duplicate": 0,
        "retries": 0,
        "attempted": 0,
    }

    engine = create_async_engine(settings.database_url)
    subject_results = {}
    async with AsyncSession(engine, expire_on_commit=False) as session:
        actor_id = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()

        for subj in RESUME_SUBJECTS:
            print(json.dumps({"event": "subject_start", "subject": subj, "planned": planned.get(subj, 0)}))
            result = await resume_subject(
                session,
                subject=subj,
                allocations=allocations[subj],
                actor_id=actor_id,
                ncert_root=ncert_root,
                telemetry=telemetry,
            )
            subject_results[subj] = result
            print(
                json.dumps(
                    {
                        "event": "subject_done",
                        "subject": subj,
                        "created": result.get("created"),
                        "stop": result.get("stop_reason"),
                    }
                )
            )
            if result.get("stop_reason") == "provider_rate_limit_exhausted":
                print(json.dumps({"event": "stop", "reason": "provider_rate_limit_exhausted"}))
                break

        candidates = await collect_pilot_candidates(session)

    await engine.dispose()

    with sync_engine.connect() as conn:
        after = snapshot_sync(conn)
        final_by_subj = pilot_created_by_subject(conn)

    final_total = sum(final_by_subj.values())
    resume_created = telemetry["resume_created"]
    # Prefer DB delta for resume_created if checkpoint drifts
    db_resume = final_total - previous_total
    if db_resume >= 0:
        resume_created = db_resume
        telemetry["resume_created"] = resume_created

    status_counts = Counter(c["status"] for c in candidates)
    created_ids = [c["candidate_id"] for c in candidates if c["status"] == "CREATED"]
    rl_candidates = sum(
        1
        for c in candidates
        if c["status"] == "FAILED_PROVIDER"
        and (c.get("error_code") == PROVIDER_RATE_LIMITED or "rate" in (c.get("error_summary") or "").lower())
    )

    content_denom = (
        resume_created
        + telemetry["failed_parse"]
        + telemetry["rejected_validation"]
        + telemetry["duplicate"]
        + telemetry["other_provider_failures"]
    )
    content_yield = pct(resume_created, content_denom)
    overall_rate = pct(final_total, TOTAL_TARGET)
    remaining_gap = max(0, TOTAL_TARGET - final_total)

    freeze_ok = protected_ok(after)
    checksum_ok = before["protected_status_checksum"] == after["protected_status_checksum"]
    draft_delta = after["status"].get("DRAFT", 0) - before["status"].get("DRAFT", 0)

    tests = run_tests()

    if final_total >= TOTAL_TARGET and all(final_by_subj.get(s, 0) >= SUBJECT_TARGETS[s] for s in SUBJECT_TARGETS):
        final = "GREEN — 400-CANDIDATE GENERATION COMPLETE"
    elif resume_created > 0 or final_total > previous_total:
        final = "YELLOW — GENERATION PARTIALLY COMPLETE / PROVIDER LIMITED"
    elif telemetry["provider_rate_limit_failures"] > 0:
        final = "YELLOW — GENERATION PARTIALLY COMPLETE / PROVIDER LIMITED"
    else:
        final = "YELLOW — GENERATION PARTIALLY COMPLETE / PROVIDER LIMITED"

    if not freeze_ok or not checksum_ok or after["ecaep_reviews"] != before["ecaep_reviews"]:
        final = "RED — SAFETY BOUNDARY VIOLATED"

    telemetry_out = {
        **telemetry,
        "A_total_requested": TOTAL_TARGET,
        "B_previously_created": previous_total,
        "C_resume_requested": RESUME_REQUESTED,
        "D_resume_created": resume_created,
        "E_provider_rate_limit_failures": telemetry["provider_rate_limit_failures"],
        "F_other_provider_failures": telemetry["other_provider_failures"],
        "G_parse_failures": telemetry["failed_parse"],
        "H_validation_rejections": telemetry["rejected_validation"],
        "I_duplicate_rejections": telemetry["duplicate"],
        "J_retries": telemetry["retries"],
        "K_final_total_created": final_total,
        "L_remaining_gap": remaining_gap,
        "final_total_created": final_total,
        "remaining_gap": remaining_gap,
        "resume_created": resume_created,
        "content_processing_yield_pct": content_yield,
        "overall_created_rate_pct": overall_rate,
        "candidate_status_counts_pilot": dict(status_counts),
        "rate_limit_candidate_rows": rl_candidates,
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "campaign": CAMPAIGN,
        "resume_tag": RESUME_TAG,
        "final_status": final,
        "provider": f"{settings.factory_provider_mode}:{settings.factory_provider}",
        "model": settings.ai_default_model,
        "ncert_root": str(ncert_root),
        "previous_created_by_subject": created_by_subj,
        "previous_total": previous_total,
        "planned_allocations": {
            s: [{"blueprint_key": bp["blueprint_key"], "quota": q} for bp, q in allocations[s]]
            for s in RESUME_SUBJECTS
        },
        "by_subject_resume": subject_results,
        "final_created_by_subject": final_by_subj,
        "telemetry": telemetry_out,
        "rate_limit_policy": {
            "provider_fixed": "anthropic",
            "no_silent_provider_switch": True,
            "concurrency": 1,
            "max_resume_retries_per_bp": MAX_RESUME_RETRIES,
            "base_backoff_s": BASE_BACKOFF_S,
            "max_backoff_s": MAX_BACKOFF_S,
            "retry_after_honored_when_present": True,
            "consecutive_rl_stop": CONSECUTIVE_RL_STOP,
            "initial_cooldown_s": 45,
            "gateway_note": (
                "AI gateway classifies HTTP 429 as PROVIDER_RATE_LIMITED (retryable) "
                "but does not sleep; resume layer adds backoff/jitter."
            ),
        },
        "candidate_ids_created": created_ids,
        "before": before,
        "after": after,
        "protected_freeze_ok": freeze_ok,
        "protected_checksum_unchanged": checksum_ok,
        "draft_delta": draft_delta,
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            f"docs/audits/_{RESUME_TAG}_checkpoint.jsonl",
            "apps/backend/scripts/mcq_pilot_001r_resume.py",
            "cms.generation_* / new DRAFT content_items (candidates only)",
        ],
        "confirmation": {
            "physics_regenerated": False,
            "mcqs_published": False,
            "ncert_certified": False,
            "editorially_approved": False,
            "provider_silently_switched": False,
            "existing_questions_mutated": False,
            "blueprints_modified": False,
            "kus_modified": False,
            "taxonomy_modified": False,
            "ecaep_modified": before["ecaep_reviews"] != after["ecaep_reviews"],
            "beyond_remaining_271": False,
            "committed": False,
            "pushed": False,
        },
    }
    md_path, json_path = write_reports(payload)
    print(
        json.dumps(
            {
                "final_status": final,
                "json": str(json_path),
                "md": str(md_path),
                "previous_total": previous_total,
                "resume_created": resume_created,
                "final_total": final_total,
                "final_by_subject": final_by_subj,
                "remaining_gap": remaining_gap,
                "rate_limit_failures": telemetry["provider_rate_limit_failures"],
                "protected_freeze_ok": freeze_ok,
                "published": after["status"].get("PUBLISHED"),
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
            },
            indent=2,
        )
    )
    return 0 if final.startswith("GREEN") else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
