#!/usr/bin/env python3
"""PRODUCTION SEED V1 — Live Student Practice E2E Audit (2026-09-03).

Read-only on question content / publication. May create student auth +
practice/attempt/answer session rows (expected product telemetry).
Does NOT approve, publish, generate questions, or mutate Seed/T6/legacy content.
"""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
AUTH_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
POST_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V1_POST_PUBLICATION_AUDIT_20260903.json"
OUT_JSON = AUDITS / "TALOS_PRODUCTION_SEED_V1_LIVE_PRACTICE_E2E_AUDIT_20260903.json"
OUT_MD = AUDITS / "TALOS_PRODUCTION_SEED_V1_LIVE_PRACTICE_E2E_AUDIT_REPORT_20260903.md"
EXPECTED_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"
DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
API = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:3000"
KIN = "a1f1d832-21a3-4fb6-86b8-fe07ed46ad18"
XE = "54907eea-4fcd-4855-8477-268bafe03e82"
T6D = "physics-t6d-pilot-20260902"
T6F2 = "physics-t6f1-pilot-20260902"
LEGACY = "legacy-physics-5000-import-20260902"


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
               COUNT(*) FILTER (WHERE status='APPROVED'),
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
    a, b, c, d, e = cur.fetchone()
    return {
        "total": a,
        "published": b,
        "draft": c,
        "approved": d,
        "content_fp": e,
        "tag": tag,
    }


def t6f2_fp(cur) -> dict:
    """Matches post-publication audit formula for T6-F2 (published-only hash)."""
    tag = T6F2
    cur.execute(
        """
        SELECT COUNT(*),
               md5(coalesce(string_agg(
                 ci.id::text||'|'||ci.slug||'|'||ci.status||'|'||md5(coalesce(cv.body::text,'')),
                 E'\\n' ORDER BY ci.id::text), ''))
        FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.content_type='QUESTION' AND ci.deleted_at IS NULL
          AND %s = ANY(ci.tags) AND ci.status = 'PUBLISHED'
        """,
        (tag,),
    )
    n, fp = cur.fetchone()
    return {"total": n, "content_fp": fp, "tag": tag}


def load_auth():
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    ids = list(auth["exact_uuid_allowlist"])
    computed = allowlist_sha(ids)
    return auth, ids, computed


def preflight(cur, auth, ids, computed) -> dict:
    failures = []
    if computed != EXPECTED_SHA or computed != auth["allowlist_sha256"]:
        failures.append(f"allowlist_sha mismatch computed={computed}")

    cur.execute(
        """
        SELECT ci.id::text, ci.status, (ci.deleted_at IS NOT NULL) AS deleted,
               cv.workflow_state, cv.body,
               s.name, ch.name, t.name,
               gc.provider, gc.routing_policy, gc.is_fallback, gc.model_used, qb.blueprint_key,
               (SELECT count(*) FROM cms.content_items x
                  WHERE x.concept_id = ci.concept_id AND x.content_type='QUESTION'
                    AND x.status='PUBLISHED' AND x.deleted_at IS NULL) AS pub_in_concept
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
        (ids,),
    )
    rows = {r[0]: r for r in cur.fetchall()}
    missing = [i for i in ids if i not in rows]
    if missing:
        failures.append(f"missing_uuids={missing}")

    status_c = Counter()
    subject_c = Counter()
    fps = {}
    ncert_fps = {}
    eligible = []
    not_pub = []
    post_fps = {}
    if POST_PATH.exists():
        post_doc = json.loads(POST_PATH.read_text(encoding="utf-8"))
        post_fps = post_doc.get("post_publication_fingerprints") or {}
    for i in ids:
        if i not in rows:
            continue
        (
            _id,
            status,
            deleted,
            wf,
            body,
            subj,
            chapter,
            topic,
            provider,
            routing,
            is_fallback,
            gc_model,
            blueprint,
            pub_in_concept,
        ) = rows[i]
        body = body or {}
        if isinstance(body, str):
            body = json.loads(body)
        published = status == "PUBLISHED"
        status_c[status] += 1
        subject_c[str(subj)] += 1
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
            is_fallback,
        )
        fps[i] = fp
        expected_fp = post_fps.get(i) or (auth.get("content_fingerprints") or {}).get(i)
        if expected_fp and expected_fp != fp:
            failures.append(f"content_fp_mismatch {i}")
        ncert_fps[i] = ncert_fp(body.get("ncert_evidence"))
        ok = published and not deleted
        eligible.append(
            {
                "id": i,
                "ok": ok,
                "status": status,
                "published": published,
                "deleted": deleted,
                "workflow_state": wf,
                "subject": subj,
                "chapter": chapter,
                "topic": topic,
                "pub_in_concept": pub_in_concept,
            }
        )
        if not ok:
            not_pub.append(i)

    # ECAEP for allowlist
    cur.execute(
        """
        SELECT count(*) FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.id = ANY(%s::uuid[]) AND (
          ci.status IN ('IN_REVIEW','AI_CHECKING','HUMAN_REVIEW','REJECTED','AI_CHECKED','CHANGES_REQUESTED')
          OR coalesce(cv.workflow_state,'') ILIKE '%%ECAEP%%'
        )
        """,
        (ids,),
    )
    ecaep = cur.fetchone()[0]

    cur.execute(
        """
        SELECT count(*) FROM cms.content_items
        WHERE content_type='QUESTION' AND status='PUBLISHED' AND deleted_at IS NULL
        """
    )
    total_published = cur.fetchone()[0]

    protected = {
        "t6d": pop_fp(cur, T6D),
        "t6f2": t6f2_fp(cur),
        "legacy": pop_fp(cur, LEGACY),
    }
    post = json.loads(POST_PATH.read_text(encoding="utf-8")) if POST_PATH.exists() else {}
    post_prot = (post.get("protected_population_integrity") or {}).get("after") or {}
    protected_unchanged = {}
    for key in ("t6d", "t6f2", "legacy"):
        before = post_prot.get(key) or {}
        now = protected[key]
        same_fp = before.get("content_fp") == now.get("content_fp") and before.get("total") == now.get("total")
        if key != "t6f2":
            same_fp = same_fp and before.get("published") == now.get("published")
        protected_unchanged[key] = {
            "unchanged": same_fp,
            "expected_fp": before.get("content_fp"),
            "actual_fp": now.get("content_fp"),
            "snapshot": now,
        }
        if not protected_unchanged[key]["unchanged"]:
            failures.append(f"protected_changed:{key}")

    for excl in (KIN, XE):
        cur.execute("SELECT status FROM cms.content_items WHERE id=%s::uuid", (excl,))
        r = cur.fetchone()
        if r and r[0] == "PUBLISHED":
            failures.append(f"historical_exclusion_published:{excl}")

    # unintended published outside allowlist+t6d+t6f2? just count seed batch extras
    cur.execute(
        """
        SELECT count(*) FROM cms.content_items
        WHERE content_type='QUESTION' AND status='PUBLISHED' AND deleted_at IS NULL
          AND id <> ALL(%s::uuid[])
          AND NOT (%s = ANY(tags))
          AND NOT (%s = ANY(tags))
          AND NOT (%s = ANY(tags))
        """,
        (ids, T6D, T6F2, LEGACY),
    )
    unintendedish = cur.fetchone()[0]

    return {
        "allowlist_sha256": computed,
        "allowlist_sha_ok": computed == EXPECTED_SHA,
        "found": len(rows),
        "missing": missing,
        "status_counts": dict(status_c),
        "subject_counts": dict(subject_c),
        "published_true_count": sum(1 for e in eligible if e["ok"]),
        "not_eligible": not_pub,
        "ecaep_allowlist": ecaep,
        "total_published_inventory": total_published,
        "content_fingerprints": fps,
        "fingerprint_mismatches": [f for f in failures if f.startswith("content_fp")],
        "ncert_fingerprints": ncert_fps,
        "protected": protected,
        "protected_unchanged": protected_unchanged,
        "unintended_published_outside_known_tags": unintendedish,
        "eligible_detail": eligible,
        "failures": failures,
        "concepts_with_only_seed_published": sum(1 for e in eligible if e.get("pub_in_concept") == 1),
    }


def csrf_headers(client: httpx.Client) -> dict:
    csrf = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": csrf} if csrf else {}


def register_student(client: httpx.Client) -> dict:
    email = f"seed-v1-practice-{uuid.uuid4().hex[:10]}@example.com"
    password = "PracticeTest!234"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "first_name": "Seed", "last_name": "Practice"},
    )
    if not r.is_success:
        # login fallback unique always succeeds on register for new email
        raise RuntimeError(f"register failed {r.status_code} {r.text}")
    return {"email": email, "password": password, "status": r.status_code}


def api_practice_full(client: httpx.Client, question_count: int = 30) -> dict:
    h = csrf_headers(client)
    gen = client.post(
        "/api/v1/assessments/practice",
        headers=h,
        json={"scope_type": "FULL", "question_count": question_count},
    )
    body = gen.json() if gen.content else {}
    return {"status": gen.status_code, "ok": gen.is_success, "body": body}


def api_practice_seed_v1(client: httpx.Client, question_count: int = 30) -> dict:
    h = csrf_headers(client)
    gen = client.post(
        "/api/v1/assessments/practice",
        headers=h,
        json={"scope_type": "SEED_V1", "question_count": question_count},
    )
    body = gen.json() if gen.content else {}
    return {"status": gen.status_code, "ok": gen.is_success, "body": body}


def start_attempt(client: httpx.Client, assessment_id: str) -> dict:
    h = csrf_headers(client)
    r = client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=h)
    body = r.json() if r.content else {}
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def get_attempt(client: httpx.Client, attempt_id: str) -> dict:
    r = client.get(f"/api/v1/attempts/{attempt_id}")
    body = r.json() if r.content else {}
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def persist_allowlist_assessment(cur, user_id: str, ids: list[str]) -> str:
    """Create PRACTICE assessment with exact allowlist order (audit-controlled selection).

    Uses same tables as AssessmentService._persist_assessment — does not change
    product selection code. Session telemetry only.
    """
    aid = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO assessment.assessments (
          id, assessment_type, scope_type, scope_id, title, question_count,
          marks_per_question, negative_marks_per_question, duration_minutes,
          created_by, updated_by, version
        ) VALUES (
          %s::uuid, 'PRACTICE', 'FULL', NULL, 'Seed V1 controlled practice (audit)',
          %s, 1, 0, NULL, %s::uuid, %s::uuid, 1
        )
        """,
        (aid, len(ids), user_id, user_id),
    )
    for order_no, qid in enumerate(ids):
        cur.execute(
            """
            INSERT INTO assessment.assessment_questions (id, assessment_id, content_item_id, order_no)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s)
            """,
            (str(uuid.uuid4()), aid, qid, order_no),
        )
    return aid


def get_user_id(cur, email: str) -> str:
    cur.execute("SELECT id::text FROM identity.users WHERE email=%s", (email,))
    r = cur.fetchone()
    if not r:
        raise RuntimeError(f"user not found {email}")
    return r[0]


def option_labels(q: dict) -> list[str]:
    opts = q.get("options") or []
    return [o.get("label") for o in opts if o.get("label")]


def run_api_flow(client: httpx.Client, cur, ids: list[str], email: str, auth_fps: dict) -> dict:
    failures = []
    runtime_errors = []

    # --- FULL regression (must remain broader than Seed) ---
    gen_full = api_practice_full(client, 30)
    if not gen_full["ok"]:
        failures.append({"gate": "practice_now_full_api", "detail": gen_full})
        return {"failures": failures, "practice_now_api": gen_full}

    full_assessment = gen_full["body"]["data"]
    full_meta = gen_full["body"].get("meta") or {}
    att_full = start_attempt(client, full_assessment["id"])
    if not att_full["ok"]:
        failures.append({"gate": "start_attempt_full", "detail": att_full})
        return {"failures": failures, "practice_now_api": gen_full, "start_attempt": att_full}

    full_attempt_id = att_full["body"]["data"]["id"]
    full_detail = get_attempt(client, full_attempt_id)
    full_questions = (full_detail["body"].get("data") or {}).get("questions") or []
    full_presented = [q["content_item_id"] for q in full_questions]
    allow = set(ids)
    full_outside = [i for i in full_presented if i not in allow]

    practice_now = {
        "generate_status": gen_full["status"],
        "scope_type": full_assessment.get("scope_type"),
        "assessment_id": full_assessment["id"],
        "attempt_id": full_attempt_id,
        "requested": 30,
        "delivered": len(full_questions),
        "availability_meta": full_meta,
        "presented_outside_allowlist": len(full_outside),
        "first_question_rendered_fields": {
            "has_stem": bool(full_questions[0].get("stem")) if full_questions else False,
            "option_count": len(full_questions[0].get("options") or []) if full_questions else 0,
        }
        if full_questions
        else None,
        "full_regression_broader_than_seed": (full_meta.get("available_count") or 0) > 30,
    }

    # --- SEED_V1 server-enforced isolation (product path) ---
    gen_seed = api_practice_seed_v1(client, 30)
    if not gen_seed["ok"]:
        failures.append({"gate": "practice_seed_v1_api", "detail": gen_seed})
        return {"failures": failures, "practice_now_api": practice_now, "seed_v1": gen_seed}

    seed_assessment = gen_seed["body"]["data"]
    seed_meta = gen_seed["body"].get("meta") or {}
    if seed_assessment.get("scope_type") != "SEED_V1":
        failures.append({"gate": "seed_scope_type", "detail": seed_assessment.get("scope_type")})
    if seed_meta.get("seed_v1_allowlist_sha256") != EXPECTED_SHA:
        failures.append({"gate": "seed_meta_hash", "detail": seed_meta})

    seed_att = start_attempt(client, seed_assessment["id"])
    if not seed_att["ok"]:
        failures.append({"gate": "start_attempt_seed", "detail": seed_att})
        return {
            "failures": failures,
            "practice_now_api": practice_now,
            "controlled_start": seed_att,
        }

    seed_assessment_id = seed_assessment["id"]
    seed_attempt_id = seed_att["body"]["data"]["id"]
    seed_detail = get_attempt(client, seed_attempt_id)
    seed_qs = (seed_detail["body"].get("data") or {}).get("questions") or []
    seed_presented = [q["content_item_id"] for q in seed_qs]
    firewall_ok = len(seed_presented) == 30 and set(seed_presented) == set(ids)
    if not firewall_ok:
        failures.append(
            {
                "gate": "practice_population_firewall",
                "detail": {
                    "count": len(seed_presented),
                    "outside": [i for i in seed_presented if i not in allow],
                    "missing": [i for i in ids if i not in set(seed_presented)],
                    "scope_type": seed_assessment.get("scope_type"),
                },
            }
        )

    # Map subjects from academic tree (body has no subject field)
    cur.execute(
        """
        SELECT ci.id::text, s.name, cv.body->>'correct_option', cv.body->>'explanation'
        FROM cms.content_items ci
        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        JOIN academic.concepts c ON c.id = ci.concept_id
        JOIN academic.topics t ON t.id = c.topic_id
        JOIN academic.chapters ch ON ch.id = t.chapter_id
        JOIN academic.subjects s ON s.id = ch.subject_id
        WHERE ci.id = ANY(%s::uuid[])
        """,
        (ids,),
    )
    meta_by_id = {r[0]: {"subject": r[1], "correct": r[2], "explanation": r[3]} for r in cur.fetchall()}

    by_subject: dict[str, list] = {}
    for q in seed_qs:
        # Prefer attempt payload subject (academic names), fallback DB
        raw_subj = q.get("subject")
        if isinstance(raw_subj, dict):
            raw_subj = raw_subj.get("name") or raw_subj.get("title")
        subj = raw_subj or (meta_by_id.get(q["content_item_id"]) or {}).get("subject") or "Unknown"
        by_subject.setdefault(str(subj), []).append(q)

    # Pre-submit leak check on controlled session
    seed_leak = [q["content_item_id"] for q in seed_qs if q.get("correct_option") is not None or q.get("explanation")]

    # Answer plan: Q0 Physics correct, Q1 Chemistry incorrect, Q2 Botany correct, Q3 Zoology incorrect
    # Then continue remaining with alternating for score check on first 3 of scoring demo
    picks = []
    for subj in ("Physics", "Chemistry", "Botany", "Zoology"):
        bucket = by_subject.get(subj) or []
        if not bucket:
            failures.append({"gate": "subject_coverage", "detail": f"no {subj} in controlled session"})
            continue
        picks.append((subj, bucket[0]))

    answer_evidence = []
    h = csrf_headers(client)

    # Intentionally: Physics correct, Chemistry incorrect, Botany correct, Zoology incorrect
    intent_map = {"Physics": True, "Chemistry": False, "Botany": True, "Zoology": False}

    for subj, q in picks:
        qid = q["content_item_id"]
        labels = option_labels(q)
        correct = meta_by_id[qid]["correct"]
        want_correct = intent_map[subj]
        if want_correct:
            selected = correct
        else:
            selected = next((L for L in labels if L != correct), labels[0] if labels else None)

        # Before submit evidence: no explanation in attempt payload for this q
        before = {
            "has_correct_option": q.get("correct_option") is not None,
            "has_explanation": bool(q.get("explanation")),
        }
        ans = client.post(
            f"/api/v1/attempts/{seed_attempt_id}/answers",
            headers=h,
            json={"content_item_id": qid, "selected_option": selected},
        )
        ans_body = ans.json() if ans.content else {}
        if not ans.is_success:
            failures.append({"gate": "answer_submit", "subject": subj, "detail": ans_body})
            runtime_errors.append({"severity": "HIGH", "where": "POST /answers", "body": ans_body})
        answer_evidence.append(
            {
                "subject": subj,
                "content_item_id": qid,
                "intent_correct": want_correct,
                "selected": selected,
                "stored_correct": correct,
                "http_status": ans.status_code,
                "before_submit_leak": before,
                "response_ok": ans.is_success,
            }
        )

    # Answer remaining questions for completion (deterministic alternating from stored key)
    answered_ids = {a["content_item_id"] for a in answer_evidence}
    expected_correct = sum(1 for a in answer_evidence if a["intent_correct"] and a["response_ok"])
    expected_incorrect = sum(1 for a in answer_evidence if (not a["intent_correct"]) and a["response_ok"])

    for idx, q in enumerate(seed_qs):
        qid = q["content_item_id"]
        if qid in answered_ids:
            continue
        labels = option_labels(q)
        correct = meta_by_id[qid]["correct"]
        # remaining: make correct for even index in remaining sequence
        # simpler: all remaining correct for predictable score
        selected = correct
        expected_correct += 1
        r = client.post(
            f"/api/v1/attempts/{seed_attempt_id}/answers",
            headers=h,
            json={"content_item_id": qid, "selected_option": selected},
        )
        if not r.is_success:
            failures.append({"gate": "answer_remaining", "id": qid, "detail": r.text[:300]})
            expected_correct -= 1

    # Next-question simulation: sequential order_no transitions (API state)
    cur.execute(
        """
        SELECT content_item_id::text FROM assessment.assessment_questions
        WHERE assessment_id = %s::uuid ORDER BY order_no
        """,
        (seed_assessment_id,),
    )
    ordered_ids = [r[0] for r in cur.fetchall()]
    next_q_evidence = {
        "mechanism": "client index over attempt.questions ordered by assessment_questions.order_no; Next button advances index",
        "question_count": len(seed_qs),
        "unique_ids": len(set(seed_presented)),
        "duplicates": len(seed_presented) - len(set(seed_presented)),
        "db_order_count": len(ordered_ids),
        "api_order_matches_db": seed_presented == ordered_ids,
        "transitions_tested": [
            {"from": ordered_ids[i], "to": ordered_ids[i + 1], "different": ordered_ids[i] != ordered_ids[i + 1]}
            for i in range(min(5, len(ordered_ids) - 1))
        ],
        "pass": len(set(seed_presented)) == 30 and seed_presented == ordered_ids,
    }

    submitted = client.post(f"/api/v1/attempts/{seed_attempt_id}/submit", headers=h)
    sub_body = submitted.json() if submitted.content else {}
    if not submitted.is_success:
        failures.append({"gate": "completion_submit", "detail": sub_body})
        runtime_errors.append({"severity": "BLOCKER", "where": "POST /submit", "body": sub_body})

    result = (sub_body.get("data") or {}) if submitted.is_success else {}
    review = get_attempt(client, seed_attempt_id)
    review_qs = (review["body"].get("data") or {}).get("questions") or []

    explanation_evidence = []
    for a in answer_evidence:
        rq = next((x for x in review_qs if x["content_item_id"] == a["content_item_id"]), None)
        stored_expl = meta_by_id[a["content_item_id"]]["explanation"]
        shown_expl = (rq or {}).get("explanation")
        shown_correct = (rq or {}).get("correct_option")
        explanation_evidence.append(
            {
                "subject": a["subject"],
                "content_item_id": a["content_item_id"],
                "pre_submit_had_explanation": a["before_submit_leak"]["has_explanation"],
                "post_submit_has_explanation": bool(shown_expl),
                "explanation_matches_stored": (shown_expl or "") == (stored_expl or ""),
                "correct_option_matches_stored": shown_correct == a["stored_correct"],
                "ui_contract": "explanation and correct_option only in submitted attempt payload",
            }
        )
        if a["before_submit_leak"]["has_explanation"] or a["before_submit_leak"]["has_correct_option"]:
            failures.append({"gate": "explanation_premature", "id": a["content_item_id"]})
        if not shown_expl:
            failures.append({"gate": "explanation_missing_after_submit", "id": a["content_item_id"]})
        if shown_correct != a["stored_correct"]:
            failures.append({"gate": "correct_option_mismatch", "id": a["content_item_id"]})

    # Score check
    score_ok = (
        result.get("status") == "SUBMITTED"
        and result.get("correct_count") == expected_correct
        and result.get("incorrect_count") == expected_incorrect
        and (result.get("correct_count") or 0) + (result.get("incorrect_count") or 0) + (result.get("skipped_count") or 0)
        == 30
    )
    if not score_ok and submitted.is_success:
        failures.append(
            {
                "gate": "scoring",
                "expected_correct": expected_correct,
                "expected_incorrect": expected_incorrect,
                "actual": {
                    "correct_count": result.get("correct_count"),
                    "incorrect_count": result.get("incorrect_count"),
                    "skipped_count": result.get("skipped_count"),
                    "score": result.get("score"),
                    "status": result.get("status"),
                },
            }
        )

    # DB consistency for attempt answers
    cur.execute(
        """
        SELECT aa.content_item_id::text, aa.selected_option, aa.is_correct
        FROM assessment.attempt_answers aa
        WHERE aa.attempt_id = %s::uuid
        """,
        (seed_attempt_id,),
    )
    db_answers = cur.fetchall()
    db_ok = True
    for qid, selected, is_correct in db_answers:
        exp = meta_by_id[qid]["correct"]
        if bool(is_correct) != (selected == exp):
            db_ok = False
            failures.append({"gate": "db_correctness", "id": qid, "selected": selected, "is_correct": is_correct})

    # Content mutation check for allowlist (same fingerprint formula as publication)
    cur.execute(
        """
        SELECT ci.id::text, cv.body, s.name, ch.name, t.name,
               gc.provider, gc.routing_policy, gc.is_fallback, gc.model_used, qb.blueprint_key
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
        (ids,),
    )
    mutated = []
    for qid, body, subj, chapter, topic, provider, routing, is_fallback, gc_model, blueprint in cur.fetchall():
        body = body or {}
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
            is_fallback,
        )
        if auth_fps.get(qid) and auth_fps[qid] != fp:
            mutated.append(qid)

    if mutated:
        failures.append({"gate": "content_mutation", "ids": mutated})

    return {
        "failures": failures,
        "runtime_errors": runtime_errors,
        "practice_now_api": practice_now,
        "practice_population_firewall": {
            "full_session_outside_allowlist_count": len(full_outside),
            "full_session_note": "FULL remains all PUBLISHED inventory (Seed+T6-D+T6-F2)",
            "full_regression_broader_than_seed": practice_now.get("full_regression_broader_than_seed"),
            "seed_v1_scope_type": seed_assessment.get("scope_type"),
            "seed_v1_meta": seed_meta,
            "controlled_session_assessment_id": seed_assessment_id,
            "controlled_session_attempt_id": seed_attempt_id,
            "controlled_presented_count": len(seed_presented),
            "controlled_exact_allowlist_match": firewall_ok,
            "controlled_outside": [i for i in seed_presented if i not in allow],
            "controlled_unique_ids": sorted(set(seed_presented)),
            "pre_submit_key_leak_ids": seed_leak,
            "selection_mechanism": "POST /practice scope_type=SEED_V1 → server allowlist IN (...) + PUBLISHED",
        },
        "answer_submission": {
            "subject_samples": answer_evidence,
            "correct_and_incorrect_tested": True,
            "pass": all(a["response_ok"] for a in answer_evidence) and len(answer_evidence) == 4,
        },
        "explanation_after_submit": {
            "samples": explanation_evidence,
            "pass": all(
                (not s["pre_submit_had_explanation"])
                and s["post_submit_has_explanation"]
                and s["explanation_matches_stored"]
                and s["correct_option_matches_stored"]
                for s in explanation_evidence
            )
            if explanation_evidence
            else False,
        },
        "next_question": next_q_evidence,
        "progress_and_score": {
            "expected_correct": expected_correct,
            "expected_incorrect": expected_incorrect,
            "actual": {
                "status": result.get("status"),
                "score": result.get("score"),
                "correct_count": result.get("correct_count"),
                "incorrect_count": result.get("incorrect_count"),
                "skipped_count": result.get("skipped_count"),
            },
            "pass": score_ok,
        },
        "completion": {
            "submit_http": submitted.status_code,
            "status": result.get("status"),
            "pass": result.get("status") == "SUBMITTED",
            "no_extra_questions_after": len(review_qs) == 30,
        },
        "backend_consistency": {
            "answer_rows": len(db_answers),
            "correctness_consistent": db_ok,
            "content_mutations": mutated,
            "pass": db_ok and not mutated and len(db_answers) == 30,
        },
    }


def post_integrity(cur, ids, computed) -> dict:
    cur.execute(
        """
        SELECT status, count(*) FROM cms.content_items
        WHERE id = ANY(%s::uuid[]) GROUP BY status
        """,
        (ids,),
    )
    status = dict(cur.fetchall())
    cur.execute(
        """
        SELECT count(*) FROM cms.content_items
        WHERE id = ANY(%s::uuid[]) AND (
          status IN ('IN_REVIEW','AI_CHECKING','HUMAN_REVIEW','REJECTED')
        )
        """,
        (ids,),
    )
    ecaep = cur.fetchone()[0]
    protected = {
        "t6d": pop_fp(cur, T6D),
        "t6f2": t6f2_fp(cur),
        "legacy": pop_fp(cur, LEGACY),
    }
    post = json.loads(POST_PATH.read_text(encoding="utf-8"))
    post_prot = (post.get("protected_population_integrity") or {}).get("after") or {}
    unchanged = {}
    for key in ("t6d", "t6f2", "legacy"):
        b = post_prot.get(key) or {}
        n = protected[key]
        unchanged[key] = b.get("content_fp") == n.get("content_fp") and b.get("total") == n.get("total")
    return {
        "allowlist_sha256": computed,
        "status_counts": status,
        "published": status.get("PUBLISHED", 0),
        "approved": status.get("APPROVED", 0),
        "draft": status.get("DRAFT", 0),
        "ecaep": ecaep,
        "protected": protected,
        "protected_unchanged": unchanged,
    }


def write_md(report: dict) -> str:
    v = report["verdict"]
    lines = [
        "# PRODUCTION SEED V1 — LIVE STUDENT PRACTICE E2E AUDIT REPORT",
        "",
        f"**Date:** {report['date']}",
        f"**Verdict:** {v}",
        f"**allowlist_sha256:** `{report['allowlist_hash']}`",
        "",
        "## 1. Executive Verdict",
        "",
        f"{v}. See failures/limitations below.",
        "",
        "## 2. Exact 30 population verification",
        "",
        "```json",
        json.dumps(report.get("preflight", {}).get("status_counts"), indent=2),
        "```",
        "",
        f"Subjects: {report.get('population')}",
        f"ECAEP preflight: {report.get('preflight', {}).get('ecaep_allowlist')}",
        "",
        "## 3. Practice Now click evidence",
        "",
        "UI path: `apps/web/src/app/student/dashboard/page.tsx` → `HeroPracticeCta` → `useStartPractice` →",
        "`POST /api/v1/assessments/practice` `{scope_type:FULL, question_count:30}` →",
        "`POST /api/v1/assessments/{id}/attempts` → `/student/attempts/{id}`.",
        "",
        "```json",
        json.dumps(report.get("practice_now_click"), indent=2),
        "```",
        "",
        "## 4. Application request/response path",
        "",
        "```json",
        json.dumps(report.get("request_response_path"), indent=2),
        "```",
        "",
        "## 5. Question-selection firewall",
        "",
        "```json",
        json.dumps(report.get("practice_population_firewall"), indent=2),
        "```",
        "",
        "## 6. Answer submission evidence",
        "",
        "```json",
        json.dumps(report.get("answer_submission"), indent=2),
        "```",
        "",
        "## 7. Explanation-after-submit evidence",
        "",
        "```json",
        json.dumps(report.get("explanation_after_submit"), indent=2),
        "```",
        "",
        "## 8. Next Question evidence",
        "",
        "```json",
        json.dumps(report.get("next_question"), indent=2),
        "```",
        "",
        "## 9. Score/progress evidence",
        "",
        "```json",
        json.dumps(report.get("progress_and_score"), indent=2),
        "```",
        "",
        "## 10. Completion evidence",
        "",
        "```json",
        json.dumps(report.get("completion"), indent=2),
        "```",
        "",
        "## 11. Runtime/API error audit",
        "",
        "```json",
        json.dumps(report.get("runtime_errors"), indent=2),
        "```",
        "",
        "## 12. Database consistency",
        "",
        "```json",
        json.dumps(report.get("backend_consistency"), indent=2),
        "```",
        "",
        "## 13. Post-audit integrity",
        "",
        "```json",
        json.dumps(report.get("post_audit_integrity"), indent=2),
        "```",
        "",
        "## 14. Failures and limitations",
        "",
        "### Failures",
        "",
        "```json",
        json.dumps(report.get("failures"), indent=2),
        "```",
        "",
        "### Limitations",
        "",
        "```json",
        json.dumps(report.get("limitations"), indent=2),
        "```",
        "",
        "## 15. Final verdict",
        "",
        v,
        "",
        "## 16. Exact next remediation step if not GREEN",
        "",
        report.get("remediation") or "None — GREEN.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    auth, ids, computed = load_auth()
    report: dict = {
        "audit": "TALOS_PRODUCTION_SEED_V1_LIVE_PRACTICE_E2E_AUDIT",
        "date": "2026-09-03",
        "allowlist_hash": computed,
        "population": {"total": 30, "physics": 10, "chemistry": 10, "botany": 5, "zoology": 5},
        "preflight": {},
        "practice_now_click": {},
        "request_response_path": {
            "ui_component": "apps/web/src/app/student/dashboard/page.tsx::HeroPracticeCta",
            "event_handler": "onClick → useStartPractice().mutate({scope_type:'FULL', question_count:30})",
            "hook": "apps/web/src/features/assessment/use-start-practice.ts",
            "generate_endpoint": "POST /api/v1/assessments/practice",
            "generate_payload": {"scope_type": "FULL", "question_count": 30},
            "start_attempt_endpoint": "POST /api/v1/assessments/{assessment_id}/attempts",
            "attempt_detail_endpoint": "GET /api/v1/attempts/{attempt_id}",
            "answer_endpoint": "POST /api/v1/attempts/{attempt_id}/answers",
            "submit_endpoint": "POST /api/v1/attempts/{attempt_id}/submit",
            "selection": "AssessmentRepository.published_question_ids_for_scope + sample_question_ids",
            "scoring": "AssessmentService.submit_attempt compares selected_option to body.correct_option; marks=1 neg=0",
            "explanation": "Omitted in in-progress attempt serializer; included after SUBMITTED",
            "next_question": "Client-side index over attempt.questions (Next button)",
            "completion": "POST submit → status SUBMITTED + score aggregates",
        },
        "practice_population_firewall": {},
        "answer_submission": {},
        "explanation_after_submit": {},
        "next_question": {},
        "progress_and_score": {},
        "completion": {},
        "backend_consistency": {},
        "runtime_errors": {},
        "post_audit_integrity": {},
        "failures": [],
        "limitations": [],
        "verdict": "RED",
        "remediation": None,
        "browser_e2e": {},
    }

    with psycopg.connect(DSN) as conn:
        cur = conn.cursor()
        pre = preflight(cur, auth, ids, computed)
        report["preflight"] = pre
        if pre["failures"]:
            report["failures"].extend(pre["failures"])
            report["verdict"] = "RED"
            report["remediation"] = "Fix preflight integrity failures before re-running live practice E2E."
            OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
            OUT_MD.write_text(write_md(report), encoding="utf-8")
            print(json.dumps({"verdict": "RED", "stage": "preflight", "failures": pre["failures"]}, indent=2))
            return 1

        # Health check API
        try:
            health = httpx.get(f"{API}/health", timeout=5.0)
            api_up = health.is_success
        except Exception as exc:  # noqa: BLE001
            api_up = False
            report["failures"].append(f"api_unreachable:{exc}")
            report["verdict"] = "RED"
            report["remediation"] = "Start backend: uvicorn app.main:app --reload --port 8000"
            OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
            OUT_MD.write_text(write_md(report), encoding="utf-8")
            print("API down")
            return 1

        report["preflight"]["api_health"] = api_up

        with httpx.Client(base_url=API, timeout=120.0) as client:
            student = register_student(client)
            flow = run_api_flow(client, cur, ids, student["email"], pre["content_fingerprints"])
            report["practice_now_click"] = {
                "mode": "API_EQUIVALENT_OF_HERO_CTA",
                "student": {"email": student["email"]},
                "evidence": flow.get("practice_now_api"),
                "pass": bool(flow.get("practice_now_api", {}).get("first_question_rendered_fields", {}).get("has_stem")),
                "note": "Browser click evidence filled by companion Playwright run when available",
            }
            report["practice_population_firewall"] = flow.get("practice_population_firewall")
            report["answer_submission"] = flow.get("answer_submission")
            report["explanation_after_submit"] = flow.get("explanation_after_submit")
            report["next_question"] = flow.get("next_question")
            report["progress_and_score"] = flow.get("progress_and and_score") if False else flow.get("progress_and_score")
            report["completion"] = flow.get("completion")
            report["backend_consistency"] = flow.get("backend_consistency")
            report["runtime_errors"] = {
                "items": flow.get("runtime_errors") or [],
                "blocker_count": sum(1 for e in (flow.get("runtime_errors") or []) if e.get("severity") == "BLOCKER"),
                "pass": not any(e.get("severity") in ("BLOCKER", "HIGH") for e in (flow.get("runtime_errors") or [])),
            }
            report["failures"].extend(flow.get("failures") or [])

        post = post_integrity(cur, ids, computed)
        report["post_audit_integrity"] = post
        if post["published"] != 30 or post["approved"] != 0 or post["draft"] != 0 or post["ecaep"] != 0:
            report["failures"].append({"gate": "post_integrity_status", "detail": post["status_counts"]})
        if not all(post["protected_unchanged"].values()):
            report["failures"].append({"gate": "protected_changed_post", "detail": post["protected_unchanged"]})

        conn.rollback()  # safety — commits already done for assessment insert

    report["limitations"] = [
        "FULL Practice Now continues to sample all PUBLISHED questions (~1079 including T6-D/T6-F2).",
        "SEED_V1 is an explicit separate scope; Hero 'Practice now' remains FULL; 'Practice Seed V1' CTA uses SEED_V1.",
    ]

    # Verdict
    fw = report.get("practice_population_firewall") or {}
    ans = report.get("answer_submission") or {}
    expl = report.get("explanation_after_submit") or {}
    prog = report.get("progress_and_score") or {}
    comp = report.get("completion") or {}
    back = report.get("backend_consistency") or {}
    click = report.get("practice_now_click") or {}

    blockers = []
    if not click.get("pass"):
        blockers.append("Practice Now / first question failed")
    if not fw.get("controlled_exact_allowlist_match"):
        blockers.append("SEED_V1 population firewall failed")
    if fw.get("seed_v1_scope_type") != "SEED_V1":
        blockers.append("SEED_V1 scope_type not persisted")
    if not fw.get("full_regression_broader_than_seed"):
        blockers.append("FULL regression failed — pool not broader than Seed")
    if not ans.get("pass"):
        blockers.append("Answer submission failed")
    if not expl.get("pass"):
        blockers.append("Explanation-after-submit failed")
    if not prog.get("pass"):
        blockers.append("Scoring/progress failed")
    if not comp.get("pass"):
        blockers.append("Completion failed")
    if not back.get("pass"):
        blockers.append("Backend consistency failed")
    if report["runtime_errors"].get("blocker_count", 0) > 0:
        blockers.append("Runtime blockers")
    if report["failures"] and any(
        isinstance(f, dict) and f.get("gate") in ("content_mutation", "protected_changed_post", "post_integrity_status")
        for f in report["failures"]
    ):
        blockers.append("Integrity failure")

    if blockers:
        report["verdict"] = "RED"
        report["remediation"] = "; ".join(blockers)
    else:
        report["verdict"] = "GREEN"
        report["remediation"] = None

    # Gate summary for console
    report["gate_summary"] = {
        "population": "30/30" if pre.get("published_true_count") == 30 else f"{pre.get('published_true_count')}/30",
        "practice_now": "PASS" if click.get("pass") else "FAIL",
        "first_question": "PASS" if click.get("pass") else "FAIL",
        "population_firewall_controlled": "PASS" if fw.get("controlled_exact_allowlist_match") else "FAIL",
        "population_firewall_full_scope": "BROADER_OK"
        if fw.get("full_regression_broader_than_seed")
        else "FAIL",
        "seed_scope": "PASS" if fw.get("seed_v1_scope_type") == "SEED_V1" else "FAIL",
        "answer_submission": "PASS" if ans.get("pass") else "FAIL",
        "explanation_after_submit": "PASS" if expl.get("pass") else "FAIL",
        "next_question": "PASS" if (report.get("next_question") or {}).get("pass") else "FAIL",
        "progress": "PASS" if prog.get("pass") else "FAIL",
        "scoring": "PASS" if prog.get("pass") else "FAIL",
        "completion": "PASS" if comp.get("pass") else "FAIL",
        "runtime_api": "PASS" if report["runtime_errors"].get("pass") else "FAIL",
        "database_consistency": "PASS" if back.get("pass") else "FAIL",
        "post_audit_integrity": "PASS"
        if post.get("published") == 30 and post.get("ecaep") == 0 and all(post.get("protected_unchanged", {}).values())
        else "FAIL",
        "t6d": "UNCHANGED" if post.get("protected_unchanged", {}).get("t6d") else "CHANGED",
        "t6f2": "UNCHANGED" if post.get("protected_unchanged", {}).get("t6f2") else "CHANGED",
        "ecaep": post.get("ecaep"),
    }

    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(write_md(report), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "gate_summary": report["gate_summary"], "artifacts": [str(OUT_JSON), str(OUT_MD)]}, indent=2))
    return 0 if report["verdict"] != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
