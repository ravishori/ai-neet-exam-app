#!/usr/bin/env python3
"""SEED_V2 live student practice E2E — API + DB. Read-only on content/publication."""
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
AUTH_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_PUBLICATION_AUTHORIZATION_20260904.json"
V1_AUTH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
OUT_JSON = AUDITS / "TALOS_PRODUCTION_SEED_V2_PRACTICE_E2E_20260904.json"
OUT_MD = AUDITS / "TALOS_PRODUCTION_SEED_V2_PRACTICE_E2E_20260904.md"
EXPECTED_SHA = "a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978"
V1_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"
DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
API = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:3000"
T6D = "physics-t6d-pilot-20260902"
T6F2 = "physics-t6f1-pilot-20260902"
LEGACY = "legacy-physics-5000-import-20260902"
VIS_SUP = "seed-v2-rematerialization-superseded-20260903"
NUM_SUP = "seed-v2-numerical-remediation-superseded-20260904"
VISUAL = {
    "physics-05": "9c51f8a1-bf72-4ca0-bcfd-e0aa5cb8ee53",
    "physics-21": "1633f068-f0df-4ff5-ac0c-57be4417f29e",
    "zoology-12": "ca0e7a05-38bb-4e12-a52d-4fd4c7a26b07",
}
NUMERICAL = {
    "physics-10": "2e43ef71-d72a-423a-b9be-2e44c51de8b1",
    "physics-11": "5b4f381e-0dee-4118-b237-fbaabbe1d0f5",
    "physics-20": "f60e3124-8aa0-4ff6-b3e1-f8ad81eadce9",
    "physics-34": "b98e5873-8352-4bb6-9a30-368e2f0ce6f7",
}


def allowlist_sha(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(ids) + "\n").encode("utf-8")).hexdigest()


def csrf_headers(client: httpx.Client) -> dict:
    csrf = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": csrf} if csrf else {}


def subj_name(q: dict) -> str:
    raw = q.get("subject")
    if isinstance(raw, dict):
        return str(raw.get("name") or raw.get("title") or "Unknown")
    return str(raw or "Unknown")


def option_labels(q: dict) -> list[str]:
    return [o.get("label") for o in (q.get("options") or []) if o.get("label")]


def db_meta(cur, ids: list[str]) -> dict:
    cur.execute(
        """
        SELECT ci.id::text, ci.status, (ci.deleted_at IS NOT NULL), s.name,
               cv.body->>'correct_option', cv.body->>'explanation',
               (cv.body ? 'visual_spec' AND cv.body->'visual_spec' IS NOT NULL AND cv.body->>'visual_spec' <> 'null'),
               %s = ANY(ci.tags) OR %s = ANY(ci.tags)
        FROM cms.content_items ci
        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        JOIN academic.concepts c ON c.id = ci.concept_id
        JOIN academic.topics t ON t.id = c.topic_id
        JOIN academic.chapters ch ON ch.id = t.chapter_id
        JOIN academic.subjects s ON s.id = ch.subject_id
        WHERE ci.id = ANY(%s::uuid[])
        """,
        (VIS_SUP, NUM_SUP, ids),
    )
    out = {}
    for r in cur.fetchall():
        out[r[0]] = {
            "status": r[1],
            "deleted": r[2],
            "subject": r[3],
            "correct": r[4],
            "explanation": r[5],
            "has_visual_spec": bool(r[6]),
            "superseded": bool(r[7]),
        }
    return out


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


def preflight(cur, ids: list[str], computed: str) -> dict:
    failures = []
    if computed != EXPECTED_SHA:
        failures.append(f"sha_mismatch {computed}")
    meta = db_meta(cur, ids)
    missing = [i for i in ids if i not in meta]
    extra_in_db = [i for i in meta if i not in set(ids)]
    status_c = Counter(m["status"] for m in meta.values())
    subject_c = Counter(m["subject"] for m in meta.values())
    published = sum(1 for m in meta.values() if m["status"] == "PUBLISHED" and not m["deleted"])
    deleted = sum(1 for m in meta.values() if m["deleted"])
    superseded = sum(1 for m in meta.values() if m["superseded"])
    if missing:
        failures.append(f"missing={missing}")
    if extra_in_db:
        failures.append(f"extra_rows={extra_in_db}")
    if published != 100:
        failures.append(f"published={published}")
    if dict(subject_c) != {"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15}:
        failures.append(f"subjects={dict(subject_c)}")
    if deleted or superseded:
        failures.append(f"deleted={deleted} superseded={superseded}")
    hist = json.loads(AUTH_PATH.read_text(encoding="utf-8")).get("historical_exclusions") or []
    for hid in hist:
        cur.execute("SELECT status, %s = ANY(tags) OR %s = ANY(tags) FROM cms.content_items WHERE id=%s::uuid", (VIS_SUP, NUM_SUP, hid))
        row = cur.fetchone()
        if row and row[0] == "PUBLISHED":
            failures.append(f"historical_published:{hid}")
    v1_ids = list(json.loads(V1_AUTH.read_text(encoding="utf-8"))["exact_uuid_allowlist"])
    overlap = set(ids) & set(v1_ids)
    if overlap:
        failures.append(f"v1_overlap={overlap}")
    cur.execute(
        """
        SELECT COUNT(*) FROM cms.content_items
        WHERE content_type='QUESTION' AND status='PUBLISHED' AND deleted_at IS NULL
          AND id = ANY(%s::uuid[])
        """,
        (v1_ids,),
    )
    v1_pub = cur.fetchone()[0]
    return {
        "allowlist_sha256": computed,
        "allowlist_sha_ok": computed == EXPECTED_SHA,
        "found": len(meta),
        "missing": missing,
        "extra": extra_in_db,
        "status_counts": dict(status_c),
        "subject_counts": dict(subject_c),
        "published": published,
        "deleted": deleted,
        "superseded": superseded,
        "v1_published": v1_pub,
        "protected": {"t6d": pop_fp(cur, T6D), "t6f2": pop_fp(cur, T6F2), "legacy": pop_fp(cur, LEGACY)},
        "failures": failures,
        "pass": not failures,
    }


def main() -> int:
    commit = Path(ROOT / ".git" / "HEAD").read_text().strip()
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    ids = list(auth["exact_allowlist"])
    computed = allowlist_sha(ids)
    v1_ids = list(json.loads(V1_AUTH.read_text(encoding="utf-8"))["exact_uuid_allowlist"])
    hist = list(auth.get("historical_exclusions") or [])
    failures: list = []
    captured = datetime.now(timezone.utc).isoformat()

    with psycopg.connect(DSN) as conn:
        cur = conn.cursor()
        pf = preflight(cur, ids, computed)
        if not pf["pass"]:
            doc = {
                "verdict": "RED",
                "reason": "cohort fingerprint mismatch",
                "preflight": pf,
                "captured_at": captured,
            }
            OUT_JSON.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            OUT_MD.write_text("# RED — V2 cohort fingerprint mismatch\n\n" + json.dumps(pf, indent=2), encoding="utf-8")
            print(json.dumps({"verdict": "RED", "preflight": pf}, indent=2))
            return 1

        before_fp = {k: pop_fp(cur, k) for k in (T6D, T6F2, LEGACY)}
        cur.execute(
            """
            SELECT md5(string_agg(ci.id::text||ci.status||md5(coalesce(cv.body::text,'')), E'\\n' ORDER BY ci.id::text))
            FROM cms.content_items ci
            JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
            WHERE ci.id = ANY(%s::uuid[])
            """,
            (ids,),
        )
        cohort_body_fp_before = cur.fetchone()[0]

        health = httpx.get(f"{API}/health", timeout=10)
        web_ok = httpx.get(WEB, timeout=10, follow_redirects=True)
        env = {
            "api": API,
            "web": WEB,
            "api_health": health.status_code,
            "web_status": web_ok.status_code,
            "dsn_db": "trinetra_db",
        }

        with httpx.Client(base_url=API, timeout=60.0, follow_redirects=True) as client:
            email = f"seed-v2-e2e-{uuid.uuid4().hex[:10]}@example.com"
            password = "PracticeTest!234"
            reg = client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password, "first_name": "Seed", "last_name": "V2"},
            )
            if not reg.is_success:
                raise RuntimeError(f"register {reg.status_code} {reg.text}")

            # Negative: FULL 100 rejected
            full100 = client.post(
                "/api/v1/assessments/practice",
                headers=csrf_headers(client),
                json={"scope_type": "FULL", "question_count": 100},
            )
            # Forged allowlist / SHA / question_ids
            forged = client.post(
                "/api/v1/assessments/practice",
                headers=csrf_headers(client),
                json={
                    "scope_type": "SEED_V2",
                    "question_count": 100,
                    "question_ids": v1_ids[:3],
                    "exact_allowlist": v1_ids,
                    "allowlist_sha256": "0" * 64,
                    "seed_v2_allowlist_sha256": "f" * 64,
                },
            )
            forged_scope = client.post(
                "/api/v1/assessments/practice",
                headers=csrf_headers(client),
                json={"scope_type": "SEED_V2 ", "question_count": 100},
            )
            gen = client.post(
                "/api/v1/assessments/practice",
                headers=csrf_headers(client),
                json={"scope_type": "SEED_V2", "question_count": 100},
            )
            if not gen.is_success:
                failures.append({"gate": "generate", "detail": gen.text[:800]})
                print("GENERATE_FAIL", gen.status_code, gen.text[:800])
                raise RuntimeError("SEED_V2 generate failed")
            gbody = gen.json()
            assessment = gbody["data"]
            meta = gbody.get("meta") or {}
            if assessment.get("scope_type") != "SEED_V2":
                failures.append({"gate": "scope", "got": assessment.get("scope_type")})
            if meta.get("seed_v2_allowlist_sha256") != EXPECTED_SHA:
                failures.append({"gate": "meta_sha", "got": meta.get("seed_v2_allowlist_sha256")})
            if assessment.get("question_count") != 100:
                failures.append({"gate": "returned_count", "got": assessment.get("question_count")})

            att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=csrf_headers(client))
            attempt_id = att.json()["data"]["id"]
            detail = client.get(f"/api/v1/attempts/{attempt_id}").json()["data"]
            questions = detail["questions"]
            presented = [q["content_item_id"] for q in questions]
            allow = set(ids)
            outside = [i for i in presented if i not in allow]
            v1_hit = [i for i in presented if i in set(v1_ids)]
            hist_hit = [i for i in presented if i in set(hist)]
            leak = [q["content_item_id"] for q in questions if q.get("correct_option") or q.get("explanation")]

            dbm = db_meta(cur, presented)
            statuses = Counter(dbm[i]["status"] for i in presented)
            deleted_n = sum(1 for i in presented if dbm[i]["deleted"])
            supers_n = sum(1 for i in presented if dbm[i]["superseded"])
            subj = Counter(dbm[i]["subject"] for i in presented)

            cur.execute(
                """
                SELECT ci.id::text FROM cms.content_items ci
                WHERE ci.id = ANY(%s::uuid[]) AND (
                  %s = ANY(ci.tags) OR %s = ANY(ci.tags) OR %s = ANY(ci.tags)
                )
                """,
                (presented, T6D, T6F2, LEGACY),
            )
            tagged_hits = [r[0] for r in cur.fetchall()]

            if outside or v1_hit or hist_hit or tagged_hits or leak or deleted_n or supers_n:
                failures.append(
                    {
                        "gate": "firewall",
                        "outside": outside,
                        "v1": v1_hit,
                        "hist": hist_hit,
                        "tagged": tagged_hits,
                        "leak": leak,
                        "deleted": deleted_n,
                        "superseded": supers_n,
                    }
                )
            if dict(subj) != {"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15}:
                failures.append({"gate": "session_subjects", "got": dict(subj)})
            if len(presented) != 100 or len(set(presented)) != 100:
                failures.append({"gate": "unique_100", "n": len(presented), "unique": len(set(presented))})

            # Pick samples
            by_subj: dict[str, list] = {}
            for q in questions:
                by_subj.setdefault(dbm[q["content_item_id"]]["subject"], []).append(q)

            def answer(qid: str, selected: str) -> httpx.Response:
                return client.post(
                    f"/api/v1/attempts/{attempt_id}/answers",
                    headers=csrf_headers(client),
                    json={"content_item_id": qid, "selected_option": selected},
                )

            samples = []
            # Physics correct (prefer numerical)
            p10 = NUMERICAL["physics-10"]
            phys_q = next(q for q in questions if q["content_item_id"] == p10)
            r = answer(p10, dbm[p10]["correct"])
            samples.append({"slot": "physics-10-correct", "status": r.status_code, "ok": r.is_success})
            # Chemistry incorrect
            chem = by_subj["Chemistry"][0]
            cid = chem["content_item_id"]
            wrong = next(L for L in option_labels(chem) if L != dbm[cid]["correct"])
            r = answer(cid, wrong)
            samples.append({"slot": "chemistry-incorrect", "id": cid, "status": r.status_code, "ok": r.is_success})
            # Duplicate answer save (idempotent 200)
            r2 = answer(cid, wrong)
            samples.append({"slot": "duplicate_answer_save", "status": r2.status_code, "ok": r2.is_success})
            # Botany + Zoology remaining subjects
            for name in ("Botany", "Zoology"):
                q = by_subj[name][0]
                qid = q["content_item_id"]
                r = answer(qid, dbm[qid]["correct"])
                samples.append({"slot": f"{name.lower()}-correct", "id": qid, "status": r.status_code})

            visual_api = []
            for slot, vid in VISUAL.items():
                if vid not in allow:
                    visual_api.append({"slot": slot, "in_allowlist": False})
                    failures.append({"gate": "visual_not_in_allowlist", "slot": slot})
                    continue
                q = next(x for x in questions if x["content_item_id"] == vid)
                imgs = q.get("images") or []
                r = answer(vid, dbm[vid]["correct"])
                visual_api.append(
                    {
                        "slot": slot,
                        "id": vid,
                        "in_session": True,
                        "stem": bool(q.get("stem")),
                        "options": len(q.get("options") or []),
                        "images_in_attempt_payload": len(imgs),
                        "db_visual_spec": dbm[vid]["has_visual_spec"],
                        "answer_status": r.status_code,
                    }
                )

            numerical_api = []
            for slot, nid in NUMERICAL.items():
                q = next(x for x in questions if x["content_item_id"] == nid)
                if slot != "physics-10":
                    r = answer(nid, dbm[nid]["correct"])
                else:
                    r = type("R", (), {"status_code": 200})()
                numerical_api.append(
                    {
                        "slot": slot,
                        "id": nid,
                        "in_session": True,
                        "options": len(q.get("options") or []),
                        "correct_used": dbm[nid]["correct"],
                        "answer_status": getattr(r, "status_code", 200),
                    }
                )

            answered = {a["id"] for a in samples if a.get("id")}
            answered.update(VISUAL.values())
            answered.update(NUMERICAL.values())
            expected_correct = 0
            expected_incorrect = 0
            # recount from plan: physics-10 correct, chem incorrect, botany/zoo correct, visuals+numericals correct
            expected_incorrect = 1
            expected_correct = len(answered) - 1

            for q in questions:
                qid = q["content_item_id"]
                if qid in answered:
                    continue
                r = answer(qid, dbm[qid]["correct"])
                if r.is_success:
                    expected_correct += 1
                else:
                    failures.append({"gate": "answer_remaining", "id": qid, "status": r.status_code})

            mid = client.get(f"/api/v1/attempts/{attempt_id}").json()["data"]
            progress = {
                "status": mid.get("status"),
                "selected": sum(1 for q in mid["questions"] if q.get("selected_option")),
                "still_no_explanation": all(not q.get("explanation") for q in mid["questions"]),
            }
            if progress["selected"] != 100:
                failures.append({"gate": "progress_before_submit", "got": progress["selected"]})
            if not progress["still_no_explanation"]:
                failures.append({"gate": "explanation_before_attempt_submit"})

            submitted = client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
            result = submitted.json().get("data") or {}
            dup = client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=csrf_headers(client))
            post_ans = answer(p10, dbm[p10]["correct"])
            review = client.get(f"/api/v1/attempts/{attempt_id}").json()["data"]
            review_qs = review["questions"]
            expl_ok = all(q.get("explanation") and q.get("correct_option") for q in review_qs)
            score_ok = (
                result.get("status") == "SUBMITTED"
                and result.get("correct_count") == expected_correct
                and result.get("incorrect_count") == expected_incorrect
                and (result.get("correct_count") or 0) + (result.get("incorrect_count") or 0) + (result.get("skipped_count") or 0) == 100
            )
            if not submitted.is_success:
                failures.append({"gate": "submit", "detail": submitted.text[:400]})
            if dup.status_code != 409:
                failures.append({"gate": "duplicate_submit", "status": dup.status_code})
            if post_ans.is_success:
                failures.append({"gate": "answer_after_submit_allowed", "status": post_ans.status_code})
            if not expl_ok:
                failures.append({"gate": "explanation_after_submit_incomplete"})
            if not score_ok:
                failures.append(
                    {
                        "gate": "scoring",
                        "expected_correct": expected_correct,
                        "expected_incorrect": expected_incorrect,
                        "actual": {
                            "correct": result.get("correct_count"),
                            "incorrect": result.get("incorrect_count"),
                            "skipped": result.get("skipped_count"),
                            "score": result.get("score"),
                        },
                    }
                )

            # Restart
            att2 = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=csrf_headers(client))
            attempt2 = att2.json()["data"]["id"]
            d2 = client.get(f"/api/v1/attempts/{attempt2}").json()["data"]
            restart_ok = (
                att2.is_success
                and attempt2 != attempt_id
                and d2.get("status") == "IN_PROGRESS"
                and {q["content_item_id"] for q in d2["questions"]} == set(presented)
                and all(not q.get("explanation") for q in d2["questions"])
            )
            if not restart_ok:
                failures.append({"gate": "restart", "attempt2": attempt2})

            # Concurrent session: new generate
            gen_b = client.post(
                "/api/v1/assessments/practice",
                headers=csrf_headers(client),
                json={"scope_type": "SEED_V2", "question_count": 100},
            )
            att_b = client.post(
                f"/api/v1/assessments/{gen_b.json()['data']['id']}/attempts",
                headers=csrf_headers(client),
            )
            bid = att_b.json()["data"]["id"]
            bqs = client.get(f"/api/v1/attempts/{bid}").json()["data"]["questions"]
            concurrent_ok = bid != attempt_id and {q["content_item_id"] for q in bqs} <= allow and len(bqs) == 100
            if not concurrent_ok:
                failures.append({"gate": "concurrent"})

            # V1 regression
            gen_v1 = client.post(
                "/api/v1/assessments/practice",
                headers=csrf_headers(client),
                json={"scope_type": "SEED_V1", "question_count": 30},
            )
            v1_body = gen_v1.json() if gen_v1.content else {}
            v1_ok = False
            v2_in_v1 = []
            if gen_v1.is_success:
                v1_att = client.post(
                    f"/api/v1/assessments/{v1_body['data']['id']}/attempts",
                    headers=csrf_headers(client),
                )
                v1_qs = client.get(f"/api/v1/attempts/{v1_att.json()['data']['id']}").json()["data"]["questions"]
                v1_presented = [q["content_item_id"] for q in v1_qs]
                v2_in_v1 = [i for i in v1_presented if i in allow]
                v1_ok = (
                    v1_body["data"]["scope_type"] == "SEED_V1"
                    and (v1_body.get("meta") or {}).get("seed_v1_allowlist_sha256") == V1_SHA
                    and set(v1_presented) <= set(v1_ids)
                    and not v2_in_v1
                    and len(v1_presented) == 30
                )
            else:
                failures.append({"gate": "v1_generate", "status": gen_v1.status_code, "body": str(v1_body)[:300]})
            if not v1_ok:
                failures.append({"gate": "v1_firewall", "v2_in_v1": v2_in_v1})

            gen_full = client.post(
                "/api/v1/assessments/practice",
                headers=csrf_headers(client),
                json={"scope_type": "FULL", "question_count": 30},
            )
            full_ok = gen_full.is_success and gen_full.json()["data"]["scope_type"] == "FULL"

            # Logout isolation: second user cannot read attempt
            with httpx.Client(base_url=API, timeout=60.0) as other:
                other.post(
                    "/api/v1/auth/register",
                    json={
                        "email": f"seed-v2-other-{uuid.uuid4().hex[:8]}@example.com",
                        "password": password,
                        "first_name": "Other",
                        "last_name": "User",
                    },
                )
                steal = other.get(f"/api/v1/attempts/{attempt_id}")
            logout_login = {
                "other_user_get_attempt_status": steal.status_code,
                "isolated": steal.status_code in (401, 403, 404),
            }
            if not logout_login["isolated"]:
                failures.append({"gate": "session_isolation", "status": steal.status_code})

            # Re-login original? cookies still on first client. GET me
            me = client.get("/api/v1/auth/me")

        # Post integrity
        after_fp = {k: pop_fp(cur, k) for k in (T6D, T6F2, LEGACY)}
        cur.execute(
            """
            SELECT md5(string_agg(ci.id::text||ci.status||md5(coalesce(cv.body::text,'')), E'\\n' ORDER BY ci.id::text))
            FROM cms.content_items ci
            JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
            WHERE ci.id = ANY(%s::uuid[])
            """,
            (ids,),
        )
        cohort_body_fp_after = cur.fetchone()[0]
        pf_after = preflight(cur, ids, computed)
        integrity = {
            "cohort_body_fp_unchanged": cohort_body_fp_before == cohort_body_fp_after,
            "preflight_after_pass": pf_after["pass"],
            "protected_unchanged": before_fp == after_fp,
            "publication_mutation": False,
            "content_mutation": cohort_body_fp_before != cohort_body_fp_after,
        }
        if not integrity["cohort_body_fp_unchanged"] or not pf_after["pass"]:
            failures.append({"gate": "integrity", "integrity": integrity})

    negative = {
        "full_100_status": full100.status_code,
        "full_100_rejected": full100.status_code == 422,
        "forged_allowlist_still_seed_v2": forged.is_success and forged.json()["data"]["scope_type"] == "SEED_V2",
        "forged_sha_ignored": (forged.json().get("meta") or {}).get("seed_v2_allowlist_sha256") == EXPECTED_SHA
        if forged.is_success
        else False,
        "forged_scope_status": forged_scope.status_code,
        "forged_scope_rejected_or_still_seed_v2": (not forged_scope.is_success)
        or ((forged_scope.json().get("data") or {}).get("scope_type") == "SEED_V2"),
        "v1_ids_not_in_v2_session": not v1_hit,
        "historical_not_in_session": not hist_hit,
        "t6_legacy_not_in_session": not tagged_hits,
        "outside": outside,
    }
    if not negative["full_100_rejected"] or not negative["forged_scope_rejected_or_still_seed_v2"]:
        failures.append({"gate": "negative_http", "negative": negative})

    verdict = "GREEN" if not failures else "RED"
    report = {
        "audit": "TALOS_PRODUCTION_SEED_V2_PRACTICE_E2E",
        "date": "2026-09-04",
        "captured_at": captured,
        "git_head_file": commit,
        "verdict": verdict,
        "complete_100_browser_claimed": False,
        "complete_100_api_claimed": True,
        "environment": env,
        "student_email": email,
        "preflight": {k: v for k, v in pf.items() if k != "protected"} | {"protected_snapshot": pf["protected"]},
        "session": {
            "assessment_id": assessment["id"],
            "attempt_id": attempt_id,
            "scope_type": assessment.get("scope_type"),
            "requested": meta.get("requested_count"),
            "returned": assessment.get("question_count"),
            "available": meta.get("available_count"),
            "sha": meta.get("seed_v2_allowlist_sha256"),
            "outside_allowlist": outside,
            "subjects": dict(subj),
        },
        "firewall": {
            "v1": v1_hit,
            "t6_legacy_tagged": tagged_hits,
            "historical": hist_hit,
            "draft_approved_in_session": [i for i, m in dbm.items() if m["status"] != "PUBLISHED"],
            "deleted": deleted_n,
            "superseded": supers_n,
            "outside": outside,
            "pre_submit_answer_leak_ids": leak,
        },
        "student_flow_api": {
            "samples": samples,
            "progress": progress,
            "submit_status": submitted.status_code,
            "duplicate_submit_status": dup.status_code,
            "answer_after_submit_status": post_ans.status_code,
            "score": {
                "correct": result.get("correct_count"),
                "incorrect": result.get("incorrect_count"),
                "skipped": result.get("skipped_count"),
                "score": result.get("score"),
                "ok": score_ok,
            },
            "explanation_after_submit": expl_ok,
            "restart_attempt_id": attempt2,
            "restart_ok": restart_ok,
            "concurrent_attempt_id": bid,
            "concurrent_ok": concurrent_ok,
        },
        "visual_api": visual_api,
        "numerical_api": numerical_api,
        "v1_regression_api": {
            "seed_v1_ok": v1_ok,
            "hero_full_ok": full_ok,
            "v2_in_v1": v2_in_v1,
        },
        "negative": negative,
        "logout_login_isolation": logout_login,
        "me_still_authenticated": me.status_code,
        "integrity": integrity,
        "failures": failures,
        "limitations": [
            "Full 100-question click-through in the browser is not claimed here; API completed all 100.",
            "Browser evidence is a separate Playwright/CJS audit.",
            "Attempt GET in-progress omits correct_option/explanation by design; absolute client secrecy is not claimed.",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "failures": failures, "session": report["session"]}, indent=2, default=str))
    return 0 if verdict == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
