#!/usr/bin/env python3
"""Independent scoring validation for Practice sessions.

Does not modify question content. Uses only PUBLISHED inventory.
Verifies server score against a local recomputation of marks.
Also documents 30-question Gate B status (BLOCKED if pilot still DRAFT).
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[3]
API = "http://localhost:8000"
DB = "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
PILOT = "phase-d-30-mcq-authorized-20260825"


def pool_evidence() -> dict:
    eng = create_engine(DB)
    with eng.connect() as conn:
        published = conn.execute(
            text(
                """
                SELECT count(*) FROM cms.content_items
                WHERE content_type='QUESTION' AND status='PUBLISHED' AND deleted_at IS NULL
                """
            )
        ).scalar()
        pilot = dict(
            conn.execute(
                text(
                    """
                    SELECT ci.status, count(DISTINCT ci.id)
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                    JOIN cms.content_version_knowledge_units cvku ON cvku.content_version_id = cv.id
                    JOIN knowledge.knowledge_units ku ON ku.id = cvku.knowledge_unit_id
                    JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                    JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                    WHERE j.pilot_run_id = :run AND ci.deleted_at IS NULL
                    GROUP BY ci.status
                    """
                ),
                {"run": PILOT},
            ).fetchall()
        )
    return {"published_pool": published, "pilot_by_status": pilot, "pilot_run_id": PILOT}


def main() -> int:
    evidence = pool_evidence()
    print("POOL", json.dumps(evidence, indent=2))
    gate_b = (
        "BLOCKED"
        if evidence["pilot_by_status"].get("PUBLISHED", 0) < 30
        else "READY"
    )
    print(
        "GATE_B_30",
        json.dumps(
            {
                "status": gate_b,
                "reason": (
                    "Phase-D pilot not PUBLISHED via ECAEP; practice pool is PUBLISHED-only. "
                    "Auto-publish forbidden (CONTENT INTEGRITY > TEST CONVENIENCE)."
                    if gate_b == "BLOCKED"
                    else "Pilot published"
                ),
            },
            indent=2,
        ),
    )

    email = f"score-audit-{uuid.uuid4().hex[:8]}@example.com"
    password = "PracticeTest!234"
    with httpx.Client(base_url=API, timeout=60.0) as client:
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "first_name": "Score", "last_name": "Audit"},
        ).raise_for_status()
        csrf = client.cookies.get("csrf_token")
        headers = {"X-CSRF-Token": csrf} if csrf else {}

        gen = client.post(
            "/api/v1/assessments/practice",
            headers=headers,
            json={"scope_type": "FULL", "question_count": 30},
        )
        gen.raise_for_status()
        gbody = gen.json()
        assessment = gbody["data"]
        meta = gbody.get("meta") or {}
        marks = float(assessment["marks_per_question"])
        neg = float(assessment["negative_marks_per_question"])

        start = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=headers)
        start.raise_for_status()
        attempt_id = start.json()["data"]["id"]

        detail = client.get(f"/api/v1/attempts/{attempt_id}")
        detail.raise_for_status()
        questions = detail.json()["data"]["questions"]
        n = len(questions)
        assert n == assessment["question_count"]
        assert n == meta.get("delivered_count", n)

        # Deterministic pattern: first half A, second half skip (null), except last answered B
        for i, q in enumerate(questions):
            if i == n - 1:
                selected = q["options"][1]["label"] if len(q["options"]) > 1 else "B"
            elif i < max(1, n // 2):
                selected = q["options"][0]["label"] if q["options"] else "A"
            else:
                selected = None
            client.post(
                f"/api/v1/attempts/{attempt_id}/answers",
                headers=headers,
                json={"content_item_id": q["content_item_id"], "selected_option": selected},
            ).raise_for_status()

        submitted = client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=headers)
        submitted.raise_for_status()
        result = submitted.json()["data"]

        review = client.get(f"/api/v1/attempts/{attempt_id}")
        review.raise_for_status()
        rq = review.json()["data"]["questions"]

        correct = incorrect = skipped = 0
        for q in rq:
            sel = q.get("selected_option")
            key = q.get("correct_option")
            if not sel:
                skipped += 1
            elif sel == key:
                correct += 1
            else:
                incorrect += 1
        expected_score = float(correct * marks - incorrect * neg)

        ok = (
            result["correct_count"] == correct
            and result["incorrect_count"] == incorrect
            and result["skipped_count"] == skipped
            and abs(float(result["score"]) - expected_score) < 1e-6
            and correct + incorrect + skipped == n
        )
        report = {
            "delivered": n,
            "requested": meta.get("requested_count"),
            "shrunk": meta.get("shrunk"),
            "server": {
                "score": result["score"],
                "correct": result["correct_count"],
                "incorrect": result["incorrect_count"],
                "skipped": result["skipped_count"],
            },
            "independent": {
                "score": expected_score,
                "correct": correct,
                "incorrect": incorrect,
                "skipped": skipped,
            },
            "match": ok,
            "gate_b_30": gate_b,
            "question_ids": [q["content_item_id"] for q in rq],
        }
        print("SCORING", json.dumps(report, indent=2))
        if not ok:
            print("RESULT=FAIL", file=sys.stderr)
            return 1
        print("RESULT=PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
