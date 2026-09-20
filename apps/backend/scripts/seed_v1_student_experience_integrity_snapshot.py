#!/usr/bin/env python3
"""Integrity snapshot for student experience regression audit (read-only)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import psycopg

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUTH = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
POST = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V1_POST_PUBLICATION_AUDIT_20260903.json"
DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
EXPECTED = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"


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
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


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
    return {"total": a, "published": b, "draft": c, "approved": d, "content_fp": e, "tag": tag}


def t6f2_fp(cur) -> dict:
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
          AND %s = ANY(ci.tags) AND ci.status = 'PUBLISHED'
        """,
        (tag,),
    )
    n, fp = cur.fetchone()
    return {"total": n, "content_fp": fp, "tag": tag}


def main() -> int:
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    post = json.loads(POST.read_text(encoding="utf-8"))
    ids = auth["exact_uuid_allowlist"]
    sha = hashlib.sha256(("\n".join(ids) + "\n").encode()).hexdigest()
    with psycopg.connect(DSN) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, count(*) FROM cms.content_items WHERE id = ANY(%s::uuid[]) GROUP BY status",
            (ids,),
        )
        status = dict(cur.fetchall())
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
        mismatches = []
        for qid, body, subj, chapter, topic, provider, routing, is_fallback, gc_model, blueprint in cur.fetchall():
            body = body or {}
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
            if post["post_publication_fingerprints"].get(qid) != fp:
                mismatches.append(qid)
        protected = {
            "t6d": pop_fp(cur, "physics-t6d-pilot-20260902"),
            "t6f2": t6f2_fp(cur),
            "legacy": pop_fp(cur, "legacy-physics-5000-import-20260902"),
        }
        exp = post["protected_population_integrity"]["after"]
        unchanged = {
            k: exp[k]["content_fp"] == protected[k]["content_fp"] and exp[k]["total"] == protected[k]["total"]
            for k in ("t6d", "t6f2", "legacy")
        }
        cur.execute(
            """
            SELECT count(*) FROM cms.content_items
            WHERE id = ANY(%s::uuid[])
              AND status IN ('IN_REVIEW','AI_CHECKING','HUMAN_REVIEW','REJECTED')
            """,
            (ids,),
        )
        ecaep = cur.fetchone()[0]
        cur.execute(
            """
            SELECT count(*)
            FROM assessment.attempts a
            JOIN assessment.assessments s ON s.id = a.assessment_id
            WHERE s.scope_type = 'SEED_V1'
              AND a.status = 'SUBMITTED'
              AND a.started_at > now() - interval '6 hours'
            """
        )
        recent_seed_submitted = cur.fetchone()[0]
    out = {
        "sha": sha,
        "expected": EXPECTED,
        "status": status,
        "mismatches": mismatches,
        "protected": protected,
        "unchanged": unchanged,
        "ecaep": ecaep,
        "recent_seed_submitted": recent_seed_submitted,
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
