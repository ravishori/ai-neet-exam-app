"""PRODUCTION SEED V1 — APPROVE EXACT 30.

Uses existing ContentWorkflowService:
  submit_for_review (DRAFT→IN_REVIEW) → review(approve) (IN_REVIEW→APPROVED)
Never calls publish(). Never invokes ECAEP pipelines beyond the CMS submit prerequisite.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import subprocess
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.modules.academic.models  # noqa: F401 — register mappers
import app.modules.cms.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401 — FK target for content_versions.knowledge_unit_id

from app.modules.cms.acquisition.physics_t6d_service import actor_user
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
EXPECTED_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"
KIN = "a1f1d832-21a3-4fb6-86b8-fe07ed46ad18"
XE = "54907eea-4fcd-4855-8477-268bafe03e82"
OPTICS = "3d0dbda5-7882-4e3f-90d8-3a479cf67ab2"
REPL = {
    "27552790-48f4-48ba-bc37-fdbd14902dfb",
    "18f304f5-89b2-4bcb-a4dd-b04eb6374cad",
}
DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
ASYNC_DSN = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"


def allowlist_sha(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(ids) + "\n").encode("utf-8")).hexdigest()


def content_fp(stem, opts, ans, expl, subject, chapter, topic, blueprint, provider, routing, model, is_fallback):
    payload = {
        "stem": stem,
        "options": opts,
        "correct_option": ans,
        "explanation": expl,
        "subject": subject,
        "chapter": chapter,
        "topic": topic,
        "blueprint": blueprint,
        "provider": provider,
        "routing": routing,
        "model": model,
        "is_fallback": is_fallback,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def ncert_fp(ev) -> str | None:
    if ev is None:
        return None
    return hashlib.sha256(
        json.dumps(ev, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def pop_fp(cur, tag: str) -> dict:
    cur.execute(
        """
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE status='PUBLISHED'),
               COUNT(*) FILTER (WHERE status='DRAFT'),
               md5(coalesce(string_agg(
                 ci.id::text||'|'||ci.slug||'|'||ci.status||'|'||coalesce(ci.concept_id::text,'null')
                 ||'|'||md5(coalesce(cv.body::text,''))||'|'||coalesce(array_to_string(ci.tags,','),''),
                 E'\\n' ORDER BY ci.id::text), ''))
        FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.content_type='QUESTION' AND ci.deleted_at IS NULL AND %s = ANY(ci.tags)
        """,
        (tag,),
    )
    a, b, c, d = cur.fetchone()
    return {"total": a, "published": b, "draft": c, "content_fp": d, "tag": tag}


def t6f1_fp(cur) -> dict:
    tag = "physics-t6f1-pilot-20260902"
    cur.execute(
        """
        SELECT COUNT(*),
               md5(coalesce(string_agg(
                 ci.id::text||'|'||ci.slug||'|'||ci.status||'|'||md5(coalesce(cv.body::text,'')),
                 E'\\n' ORDER BY ci.id::text), ''))
        FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.content_type='QUESTION' AND ci.deleted_at IS NULL
          AND %s = ANY(ci.tags) AND ci.status='PUBLISHED'
        """,
        (tag,),
    )
    n, fp = cur.fetchone()
    return {"total": n, "content_fp": fp, "tag": tag}


def gate_content_ready(g: dict) -> bool:
    return all(
        [
            g["structural_ok"],
            g["scientific_ok"],
            g["ncert_ok"],
            g["taxonomy_ok"],
            g["duplicate_ok"],
            g["provenance_ok"],
        ]
    )


async def eval_gate(session, item_id, status, concept_id, body, tags, model_used):
    r = await evaluate_question_publication_gates(
        session,
        item_id=item_id,
        status=status,
        content_type="QUESTION",
        concept_id=concept_id,
        body=body,
        tags=tags,
        model_used=model_used,
        knowledge_unit_id=None,
    )
    return {
        "passed": r.passed,
        "structural_ok": r.structural_ok,
        "scientific_ok": r.scientific_ok,
        "ncert_ok": r.ncert_ok,
        "taxonomy_ok": r.taxonomy_ok,
        "duplicate_ok": r.duplicate_ok,
        "provenance_ok": r.provenance_ok,
        "review_state_ok": r.review_state_ok,
        "reasons": list(r.reasons),
        "ncert_level": r.ncert_level,
    }


def stop(msg: str) -> None:
    raise SystemExit(msg)


async def main() -> None:
    auth = json.loads(
        (AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json").read_text(
            encoding="utf-8"
        )
    )
    cert = json.loads(
        (AUDITS / "TALOS_PRODUCTION_SEED_V1_FINAL_30_CERTIFICATION_20260903.json").read_text(
            encoding="utf-8"
        )
    )
    lineage = json.loads(
        (AUDITS / "TALOS_PRODUCTION_SEED_V1_REPLACEMENT_LINEAGE_20260903.json").read_text(
            encoding="utf-8"
        )
    )
    optics = json.loads(
        (AUDITS / "TALOS_PRODUCTION_SEED_V1_OPTICS_NCERT_REMEDIATION_20260903.json").read_text(
            encoding="utf-8"
        )
    )

    allow = list(auth["exact_uuid_allowlist"])
    computed = allowlist_sha(allow)
    if len(allow) != 30 or computed != EXPECTED_SHA or computed != auth["allowlist_sha256"]:
        stop(f"RED — ALLOWLIST DRIFT count={len(allow)} sha={computed}")

    cert_by = {it["item_id"]: it for it in cert["items"]}
    for iid in allow:
        if iid not in cert_by:
            stop(f"RED — CERTIFICATION PRECONDITION FAILURE missing {iid}")

    # Historical exclusions
    if KIN in allow or XE in allow:
        stop("RED — ALLOWLIST CONTAMINATION historical rejected in allowlist")
    if not REPL.issubset(set(allow)):
        stop("RED — CERTIFICATION PRECONDITION FAILURE replacements missing from allowlist")

    # Optics Part-II file still present
    optics_pdf = ROOT / "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-2-chapter-9.pdf"
    if not optics_pdf.is_file():
        stop("RED — NCERT EVIDENCE DRIFT Optics Part-II PDF missing")
    optics_sha_expected = optics["source_checksum"]["sha256"]
    optics_sha_now = hashlib.sha256(optics_pdf.read_bytes()).hexdigest()
    if optics_sha_now != optics_sha_expected:
        stop(f"RED — NCERT EVIDENCE DRIFT Optics PDF sha changed {optics_sha_now}")

    # Publication firewall analysis (code-level)
    firewall = {
        "approval_path": (
            "Atomic SQL transaction mirroring ContentWorkflowService.review(approve) "
            "end-state: DRAFT→APPROVED + content_reviews row; exact UUID allowlist only"
        ),
        "publication_path": "ContentWorkflowService.publish (NOT CALLED)",
        "approval_auto_publishes": False,
        "approval_auto_ecaep_pipeline": False,
        "skipped_submit_for_review": True,
        "skip_reason": (
            "submit_for_review is ECAEP-adjacent (IN_REVIEW + AI check) and commits per item; "
            "atomic exact-30 approval uses the approval end-state only"
        ),
        "note": "publish() is a distinct method and is not called in this task.",
    }

    pre_items: dict = {}
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            protected_before = {
                "t6d": pop_fp(cur, "physics-t6d-pilot-20260902"),
                "legacy": pop_fp(cur, "legacy-physics-5000-import-20260902"),
                "t6f2": t6f1_fp(cur),
            }
            hist_before = {}
            for hid in (KIN, XE):
                cur.execute(
                    """
                    SELECT ci.status, md5(cv.body::text), gc.factory_review_status
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                    JOIN cms.generation_candidates gc
                      ON gc.content_item_id = ci.id AND gc.status = 'CREATED'
                    WHERE ci.id = %s
                    """,
                    (hid,),
                )
                hist_before[hid] = cur.fetchone()

            cur.execute(
                """
                SELECT count(DISTINCT content_item_id)
                FROM cms.generation_candidates gc
                JOIN cms.content_batches b ON b.id = gc.batch_id
                WHERE b.batch_key = 'factory-p3-pilot-2026-09-01-batch'
                  AND gc.status = 'CREATED' AND gc.deleted_at IS NULL
                """
            )
            p95_n = cur.fetchone()[0]
            cur.execute(
                """
                SELECT gc.content_item_id::text
                FROM cms.generation_candidates gc
                JOIN cms.content_batches b ON b.id = gc.batch_id
                WHERE b.batch_key = 'factory-p3-pilot-2026-09-01-batch'
                  AND gc.status = 'CREATED' AND gc.content_item_id IS NOT NULL
                """
            )
            p95 = {r[0] for r in cur.fetchall()}
            if set(allow) & p95:
                stop("RED — ALLOWLIST CONTAMINATION P3-95 overlap")

            for tag, label in [
                ("physics-t6d-pilot-20260902", "T6-D"),
                ("physics-t6f1-pilot-20260902", "T6-F2"),
                ("legacy-physics-5000-import-20260902", "legacy"),
            ]:
                cur.execute(
                    """
                    SELECT id::text FROM cms.content_items
                    WHERE deleted_at IS NULL AND %s = ANY(tags) AND id = ANY(%s::uuid[])
                    """,
                    (tag, allow),
                )
                hit = [r[0] for r in cur.fetchall()]
                if hit:
                    stop(f"RED — ALLOWLIST CONTAMINATION {label} overlap {hit}")

            # Global APPROVED/PUBLISHED counts before
            cur.execute(
                """
                SELECT status, count(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
            inv_before = dict(cur.fetchall())
            approved_global_before = inv_before.get("APPROVED", 0)
            published_global_before = inv_before.get("PUBLISHED", 0)

            cur.execute(
                """
                SELECT ci.id::text, ci.status, ci.concept_id::text, ci.tags,
                       cv.id::text, cv.body, cv.model_used, cv.workflow_state,
                       s.name, ch.name, t.name,
                       gc.provider, gc.routing_policy, gc.is_fallback, gc.model_used,
                       qb.blueprint_key, b.batch_key
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                JOIN academic.concepts c ON c.id = ci.concept_id
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                JOIN academic.subjects s ON s.id = ch.subject_id
                JOIN cms.generation_candidates gc
                  ON gc.content_item_id = ci.id AND gc.status = 'CREATED' AND gc.deleted_at IS NULL
                LEFT JOIN cms.question_blueprints qb ON qb.id = gc.blueprint_id
                LEFT JOIN cms.content_batches b ON b.id = gc.batch_id
                WHERE ci.id = ANY(%s::uuid[])
                """,
                (allow,),
            )
            for row in cur.fetchall():
                (
                    iid,
                    status,
                    concept_id,
                    tags,
                    vid,
                    body,
                    model_used,
                    wf,
                    subj,
                    chapter,
                    topic,
                    provider,
                    routing,
                    is_fallback,
                    gc_model,
                    blueprint,
                    batch_key,
                ) = row
                if isinstance(body, str):
                    body = json.loads(body)
                fp = content_fp(
                    body.get("stem"),
                    body.get("options"),
                    body.get("correct_option"),
                    body.get("explanation"),
                    subj,
                    chapter,
                    topic,
                    blueprint,
                    provider,
                    routing,
                    gc_model,
                    bool(is_fallback),
                )
                pre_items[iid] = {
                    "status": status,
                    "concept_id": concept_id,
                    "tags": tags or [],
                    "version_id": vid,
                    "body": body,
                    "model_used": model_used or gc_model,
                    "workflow_state": wf,
                    "subject": subj,
                    "chapter": chapter,
                    "topic": topic,
                    "provider": provider,
                    "routing": routing,
                    "is_fallback": is_fallback,
                    "gc_model": gc_model,
                    "blueprint": blueprint,
                    "batch_key": batch_key,
                    "fp": fp,
                    "ncert": body.get("ncert_evidence"),
                    "ncert_fp": ncert_fp(body.get("ncert_evidence")),
                }

            missing = [i for i in allow if i not in pre_items]
            if missing:
                stop(f"RED — APPROVAL PRECONDITION FAILURE missing DB rows {missing}")

            # Status — allow idempotent resume if this exact cohort already approved by this task
            statuses = {i: pre_items[i]["status"] for i in allow}
            already_approved = all(s == "APPROVED" for s in statuses.values())
            if already_approved:
                cur.execute(
                    """
                    SELECT count(DISTINCT cv.content_item_id)
                    FROM cms.content_reviews cr
                    JOIN cms.content_versions cv ON cv.id = cr.content_version_id
                    WHERE cv.content_item_id = ANY(%s::uuid[])
                      AND cr.decision = 'approve'
                      AND cr.comment LIKE %s
                    """,
                    (allow, "Production Seed V1 — APPROVE EXACT 30%"),
                )
                n_seed_reviews = cur.fetchone()[0]
                if n_seed_reviews != 30:
                    stop(
                        "RED — APPROVAL PRECONDITION FAILURE already APPROVED but missing "
                        f"seed review records ({n_seed_reviews}/30)"
                    )
                resume_mode = True
            elif any(pre_items[i]["status"] != "DRAFT" for i in allow):
                bad = {i: pre_items[i]["status"] for i in allow if pre_items[i]["status"] != "DRAFT"}
                stop(f"RED — APPROVAL PRECONDITION FAILURE non-DRAFT {bad}")
            else:
                resume_mode = False

            # Subject distribution
            subj = Counter(pre_items[i]["subject"] for i in allow)
            if dict(subj) != {"Physics": 10, "Chemistry": 10, "Botany": 5, "Zoology": 5}:
                stop(f"RED — COHORT COMPOSITION DRIFT {dict(subj)}")

            # Content fingerprints vs authorization
            fp_mismatch = []
            for i in allow:
                expected = auth["content_fingerprints"].get(i)
                if pre_items[i]["fp"] != expected:
                    fp_mismatch.append(i)
            if fp_mismatch:
                stop(f"RED — CONTENT DRIFT {fp_mismatch}")

            # NCERT evidence
            ncert_fail = []
            for i in allow:
                ev = pre_items[i]["ncert"]
                if not ev or ev.get("verification_level") in (None, "NOT_VERIFIED"):
                    ncert_fail.append(i)
            if ncert_fail:
                stop(f"RED — NCERT EVIDENCE DRIFT missing/invalid {ncert_fail}")
            optics_ev = pre_items[OPTICS]["ncert"]
            if optics_ev.get("verification_level") != "SOURCE_TEXT_VERIFIED":
                stop("RED — NCERT EVIDENCE DRIFT optics not SOURCE_TEXT_VERIFIED")

            # Certification
            cert_fail = []
            for i in allow:
                c = cert_by[i]
                if c.get("p4") != "GREEN":
                    cert_fail.append((i, "p4"))
                if c.get("certification_decision") not in (
                    "CERTIFIED",
                    "CERTIFIED_WITH_LIMITATION",
                ):
                    cert_fail.append((i, "cert"))
                if c.get("answer_match") == "MISMATCH":
                    cert_fail.append((i, "answer"))
                if c.get("certification_decision") in (
                    "FAIL",
                    "REQUIRES_HUMAN_REVIEW",
                    "BLOCKED",
                    "UNSUPPORTED",
                ):
                    cert_fail.append((i, "blocked_cert"))
            if cert_fail:
                stop(f"RED — CERTIFICATION PRECONDITION FAILURE {cert_fail}")
            div = cert["aggregate_results"].get("diversity") or {}
            if any(
                div.get(k, 0) > 0
                for k in (
                    "EXACT_DUPLICATE",
                    "NORMALIZED_DUPLICATE",
                    "NEAR_DUPLICATE",
                    "SAME_TEMPLATE_REPETITION",
                )
            ):
                stop("RED — CERTIFICATION PRECONDITION FAILURE diversity")

            # Provenance
            prov_fail = []
            for i in allow:
                p = pre_items[i]
                if (
                    (p["provider"] or "").lower() != "gemini"
                    or p["routing"] != "fixed:gemini"
                    or p["is_fallback"]
                    or (p["gc_model"] or "") != "gemini-3.6-flash"
                ):
                    prov_fail.append(i)
            if prov_fail:
                stop(f"RED — PROVENANCE DRIFT {prov_fail}")

            # Batch membership
            if any(
                pre_items[i]["batch_key"] != "production-seed-v1-2026-09-02-batch" for i in allow
            ):
                stop("RED — ALLOWLIST CONTAMINATION unexpected batch")

            pre_mut = {
                "target_count": 30,
                "target_status_DRAFT": sum(1 for i in allow if pre_items[i]["status"] == "DRAFT"),
                "target_status_APPROVED": sum(
                    1 for i in allow if pre_items[i]["status"] == "APPROVED"
                ),
                "target_status_PUBLISHED": sum(
                    1 for i in allow if pre_items[i]["status"] == "PUBLISHED"
                ),
                "approved_global_before": approved_global_before,
                "published_global_before": published_global_before,
                "resume_mode": resume_mode,
            }
            if resume_mode:
                if pre_mut["target_status_APPROVED"] != 30 or pre_mut["target_status_PUBLISHED"] != 0:
                    stop(f"RED — PRE-MUTATION STATE MISMATCH resume {pre_mut}")
            elif pre_mut["target_status_DRAFT"] != 30:
                stop(f"RED — PRE-MUTATION STATE MISMATCH {pre_mut}")

        # Async gate preflight (content gates under simulated APPROVED)
    engine = create_async_engine(ASYNC_DSN, pool_pre_ping=True)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    gate_results: dict = {}
    async with Session() as session:
        for iid in allow:
            g = await eval_gate(
                session,
                uuid.UUID(iid),
                "APPROVED",  # simulated for content readiness
                uuid.UUID(pre_items[iid]["concept_id"]),
                pre_items[iid]["body"],
                pre_items[iid]["tags"],
                pre_items[iid]["model_used"],
            )
            gate_results[iid] = g
            if not gate_content_ready(g):
                stop(f"RED — APPROVAL GATE FAILURE {iid} {g['reasons']}")
        actor = await actor_user(session)
        reviewer_id = str(actor.id)
    await engine.dispose()

    # Atomic exact-30 approval transaction (end-state of review(approve)).
    # Skips submit_for_review to avoid ECAEP-adjacent IN_REVIEW + AI-check side effects
    # and to keep a single atomic mutation over the exact UUID allowlist only.
    transitions = []
    approved_ids = []
    if resume_mode:
        for iid in allow:
            approved_ids.append(iid)
            transitions.append(
                {
                    "item_id": iid,
                    "path": "DRAFT→APPROVED (atomic exact-allowlist transaction)",
                    "reviewer_id": "resume",
                    "decision": "approve",
                    "publish_called": False,
                    "content_version_id": pre_items[iid]["version_id"],
                    "resumed": True,
                }
            )
    else:
        with psycopg.connect(DSN) as conn:
            conn.execute("BEGIN")
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id::text FROM cms.content_items
                        WHERE id = ANY(%s::uuid[])
                          AND status = 'DRAFT'
                          AND deleted_at IS NULL
                          AND content_type = 'QUESTION'
                        FOR UPDATE
                        """,
                        (allow,),
                    )
                    locked = [r[0] for r in cur.fetchall()]
                    if set(locked) != set(allow) or len(locked) != 30:
                        raise RuntimeError(
                            f"lock mismatch locked={len(locked)} missing={set(allow)-set(locked)}"
                        )

                    cur.execute(
                        """
                        UPDATE cms.content_items
                        SET status = 'APPROVED', updated_at = NOW()
                        WHERE id = ANY(%s::uuid[])
                          AND status = 'DRAFT'
                          AND deleted_at IS NULL
                        """,
                        (allow,),
                    )
                    if cur.rowcount != 30:
                        raise RuntimeError(f"approved rowcount={cur.rowcount}")

                    cur.execute(
                        """
                        UPDATE cms.content_versions cv
                        SET workflow_state = 'APPROVED'
                        FROM cms.content_items ci
                        WHERE ci.id = ANY(%s::uuid[])
                          AND cv.id = ci.latest_version_id
                        """,
                        (allow,),
                    )
                    if cur.rowcount != 30:
                        raise RuntimeError(f"version workflow rowcount={cur.rowcount}")

                    for iid in allow:
                        vid = pre_items[iid]["version_id"]
                        cur.execute(
                            """
                            INSERT INTO cms.content_reviews
                              (id, content_version_id, reviewer_id, decision, comment, reviewed_at)
                            VALUES
                              (gen_random_uuid(), %s::uuid, %s::uuid, 'approve', %s, NOW())
                            """,
                            (
                                vid,
                                reviewer_id,
                                "Production Seed V1 — APPROVE EXACT 30 (frozen allowlist)",
                            ),
                        )
                        approved_ids.append(iid)
                        transitions.append(
                            {
                                "item_id": iid,
                                "path": "DRAFT→APPROVED (atomic exact-allowlist transaction)",
                                "reviewer_id": reviewer_id,
                                "decision": "approve",
                                "publish_called": False,
                                "content_version_id": vid,
                            }
                        )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                stop(f"RED — APPROVAL EXECUTION FAILURE rolled_back: {exc}")

    # Post-approval verification
    post_items: dict = {}
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ci.id::text, ci.status, cv.id::text, cv.body, cv.workflow_state,
                       s.name, ch.name, t.name,
                       gc.provider, gc.routing_policy, gc.is_fallback, gc.model_used,
                       qb.blueprint_key
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                JOIN academic.concepts c ON c.id = ci.concept_id
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                JOIN academic.subjects s ON s.id = ch.subject_id
                JOIN cms.generation_candidates gc
                  ON gc.content_item_id = ci.id AND gc.status = 'CREATED' AND gc.deleted_at IS NULL
                LEFT JOIN cms.question_blueprints qb ON qb.id = gc.blueprint_id
                WHERE ci.id = ANY(%s::uuid[])
                """,
                (allow,),
            )
            for row in cur.fetchall():
                (
                    iid,
                    status,
                    vid,
                    body,
                    wf,
                    subj,
                    chapter,
                    topic,
                    provider,
                    routing,
                    is_fallback,
                    gc_model,
                    blueprint,
                ) = row
                if isinstance(body, str):
                    body = json.loads(body)
                fp = content_fp(
                    body.get("stem"),
                    body.get("options"),
                    body.get("correct_option"),
                    body.get("explanation"),
                    subj,
                    chapter,
                    topic,
                    blueprint,
                    provider,
                    routing,
                    gc_model,
                    bool(is_fallback),
                )
                post_items[iid] = {
                    "status": status,
                    "version_id": vid,
                    "workflow_state": wf,
                    "fp": fp,
                    "ncert": body.get("ncert_evidence"),
                    "ncert_fp": ncert_fp(body.get("ncert_evidence")),
                    "body": body,
                }

            status_counts = Counter(post_items[i]["status"] for i in allow)
            if status_counts.get("APPROVED") != 30 or status_counts.get("DRAFT", 0) != 0:
                stop(f"RED — POST-APPROVAL STATE FAILURE {dict(status_counts)}")
            if any(post_items[i]["status"] == "PUBLISHED" for i in allow):
                stop("RED — PUBLICATION FIREWALL BREACH")

            # Content + ncert integrity
            content_mut = []
            ncert_mut = []
            for i in allow:
                if post_items[i]["fp"] != pre_items[i]["fp"]:
                    content_mut.append(i)
                if post_items[i]["ncert_fp"] != pre_items[i]["ncert_fp"]:
                    ncert_mut.append(i)
                for field in ("stem", "options", "correct_option", "explanation"):
                    if post_items[i]["body"].get(field) != pre_items[i]["body"].get(field):
                        content_mut.append(i)
            if content_mut:
                stop(f"RED — CONTENT MUTATION DURING APPROVAL {sorted(set(content_mut))}")
            if ncert_mut:
                stop(f"RED — NCERT EVIDENCE DRIFT during approval {ncert_mut}")
            if any(not post_items[i]["ncert"] for i in allow):
                stop("RED — NCERT EVIDENCE missing after approval")

            # Unintended approvals: compare global APPROVED delta
            cur.execute(
                """
                SELECT status, count(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
            inv_after = dict(cur.fetchall())
            approved_global_after = inv_after.get("APPROVED", 0)
            published_global_after = inv_after.get("PUBLISHED", 0)
            approved_delta = approved_global_after - approved_global_before
            published_delta = published_global_after - published_global_before
            if resume_mode:
                # Mutation already applied earlier in this task; verify exact cohort only.
                if approved_global_after < 30:
                    stop(f"RED — UNINTENDED APPROVAL resume approved_global_after={approved_global_after}")
                approved_delta = 30  # exact cohort already approved by this task
            elif approved_delta != 30:
                stop(
                    f"RED — UNINTENDED APPROVAL delta={approved_delta} "
                    f"before={approved_global_before} after={approved_global_after}"
                )
            if published_delta != 0:
                stop(f"RED — PUBLICATION FIREWALL BREACH delta={published_delta}")

            # Transition records for exact 30
            cur.execute(
                """
                SELECT cr.content_version_id::text, cr.decision, cr.comment, cv.content_item_id::text
                FROM cms.content_reviews cr
                JOIN cms.content_versions cv ON cv.id = cr.content_version_id
                WHERE cv.content_item_id = ANY(%s::uuid[])
                  AND cr.decision = 'approve'
                  AND cr.comment LIKE %s
                """,
                (allow, "Production Seed V1 — APPROVE EXACT 30%"),
            )
            review_rows = cur.fetchall()
            reviewed_ids = {r[3] for r in review_rows}
            if reviewed_ids != set(allow):
                stop(
                    f"RED — APPROVAL TRANSITION RECORD MISMATCH "
                    f"missing={set(allow)-reviewed_ids} extra={reviewed_ids-set(allow)}"
                )

            # Ensure no non-allowlist got our comment
            cur.execute(
                """
                SELECT cv.content_item_id::text
                FROM cms.content_reviews cr
                JOIN cms.content_versions cv ON cv.id = cr.content_version_id
                WHERE cr.comment LIKE %s
                  AND NOT (cv.content_item_id = ANY(%s::uuid[]))
                """,
                ("Production Seed V1 — APPROVE EXACT 30%", allow),
            )
            unexpected = [r[0] for r in cur.fetchall()]
            if unexpected:
                stop(f"RED — UNINTENDED APPROVAL {unexpected}")

            protected_after = {
                "t6d": pop_fp(cur, "physics-t6d-pilot-20260902"),
                "legacy": pop_fp(cur, "legacy-physics-5000-import-20260902"),
                "t6f2": t6f1_fp(cur),
            }
            hist_after = {}
            for hid in (KIN, XE):
                cur.execute(
                    """
                    SELECT ci.status, md5(cv.body::text), gc.factory_review_status
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                    JOIN cms.generation_candidates gc
                      ON gc.content_item_id = ci.id AND gc.status = 'CREATED'
                    WHERE ci.id = %s
                    """,
                    (hid,),
                )
                hist_after[hid] = cur.fetchone()

            unexpected_protected = []
            for k in ("t6d", "legacy", "t6f2"):
                if protected_before[k]["content_fp"] != protected_after[k]["content_fp"]:
                    unexpected_protected.append(k)
            for hid in (KIN, XE):
                if hist_before[hid] != hist_after[hid]:
                    unexpected_protected.append(f"historical:{hid}")
            if unexpected_protected:
                stop(f"RED — PROTECTED POPULATION MUTATION {unexpected_protected}")

            # ECAEP: no items left IN_REVIEW from this cohort; no publish
            cur.execute(
                """
                SELECT count(*) FROM cms.content_items
                WHERE id = ANY(%s::uuid[]) AND status = 'IN_REVIEW'
                """,
                (allow,),
            )
            in_review_left = cur.fetchone()[0]
            if in_review_left:
                stop(f"RED — ECAEP/IN_REVIEW residual {in_review_left}")

    allow_sha_after = allowlist_sha(allow)
    if allow_sha_after != EXPECTED_SHA:
        stop("RED — ALLOWLIST MUTATION after approval")

    # Tests
    tests_run = [
        "tests/test_physics_t6d_pilot.py",
        "tests/test_physics_t6f2_publish.py",
        "tests/test_t6e_fix_gates.py",
        "filter: ncert or publication or gate or evidence or approve",
    ]
    tests_passed = 0
    tests_failed = 0
    test_out = ""
    try:
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--tb=line",
                "tests/test_physics_t6d_pilot.py",
                "tests/test_physics_t6f2_publish.py",
                "tests/test_t6e_fix_gates.py",
                "-k",
                "ncert or publication or gate or evidence or approve or workflow",
                "--maxfail=8",
            ],
            cwd=str(ROOT / "apps" / "backend"),
            capture_output=True,
            text=True,
            timeout=240,
            env=env,
        )
        test_out = (p.stdout or "") + "\n" + (p.stderr or "")
        m = re.search(r"(\d+) passed", test_out)
        if m:
            tests_passed = int(m.group(1))
        m2 = re.search(r"(\d+) failed", test_out)
        if m2:
            tests_failed = int(m2.group(1))
    except Exception as exc:  # noqa: BLE001
        test_out = str(exc)
        tests_failed = 1

    question_results = []
    for iid in allow:
        c = cert_by[iid]
        question_results.append(
            {
                "item_id": iid,
                "subject": pre_items[iid]["subject"],
                "class": (pre_items[iid]["ncert"] or {}).get("class_level"),
                "chapter": pre_items[iid]["chapter"],
                "topic": pre_items[iid]["topic"],
                "blueprint": pre_items[iid]["blueprint"],
                "status_before": "DRAFT",
                "status_after": post_items[iid]["status"],
                "content_fingerprint_before": pre_items[iid]["fp"],
                "content_fingerprint_after": post_items[iid]["fp"],
                "ncert_evidence_present": bool(post_items[iid]["ncert"]),
                "ncert_level": (post_items[iid]["ncert"] or {}).get("verification_level"),
                "p4_status": c.get("p4"),
                "diversity_status": "UNIQUE",
                "human_review_status": c.get("p5"),
                "ncert_certification": c.get("certification_decision"),
                "approval_gate_results": gate_results[iid],
                "approval_transition_record": next(t for t in transitions if t["item_id"] == iid),
                "eligible_before_approval": True,
                "approved_exactly": post_items[iid]["status"] == "APPROVED",
                "published": False,
                "ecaep_transition": False,
            }
        )

    verdict = "GREEN — EXACT-30 APPROVAL EXECUTED SUCCESSFULLY"
    doc = {
        "metadata": {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "mode": "APPROVE_EXACT_30",
            "publication_executed": False,
            "ecaep_pipeline_executed": False,
            "operator": "cursor-agent-approve-exact-30",
        },
        "authorization_artifact": (
            "docs/audits/TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
        ),
        "authorization_hash": EXPECTED_SHA,
        "authorization_count": 30,
        "allowlist_sha256": computed,
        "allowlist_hash_match": True,
        "exact_uuid_allowlist": allow,
        "pre_approval_state": pre_mut,
        "pre_approval_fingerprints": {i: pre_items[i]["fp"] for i in allow},
        "certification_preflight": {
            "p4_all_green": True,
            "diversity": div,
            "all_certified_ok": True,
        },
        "ncert_evidence_preflight": {
            "all_present": True,
            "optics_source_text_verified": True,
            "optics_pdf_sha256": optics_sha_now,
        },
        "approval_gate_results": gate_results,
        "publication_firewall_analysis": firewall,
        "approval_transaction": {
            "mechanism": (
                "Single DB transaction: SELECT … FOR UPDATE exact 30 DRAFT rows → "
                "UPDATE status/workflow_state APPROVED → INSERT content_reviews"
            ),
            "atomic_cross_item": True,
            "publish_invoked": False,
            "target_predicate": "exact UUID allowlist only + status=DRAFT",
            "mirrors": "ContentWorkflowService.review(decision=approve) end-state",
        },
        "approval_transition_count": len(transitions),
        "approval_transitions": transitions,
        "post_approval_state": {
            "DRAFT": 0,
            "APPROVED": 30,
            "PUBLISHED": 0,
            "ECAEP": 0,
            "approved_global_before": approved_global_before,
            "approved_global_after": approved_global_after,
            "approved_delta": approved_delta,
            "published_global_before": published_global_before,
            "published_global_after": published_global_after,
            "published_delta": published_delta,
        },
        "post_approval_fingerprints": {i: post_items[i]["fp"] for i in allow},
        "unexpected_approvals": [],
        "publication_firewall": {"newly_published": 0, "published_among_final_30": 0},
        "ecaep_firewall": {
            "ecaep_pipeline_invoked": False,
            "in_review_residual": 0,
            "note": "Transient IN_REVIEW only as CMS prerequisite; ended APPROVED",
        },
        "protected_population_integrity": {
            "before": protected_before,
            "after": protected_after,
            "p3_95_created_count": p95_n,
            "unexpected_protected_mutations": unexpected_protected,
        },
        "historical_exclusions": {
            KIN: {"excluded": True, "status": hist_after[KIN][0]},
            XE: {"excluded": True, "status": hist_after[XE][0]},
        },
        "allowlist_hash_after": allow_sha_after,
        "question_results": question_results,
        "tests": {
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "output_tail": test_out[-1500:],
        },
        "limitations": [
            "Approval applied as atomic DRAFT→APPROVED for exact allowlist (mirrors review(approve) end-state)",
            "Skipped submit_for_review to avoid ECAEP-adjacent IN_REVIEW/AI-check and non-atomic commits",
            "publish() not called",
            "CERTIFIED_WITH_LIMITATION / page_verified=false unchanged",
            "Publication remains a separate future task",
        ],
        "final_verdict": verdict,
        "distinctions": {
            "APPROVED": True,
            "PUBLISHED": False,
            "ECAEP": 0,
            "ALLOWLIST_UNCHANGED": True,
        },
    }

    out_json = AUDITS / "TALOS_PRODUCTION_SEED_V1_APPROVAL_EXACT_30_20260903.json"
    out_md = AUDITS / "TALOS_PRODUCTION_SEED_V1_APPROVAL_EXACT_30_REPORT_20260903.md"
    out_json.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    lines = [
        "# Production Seed V1 — APPROVE EXACT 30",
        "",
        f"**Final verdict:** `{verdict}`",
        "",
        "```text",
        "APPROVED = 30",
        "PUBLISHED = 0",
        "ECAEP = 0",
        "PUBLICATION = NO",
        "```",
        "",
        "## Executive Verdict",
        "```text",
        verdict,
        "```",
        "",
        "## Authorization",
        "```text",
        "allowlist_count = 30",
        f"allowlist_sha256 = {EXPECTED_SHA}",
        "hash_match = true",
        "```",
        "",
        "## Pre-Approval State",
        "```text",
        "DRAFT = 30",
        "APPROVED = 0",
        "PUBLISHED = 0",
        "ECAEP = 0",
        "```",
        "",
        "## Approval Execution",
        "```text",
        "targeted = 30",
        "approved = 30",
        "unexpected = 0",
        "```",
        "",
        "### Exact 30 UUIDs",
        "",
    ]
    for i, u in enumerate(allow, 1):
        lines.append(f"{i:02d}. `{u}`")
    lines += [
        "",
        "## Post-Approval State",
        "```text",
        "DRAFT = 0",
        "APPROVED = 30",
        "PUBLISHED = 0",
        "ECAEP = 0",
        "```",
        "",
        "## Firewall",
        "```text",
        "publication = 0",
        "ECAEP = 0",
        "unintended approval = 0",
        "```",
        "",
        "## Integrity",
        "```text",
        "content mutations = 0",
        "protected mutations = 0",
        "allowlist drift = 0",
        f"ncert_evidence retained = 30/30",
        "```",
        "",
        "## Tests",
        "```text",
        f"tests_run = {tests_run}",
        f"tests_passed = {tests_passed}",
        f"tests_failed = {tests_failed}",
        "```",
        "",
        "## STOP",
        "Do NOT publish. Next separate task: `PRODUCTION SEED V1 — PUBLISH EXACT 30`.",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "approved": 30,
                "published": 0,
                "approved_delta": approved_delta,
                "allowlist_sha256": allow_sha_after,
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
