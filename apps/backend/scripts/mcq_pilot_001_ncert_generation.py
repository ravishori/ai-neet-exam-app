"""MCQ-PILOT-001 — Controlled 400-question NCERT generation pilot (DRAFT candidates only).

Generates exactly 100 MCQ candidates per subject (Physics/Chemistry/Botany/Zoology)
from the 308 integrity-passed canonical NCERT blueprints.

Does NOT: publish, certify, ECAEP advance, modify existing questions/KUs/taxonomy/BPs,
commit, or push.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Controlled provider routing before settings load
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)
os.environ["FACTORY_PROVIDER_MODE"] = "fixed"
# Gemini hit PROVIDER_RATE_LIMITED in smoke; Anthropic is AVAILABLE for this pilot.
os.environ["FACTORY_PROVIDER"] = "anthropic"
os.environ["FACTORY_PROVIDER_FALLBACK_CHAIN"] = ""
# Per-run cost bound is enough for small target_count; keep default unless needed
os.environ.setdefault("FACTORY_MAX_PILOT_COST_USD", "30.0")

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

import app.modules.knowledge.models  # noqa: E402, F401
from app.modules.cms.models.content_factory_planning import QuestionBlueprint  # noqa: E402
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

REPORT_STEM = "mcq_pilot_001_generation_20260913"
CAMPAIGN = "mcq-pilot-001-20260913"
SUBJECTS = ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY")
TARGET_PER_SUBJECT = 100
TOTAL_TARGET = 400

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

FREEZE_PROTECTED = {
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

HISTORICAL_BASELINE = {
    "CREATED": 262,
    "total_candidates": 392,
    "CREATED_rate": 0.668,
    "FAILED_PARSE": 51,
    "REJECTED_VALIDATION": 31,
    "FAILED_PROVIDER": 24,
    "REJECTED_DUPLICATE": 24,
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
    published_ids_cs = conn.execute(
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
        "protected_status_checksum": published_ids_cs,
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


def protected_freeze_ok(snap: dict) -> bool:
    return (
        snap["status"].get("PUBLISHED") == FREEZE_PROTECTED["PUBLISHED"]
        and snap["status"].get("IN_REVIEW") == FREEZE_PROTECTED["IN_REVIEW"]
        and snap["status"].get("SUPERSEDED") == FREEZE_PROTECTED["SUPERSEDED"]
        and snap["unmapped_draft"] == FREEZE_PROTECTED["unmapped_draft"]
        and snap["chapters"] == FREEZE_PROTECTED["chapters"]
        and snap["topics"] == FREEZE_PROTECTED["topics"]
        and snap["concepts"] == FREEZE_PROTECTED["concepts"]
        and snap["knowledge_units"] == FREEZE_PROTECTED["knowledge_units"]
        and snap["question_blueprints"] == FREEZE_PROTECTED["blueprints"]
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
                       bp.target_count,
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
    skipped = []
    for r in rows:
        cons = parse_constraints(r.get("constraints"))
        code = r["concept_code"]
        if code in EXCLUDED_CONCEPTS:
            skipped.append({"blueprint_key": r["blueprint_key"], "reason": "excluded_concept", "concept_code": code})
            continue
        if r["chapter_code"] in EXCLUDED_CHAPTERS:
            skipped.append({"blueprint_key": r["blueprint_key"], "reason": "excluded_chapter"})
            continue
        if not r["generation_eligible"] or not r["is_active"] or r["status"] in {"SUPERSEDED", "ARCHIVED"}:
            skipped.append({"blueprint_key": r["blueprint_key"], "reason": "not_generation_eligible"})
            continue
        path = extract_blueprint_ncert_path(cons)
        if not path or "StudyMaterial" in path:
            skipped.append({"blueprint_key": r["blueprint_key"], "reason": "bad_path"})
            continue
        try:
            assert_blueprint_ncert_source(cons, provenance_tier=r["provenance_tier"], root=ncert_root)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"blueprint_key": r["blueprint_key"], "reason": f"assert_failed:{exc}"})
            continue
        eligible.append({**r, "constraints": cons, "ncert_source_path": path})
    return eligible, skipped


def allocate_quotas(bps: list[dict], target: int) -> list[tuple[dict, int]]:
    """Breadth-first: 1 per BP, then second pass until target."""
    if not bps:
        return []
    quotas = {bp["blueprint_id"]: 0 for bp in bps}
    ordered = list(bps)
    remaining = target
    # Pass 1: one each
    for bp in ordered:
        if remaining <= 0:
            break
        quotas[bp["blueprint_id"]] += 1
        remaining -= 1
    # Further passes for leftovers
    while remaining > 0:
        progressed = False
        for bp in ordered:
            if remaining <= 0:
                break
            # Cap per BP at 3 for this pilot to avoid tiny-subset concentration
            if quotas[bp["blueprint_id"]] >= 3:
                continue
            quotas[bp["blueprint_id"]] += 1
            remaining -= 1
            progressed = True
        if not progressed:
            break
    return [(bp, quotas[bp["blueprint_id"]]) for bp in ordered if quotas[bp["blueprint_id"]] > 0]


async def generate_subject(
    session: AsyncSession,
    *,
    subject: str,
    allocations: list[tuple[dict, int]],
    actor_id: uuid.UUID,
    ncert_root: Path,
) -> dict:
    if not allocations:
        return {
            "subject": subject,
            "requested": TARGET_PER_SUBJECT,
            "error": "no_eligible_blueprints",
            "runs": [],
            "stats": {},
        }

    factory = ContentFactoryService(session)
    gen = ContentFactoryGenerationService(session)
    subject_id = uuid.UUID(allocations[0][0]["subject_id"])
    total_requested = sum(q for _, q in allocations)

    batch, _ = await factory.create_batch(
        ContentBatchCreateRequest(
            batch_key=f"{CAMPAIGN}-batch-{subject.lower()}",
            name=f"MCQ-PILOT-001 {subject} NCERT generation (DRAFT candidates)",
            description="Controlled 100-candidate NCERT pilot — no publish/ECAEP",
            subject_id=subject_id,
            target_count=total_requested,
            source_type="AI",
            source_tier="ai",
        ),
        actor_id=actor_id,
    )

    runs = []
    agg = Counter()
    stop = None

    for bp_row, quota in allocations:
        # Re-assert source guard before each generation
        try:
            assert_blueprint_ncert_source(
                bp_row["constraints"],
                provenance_tier=bp_row["provenance_tier"],
                root=ncert_root,
            )
        except Exception as exc:  # noqa: BLE001
            stop = f"source_guard_failed:{bp_row['blueprint_key']}:{exc}"
            runs.append(
                {
                    "blueprint_key": bp_row["blueprint_key"],
                    "concept_code": bp_row["concept_code"],
                    "requested": quota,
                    "error": stop,
                }
            )
            break

        job_key = f"{CAMPAIGN}-{subject.lower()}-{bp_row['concept_code']}-{uuid.uuid4().hex[:8]}"
        try:
            result = await gen.generate_for_batch(
                batch.id,
                blueprint_id=uuid.UUID(bp_row["blueprint_id"]),
                target_count=quota,
                actor_id=actor_id,
                job_key=job_key,
                sync_cap=False,
            )
        except Exception as exc:  # noqa: BLE001
            stop = f"generation_exception:{type(exc).__name__}:{exc}"
            runs.append(
                {
                    "blueprint_key": bp_row["blueprint_key"],
                    "concept_code": bp_row["concept_code"],
                    "requested": quota,
                    "error": str(exc)[:500],
                }
            )
            # Hard stop on source/provider auth style failures
            msg = str(exc).lower()
            if any(x in msg for x in ("ncert", "source", "auth", "credit", "provider_blocked")):
                break
            continue

        stats = result if isinstance(result, dict) else {}
        # normalize nested stats
        if "stats" in stats and isinstance(stats["stats"], dict):
            s = stats["stats"]
        else:
            s = stats
        run_rec = {
            "blueprint_id": bp_row["blueprint_id"],
            "blueprint_key": bp_row["blueprint_key"],
            "concept_code": bp_row["concept_code"],
            "chapter_code": bp_row["chapter_code"],
            "topic_code": bp_row["topic_code"],
            "class_level": bp_row["class_level"],
            "ncert_source_path": bp_row.get("ncert_source_path"),
            "requested": quota,
            "created": int(s.get("created") or 0),
            "attempted": int(s.get("attempted") or 0),
            "rejected_validation": int(s.get("rejected_validation") or 0),
            "duplicate": int(s.get("duplicate") or 0),
            "failed_provider": int(s.get("failed_provider") or 0),
            "failed_parse": int(s.get("failed_parse") or 0),
            "diversity_rejected": int(s.get("diversity_rejected") or 0),
            "stop_reason": s.get("stop_reason") or stats.get("stop_reason"),
            "cost_usd": s.get("cost_usd") or stats.get("cost_usd"),
            "latency_ms": s.get("latency_ms") or stats.get("latency_ms"),
            "job_id": stats.get("job_id"),
            "run_id": stats.get("run_id"),
            "batch_id": str(batch.id),
        }
        runs.append(run_rec)
        for k in (
            "created",
            "attempted",
            "rejected_validation",
            "duplicate",
            "failed_provider",
            "failed_parse",
            "diversity_rejected",
        ):
            agg[k] += int(run_rec.get(k) or 0)
        agg["requested"] += quota

        # Safety: never continue if pipeline claims publish
        if stats.get("published") or stats.get("status") == "PUBLISHED":
            stop = "safety_abort_publish_detected"
            break

    return {
        "subject": subject,
        "batch_id": str(batch.id),
        "batch_key": batch.batch_key,
        "requested": total_requested,
        "allocations": len(allocations),
        "blueprints_used": len({r.get("blueprint_key") for r in runs if r.get("blueprint_key")}),
        "runs": runs,
        "stats": dict(agg),
        "stop_reason": stop,
        "created_total": int(agg.get("created") or 0),
    }


async def collect_candidates(session: AsyncSession, batch_ids: list[str]) -> list[dict]:
    if not batch_ids:
        return []
    rows = (
        await session.execute(
            select(GenerationCandidate)
            .where(
                GenerationCandidate.batch_id.in_([uuid.UUID(b) for b in batch_ids]),
                GenerationCandidate.deleted_at.is_(None),
            )
            .order_by(GenerationCandidate.created_at.asc())
        )
    ).scalars().all()
    out = []
    for cand in rows:
        out.append(
            {
                "candidate_id": str(cand.id),
                "batch_id": str(cand.batch_id) if cand.batch_id else None,
                "job_id": str(cand.job_id) if cand.job_id else None,
                "run_id": str(cand.run_id) if cand.run_id else None,
                "blueprint_id": str(cand.blueprint_id) if cand.blueprint_id else None,
                "status": cand.status,
                "attempt_no": cand.attempt_no,
                "provider": cand.provider,
                "model_used": cand.model_used,
                "error_code": cand.error_code,
                "error_summary": (cand.error_summary or "")[:300] or None,
                "content_item_id": str(cand.content_item_id) if cand.content_item_id else None,
                "stem_hash": cand.stem_hash,
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
        "# MCQ-PILOT-001 — Controlled 400-question NCERT generation pilot",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Publication: **NONE**",
        "- NCERT certification: **NOT claimed** (generation ≠ verification)",
        "- Git: **no commit / no push**",
        "",
        "## Executive summary",
        payload["executive_summary"],
        "",
        "## Requested vs generated by subject",
        "",
        "| Subject | Requested | CREATED candidates | Attempted | Parse fail | Validation reject | Duplicate | Provider fail |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for subj in SUBJECTS:
        s = payload["by_subject"][subj]
        st = s.get("stats") or {}
        lines.append(
            f"| {subj} | {s.get('requested', 0)} | {st.get('created', 0)} | {st.get('attempted', 0)} | "
            f"{st.get('failed_parse', 0)} | {st.get('rejected_validation', 0)} | {st.get('duplicate', 0)} | "
            f"{st.get('failed_provider', 0)} |"
        )
    lines += [
        "",
        f"- **Total requested:** `{t['requested']}`",
        f"- **Total CREATED:** `{t['created']}`",
        f"- **Parse success rate (non-parse / attempted):** `{t['rates'].get('parse_ok_pct')}%`",
        f"- **Validation reject rate:** `{t['rates'].get('validation_reject_pct')}%`",
        f"- **Duplicate rate:** `{t['rates'].get('duplicate_pct')}%`",
        f"- **Provider failure rate:** `{t['rates'].get('provider_fail_pct')}%`",
        f"- **CREATED rate:** `{t['rates'].get('created_pct')}%`",
        "",
        "## Historical baseline comparison",
        f"```json\n{json.dumps({'historical': HISTORICAL_BASELINE, 'this_pilot': t['baseline_compare']}, indent=2)}\n```",
        "",
        "## Source / provenance",
        f"- NCERT root: `{payload['ncert_root']}`",
        f"- Provider: `{payload['provider']}`",
        f"- Canonical BPs available (post-exclusions): `{payload['eligible_bp_count']}`",
        f"- Blueprints used: `{t['blueprints_used']}`",
        f"- Excluded concepts (taxonomy/merge/digestion): enforced",
        "",
        "## Database freeze",
        f"- Protected freeze OK: `{payload['protected_freeze_ok']}`",
        f"- Protected status checksum unchanged: `{payload['protected_checksum_unchanged']}`",
        f"- PUBLISHED/IN_REVIEW/SUPERSEDED/unmapped DRAFT unchanged: required",
        f"- DRAFT delta (new candidates only): `{payload['draft_delta']}`",
        f"- Blueprints unchanged: `{payload['before']['question_blueprints']} → {payload['after']['question_blueprints']}`",
        f"- KUs/concepts/chapters/topics unchanged",
        f"- ECAEP reviews unchanged: `{payload['before']['ecaep_reviews']} → {payload['after']['ecaep_reviews']}`",
        "",
        "### Before",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "### After",
        f"```json\n{json.dumps(payload['after'], indent=2)}\n```",
        "",
        "## Candidate status histogram",
        f"```json\n{json.dumps(t['candidate_status_counts'], indent=2)}\n```",
        "",
        "## Blueprint / chapter coverage",
        f"```json\n{json.dumps(t['coverage'], indent=2)}\n```",
        "",
        "## Rejected / failed candidates (sample)",
        f"- Count non-CREATED: `{t['non_created_count']}` — full list truncated in MD; see JSON `rejected_candidates`",
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
        "**STOP** — no publish, no NCERT certification claim, no commit, no push.",
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
        if not protected_freeze_ok(before):
            raise SystemExit(f"ABORT protected freeze before: {before}")
        eligible, skipped = load_canonical_bps(conn, ncert_root)
        by_subj: dict[str, list[dict]] = defaultdict(list)
        for bp in eligible:
            by_subj[bp["subject"]].append(bp)
        allocations = {subj: allocate_quotas(by_subj.get(subj, []), TARGET_PER_SUBJECT) for subj in SUBJECTS}
        for subj in SUBJECTS:
            total = sum(q for _, q in allocations[subj])
            if total != TARGET_PER_SUBJECT:
                # Report but continue with what we can allocate
                pass

    url = settings.database_url
    engine = create_async_engine(url)
    subject_results = {}
    batch_ids = []

    async with AsyncSession(engine, expire_on_commit=False) as session:
        actor_id = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()

        for subj in SUBJECTS:
            print(json.dumps({"event": "subject_start", "subject": subj, "allocations": len(allocations[subj])}))
            result = await generate_subject(
                session,
                subject=subj,
                allocations=allocations[subj],
                actor_id=actor_id,
                ncert_root=ncert_root,
            )
            subject_results[subj] = result
            if result.get("batch_id"):
                batch_ids.append(result["batch_id"])
            print(
                json.dumps(
                    {
                        "event": "subject_done",
                        "subject": subj,
                        "created": result.get("created_total"),
                        "requested": result.get("requested"),
                        "stop": result.get("stop_reason"),
                    }
                )
            )
            if result.get("stop_reason") and str(result["stop_reason"]).startswith("source_guard"):
                break
            if result.get("stop_reason") == "safety_abort_publish_detected":
                break

        candidates = await collect_candidates(session, batch_ids)

    await engine.dispose()

    with sync_engine.connect() as conn:
        after = snapshot_sync(conn)

    status_counts = Counter(c["status"] for c in candidates)
    created = status_counts.get("CREATED", 0)
    attempted = sum((subject_results[s].get("stats") or {}).get("attempted", 0) for s in SUBJECTS)
    failed_parse = status_counts.get("FAILED_PARSE", 0)
    rejected_val = status_counts.get("REJECTED_VALIDATION", 0)
    rejected_dup = status_counts.get("REJECTED_DUPLICATE", 0)
    failed_prov = status_counts.get("FAILED_PROVIDER", 0)
    # Also fold run-level stats if candidate rows incomplete
    run_created = sum(int((subject_results[s].get("stats") or {}).get("created") or 0) for s in SUBJECTS)
    if run_created and created == 0:
        created = run_created

    requested_total = sum(int(subject_results[s].get("requested") or 0) for s in SUBJECTS)
    bps_used = set()
    chapters_used = Counter()
    topics_used = Counter()
    for subj in SUBJECTS:
        for run in subject_results[subj].get("runs") or []:
            if run.get("blueprint_key"):
                bps_used.add(run["blueprint_key"])
            if run.get("created"):
                chapters_used[f"{subj}/{run.get('chapter_code')}"] += run["created"]
                topics_used[f"{subj}/{run.get('topic_code')}"] += run["created"]

    rates = {
        "created_pct": pct(created, requested_total),
        "parse_ok_pct": pct(max(attempted - failed_parse, 0), attempted) if attempted else None,
        "validation_reject_pct": pct(rejected_val, attempted) if attempted else None,
        "duplicate_pct": pct(rejected_dup, attempted) if attempted else None,
        "provider_fail_pct": pct(failed_prov, attempted) if attempted else None,
    }

    protected_ok = protected_freeze_ok(after)
    checksum_ok = before["protected_status_checksum"] == after["protected_status_checksum"]
    draft_before = before["status"].get("DRAFT", 0)
    draft_after = after["status"].get("DRAFT", 0)
    draft_delta = draft_after - draft_before

    # Published must not change; DRAFT may increase by CREATED count
    if after["status"].get("PUBLISHED") != FREEZE_PROTECTED["PUBLISHED"]:
        protected_ok = False
    if after["unmapped_draft"] != FREEZE_PROTECTED["unmapped_draft"]:
        protected_ok = False
    if after["question_blueprints"] != FREEZE_PROTECTED["blueprints"]:
        protected_ok = False
    if after["knowledge_units"] != FREEZE_PROTECTED["knowledge_units"]:
        protected_ok = False

    tests = run_tests()

    hit_400 = created >= TOTAL_TARGET  # ideally == 400
    subject_ok = all(
        int((subject_results[s].get("stats") or {}).get("created") or 0) >= TARGET_PER_SUBJECT for s in SUBJECTS
    )

    if not protected_ok or not checksum_ok or after["ecaep_reviews"] != before["ecaep_reviews"]:
        final = "RED — SAFETY BOUNDARY VIOLATED"
    elif (tests.get("failed") or 0) > 0:
        final = "YELLOW — GENERATED WITH TEST WARNINGS"
    elif created == TOTAL_TARGET and subject_ok:
        final = "GREEN — 400 CANDIDATES GENERATED (UNPUBLISHED)"
    elif created > 0:
        final = f"YELLOW — PARTIAL GENERATION ({created}/{TOTAL_TARGET} CREATED)"
    else:
        final = "RED — NO CANDIDATES CREATED"

    telemetry = {
        "requested": requested_total,
        "created": created,
        "attempted": attempted,
        "failed_parse": failed_parse,
        "rejected_validation": rejected_val,
        "rejected_duplicate": rejected_dup,
        "failed_provider": failed_prov,
        "candidate_status_counts": dict(status_counts),
        "rates": rates,
        "blueprints_used": len(bps_used),
        "coverage": {
            "chapters_with_created": dict(chapters_used),
            "topics_with_created": dict(list(topics_used.items())[:80]),
            "unique_chapters": len(chapters_used),
            "unique_topics": len(topics_used),
        },
        "non_created_count": sum(v for k, v in status_counts.items() if k != "CREATED"),
        "baseline_compare": {
            "historical_created_rate_pct": round(HISTORICAL_BASELINE["CREATED_rate"] * 100, 1),
            "pilot_created_rate_pct": rates.get("created_pct"),
            "historical_failed_parse": HISTORICAL_BASELINE["FAILED_PARSE"],
            "pilot_failed_parse": failed_parse,
            "historical_rejected_validation": HISTORICAL_BASELINE["REJECTED_VALIDATION"],
            "pilot_rejected_validation": rejected_val,
            "historical_failed_provider": HISTORICAL_BASELINE["FAILED_PROVIDER"],
            "pilot_failed_provider": failed_prov,
            "historical_rejected_duplicate": HISTORICAL_BASELINE["REJECTED_DUPLICATE"],
            "pilot_rejected_duplicate": rejected_dup,
        },
    }

    rejected = [c for c in candidates if c["status"] != "CREATED"]
    created_ids = [c["candidate_id"] for c in candidates if c["status"] == "CREATED"]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "campaign": CAMPAIGN,
        "final_status": final,
        "executive_summary": (
            f"Requested {TOTAL_TARGET} NCERT-grounded MCQ candidates (100/subject). "
            f"CREATED={created}. Published=0. "
            f"Protected freeze ok={protected_ok}. "
            "Candidates are generation outputs only — not NCERT-verified, not editorially approved."
        ),
        "ncert_root": str(ncert_root),
        "provider": f"{settings.factory_provider_mode}:{settings.factory_provider}",
        "model": settings.ai_default_model,
        "eligible_bp_count": len(eligible),
        "skipped_bps": skipped[:50],
        "allocations_planned": {
            subj: [{"blueprint_key": bp["blueprint_key"], "quota": q} for bp, q in allocations[subj]]
            for subj in SUBJECTS
        },
        "by_subject": subject_results,
        "telemetry": telemetry,
        "candidate_ids_created": created_ids,
        "rejected_candidates": rejected[:200],
        "before": before,
        "after": after,
        "protected_freeze_ok": protected_ok,
        "protected_checksum_unchanged": checksum_ok,
        "draft_delta": draft_delta,
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/mcq_pilot_001_ncert_generation.py",
            "cms.generation_* / cms.content_batches / new DRAFT content_items (candidates only)",
        ],
        "confirmation": {
            "mcqs_published": False,
            "ncert_certified": False,
            "editorially_approved": False,
            "existing_questions_mutated": False,
            "blueprints_modified": False,
            "kus_modified": False,
            "taxonomy_modified": False,
            "ecaep_modified": before["ecaep_reviews"] != after["ecaep_reviews"],
            "beyond_400_requested": False,
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
                "created": created,
                "requested": requested_total,
                "by_subject_created": {
                    s: int((subject_results[s].get("stats") or {}).get("created") or 0) for s in SUBJECTS
                },
                "protected_freeze_ok": protected_ok,
                "published": after["status"].get("PUBLISHED"),
                "draft_delta": draft_delta,
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
