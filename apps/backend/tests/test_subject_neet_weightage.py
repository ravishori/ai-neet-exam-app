"""Task A guard: subject-level NEET weightage storage + API exposure.

Confirms:
- ``academic.subjects.neet_weightage_percent`` exists as a nullable
  Numeric(4,1) column;
- the four seeded NEET subjects have the official 25/25/25/25 defaults;
- the value flows out of ``GET /api/v1/academic/subjects``.
Zero impact on scoring, generation, mastery or existing tests.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.modules.academic.models import Subject

pytestmark = pytest.mark.asyncio(loop_scope="session")


EXPECTED_DEFAULTS = {
    "PHYSICS": 25.0,
    "CHEMISTRY": 25.0,
    "BOTANY": 25.0,
    "ZOOLOGY": 25.0,
}


async def test_subjects_have_neet_weightage_defaults(db_session):
    rows = (
        await db_session.execute(select(Subject.code, Subject.neet_weightage_percent).order_by(Subject.code))
    ).all()
    by_code = {code: (float(pct) if pct is not None else None) for code, pct in rows}
    for code, expected in EXPECTED_DEFAULTS.items():
        assert code in by_code, f"seed missing subject {code}"
        assert by_code[code] == expected, f"{code}: expected {expected}, got {by_code[code]}"


async def test_subject_weightage_sums_to_100(db_session):
    rows = (
        await db_session.execute(
            select(Subject.code, Subject.neet_weightage_percent).where(
                Subject.code.in_(list(EXPECTED_DEFAULTS.keys()))
            )
        )
    ).all()
    total = sum(float(pct or 0) for _code, pct in rows)
    # Physics + Chemistry + Botany + Zoology should sum to the full NEET
    # blueprint (Biology bucket = Botany + Zoology = 50).
    assert total == 100.0, f"expected 100, got {total}"


async def test_subject_api_exposes_weightage(client, db_session, register_user):
    # The academic router requires an authenticated session.
    await register_user(client, db_session=db_session)
    resp = await client.get("/api/v1/subjects")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert isinstance(body, list) and body, "expected non-empty subject list"
    by_code = {row["code"]: row for row in body}
    for code, expected in EXPECTED_DEFAULTS.items():
        assert code in by_code, f"API missing subject {code}"
        assert by_code[code].get("neet_weightage_percent") == expected


async def test_neet_weightage_is_nullable_for_new_rows(db_session):
    """Column must remain nullable so unrelated exam boards / custom subjects
    are not forced to declare a NEET weightage."""
    from sqlalchemy import text

    row = (
        await db_session.execute(
            text(
                "SELECT is_nullable, data_type FROM information_schema.columns "
                "WHERE table_schema='academic' AND table_name='subjects' AND column_name='neet_weightage_percent'"
            )
        )
    ).first()
    assert row is not None, "column not present"
    assert row[0] == "YES", "column must remain NULLABLE"
    assert row[1] in ("numeric", "double precision"), f"unexpected type {row[1]}"
