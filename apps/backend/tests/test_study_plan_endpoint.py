"""End-to-end check that is_fallback is actually surfaced through the real
HTTP route (not just the service layer) -- see test_study_planner_service.py
for the service-level coverage this complements."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _mobile() -> str:
    import random

    return str(random.choice("6789")) + "".join(str(random.randint(0, 9)) for _ in range(9))


async def _register(client) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"study-plan-endpoint-{uuid.uuid4().hex[:12]}@example.com",
            "first_name": "StudyPlan",
            "last_name": "Endpoint",
            "mobile": _mobile(),
            "state_code": "KARNATAKA",
            "city": "Bangalore",
            "password": "StudyPlanEndpointPass!42",
        },
    )
    assert resp.status_code == 201, resp.text


async def test_study_plan_response_surfaces_is_fallback_field(client):
    """No real provider API key is configured in the test environment, so
    this must fall back to the deterministic plan -- and the response
    must say so via is_fallback, not silently claim AI personalization."""
    await _register(client)

    resp = await client.post(
        "/api/v1/ai/study-plan",
        headers=csrf_headers(client),
        json={
            "target_score": 650,
            "current_score": 450,
            "exam_date": (date.today() + timedelta(days=90)).isoformat(),
            "hours_per_day": 6,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert "is_fallback" in data
    assert data["is_fallback"] is True
    assert data["plan"]["summary"].startswith("Deterministic plan:")

    fetched = await client.get("/api/v1/ai/study-plan")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["is_fallback"] is True
