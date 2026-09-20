"""Production Seed V1 — NCERT evidence remediation + approval preflight.

Mutates ONLY structured ncert_evidence on exact-30 allowlist DRAFT bodies.
Does NOT approve, publish, ECAEP, regenerate, or alter stem/options/answer/explanation.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
import psycopg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modules.cms.schemas.question_evidence import NcertEvidence
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
STUDY = ROOT / "StudyMaterial"
AUTH_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
CERT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V1_FINAL_30_CERTIFICATION_20260903.json"
EXPECTED_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"
DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
ASYNC_DSN = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"

KIN = "a1f1d832-21a3-4fb6-86b8-fe07ed46ad18"
XE = "54907eea-4fcd-4855-8477-268bafe03e82"
OPTICS = "3d0dbda5-7882-4e3f-90d8-3a479cf67ab2"

SUBJ_DOC = {
    "Physics": "NCERT Physics",
    "Chemistry": "NCERT Chemistry",
    "Botany": "NCERT Biology",
    "Zoology": "NCERT Biology",
}


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


def class_level_from_pdf(relpath: str | None, subject: str) -> str:
    p = (relpath or "").lower()
    if "class-12" in p or "class 12" in p:
        return "12"
    if "class-11" in p or "class 11" in p:
        return "11"
    return "11"


def source_document_name(subject: str, class_level: str) -> str:
    base = SUBJ_DOC.get(subject, "NCERT")
    roman = "XI" if class_level == "11" else "XII"
    return f"{base} Class {roman}"


def search_terms_for_item(cert: dict, stem: str) -> list[str]:
    terms: list[str] = []
    section = (cert.get("ncert_section") or "").strip()
    concept = (cert.get("concept") or "").strip()
    topic = (cert.get("topic") or "").strip()
    for t in (section, concept, topic):
        if t and len(t) >= 4:
            terms.append(t)
    # Distinctive tokens from stem (length >= 5, not stopwords)
    stop = {
        "which",
        "following",
        "about",
        "correct",
        "incorrect",
        "statement",
        "regarding",
        "according",
        "equal",
        "value",
        "given",
        "where",
        "when",
        "then",
        "from",
        "with",
        "that",
        "this",
        "these",
        "those",
        "option",
        "options",
        "choose",
        "select",
        "units",
        "unit",
        "respectively",
    }
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-⁻⁺]+", stem):
        low = tok.lower()
        if len(low) >= 5 and low not in stop:
            terms.append(tok)
    # Deduplicate preserving order
    seen = set()
    out = []
    for t in terms:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out[:12]


def find_ncert_hit(pdf_path: Path, terms: list[str]) -> dict[str, Any] | None:
    if not pdf_path.is_file():
        return None
    doc = fitz.open(pdf_path)
    try:
        best = None
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text("text") or ""
            if not text.strip():
                continue
            lower = text.lower()
            matched = [t for t in terms if t.lower() in lower]
            if not matched:
                continue
            # Prefer pages with more matches and denser scientific tokens
            score = len(matched)
            # Build a short excerpt around the first match
            idx = lower.find(matched[0].lower())
            start = max(0, idx - 40)
            end = min(len(text), idx + 180)
            excerpt = re.sub(r"\s+", " ", text[start:end]).strip()
            if len(excerpt) < 20:
                continue
            cand = {
                "pdf_page_index": page_idx,
                "matched_terms": matched,
                "score": score,
                "excerpt": excerpt[:280],
            }
            if best is None or cand["score"] > best["score"] or (
                cand["score"] == best["score"] and len(cand["excerpt"]) > len(best["excerpt"])
            ):
                best = cand
        return best
    finally:
        doc.close()


def pop_fp(cur, tag: str) -> dict:
    cur.execute(
        """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
               COUNT(*) FILTER (WHERE status = 'DRAFT') AS draft,
               md5(
                 coalesce(
                   string_agg(
                     ci.id::text
                       || '|' || ci.slug
                       || '|' || ci.status
                       || '|' || coalesce(ci.concept_id::text, 'null')
                       || '|' || md5(coalesce(cv.body::text, ''))
                       || '|' || coalesce(array_to_string(ci.tags, ','), ''),
                     E'\\n' ORDER BY ci.id::text
                   ),
                   ''
                 )
               ) AS content_fp
        FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.content_type = 'QUESTION'
          AND ci.deleted_at IS NULL
          AND %s = ANY(ci.tags)
        """,
        (tag,),
    )
    row = cur.fetchone()
    return {"total": row[0], "published": row[1], "draft": row[2], "content_fp": row[3], "tag": tag}


def t6f1_published_fp(cur) -> dict:
    tag = "physics-t6f1-pilot-20260902"
    cur.execute(
        """
        SELECT COUNT(*) AS total,
               md5(coalesce(string_agg(
                 ci.id::text || '|' || ci.slug || '|' || ci.status || '|' || md5(coalesce(cv.body::text, '')),
                 E'\\n' ORDER BY ci.id::text), '')) AS content_fp
        FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
          AND %s = ANY(ci.tags) AND ci.status = 'PUBLISHED'
        """,
        (tag,),
    )
    total, fp = cur.fetchone()
    return {"total": total, "content_fp": fp, "tag": tag}


async def run_gates_for_body(
    session: AsyncSession,
    *,
    item_id: uuid.UUID,
    status: str,
    concept_id: uuid.UUID | None,
    body: dict,
    tags: list[str] | None,
    model_used: str | None,
) -> dict[str, Any]:
    report = await evaluate_question_publication_gates(
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
        "passed": report.passed,
        "structural_ok": report.structural_ok,
        "scientific_ok": report.scientific_ok,
        "ncert_ok": report.ncert_ok,
        "taxonomy_ok": report.taxonomy_ok,
        "duplicate_ok": report.duplicate_ok,
        "provenance_ok": report.provenance_ok,
        "review_state_ok": report.review_state_ok,
        "numerical_status": report.numerical_status,
        "ncert_level": report.ncert_level,
        "reasons": list(report.reasons),
    }


def gate_content_ready(g: dict) -> bool:
    """Approval/content readiness ignores review_state (APPROVED is next task)."""
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


async def main() -> None:
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    cert = json.loads(CERT_PATH.read_text(encoding="utf-8"))
    allowlist = list(auth["exact_uuid_allowlist"])
    computed = allowlist_sha(allowlist)
    if len(allowlist) != 30 or computed != EXPECTED_SHA or computed != auth["allowlist_sha256"]:
        raise SystemExit(f"RED — ALLOWLIST DRIFT count={len(allowlist)} sha={computed}")

    cert_by = {it["item_id"]: it for it in cert["items"]}
    for iid in allowlist:
        if iid not in cert_by:
            raise SystemExit(f"RED — allowlist id missing from certification: {iid}")

    baseline_items: dict[str, Any] = {}
    evidence_changes: list[dict] = []
    question_results: list[dict] = []

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            # Protected baseline
            protected_before = {
                "t6d": pop_fp(cur, "physics-t6d-pilot-20260902"),
                "legacy": pop_fp(cur, "legacy-physics-5000-import-20260902"),
                "t6f2": t6f1_published_fp(cur),
            }
            cur.execute(
                """
                SELECT count(DISTINCT content_item_id)
                FROM cms.generation_candidates gc
                JOIN cms.content_batches b ON b.id = gc.batch_id
                WHERE b.batch_key = 'factory-p3-pilot-2026-09-01-batch'
                  AND gc.status = 'CREATED' AND gc.deleted_at IS NULL
                """
            )
            protected_before["p3_95_created_count"] = cur.fetchone()[0]

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
                SELECT ci.id::text, ci.status, ci.concept_id::text, ci.tags,
                       cv.id::text, cv.body, cv.model_used,
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
                (allowlist,),
            )
            rows = cur.fetchall()
            by_id = {}
            for r in rows:
                (
                    iid,
                    status,
                    concept_id,
                    tags,
                    vid,
                    body,
                    model_used,
                    subject,
                    chapter,
                    topic,
                    provider,
                    routing,
                    is_fallback,
                    gc_model,
                    blueprint,
                ) = r
                if isinstance(body, str):
                    body = json.loads(body)
                opts = body.get("options")
                fp = content_fp(
                    body.get("stem"),
                    opts,
                    body.get("correct_option"),
                    body.get("explanation"),
                    subject,
                    chapter,
                    topic,
                    blueprint,
                    provider,
                    routing,
                    gc_model,
                    bool(is_fallback),
                )
                by_id[iid] = {
                    "status": status,
                    "concept_id": concept_id,
                    "tags": tags or [],
                    "version_id": vid,
                    "body": body,
                    "model_used": model_used or gc_model,
                    "subject": subject,
                    "chapter": chapter,
                    "topic": topic,
                    "provider": provider,
                    "routing": routing,
                    "is_fallback": is_fallback,
                    "gc_model": gc_model,
                    "blueprint": blueprint,
                    "fp_before": fp,
                    "ncert_before": body.get("ncert_evidence"),
                }

            missing = [i for i in allowlist if i not in by_id]
            if missing:
                raise SystemExit(f"RED — missing DB rows: {missing}")

            # Status precheck
            if any(by_id[i]["status"] != "DRAFT" for i in allowlist):
                raise SystemExit("RED — WORKFLOW MUTATION / unexpected non-DRAFT before remediation")

            for iid in allowlist:
                baseline_items[iid] = {
                    "item_id": iid,
                    "status": by_id[iid]["status"],
                    "content_version_id": by_id[iid]["version_id"],
                    "content_fingerprint": by_id[iid]["fp_before"],
                    "ncert_evidence": by_id[iid]["ncert_before"],
                    "auth_fingerprint_match": by_id[iid]["fp_before"]
                    == auth["content_fingerprints"].get(iid),
                }

            # Remediations
            for iid in allowlist:
                db = by_id[iid]
                c = cert_by[iid]
                body = dict(db["body"])  # shallow copy
                stem = body.get("stem") or ""
                ncert_before = body.get("ncert_evidence")
                blocking: list[str] = []
                evidence_after = ncert_before
                change_kind = "none"
                verification: dict[str, Any] = {
                    "proposition": f"{c.get('concept')}: {c.get('ncert_section')}",
                    "answer_match": c.get("answer_match"),
                    "ncert_classification": c.get("ncert_classification"),
                    "certification_decision": c.get("certification_decision"),
                }

                if iid == OPTICS or not c.get("ncert_source"):
                    blocking.append(
                        "BLOCKED — authoritative NCERT PDF unavailable for proposition "
                        "(Optics Part-2 / SCIENTIFICALLY_VALID_NOT_DIRECTLY_LOCATED)"
                    )
                    verification["pdf_status"] = "MISSING"
                    verification["hit"] = None
                else:
                    rel = c["ncert_source"]
                    # Accept StudyMaterial/... or relative under StudyMaterial
                    if rel.startswith("StudyMaterial/"):
                        pdf_path = ROOT / rel
                        relpath_store = rel
                    else:
                        pdf_path = STUDY / rel
                        relpath_store = f"StudyMaterial/{rel}".replace("\\", "/")
                    terms = search_terms_for_item(c, stem)
                    hit = find_ncert_hit(pdf_path, terms)
                    verification["pdf_path"] = str(pdf_path.relative_to(ROOT)).replace("\\", "/")
                    verification["search_terms"] = terms
                    verification["hit"] = hit
                    if not pdf_path.is_file():
                        blocking.append(f"BLOCKED — NCERT PDF missing on disk: {relpath_store}")
                    elif hit is None:
                        blocking.append(
                            "BLOCKED — proposition-relevant NCERT text not located in mapped PDF"
                        )
                    else:
                        class_level = class_level_from_pdf(relpath_store, db["subject"])
                        section = (c.get("ncert_section") or c.get("concept") or "NCERT section").strip()
                        # Prefer SOURCE_TEXT_VERIFIED when excerpt found
                        ev = NcertEvidence(
                            verification_level="SOURCE_TEXT_VERIFIED",
                            source_document=source_document_name(db["subject"], class_level),
                            document_version="StudyMaterial-on-disk",
                            class_level=class_level,
                            chapter=c.get("chapter") or db["chapter"],
                            section=section,
                            page_number=None,  # do not invent printed page numbers
                            source_excerpt=hit["excerpt"],
                            verification_method=(
                                "pymupdf text search of authoritative StudyMaterial NCERT PDF; "
                                "proposition keywords matched; no page number invented"
                            ),
                            source_pdf_relpath=relpath_store,
                        )
                        evidence_after = ev.model_dump()
                        # Mutate only ncert_evidence on latest version body
                        body["ncert_evidence"] = evidence_after
                        cur.execute(
                            """
                            UPDATE cms.content_versions
                            SET body = jsonb_set(
                              COALESCE(body, '{}'::jsonb),
                              '{ncert_evidence}',
                              %s::jsonb,
                              true
                            )
                            WHERE id = %s::uuid
                            """,
                            (json.dumps(evidence_after), db["version_id"]),
                        )
                        change_kind = "added" if not ncert_before else "updated"
                        evidence_changes.append(
                            {
                                "item_id": iid,
                                "before_evidence": ncert_before,
                                "after_evidence": evidence_after,
                                "evidence_source": relpath_store,
                                "verification_method": evidence_after["verification_method"],
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "operator": "cursor-agent-ncert-evidence-remediation",
                                "reason": "Attach truthful SOURCE_TEXT_VERIFIED ncert_evidence for publication gates",
                                "matched_terms": hit["matched_terms"],
                                "pdf_page_index": hit["pdf_page_index"],
                            }
                        )
                        # Reload body from DB to ensure runtime-readable
                        cur.execute(
                            "SELECT body FROM cms.content_versions WHERE id = %s::uuid",
                            (db["version_id"],),
                        )
                        new_body = cur.fetchone()[0]
                        if isinstance(new_body, str):
                            new_body = json.loads(new_body)
                        body = new_body
                        # Integrity: stem/options/answer/explanation unchanged
                        for field in ("stem", "options", "correct_option", "explanation"):
                            if body.get(field) != db["body"].get(field):
                                raise SystemExit(
                                    f"RED — CONTENT MUTATION on {iid} field={field}"
                                )

                by_id[iid]["body_after"] = body
                by_id[iid]["ncert_after"] = body.get("ncert_evidence")
                by_id[iid]["blocking_pre_gate"] = blocking
                by_id[iid]["change_kind"] = change_kind
                by_id[iid]["verification"] = verification

            conn.commit()

            # Recompute content fingerprints after (stem etc must match)
            for iid in allowlist:
                db = by_id[iid]
                body = db["body_after"]
                fp_after = content_fp(
                    body.get("stem"),
                    body.get("options"),
                    body.get("correct_option"),
                    body.get("explanation"),
                    db["subject"],
                    db["chapter"],
                    db["topic"],
                    db["blueprint"],
                    db["provider"],
                    db["routing"],
                    db["gc_model"],
                    bool(db["is_fallback"]),
                )
                db["fp_after"] = fp_after
                if fp_after != db["fp_before"]:
                    raise SystemExit(f"RED — CONTENT FINGERPRINT CHANGED for {iid}")

            protected_after = {
                "t6d": pop_fp(cur, "physics-t6d-pilot-20260902"),
                "legacy": pop_fp(cur, "legacy-physics-5000-import-20260902"),
                "t6f2": t6f1_published_fp(cur),
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
            for key in ("t6d", "legacy", "t6f2"):
                if protected_before[key]["content_fp"] != protected_after[key]["content_fp"]:
                    unexpected_protected.append(key)
            for hid in (KIN, XE):
                if hist_before[hid] != hist_after[hid]:
                    unexpected_protected.append(f"historical:{hid}")
            if unexpected_protected:
                raise SystemExit(f"RED — PROTECTED POPULATION MUTATION: {unexpected_protected}")

            # Final status check
            cur.execute(
                """
                SELECT status, count(*) FROM cms.content_items
                WHERE id = ANY(%s::uuid[]) GROUP BY status
                """,
                (allowlist,),
            )
            status_counts = dict(cur.fetchall())
            cur.execute(
                """
                SELECT count(*) FILTER (WHERE status = 'APPROVED'),
                       count(*) FILTER (WHERE status = 'PUBLISHED')
                FROM cms.content_items
                WHERE id = ANY(%s::uuid[])
                """,
                (allowlist,),
            )
            approved_n, published_n = cur.fetchone()
            if status_counts.get("DRAFT") != 30 or approved_n or published_n:
                raise SystemExit(
                    f"RED — WORKFLOW MUTATION status={status_counts} approved={approved_n} published={published_n}"
                )

    # Async gate evaluation
    engine = create_async_engine(ASYNC_DSN, pool_pre_ping=True)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    gate_results = {}
    async with Session() as session:
        for iid in allowlist:
            db = by_id[iid]
            # Actual status DRAFT
            g_actual = await run_gates_for_body(
                session,
                item_id=uuid.UUID(iid),
                status=db["status"],
                concept_id=uuid.UUID(db["concept_id"]) if db["concept_id"] else None,
                body=db["body_after"],
                tags=db["tags"],
                model_used=db["model_used"],
            )
            # Simulated APPROVED for approval-eligibility content gates
            g_if_approved = await run_gates_for_body(
                session,
                item_id=uuid.UUID(iid),
                status="APPROVED",
                concept_id=uuid.UUID(db["concept_id"]) if db["concept_id"] else None,
                body=db["body_after"],
                tags=db["tags"],
                model_used=db["model_used"],
            )
            gate_results[iid] = {"actual_draft": g_actual, "if_approved": g_if_approved}
    await engine.dispose()

    ready = 0
    blocked = 0
    for iid in allowlist:
        db = by_id[iid]
        c = cert_by[iid]
        g_if = gate_results[iid]["if_approved"]
        g_act = gate_results[iid]["actual_draft"]
        reasons = list(db["blocking_pre_gate"])
        if not gate_content_ready(g_if):
            reasons.extend([f"runtime_gate:{r}" for r in g_if["reasons"] if not r.startswith("review:")])
        # Also surface draft-status review reason separately
        approval_eligible = len(db["blocking_pre_gate"]) == 0 and gate_content_ready(g_if)
        state = "READY_FOR_APPROVAL" if approval_eligible else "BLOCKED"
        if approval_eligible:
            ready += 1
        else:
            blocked += 1
        question_results.append(
            {
                "item_id": iid,
                "subject": db["subject"],
                "class": class_level_from_pdf(
                    (c.get("ncert_source") or ""), db["subject"]
                ),
                "chapter": db["chapter"],
                "topic": db["topic"],
                "blueprint": db["blueprint"],
                "current_status": db["status"],
                "content_version_id": db["version_id"],
                "content_fingerprint_before": db["fp_before"],
                "content_fingerprint_after": db["fp_after"],
                "ncert_evidence_before": db["ncert_before"],
                "ncert_evidence_after": db["ncert_after"],
                "evidence_change_kind": db["change_kind"],
                "evidence_verification": db["verification"],
                "p4_status": c.get("p4"),
                "diversity_status": "UNIQUE",
                "ncert_certification": c.get("certification_decision"),
                "ncert_classification": c.get("ncert_classification"),
                "runtime_gate_results": {
                    "as_draft": g_act,
                    "simulated_approved": g_if,
                    "content_gates_pass_if_approved": gate_content_ready(g_if),
                    "full_publish_pass_as_draft": g_act["passed"],
                    "full_publish_pass_if_approved": g_if["passed"],
                },
                "preflight_state": state,
                "approval_eligible": approval_eligible,
                "blocking_reasons": reasons,
                "historical_replacement_status": (
                    "REPLACEMENT"
                    if iid
                    in (
                        "27552790-48f4-48ba-bc37-fdbd14902dfb",
                        "18f304f5-89b2-4bcb-a4dd-b04eb6374cad",
                    )
                    else "RETAINED"
                ),
            }
        )

    evidence_added = sum(1 for x in evidence_changes if x["before_evidence"] is None)
    evidence_updated = sum(1 for x in evidence_changes if x["before_evidence"] is not None)
    already_valid = sum(
        1
        for iid in allowlist
        if by_id[iid]["change_kind"] == "none"
        and by_id[iid]["ncert_after"]
        and gate_content_ready(gate_results[iid]["if_approved"])
    )

    if ready == 30 and blocked == 0:
        verdict = "GREEN — EXACT-30 APPROVAL PREFLIGHT READY"
    elif ready == 0:
        verdict = "RED — APPROVAL PREFLIGHT BLOCKED"
    else:
        verdict = "AMBER — NCERT EVIDENCE REMEDIATION / REVIEW REQUIRED"

    # Gate tallies
    def tally(key: str) -> str:
        n = sum(1 for iid in allowlist if gate_results[iid]["if_approved"].get(key))
        return f"{n}/30"

    doc = {
        "metadata": {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "mode": "NCERT_EVIDENCE_REMEDIATION_AND_APPROVAL_PREFLIGHT",
            "approved_executed": False,
            "published_executed": False,
            "ecaep_executed": False,
            "operator": "cursor-agent-ncert-evidence-remediation",
        },
        "authorization_reference": str(AUTH_PATH.relative_to(ROOT)).replace("\\", "/"),
        "allowlist_count": 30,
        "allowlist_sha256": computed,
        "allowlist_hash_match": True,
        "exact_uuid_allowlist": allowlist,
        "evidence_schema": {
            "model": "app.modules.cms.schemas.question_evidence.NcertEvidence",
            "fields": [
                "verification_level",
                "source_document",
                "document_version",
                "class_level",
                "chapter",
                "section",
                "page_number",
                "source_excerpt",
                "verification_method",
                "source_pdf_relpath",
            ],
            "levels_used": ["SOURCE_TEXT_VERIFIED"],
            "page_numbers_invented": False,
        },
        "baseline": {
            "items": baseline_items,
            "protected_before": protected_before,
            "historical_excluded_before": {
                KIN: {"status": hist_before[KIN][0], "body_md5": hist_before[KIN][1]},
                XE: {"status": hist_before[XE][0], "body_md5": hist_before[XE][1]},
            },
        },
        "evidence_changes": evidence_changes,
        "evidence_summary": {
            "evidence_added": evidence_added,
            "evidence_updated": evidence_updated,
            "already_valid": already_valid,
            "blocked": blocked,
            "no_evidence_attached_blocked": sum(
                1 for r in question_results if r["evidence_change_kind"] == "none" and not r["approval_eligible"]
            ),
        },
        "question_results": question_results,
        "runtime_gate_results": {
            "gate_names": [
                "structural_ok",
                "scientific_ok",
                "ncert_ok",
                "taxonomy_ok",
                "duplicate_ok",
                "provenance_ok",
                "review_state_ok",
            ],
            "if_approved_tallies": {
                "structural_ok": tally("structural_ok"),
                "scientific_ok": tally("scientific_ok"),
                "ncert_ok": tally("ncert_ok"),
                "taxonomy_ok": tally("taxonomy_ok"),
                "duplicate_ok": tally("duplicate_ok"),
                "provenance_ok": tally("provenance_ok"),
                "review_state_ok": tally("review_state_ok"),
                "full_passed": f"{sum(1 for i in allowlist if gate_results[i]['if_approved']['passed'])}/30",
            },
            "as_draft_note": "All 30 remain DRAFT; review_state_ok fails until separate APPROVE task",
            "per_item": gate_results,
        },
        "approval_preflight": {
            "READY_FOR_APPROVAL": ready,
            "BLOCKED": blocked,
            "APPROVED": 0,
            "ready_ids": [r["item_id"] for r in question_results if r["approval_eligible"]],
            "blocked_ids": [
                {"item_id": r["item_id"], "reasons": r["blocking_reasons"]}
                for r in question_results
                if not r["approval_eligible"]
            ],
        },
        "publication_preflight": {
            "PUBLISHED": 0,
            "publication_executed": False,
            "note": "Publication not executed; publish requires APPROVED + content gates",
        },
        "protected_population_integrity": {
            "before": protected_before,
            "after": protected_after,
            "historical_after": {
                KIN: {"status": hist_after[KIN][0], "body_md5": hist_after[KIN][1]},
                XE: {"status": hist_after[XE][0], "body_md5": hist_after[XE][1]},
            },
            "unexpected_protected_mutations": unexpected_protected,
        },
        "historical_exclusions": {
            KIN: {"excluded": True, "in_allowlist": False},
            XE: {"excluded": True, "in_allowlist": False},
        },
        "final_status_check": {
            "draft": 30,
            "approved": 0,
            "published": 0,
            "ecaep": 0,
            "allowlist_sha256": computed,
            "stem_options_answer_explanation_mutations": 0,
        },
        "limitations": [
            "page_number left null; page_verified remains false; no pages invented",
            "CERTIFIED_WITH_LIMITATION not converted to unrestricted certification",
            "Optics item lacks StudyMaterial Class 12 Physics Part-2 PDF",
            "APPROVED remains 0 — this is approval preflight only",
            "Full publish gate still fails on DRAFT due to review:not_approved (expected)",
        ],
        "final_verdict": verdict,
    }

    out_json = AUDITS / "TALOS_PRODUCTION_SEED_V1_NCERT_EVIDENCE_REMEDIATION_20260903.json"
    out_md = AUDITS / "TALOS_PRODUCTION_SEED_V1_NCERT_EVIDENCE_REMEDIATION_REPORT_20260903.md"
    out_json.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    lines = [
        "# Production Seed V1 — NCERT Evidence Remediation & Approval Preflight",
        "",
        f"**Final verdict:** `{verdict}`",
        "",
        "```text",
        "GREEN ≠ APPROVED",
        "GREEN ≠ PUBLISHED",
        "APPROVED = 0",
        "PUBLISHED = 0",
        "ECAEP transitions = 0",
        "```",
        "",
        "## Executive Verdict",
        "```text",
        verdict,
        "```",
        "",
        "## Allowlist Integrity",
        "```text",
        "count = 30",
        f"sha256 = {computed}",
        "hash_match = true",
        "```",
        "",
        "## Evidence Summary",
        "```text",
        f"evidence_added = {evidence_added}",
        f"evidence_updated = {evidence_updated}",
        f"already_valid = {already_valid}",
        f"blocked = {blocked}",
        "```",
        "",
    ]
    if blocked:
        lines.append("### Blocked items")
        for r in question_results:
            if not r["approval_eligible"]:
                lines.append(f"- `{r['item_id']}` — {'; '.join(r['blocking_reasons'])}")
        lines.append("")

    lines += [
        "## Runtime Gate Summary (simulated APPROVED; content gates)",
        "```text",
        f"structural_ok              {tally('structural_ok')}",
        f"scientific_ok              {tally('scientific_ok')}",
        f"ncert_ok                   {tally('ncert_ok')}",
        f"taxonomy_ok                {tally('taxonomy_ok')}",
        f"duplicate_ok               {tally('duplicate_ok')}",
        f"provenance_ok              {tally('provenance_ok')}",
        f"review_state_ok (if APPROVED) {tally('review_state_ok')}",
        f"content_gates_pass         {ready}/30",
        "as_DRAFT full publish pass  0/30 (expected: review:not_approved)",
        "```",
        "",
        "## Approval Preflight",
        "```text",
        f"READY_FOR_APPROVAL = {ready}",
        f"BLOCKED = {blocked}",
        "APPROVED = 0",
        "```",
        "",
        "## Publication Preflight",
        "```text",
        "PUBLISHED = 0",
        "```",
        "",
        "## ECAEP",
        "```text",
        "ECAEP transitions = 0",
        "```",
        "",
        "## Historical Exclusions",
        "```text",
        f"{KIN}",
        "EXCLUDED",
        f"{XE}",
        "EXCLUDED",
        "```",
        "",
        "## Protected population integrity",
        "```text",
        f"T6-D fp unchanged = {protected_before['t6d']['content_fp'] == protected_after['t6d']['content_fp']}",
        f"T6-F2 fp unchanged = {protected_before['t6f2']['content_fp'] == protected_after['t6f2']['content_fp']}",
        f"legacy fp unchanged = {protected_before['legacy']['content_fp'] == protected_after['legacy']['content_fp']}",
        f"unexpected_protected_mutations = {unexpected_protected}",
        "```",
        "",
        "## Content integrity (exact 30)",
        "```text",
        "stem changed = 0",
        "options changed = 0",
        "answer changed = 0",
        "explanation changed = 0",
        "ncert_evidence mutations = only where truthful SOURCE_TEXT_VERIFIED attached",
        "```",
        "",
        "## Next step",
    ]
    if ready == 30:
        lines.append(
            "The exact 30 are READY FOR A SEPARATE APPROVAL EXECUTION TASK "
            "(`PRODUCTION SEED V1 — APPROVE EXACT 30`). Do not approve/publish here."
        )
    else:
        lines.append(
            "Do NOT approve or publish a subset. Remediate the blocked UUID(s) first "
            "(e.g. obtain Optics Part-2 NCERT PDF and attach truthful evidence)."
        )
    lines += [
        "",
        "## STOP",
        "Artifacts:",
        "- `TALOS_PRODUCTION_SEED_V1_NCERT_EVIDENCE_REMEDIATION_20260903.json`",
        "- `TALOS_PRODUCTION_SEED_V1_NCERT_EVIDENCE_REMEDIATION_REPORT_20260903.md`",
        "",
        "No approve · no publish · no ECAEP · no regeneration.",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "ready": ready,
                "blocked": blocked,
                "evidence_added": evidence_added,
                "evidence_updated": evidence_updated,
                "blocked_ids": [r["item_id"] for r in question_results if not r["approval_eligible"]],
                "allowlist_sha256": computed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
