"""GET /api/v1/locations/states + /states/{id}/cities — read-only master data."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_list_states_alphabetical(client):
    resp = await client.get("/api/v1/locations/states")
    assert resp.status_code == 200
    body = resp.json()
    names = [row["name"] for row in body["data"]]
    assert names == sorted(names)
    # 27 distinct State values from the current source XLSX. The workbook
    # was corrected upstream to list all Odisha cities under "Odisha" only
    # — the pre-2011 name "Orissa" is no longer a separate source row.
    assert body["meta"]["total"] == len(names) == 27
    codes = {row["code"] for row in body["data"]}
    # A few known slugs.
    assert {"KARNATAKA", "TAMIL_NADU", "ODISHA"}.issubset(codes)
    assert "ORISSA" not in codes


async def test_list_cities_for_karnataka_alphabetical(client):
    states = (await client.get("/api/v1/locations/states")).json()["data"]
    ka = next(s for s in states if s["code"] == "KARNATAKA")

    resp = await client.get(f"/api/v1/locations/states/{ka['id']}/cities")
    assert resp.status_code == 200
    body = resp.json()
    names = [row["name"] for row in body["data"]]
    assert names == sorted(names)
    assert "Bangalore" in names
    assert body["meta"]["state_code"] == "KARNATAKA"


async def test_list_cities_404_for_unknown_state(client):
    resp = await client.get("/api/v1/locations/states/00000000-0000-0000-0000-000000000000/cities")
    assert resp.status_code == 404
