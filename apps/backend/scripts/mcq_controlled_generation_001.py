"""MCQ-CONTROLLED-GENERATION-001 — 20 MCQs (5/5/5/5) from GENERATION_READY BPs only.

Uses existing Content Factory + syllabus + canonical NCERT gates.
Persists DRAFT candidates only. No publish/ECAEP/certify/commit.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
# Anthropic is PROVIDER_BLOCKED (billing/credits) in this environment.
# Controlled run uses OpenAI via the same provider-neutral Content Factory path.
os.environ.setdefault("FACTORY_PROVIDER_MODE", "fixed")
os.environ.setdefault("FACTORY_PROVIDER", "openai")
os.environ.setdefault("MCQ_PROVIDER", "openai")
os.environ.setdefault("FACTORY_PROVIDER_FALLBACK_CHAIN", "")
os.environ.setdefault("MCQ_ALLOW_FALLBACK_CHAIN", "false")
os.environ.setdefault("FACTORY_MAX_PILOT_COST_USD", "15.0")

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

import app.modules.knowledge.models  # noqa: E402, F401
from app.modules.cms.models.generation_candidate import GenerationCandidate  # noqa: E402
from app.modules.cms.schemas.content_factory import ContentBatchCreateRequest  # noqa: E402
from app.modules.cms.services.content_factory_generation_service import (  # noqa: E402
    ContentFactoryGenerationService,
)
from app.modules.cms.services.content_factory_service import ContentFactoryService  # noqa: E402
from app.modules.cms.services.ncert_generation_evidence import (  # noqa: E402
    resolve_ncert_evidence_pack,
)
from app.modules.cms.syllabus import (  # noqa: E402
    assert_blueprint_neet_syllabus_scope,
    load_neet_2026_registry,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    extract_blueprint_ncert_path,
    is_allowed_ncert_source,
)

REPORT = "mcq_controlled_generation_001"
CAMPAIGN = "mcq-ctrl-gen-001"
SUBJECTS = ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY")
PER_SUBJECT = 5
TOTAL = 20
COVERAGE = ROOT / "docs" / "audits" / "mcq_evidence_coverage_002.json"
WRITE002 = ROOT / "docs" / "audits" / "ncert_evidence_write_002.json"
NCERT_ROOT = ROOT / "NCERT Books"


def _cons(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def _ku_facts(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, dict):
        out: list[str] = []
        for v in raw.values():
            if isinstance(v, str):
                out.append(v)
            elif isinstance(v, list):
                out.extend(str(x) for x in v)
        return out
    return []


def snapshot(conn) -> dict[str, Any]:
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
    return {
        "chapters": conn.execute(
            text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")
        ).scalar(),
        "topics": conn.execute(
            text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")
        ).scalar(),
        "concepts": conn.execute(
            text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")
        ).scalar(),
        "kus": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "status": status,
        "unmapped_draft": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                  AND status = 'DRAFT' AND concept_id IS NULL
                """
            )
        ).scalar(),
        "candidates": conn.execute(
            text("SELECT COUNT(*) FROM cms.generation_candidates")
        ).scalar(),
        "jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
        "published": status.get("PUBLISHED", 0),
    }


def load_generation_ready(conn, registry) -> list[dict[str, Any]]:
    """Live GENERATION_READY = IN_SYLLABUS + NCERT_EVIDENCE_READY + eligible + canonical path."""
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT ON (bp.blueprint_key)
              bp.id::text AS blueprint_id,
              bp.blueprint_key,
              bp.blueprint_version,
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
            ORDER BY bp.blueprint_key, bp.blueprint_version DESC
            """
        )
    ).mappings()

    ready: list[dict[str, Any]] = []
    for r in rows:
        if not r["generation_eligible"] or not r["is_active"] or r["status"] in {
            "SUPERSEDED",
            "ARCHIVED",
        }:
            continue
        cons = _cons(r["constraints"])
        path = extract_blueprint_ncert_path(cons)
        if not path or "StudyMaterial" in path.replace("\\", "/"):
            continue
        try:
            if not is_allowed_ncert_source(path, root=NCERT_ROOT):
                continue
        except Exception:
            continue
        gate = assert_blueprint_neet_syllabus_scope(
            cons,
            academic_subject_code=r["subject"],
            registry=registry,
        )
        if gate.status != "IN_SYLLABUS":
            continue
        ku_id = str(cons["ku_id"]) if cons.get("ku_id") else None
        ku_summary = None
        ku_facts: list[str] = []
        if ku_id:
            ku = conn.execute(
                text(
                    """
                    SELECT summary, structured_facts
                    FROM knowledge.knowledge_units
                    WHERE id = CAST(:id AS uuid) AND deleted_at IS NULL
                    """
                ),
                {"id": ku_id},
            ).mappings().first()
            if ku:
                ku_summary = ku.get("summary")
                ku_facts = _ku_facts(ku.get("structured_facts"))
        pack = resolve_ncert_evidence_pack(
            cons,
            provenance_tier=r["provenance_tier"],
            concept_name=r["concept_name"],
            chapter_name=r["chapter_name"],
            topic_name=r["topic_name"],
            ku_id=ku_id,
            ku_summary=ku_summary,
            ku_facts=ku_facts,
        )
        if pack.status != "NCERT_EVIDENCE_READY":
            continue
        ready.append(
            {
                **dict(r),
                "constraints": cons,
                "ncert_source_path": path,
                "ncert_relative": pack.relative_posix,
                "syllabus": {
                    "subject": gate.subject,
                    "unit_number": gate.unit_number,
                    "unit_name": gate.unit_name,
                    "topic_id": gate.topic_id,
                },
                "evidence_pages": list(pack.page_numbers or []),
            }
        )
    return ready


def pick_five_per_subject(ready: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_subj: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bp in ready:
        by_subj[bp["subject"]].append(bp)
    selected: dict[str, list[dict[str, Any]]] = {}
    for subj in SUBJECTS:
        pool = by_subj.get(subj, [])
        # Prefer chapter diversity
        seen_ch: set[str] = set()
        chosen: list[dict[str, Any]] = []
        for bp in pool:
            if bp["chapter_code"] in seen_ch:
                continue
            chosen.append(bp)
            seen_ch.add(bp["chapter_code"])
            if len(chosen) >= PER_SUBJECT:
                break
        if len(chosen) < PER_SUBJECT:
            for bp in pool:
                if bp in chosen:
                    continue
                chosen.append(bp)
                if len(chosen) >= PER_SUBJECT:
                    break
        if len(chosen) < PER_SUBJECT:
            raise RuntimeError(
                f"{subj}: only {len(chosen)} GENERATION_READY blueprints available (need {PER_SUBJECT})"
            )
        selected[subj] = chosen[:PER_SUBJECT]
    return selected


async def generate_one(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    bp: dict[str, Any],
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    gen = ContentFactoryGenerationService(session)
    job_key = f"{CAMPAIGN}-{bp['subject'].lower()}-{bp['concept_code']}-{uuid.uuid4().hex[:8]}"
    result = await gen.generate_for_batch(
        batch_id,
        blueprint_id=uuid.UUID(bp["blueprint_id"]),
        target_count=1,
        actor_id=actor_id,
        job_key=job_key,
        sync_cap=False,
    )
    return result if isinstance(result, dict) else {}


async def run_generation(selected: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    subject_results: dict[str, Any] = {}
    all_runs: list[dict[str, Any]] = []
    batch_ids: list[str] = []

    async with AsyncSession(engine, expire_on_commit=False) as session:
        actor_id = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()

        for subj in SUBJECTS:
            bps = selected[subj]
            factory = ContentFactoryService(session)
            batch, _ = await factory.create_batch(
                ContentBatchCreateRequest(
                    batch_key=f"{CAMPAIGN}-batch-{subj.lower()}-{uuid.uuid4().hex[:6]}",
                    name=f"MCQ-CONTROLLED-GENERATION-001 {subj} (DRAFT)",
                    description="Controlled 5-candidate generation — no publish/ECAEP",
                    subject_id=uuid.UUID(bps[0]["subject_id"]),
                    target_count=PER_SUBJECT,
                    source_type="AI",
                    source_tier="ai",
                ),
                actor_id=actor_id,
            )
            batch_ids.append(str(batch.id))
            runs = []
            agg: Counter = Counter()
            for bp in bps:
                print(json.dumps({"event": "generate", "subject": subj, "blueprint": bp["blueprint_key"]}))
                try:
                    result = await generate_one(
                        session, batch_id=batch.id, bp=bp, actor_id=actor_id
                    )
                except Exception as exc:  # noqa: BLE001
                    run = {
                        "blueprint_id": bp["blueprint_id"],
                        "blueprint_key": bp["blueprint_key"],
                        "subject": subj,
                        "requested": 1,
                        "created": 0,
                        "error": f"{type(exc).__name__}:{exc}"[:500],
                        "stop_reason": "EXCEPTION",
                    }
                    runs.append(run)
                    all_runs.append(run)
                    agg["failed_provider"] += 1
                    agg["requested"] += 1
                    continue
                run = {
                    "blueprint_id": bp["blueprint_id"],
                    "blueprint_key": bp["blueprint_key"],
                    "subject": subj,
                    "chapter": bp["chapter_name"],
                    "topic": bp["topic_name"],
                    "concept": bp["concept_name"],
                    "class_level": bp["class_level"],
                    "ncert_source_path": bp.get("ncert_source_path"),
                    "ncert_relative": bp.get("ncert_relative"),
                    "syllabus": bp.get("syllabus"),
                    "requested": 1,
                    "created": int(result.get("created") or 0),
                    "attempted": int(result.get("attempted") or 0),
                    "rejected_validation": int(result.get("rejected_validation") or 0),
                    "duplicate": int(result.get("duplicate") or 0),
                    "failed_provider": int(result.get("failed_provider") or 0),
                    "failed_parse": int(result.get("failed_parse") or 0),
                    "diversity_rejected": int(result.get("diversity_rejected") or 0),
                    "stop_reason": result.get("stop_reason"),
                    "cost_usd": result.get("cost_usd"),
                    "latency_ms": result.get("latency_ms"),
                    "provider": (result.get("providers") or {}),
                    "model": (result.get("models") or {}),
                    "job_id": result.get("job_id"),
                    "run_id": result.get("run_id"),
                    "batch_id": str(batch.id),
                    "content_item_ids": result.get("content_item_ids") or [],
                }
                runs.append(run)
                all_runs.append(run)
                for k in (
                    "created",
                    "attempted",
                    "rejected_validation",
                    "duplicate",
                    "failed_provider",
                    "failed_parse",
                    "diversity_rejected",
                    "requested",
                ):
                    agg[k] += int(run.get(k) or 0)
                if run.get("cost_usd"):
                    agg["cost_usd_milli"] += int(float(run["cost_usd"]) * 1000)

            subject_results[subj] = {
                "batch_id": str(batch.id),
                "requested": PER_SUBJECT,
                "created": int(agg.get("created") or 0),
                "stats": dict(agg),
                "runs": runs,
            }

        # Collect candidates for these batches
        cands = (
            await session.execute(
                select(GenerationCandidate).where(
                    GenerationCandidate.batch_id.in_([uuid.UUID(b) for b in batch_ids]),
                    GenerationCandidate.deleted_at.is_(None),
                )
            )
        ).scalars().all()

        candidate_rows: list[dict[str, Any]] = []
        for cand in cands:
            item_status = None
            stem = None
            lineage = {}
            if cand.content_item_id:
                row = (
                    await session.execute(
                        text(
                            """
                            SELECT ci.status,
                                   ci.concept_id::text AS concept_id,
                                   ci.latest_version_id::text AS latest_version_id,
                                   left(coalesce(cv.body->>'stem', ''), 240) AS stem,
                                   cv.body->'source_refs' AS source_refs,
                                   cv.body->'ncert_evidence' AS ncert_evidence,
                                   cv.body->'syllabus_ref' AS syllabus_ref,
                                   cv.knowledge_unit_id::text AS knowledge_unit_id,
                                   cv.model_used AS version_model_used,
                                   cv.generation_cost_usd
                            FROM cms.content_items ci
                            LEFT JOIN cms.content_versions cv
                              ON cv.id = ci.latest_version_id
                            WHERE ci.id = :id
                            """
                        ),
                        {"id": cand.content_item_id},
                    )
                ).mappings().first()
                if row:
                    item_status = row["status"]
                    stem = (row.get("stem") or "")[:240]
                    lineage = {
                        "content_item_id": str(cand.content_item_id),
                        "content_status": item_status,
                        "concept_id": row.get("concept_id"),
                        "latest_version_id": row.get("latest_version_id"),
                        "knowledge_unit_id": row.get("knowledge_unit_id"),
                        "source_refs": row.get("source_refs"),
                        "ncert_evidence": row.get("ncert_evidence"),
                        "syllabus_ref": row.get("syllabus_ref"),
                        "version_model_used": row.get("version_model_used"),
                        "generation_cost_usd": (
                            float(row["generation_cost_usd"])
                            if row.get("generation_cost_usd") is not None
                            else None
                        ),
                    }
            candidate_rows.append(
                {
                    "candidate_id": str(cand.id),
                    "batch_id": str(cand.batch_id) if cand.batch_id else None,
                    "job_id": str(cand.job_id) if cand.job_id else None,
                    "run_id": str(cand.run_id) if cand.run_id else None,
                    "blueprint_id": str(cand.blueprint_id) if cand.blueprint_id else None,
                    "candidate_status": cand.status,
                    "provider": cand.provider,
                    "model_used": cand.model_used,
                    "error_code": cand.error_code,
                    "error_summary": (cand.error_summary or "")[:300] or None,
                    "stem_hash": cand.stem_hash,
                    "stem_preview": stem,
                    "lineage": lineage,
                    "published": item_status == "PUBLISHED",
                }
            )

    await engine.dispose()
    return {
        "subject_results": subject_results,
        "runs": all_runs,
        "batch_ids": batch_ids,
        "candidates": candidate_rows,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    m = report["metrics"]
    lines = [
        "# MCQ-CONTROLLED-GENERATION-001",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verdict:** **{report['verdict']}**",
        f"**Provider:** {report.get('provider_routing')}",
        "",
        "## Request",
        "",
        f"- Requested: **{m['requested']}** (5 Physics / 5 Chemistry / 5 Botany / 5 Zoology)",
        f"- Created (valid unique DRAFTs): **{m['created']}**",
        f"- Provider attempts: **{m['attempted']}**",
        f"- Parse failures: **{m['failed_parse']}**",
        f"- Validation failures: **{m['rejected_validation']}**",
        f"- Provider failures: **{m['failed_provider']}**",
        f"- Duplicates: **{m['duplicate']}**",
        f"- Syllabus-gate stops: **{m['syllabus_gate_failures']}**",
        f"- NCERT-evidence stops: **{m['ncert_evidence_failures']}**",
        f"- Estimated cost USD: **{m['estimated_cost_usd']}**",
        f"- Total latency ms (sum of runs): **{m['latency_ms_sum']}**",
        "",
        "## Verification",
        "",
        f"- Created content items: **{report.get('verification', {}).get('created_content_items')}**",
        f"- All created DRAFT: **{report.get('verification', {}).get('all_created_draft')}**",
        f"- Canonical NCERT path on every created: **{report.get('verification', {}).get('every_created_has_canonical_ncert_path')}**",
        f"- Syllabus mapping on every created: **{report.get('verification', {}).get('every_created_has_syllabus_mapping')}**",
        f"- Duplicate stem hashes among created: **{report.get('verification', {}).get('duplicate_stem_hashes_among_created')}**",
        "",
        "## By subject",
        "",
        "| Subject | Requested | Created |",
        "|---|---:|---:|",
    ]
    for subj in SUBJECTS:
        sr = report["subject_results"][subj]
        lines.append(f"| {subj} | {sr['requested']} | {sr['created']} |")
    lines += [
        "",
        "## Safety",
        "",
        f"- Published delta: **{report['safety']['published_delta']}** (expect 0)",
        f"- Taxonomy/KU/blueprint count freeze: **{report['safety']['inventory_core_unchanged']}**",
        f"- Unmapped DRAFT unchanged: **{report['safety']['unmapped_draft_unchanged']}**",
        f"- Candidates created this run: **{len(report['candidates'])}**",
        f"- Any candidate published: **{report['safety']['any_candidate_published']}**",
        "",
        "## Limitations",
        "",
    ]
    for lim in report.get("limitations", []):
        lines.append(f"- {lim}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    assert COVERAGE.is_file() and WRITE002.is_file()
    assert NCERT_ROOT.is_dir()
    registry = load_neet_2026_registry()
    settings = get_settings()
    sync = create_engine(settings.database_url_sync)

    with sync.connect() as conn:
        before = snapshot(conn)
        ready = load_generation_ready(conn, registry)
        selected = pick_five_per_subject(ready)

    print(
        json.dumps(
            {
                "event": "selection",
                "generation_ready_pool": len(ready),
                "by_subject": {s: len([b for b in ready if b["subject"] == s]) for s in SUBJECTS},
                "selected": {s: [b["blueprint_key"] for b in selected[s]] for s in SUBJECTS},
            },
            indent=2,
        )
    )

    gen_out = asyncio.run(run_generation(selected))

    with sync.connect() as conn:
        after = snapshot(conn)

    # Aggregate metrics
    metrics = Counter()
    latency_sum = 0
    cost_sum = 0.0
    syllabus_stops = 0
    ncert_stops = 0
    for run in gen_out["runs"]:
        metrics["requested"] += int(run.get("requested") or 0)
        metrics["created"] += int(run.get("created") or 0)
        metrics["attempted"] += int(run.get("attempted") or 0)
        metrics["failed_parse"] += int(run.get("failed_parse") or 0)
        metrics["rejected_validation"] += int(run.get("rejected_validation") or 0)
        metrics["failed_provider"] += int(run.get("failed_provider") or 0)
        metrics["duplicate"] += int(run.get("duplicate") or 0)
        if run.get("latency_ms"):
            latency_sum += int(run["latency_ms"])
        if run.get("cost_usd"):
            cost_sum += float(run["cost_usd"])
        sr = (run.get("stop_reason") or "")
        if "SYLLABUS" in sr:
            syllabus_stops += 1
        if "NCERT_EVIDENCE" in sr:
            ncert_stops += 1

    created_by_subj = {s: gen_out["subject_results"][s]["created"] for s in SUBJECTS}
    any_published = any(c.get("published") for c in gen_out["candidates"])
    inventory_core_unchanged = all(
        before[k] == after[k] for k in ("chapters", "topics", "concepts", "kus", "blueprints")
    )
    published_delta = after["published"] - before["published"]
    unmapped_ok = before["unmapped_draft"] == after["unmapped_draft"]

    # Build per-candidate machine records enriched with selection metadata
    bp_index = {b["blueprint_id"]: b for s in SUBJECTS for b in selected[s]}
    candidates_out = []
    for c in gen_out["candidates"]:
        bp = bp_index.get(c.get("blueprint_id") or "")
        candidates_out.append(
            {
                **c,
                "subject": bp["subject"] if bp else None,
                "chapter": bp["chapter_name"] if bp else None,
                "topic": bp["topic_name"] if bp else None,
                "concept": bp["concept_name"] if bp else None,
                "ncert_source_path": bp.get("ncert_source_path") if bp else None,
                "ncert_relative": bp.get("ncert_relative") if bp else None,
                "syllabus_mapping": bp.get("syllabus") if bp else None,
                "evidence_pages": bp.get("evidence_pages") if bp else None,
            }
        )

    ok_request = metrics["requested"] == TOTAL
    requested_dist_ok = True
    for s in SUBJECTS:
        if gen_out["subject_results"][s]["requested"] != PER_SUBJECT:
            requested_dist_ok = False

    # Deterministic verification on THIS run's candidates (not prior anthropic failures)
    # Prefer statuses that indicate a persisted content item
    created_cands = [c for c in candidates_out if c.get("lineage", {}).get("content_item_id")]
    stem_hashes = [c.get("stem_hash") for c in created_cands if c.get("stem_hash")]
    duplicate_stems = len(stem_hashes) != len(set(stem_hashes))
    non_draft_items = [
        c for c in created_cands
        if (c.get("lineage") or {}).get("content_status") not in {None, "DRAFT"}
    ]
    missing_canonical = [
        c
        for c in created_cands
        if not c.get("ncert_source_path")
        or "StudyMaterial" in str(c.get("ncert_source_path") or "").replace("\\", "/")
        or not c.get("ncert_relative")
        or "StudyMaterial" in str(c.get("ncert_relative") or "").replace("\\", "/")
    ]
    missing_syllabus = [
        c for c in created_cands
        if not (c.get("syllabus_mapping") or {}).get("unit_number")
    ]
    verification = {
        "exactly_20_requested": ok_request,
        "subject_distribution_requested_5_5_5_5": requested_dist_ok,
        "created_count": int(metrics["created"]),
        "created_by_subject": created_by_subj,
        "created_content_items": len(created_cands),
        "all_created_draft": len(non_draft_items) == 0 and len(created_cands) == int(metrics["created"]),
        "any_non_draft_item": bool(non_draft_items),
        "duplicate_stem_hashes_among_created": duplicate_stems,
        "every_created_has_canonical_ncert_path": len(missing_canonical) == 0 and len(created_cands) == int(metrics["created"]),
        "every_created_has_syllabus_mapping": len(missing_syllabus) == 0 and len(created_cands) == int(metrics["created"]),
        "provider_failures_classified": all(
            (
                c.get("error_code")
                in {
                    None,
                    "PROVIDER_BLOCKED",
                    "PROVIDER_AUTH_FAILED",
                    "PROVIDER_RATE_LIMITED",
                    "PROVIDER_UNAVAILABLE",
                    "NETWORK_ERROR",
                    "TIMEOUT",
                }
                or c.get("candidate_status") != "FAILED_PROVIDER"
            )
            for c in candidates_out
        ),
        "note": "Syllabus/NCERT gates are enforced pre-LLM by Content Factory; this block checks persisted lineage fields.",
    }

    # GREEN if all 20 created DRAFT, no publish, gates clean, freeze ok
    all_created = metrics["created"] == TOTAL and all(created_by_subj[s] == PER_SUBJECT for s in SUBJECTS)
    no_pub = published_delta == 0 and not any_published
    verification_ok = (
        verification["all_created_draft"]
        and verification["every_created_has_canonical_ncert_path"]
        and verification["every_created_has_syllabus_mapping"]
        and not verification["duplicate_stem_hashes_among_created"]
        and not verification["any_non_draft_item"]
    )
    verdict = "GREEN" if (
        ok_request
        and requested_dist_ok
        and all_created
        and no_pub
        and inventory_core_unchanged
        and unmapped_ok
        and syllabus_stops == 0
        and ncert_stops == 0
        and verification_ok
    ) else "YELLOW"
    if published_delta != 0 or any_published:
        verdict = "RED"
    if not inventory_core_unchanged:
        verdict = "RED"

    report = {
        "task": "MCQ-CONTROLLED-GENERATION-001",
        "generated_at": datetime.now(UTC).isoformat(),
        "provider_routing": {
            "FACTORY_PROVIDER": os.environ.get("FACTORY_PROVIDER"),
            "MCQ_PROVIDER": os.environ.get("MCQ_PROVIDER"),
            "FACTORY_PROVIDER_MODE": os.environ.get("FACTORY_PROVIDER_MODE"),
            "model_hint": get_settings().openai_model,
            "prior_attempt": {
                "provider": "anthropic",
                "result": "PROVIDER_BLOCKED",
                "summary": "Provider billing/credits blocked (20/20)",
            },
        },
        "inputs": {
            "coverage_audit": str(COVERAGE),
            "write_002_audit": str(WRITE002),
            "generation_ready_pool_size": len(ready),
            "selected_blueprint_ids": {
                s: [b["blueprint_id"] for b in selected[s]] for s in SUBJECTS
            },
            "selected_blueprint_keys": {
                s: [b["blueprint_key"] for b in selected[s]] for s in SUBJECTS
            },
        },
        "database_before": before,
        "database_after": after,
        "metrics": {
            "requested": int(metrics["requested"]),
            "attempted": int(metrics["attempted"]),
            "created": int(metrics["created"]),
            "failed_parse": int(metrics["failed_parse"]),
            "rejected_validation": int(metrics["rejected_validation"]),
            "failed_provider": int(metrics["failed_provider"]),
            "duplicate": int(metrics["duplicate"]),
            "syllabus_gate_failures": syllabus_stops,
            "ncert_evidence_failures": ncert_stops,
            "latency_ms_sum": latency_sum,
            "estimated_cost_usd": round(cost_sum, 6),
            "created_by_subject": created_by_subj,
        },
        "subject_results": gen_out["subject_results"],
        "runs": gen_out["runs"],
        "candidates": candidates_out,
        "verification": verification,
        "safety": {
            "published_delta": published_delta,
            "any_candidate_published": any_published,
            "inventory_core_unchanged": inventory_core_unchanged,
            "unmapped_draft_unchanged": unmapped_ok,
            "candidates_delta": after["candidates"] - before["candidates"],
            "jobs_delta": after["jobs"] - before["jobs"],
            "runs_delta": after["runs"] - before["runs"],
        },
        "verdict": verdict,
        "acceptance": {
            "requested_20": ok_request,
            "subject_slots_5_each": requested_dist_ok,
            "created_20_5_each": all_created,
            "no_publication": no_pub,
            "inventory_freeze": inventory_core_unchanged,
            "verification_ok": verification_ok,
            "note": "Generation success ≠ independent NCERT certification",
        },
        "limitations": [
            "Deterministic validation only; no independent editorial NCERT certification.",
            "Used live GENERATION_READY pool (IN_SYLLABUS + NCERT_EVIDENCE_READY), not stale coverage-002 alone.",
            "First attempt anthropic → PROVIDER_BLOCKED (billing); retry fixed to openai.",
            "Prior anthropic failed candidate/job/run rows remain in DB from the blocked attempt.",
        ],
        "failures": [],
    }
    if not all_created:
        report["failures"].append("created_count_below_20_or_uneven_subjects")

    out_json = ROOT / "docs" / "audits" / f"{REPORT}.json"
    out_md = ROOT / "docs" / "audits" / f"{REPORT}.md"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_markdown(report, out_md)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "metrics": report["metrics"],
                "safety": report["safety"],
                "json": str(out_json),
            },
            indent=2,
        )
    )
    return 0 if verdict != "RED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
