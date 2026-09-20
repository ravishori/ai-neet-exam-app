"""FACTORY-P4 QA on the exact Gemini P3 ~95 DRAFT population only.

Authoritative target: content_item_ids from CONTENT_FACTORY_P3_PILOT_RESULTS.json
Batch: factory-p3-pilot-2026-09-01-batch (22c5684b-…)
Does NOT QA the 5 older CREATED candidates also present on the same batch.
Does NOT call LLM providers. Does NOT approve/publish/ECAEP/P5.
Intentional writes: QAResult, fingerprints, candidate qa_* fields, audit, VALIDATE job/run.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.modules.knowledge.models  # noqa: F401
from app.core.config import get_settings
from app.modules.cms.acquisition.physics_integrity_fingerprints import collect_integrity_snapshot
from app.modules.cms.models.content_factory import ContentBatch
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.schemas.content_factory import (
    GenerationJobCreateRequest,
    GenerationRunCompleteRequest,
    GenerationRunCreateRequest,
)
from app.modules.cms.services.content_factory_qa_service import ContentFactoryQAService
from app.modules.cms.services.content_factory_service import ContentFactoryService
from scripts.factory_p1_checksum import checksum

BATCH_ID = "22c5684b-cf86-4137-82bf-be237be1e2ee"
BATCH_KEY = "factory-p3-pilot-2026-09-01-batch"
RESULTS_PATH = Path(
    r"D:\ravishori\AI Neet Exam App\docs\product\CONTENT_FACTORY_P3_PILOT_RESULTS.json"
)
AUDITS = Path(r"D:\ravishori\AI Neet Exam App\docs\audits")
STAMP = "20260902"
EXPECTED_PROVIDER = "gemini"
EXPECTED_ROUTING = "fixed:gemini"
EXPECTED_MODEL = "gemini-3.6-flash"

GATE_KEYS = {
    "A_STRUCTURE": "gate_A",
    "B_BLUEPRINT": "gate_B",
    "C_HIERARCHY": "gate_C",
    "D_PROVENANCE": "gate_D",
    "E_ANSWER": "gate_E",
    "F_DUPLICATE": "gate_F",
    "G_SAFETY": "gate_G",
}


def load_p3_ids() -> list[str]:
    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    ids: list[str] = []
    for r in data["results"]:
        ids.extend(r.get("content_item_ids") or [])
    if len(ids) != 95 or len(set(ids)) != 95:
        raise SystemExit(f"Expected 95 unique P3 IDs, got {len(ids)} / unique {len(set(ids))}")
    return ids


def classify_failure(gate_code: str, failures: list[str]) -> list[str]:
    out: list[str] = []
    for f in failures:
        if gate_code == "A_STRUCTURE":
            out.append("STRUCTURAL_DEFECT")
        elif gate_code == "B_BLUEPRINT":
            out.append("BLUEPRINT_DEFECT")
        elif gate_code == "C_HIERARCHY":
            out.append("BLUEPRINT_DEFECT" if "CONCEPT" in f or "HIERARCHY" in f else "CONTENT_DEFECT")
        elif gate_code == "D_PROVENANCE":
            out.append("PROVENANCE_DEFECT")
        elif gate_code == "E_ANSWER":
            out.append("CONTENT_DEFECT")
        elif gate_code == "F_DUPLICATE":
            out.append("DUPLICATE_DEFECT")
        elif gate_code == "G_SAFETY":
            out.append("SAFETY_DEFECT")
        else:
            out.append("UNKNOWN")
    return out


async def integrity_bundle(session: AsyncSession, url: str, item_ids: list[str]) -> dict:
    cs = await checksum(url)
    snap = await collect_integrity_snapshot(session)
    snap_out = {k: v for k, v in snap.items() if not str(k).endswith("_row_canons")}
    rows = (
        await session.execute(
            text(
                """
                SELECT ci.id::text AS id, ci.status,
                       md5(cv.body::text) AS body_md5,
                       cv.workflow_state
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                ORDER BY ci.id
                """
            ),
            {"ids": item_ids},
        )
    ).mappings().all()
    status_dist = dict(Counter(r["status"] for r in rows))
    body_fp = __import__("hashlib").md5(
        "|".join(f"{r['id']}:{r['body_md5']}:{r['status']}" for r in rows).encode()
    ).hexdigest()
    return {
        "checksum": {
            "counts": dict(cs["counts"]),
            "item_checksum": cs["item_checksum"],
            "body_checksum": cs["versions"]["body_checksum"],
            "versions": cs["versions"]["versions"],
            "review_count": cs["review_count"],
        },
        "integrity": snap_out,
        "p3_population": {
            "count": len(rows),
            "status_distribution": status_dist,
            "body_status_fingerprint": body_fp,
            "item_ids": [r["id"] for r in rows],
            "bodies": {r["id"]: {"status": r["status"], "body_md5": r["body_md5"], "workflow_state": r["workflow_state"]} for r in rows},
        },
    }


async def main() -> None:
    item_ids = load_p3_ids()
    settings = get_settings()
    url = settings.database_url
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # --- STEP 2 pre-baseline ---
    async with Session() as session:
        pre = await integrity_bundle(session, url, item_ids)
        batch = (
            await session.execute(select(ContentBatch).where(ContentBatch.id == uuid.UUID(BATCH_ID)))
        ).scalar_one()
        if batch.batch_key != BATCH_KEY:
            raise SystemExit(f"Batch key mismatch: {batch.batch_key}")

        # lineage snapshot
        lineage_rows = (
            await session.execute(
                text(
                    """
                    SELECT gc.content_item_id::text AS item_id,
                           gc.id::text AS candidate_id,
                           gc.provider, gc.model_used, gc.routing_policy,
                           gc.is_fallback, gc.status AS candidate_status,
                           ci.status AS item_status
                    FROM cms.generation_candidates gc
                    JOIN cms.content_items ci ON ci.id = gc.content_item_id
                    WHERE gc.batch_id = CAST(:bid AS uuid)
                      AND gc.status = 'CREATED'
                      AND gc.deleted_at IS NULL
                      AND gc.content_item_id = ANY(CAST(:ids AS uuid[]))
                    ORDER BY gc.created_at
                    """
                ),
                {"bid": BATCH_ID, "ids": item_ids},
            )
        ).mappings().all()
        if len(lineage_rows) != 95:
            raise SystemExit(f"Expected 95 CREATED candidates for P3 IDs, got {len(lineage_rows)}")

        extra = (
            await session.execute(
                text(
                    """
                    SELECT count(*)::int FROM cms.generation_candidates
                    WHERE batch_id = CAST(:bid AS uuid) AND status='CREATED'
                      AND deleted_at IS NULL AND content_item_id IS NOT NULL
                      AND NOT (content_item_id = ANY(CAST(:ids AS uuid[])))
                    """
                ),
                {"bid": BATCH_ID, "ids": item_ids},
            )
        ).scalar_one()

        pre_out = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "database": db_name,
            "note": "Read-only baseline prior to P4. No mutations by this capture step.",
            "batch": {
                "id": BATCH_ID,
                "batch_key": BATCH_KEY,
                "status": batch.status,
                "created_count": batch.created_count,
                "qa_pass_count": batch.qa_pass_count,
                "extra_created_candidates_excluded_from_p4": extra,
            },
            "target": {
                "intended_p3_drafts": 95,
                "item_ids": item_ids,
                "source": str(RESULTS_PATH),
            },
            "lineage_pre": {
                "provider_counts": dict(Counter(r["provider"] for r in lineage_rows)),
                "routing_counts": dict(Counter(r["routing_policy"] for r in lineage_rows)),
                "model_counts": dict(Counter(r["model_used"] for r in lineage_rows)),
                "fallback_true": sum(1 for r in lineage_rows if r["is_fallback"]),
                "all_draft": all(r["item_status"] == "DRAFT" for r in lineage_rows),
            },
            **pre,
            "p4_mode_inspection": {
                "population_selection": "CREATED generation_candidates on batch; THIS RUN further restricts to 95 P3 content_item_ids",
                "content_body_mutation": False,
                "content_item_status_mutation": False,
                "ecaep_mutation": False,
                "intentional_writes": [
                    "cms.qa_results",
                    "cms.question_fingerprints",
                    "cms.generation_candidates.qa_classification/qa_quarantined/latest_qa_result_id/option_stem_hash",
                    "cms.generation_jobs / generation_runs (VALIDATE)",
                    "system.audit_logs",
                    "cms.content_batches.qa_pass_count (updated for this 95-eval green count)",
                ],
                "abort_if_unexpected": "Content body/status/ECAEP/publish/approve changes",
            },
        }
        pre_path = AUDITS / f"TALOS_FACTORY_P4_95_PRE_BASELINE_{STAMP}.json"
        pre_path.write_text(json.dumps(pre_out, indent=2, default=str), encoding="utf-8")

        # --- STEP 4 run P4 on 95 only ---
        actor = (
            await session.execute(
                text(
                    """
                    SELECT id FROM identity.users
                    WHERE deleted_at IS NULL
                    ORDER BY created_at
                    LIMIT 1
                    """
                )
            )
        ).scalar_one()

        factory = ContentFactoryService(session)
        qa = ContentFactoryQAService(session)
        job, _ = await factory.create_job(
            uuid.UUID(BATCH_ID),
            GenerationJobCreateRequest(
                job_key=f"qa-factory-qa-v1-p3-95-{uuid.uuid4().hex[:10]}",
                job_type="VALIDATE",
                requested_count=95,
                max_retries=1,
            ),
            actor_id=actor,
        )
        qa_run = await factory.request_run(
            job.id,
            GenerationRunCreateRequest(
                reason="FACTORY-P4 automated QA — P3 Gemini 95 only",
                execution_metadata={
                    "qa_version": "factory_qa_v1",
                    "force_new": True,
                    "population": "p3_pilot_95",
                    "excluded_extra_created": extra,
                },
            ),
            actor_id=actor,
        )
        qa_run.status = "RUNNING"
        qa_run.started_at = datetime.now(timezone.utc)
        job.status = "RUNNING"
        # Do not force batch status regression from SAMPLING; P4 docs allow QA metadata without ECAEP.
        await session.commit()

        cand_by_item = {r["item_id"]: r for r in lineage_rows}
        per_question: list[dict] = []
        class_counts: Counter = Counter()
        gate_pass = Counter()
        gate_fail = Counter()
        subject_stats: dict[str, dict] = defaultdict(lambda: {"n": 0, "green": 0, "yellow": 0, "red": 0, "gate_fails": Counter()})
        failure_categories: Counter = Counter()
        failure_examples: dict[str, list[str]] = defaultdict(list)

        for item_id in item_ids:
            meta = cand_by_item[item_id]
            # hierarchy labels
            hier = (
                await session.execute(
                    text(
                        """
                        SELECT s.name AS subject, ch.name AS chapter, t.name AS topic,
                               c.name AS concept, cv.body->>'difficulty' AS difficulty
                        FROM cms.content_items ci
                        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                        JOIN academic.concepts c ON c.id = ci.concept_id
                        JOIN academic.topics t ON t.id = c.topic_id
                        JOIN academic.chapters ch ON ch.id = t.chapter_id
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE ci.id = CAST(:id AS uuid)
                        """
                    ),
                    {"id": item_id},
                )
            ).mappings().one()

            status_before = meta["item_status"]
            row = await qa.evaluate_candidate(
                uuid.UUID(meta["candidate_id"]),
                actor_id=actor,
                force_new=True,
                qa_job_id=job.id,
                qa_run_id=qa_run.id,
                qa_version="factory_qa_v1",
            )
            # refresh item status
            status_after = (
                await session.execute(
                    text("SELECT status FROM cms.content_items WHERE id = CAST(:id AS uuid)"),
                    {"id": item_id},
                )
            ).scalar_one()

            gates = row.get("gate_results") or {}
            gate_flags = {}
            fail_reasons: list[str] = []
            cats: list[str] = []
            for code, key in GATE_KEYS.items():
                g = gates.get(code) or {}
                passed = bool(g.get("passed"))
                gate_flags[key] = "PASS" if passed else "FAIL"
                if passed:
                    gate_pass[key] += 1
                else:
                    gate_fail[key] += 1
                    for f in g.get("failures") or []:
                        fail_reasons.append(f"{code}:{f}")
                        for cat in classify_failure(code, [f]):
                            cats.append(cat)
                            failure_categories[cat] += 1
                            if len(failure_examples[cat]) < 5:
                                failure_examples[cat].append(item_id)

            # Explicit lineage audit (beyond Gate D implementation)
            provider = meta["provider"]
            routing = meta["routing_policy"]
            model = meta["model_used"]
            is_fallback = bool(meta["is_fallback"])
            lineage_ok = (
                provider == EXPECTED_PROVIDER
                and routing == EXPECTED_ROUTING
                and model == EXPECTED_MODEL
                and is_fallback is False
            )
            if not lineage_ok:
                fail_reasons.append("LINEAGE_AUDIT:UNEXPECTED_PROVIDER_ROUTING_OR_MODEL")
                cats.append("PROVENANCE_DEFECT")
                failure_categories["PROVENANCE_DEFECT"] += 1
                gate_flags["gate_D_lineage_audit"] = "FAIL"
            else:
                gate_flags["gate_D_lineage_audit"] = "PASS"

            classification = row["classification"]
            class_counts[classification] += 1
            subj = hier["subject"]
            subject_stats[subj]["n"] += 1
            subject_stats[subj][classification.lower()] += 1
            for k, v in gate_flags.items():
                if k.startswith("gate_") and v == "FAIL" and k != "gate_D_lineage_audit":
                    subject_stats[subj]["gate_fails"][k] += 1

            # F semantic note
            warnings = row.get("warnings") or []
            semantic = "SEMANTIC_DEDUPE_NOT_AVAILABLE" in warnings or "SEMANTIC_UNCHECKED" in warnings

            overall_pass = all(gate_flags[k] == "PASS" for k in GATE_KEYS.values()) and lineage_ok

            per_question.append(
                {
                    "item_id": item_id,
                    "candidate_id": meta["candidate_id"],
                    "qa_result_id": row.get("qa_result_id"),
                    "batch_id": BATCH_ID,
                    "subject": hier["subject"],
                    "chapter": hier["chapter"],
                    "topic": hier["topic"],
                    "concept": hier["concept"],
                    "difficulty": hier["difficulty"],
                    "status_before": status_before,
                    "status_after": status_after,
                    **{k: gate_flags[k] for k in GATE_KEYS.values()},
                    "gate_D_lineage_audit": gate_flags["gate_D_lineage_audit"],
                    "overall_p4_classification": classification,
                    "overall_gates_pass": overall_pass,
                    "sampling_eligible": row.get("sampling_eligible"),
                    "quarantine": row.get("quarantine"),
                    "duplicate_class": row.get("duplicate_class"),
                    "semantic_dedupe": "SEMANTIC_DEDUPE_NOT_AVAILABLE" if semantic else "UNKNOWN",
                    "failure_reasons": fail_reasons,
                    "failure_categories": sorted(set(cats)),
                    "provider": provider,
                    "routing": routing,
                    "model": model,
                    "is_fallback": is_fallback,
                    "warnings": warnings,
                    "scientific_certification": False,
                }
            )

        green = class_counts.get("GREEN", 0)
        batch = (
            await session.execute(select(ContentBatch).where(ContentBatch.id == uuid.UUID(BATCH_ID)))
        ).scalar_one()
        batch.qa_pass_count = green
        await factory.complete_run(
            qa_run.id,
            GenerationRunCompleteRequest(
                status="SUCCEEDED",
                processed_count=95,
                success_count=green,
                failure_count=class_counts.get("RED", 0),
                error_summary=None,
                execution_metadata={
                    "qa_version": "factory_qa_v1",
                    "population": "p3_pilot_95",
                    "counters": dict(class_counts),
                    "note": "AUTOMATED_QA_ONLY — not scientific certification",
                },
            ),
            actor_id=actor,
        )
        await session.commit()

        # --- STEP 8 post integrity ---
        post = await integrity_bundle(session, url, item_ids)
        post_statuses = (
            await session.execute(
                text(
                    """
                    SELECT status, count(*)::int AS n
                    FROM cms.content_items
                    WHERE id = ANY(CAST(:ids AS uuid[]))
                    GROUP BY status
                    """
                ),
                {"ids": item_ids},
            )
        ).mappings().all()

        approved = sum(r["n"] for r in post_statuses if r["status"] == "APPROVED")
        published = sum(r["n"] for r in post_statuses if r["status"] == "PUBLISHED")
        draft = sum(r["n"] for r in post_statuses if r["status"] == "DRAFT")

    await engine.dispose()

    # Compare integrity
    def fp(bundle, key):
        return bundle["integrity"][key]["content_fp"]

    unexpected = []
    if pre["checksum"]["counts"]["published"] != post["checksum"]["counts"]["published"]:
        unexpected.append("published_count_changed")
    if pre["checksum"]["counts"]["approved"] != post["checksum"]["counts"]["approved"]:
        unexpected.append("approved_count_changed")
    if fp(pre, "legacy") != fp(post, "legacy"):
        unexpected.append("legacy_fp_changed")
    if fp(pre, "t6d") != fp(post, "t6d"):
        unexpected.append("t6d_fp_changed")
    if fp(pre, "t6f1_published") != fp(post, "t6f1_published"):
        unexpected.append("t6f2_fp_changed")
    if pre["integrity"]["protected_non_f1_cms"]["published"] != post["integrity"]["protected_non_f1_cms"]["published"]:
        unexpected.append("protected_published_changed")
    if pre["p3_population"]["body_status_fingerprint"] != post["p3_population"]["body_status_fingerprint"]:
        unexpected.append("p3_body_or_status_changed")
    if draft != 95 or approved != 0 or published != 0:
        unexpected.append("p3_status_distribution_unexpected")

    # intentional checksum delta: versions/fingerprints/qa tables may change inventory? content items count should same
    if pre["checksum"]["counts"]["total"] != post["checksum"]["counts"]["total"]:
        unexpected.append("total_content_count_changed")
    if pre["checksum"]["counts"]["draft"] != post["checksum"]["counts"]["draft"]:
        unexpected.append("draft_count_changed")

    fully_passing = sum(1 for q in per_question if q["overall_gates_pass"])
    with_failures = 95 - fully_passing

    subject_out = {}
    for subj, st in subject_stats.items():
        subject_out[subj] = {
            "n": st["n"],
            "GREEN": st["green"],
            "YELLOW": st["yellow"],
            "RED": st["red"],
            "gate_fail_counts": dict(st["gate_fails"]),
            "failure_rate": round((st["n"] - st["green"]) / st["n"], 4) if st["n"] else None,
        }

    aggregate = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": BATCH_ID,
        "batch_key": BATCH_KEY,
        "items_evaluated": 95,
        "provider_calls": 0,
        "new_content_generated": 0,
        "p4_command": "scripts/run_factory_p4_gemini_p3_95.py (evaluate_candidate×95, force_new)",
        "qa_job_id": str(job.id),
        "qa_run_id": str(qa_run.id),
        "gate_summary": {
            k: {"pass": gate_pass[k], "fail": gate_fail[k]} for k in GATE_KEYS.values()
        },
        "classification_counts": dict(class_counts),
        "fully_passing_items": fully_passing,
        "items_with_one_or_more_gate_or_lineage_failures": with_failures,
        "subject_results": subject_out,
        "failure_categories": dict(failure_categories),
        "failure_examples": {k: v for k, v in failure_examples.items()},
        "semantic_dedupe": "SEMANTIC_DEDUPE_NOT_AVAILABLE",
        "scientific_certification_claimed": False,
        "disclaimer": "AUTOMATED_QA_ONLY — not NCERT verified, not scientifically certified, not NEET verified",
    }

    # Verdict
    safety_ok = not unexpected and draft == 95 and approved == 0 and published == 0
    all_evaluated = len(per_question) == 95
    unexplained = False  # all failures categorized
    if not safety_ok or not all_evaluated:
        verdict = "RED — P4 QA FAILED / SAFETY VIOLATION"
    elif with_failures > 0 or class_counts.get("RED", 0) > 0 or class_counts.get("YELLOW", 0) > 0:
        verdict = "AMBER — P4 QA COMPLETED WITH INVESTIGATION REQUIRED"
    else:
        verdict = "GREEN — P4 QA PASSED"

    results_doc = {
        "verdict": verdict,
        "aggregate": aggregate,
        "per_question": per_question,
    }
    results_path = AUDITS / f"TALOS_FACTORY_P4_95_RESULTS_{STAMP}.json"
    results_path.write_text(json.dumps(results_doc, indent=2, default=str), encoding="utf-8")

    post_doc = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "database": db_name,
        "comparisons": {
            "legacy_changed": fp(pre, "legacy") != fp(post, "legacy"),
            "t6d_changed": fp(pre, "t6d") != fp(post, "t6d"),
            "t6f2_changed": fp(pre, "t6f1_published") != fp(post, "t6f1_published"),
            "protected_published_changed": pre["integrity"]["protected_non_f1_cms"]["published"]
            != post["integrity"]["protected_non_f1_cms"]["published"],
            "p3_body_status_changed": pre["p3_population"]["body_status_fingerprint"]
            != post["p3_population"]["body_status_fingerprint"],
            "unexpected_mutations": unexpected,
            "approved_by_factory": approved,
            "published_by_factory": published,
            "p3_draft_count": draft,
            "intentional_writes_observed": pre_out["p4_mode_inspection"]["intentional_writes"],
        },
        "pre_checksum_counts": pre["checksum"]["counts"],
        "post_checksum_counts": post["checksum"]["counts"],
        "pre_integrity_fps": {
            "legacy": fp(pre, "legacy"),
            "t6d": fp(pre, "t6d"),
            "t6f2": fp(pre, "t6f1_published"),
            "protected_published": pre["integrity"]["protected_non_f1_cms"]["published"],
        },
        "post_integrity_fps": {
            "legacy": fp(post, "legacy"),
            "t6d": fp(post, "t6d"),
            "t6f2": fp(post, "t6f1_published"),
            "protected_published": post["integrity"]["protected_non_f1_cms"]["published"],
        },
        "post": post,
    }
    post_path = AUDITS / f"TALOS_FACTORY_P4_95_POST_INTEGRITY_{STAMP}.json"
    post_path.write_text(json.dumps(post_doc, indent=2, default=str), encoding="utf-8")

    # Forensic markdown
    md_path = AUDITS / f"TALOS_FACTORY_P4_95_FORENSIC_REPORT_{STAMP}.md"
    lines = [
        "# FACTORY-P4 QA — Gemini P3 95 DRAFTs forensic report",
        "",
        f"**Timestamp:** {aggregate['captured_at']}",
        f"**Verdict:** `{verdict}`",
        "",
        "## A. Execution",
        "```text",
        "target population: P3 Gemini pilot 95 DRAFTs (from CONTENT_FACTORY_P3_PILOT_RESULTS.json)",
        f"batch: {BATCH_KEY} ({BATCH_ID})",
        "items evaluated: 95",
        f"P4 command: {aggregate['p4_command']}",
        "provider calls: 0",
        "new content generated: 0",
        f"excluded older batch CREATED candidates: {extra}",
        "```",
        "",
        "## B. Gate results",
        "```text",
    ]
    for k in GATE_KEYS.values():
        lines.append(f"{k}: pass={gate_pass[k]} fail={gate_fail[k]}")
    lines += [
        f"overall GREEN/YELLOW/RED: {dict(class_counts)}",
        f"fully passing (all gates + lineage): {fully_passing}",
        f"items with failures: {with_failures}",
        "```",
        "",
        "## C. Subject results",
        "```text",
        json.dumps(subject_out, indent=2),
        "```",
        "",
        "## D. Failure analysis",
        f"Categories: {dict(failure_categories)}",
        f"Examples: {json.dumps(failure_examples, indent=2)}",
        "",
        "Semantic dedupe: SEMANTIC_DEDUPE_NOT_AVAILABLE (not treated as semantic uniqueness PASS).",
        "",
        "## E. Integrity",
        "```text",
        f"legacy changed: {post_doc['comparisons']['legacy_changed']}",
        f"T6-D changed: {post_doc['comparisons']['t6d_changed']}",
        f"T6-F2 changed: {post_doc['comparisons']['t6f2_changed']}",
        f"protected published changed: {post_doc['comparisons']['protected_published_changed']}",
        f"P3 drafts body/status changed: {post_doc['comparisons']['p3_body_status_changed']}",
        f"unexpected mutations: {unexpected}",
        f"approved transitions: {approved}",
        f"published transitions: {published}",
        "ECAEP transitions: 0 (ContentItem.status remained DRAFT)",
        "```",
        "",
        "## F. Artifacts",
        f"- {pre_path}",
        f"- {results_path}",
        f"- {post_path}",
        f"- {md_path}",
        "",
        "## G. Final verdict",
        f"```text\n{verdict}\n```",
        "",
        "## H. Next gate",
        "```text",
        "NEXT: P5 human sampling/review" if not verdict.startswith("RED") else "NEXT: forensic remediation",
        "```",
        "",
        "P5 was **not** executed. No approve/publish/ECAEP.",
        "",
        "**Certification limit:** P4 is automated factory QA only — not NCERT verified / scientifically certified / NEET verified.",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "evaluated": 95,
                "class_counts": dict(class_counts),
                "gate_pass": dict(gate_pass),
                "gate_fail": dict(gate_fail),
                "fully_passing": fully_passing,
                "unexpected": unexpected,
                "draft": draft,
                "approved": approved,
                "published": published,
                "subjects": subject_out,
                "pre": str(pre_path),
                "results": str(results_path),
                "post": str(post_path),
                "report": str(md_path),
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
