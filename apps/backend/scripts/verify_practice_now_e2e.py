#!/usr/bin/env python3
"""End-to-end API validation of Practice Now for currently PUBLISHED inventory.

Does not modify question content. Reports delivered vs requested counts.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
API = "http://localhost:8000"
EMAIL = f"practice-e2e-{uuid.uuid4().hex[:8]}@example.com"
PASSWORD = "PracticeTest!234"


def main() -> int:
    with httpx.Client(base_url=API, timeout=60.0) as client:
        r = client.post(
            "/api/v1/auth/register",
            json={"email": EMAIL, "password": PASSWORD, "first_name": "E2E", "last_name": "Practice"},
        )
        r.raise_for_status()
        csrf = client.cookies.get("csrf_token")
        headers = {"X-CSRF-Token": csrf} if csrf else {}

        gen = client.post(
            "/api/v1/assessments/practice",
            headers=headers,
            json={"scope_type": "FULL", "question_count": 30},
        )
        gen.raise_for_status()
        body = gen.json()
        assessment = body["data"]
        meta = body.get("meta") or {}
        print("generate", json.dumps({"question_count": assessment["question_count"], "meta": meta}, indent=2))

        start = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=headers)
        start.raise_for_status()
        attempt_id = start.json()["data"]["id"]

        detail = client.get(f"/api/v1/attempts/{attempt_id}")
        detail.raise_for_status()
        questions = detail.json()["data"]["questions"]
        print(f"loaded_questions={len(questions)}")
        assert len(questions) == assessment["question_count"]
        assert len(questions) > 0

        correctish = 0
        for q in questions:
            # Choose first option without peeking at key (in-progress has no correct_option)
            label = q["options"][0]["label"] if q["options"] else None
            ans = client.post(
                f"/api/v1/attempts/{attempt_id}/answers",
                headers=headers,
                json={"content_item_id": q["content_item_id"], "selected_option": label},
            )
            ans.raise_for_status()
            correctish += 1

        submitted = client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=headers)
        submitted.raise_for_status()
        result = submitted.json()["data"]
        print(
            "submit",
            json.dumps(
                {
                    "status": result["status"],
                    "score": result["score"],
                    "correct_count": result["correct_count"],
                    "incorrect_count": result["incorrect_count"],
                    "skipped_count": result["skipped_count"],
                    "answered": correctish,
                },
                indent=2,
            ),
        )
        assert result["status"] == "SUBMITTED"
        assert result["score"] is not None
        assert (result["correct_count"] or 0) + (result["incorrect_count"] or 0) + (result["skipped_count"] or 0) == len(
            questions
        )

        review = client.get(f"/api/v1/attempts/{attempt_id}")
        review.raise_for_status()
        rq = review.json()["data"]["questions"]
        assert all("correct_option" in q for q in rq)
        print("RESULT=PASS")
        print(
            json.dumps(
                {
                    "requested": 30,
                    "delivered": len(questions),
                    "published_inventory_note": "Phase-D 30-question pilot remains DRAFT; session used PUBLISHED pool only",
                    "session_completion": "PASS",
                    "scoring": "PASS",
                    "result": "PASS",
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print("RESULT=FAIL", exc, file=sys.stderr)
        raise SystemExit(1)
