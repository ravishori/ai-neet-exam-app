"""State/City master-data tests — dataset audit + DB reconciliation + validator."""

import pytest

from app.core.exceptions import AppError
from app.modules.identity.geo_seed import load_source, seed_geo_master
from app.modules.identity.models.geo import slug_state_code
from app.modules.identity.repositories.geo_repository import GeoRepository
from app.modules.identity.services.profile_validation import (
    normalize_indian_mobile,
    resolve_state_and_city,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


# --------------------------------------------------------------------------- source


def test_source_json_shape():
    src = load_source()
    assert src["source"] == "Cities-List.xlsx"
    assert isinstance(src["states"], list) and len(src["states"]) > 0
    # Each row is (name, cities[])
    for row in src["states"]:
        assert isinstance(row["name"], str) and row["name"].strip() == row["name"]
        assert isinstance(row["cities"], list)


def test_source_contains_odisha_not_the_obsolete_orissa_name():
    """Cities-List.xlsx lists Sambalpur (and all other Odisha cities) under
    the current name "Odisha" only. An earlier version of the source
    listed a subset of Odisha cities under the pre-2011 name "Orissa" as a
    separate, unmerged state entry; the authoritative workbook was
    corrected upstream and no longer contains that entry. The loader must
    reflect the workbook as-is, not preserve a name the source no longer
    has."""
    src = load_source()
    names = {row["name"] for row in src["states"]}
    assert "Odisha" in names
    assert "Orissa" not in names


def test_source_contains_aurangabad_under_two_states():
    """Aurangabad, Bihar and Aurangabad, Maharashtra are distinct real cities."""
    src = load_source()
    by = {row["name"]: row["cities"] for row in src["states"]}
    assert "Aurangabad" in by["Bihar"]
    assert "Aurangabad" in by["Maharashtra"]


def test_slug_state_code_is_deterministic_and_uppercased():
    assert slug_state_code("Andhra Pradesh") == "ANDHRA_PRADESH"
    assert slug_state_code(" Tamil Nadu ") == "TAMIL_NADU"
    assert slug_state_code("Jammu and Kashmir") == "JAMMU_AND_KASHMIR"


# --------------------------------------------------------------------------- DB seeded


async def test_seed_reconciliation_source_matches_database(db_session):
    src = load_source()
    src_state_count = len(src["states"])
    src_city_count = sum(len(row["cities"]) for row in src["states"])

    repo = GeoRepository(db_session)
    db_states, db_cities = await repo.count_states_and_cities()
    # seed_identity runs once per test session (see conftest _seed_reference_data)
    # so counts must match the source exactly with no duplicates.
    assert db_states == src_state_count, (
        f"State count mismatch: source={src_state_count} db={db_states}"
    )
    assert db_cities == src_city_count, (
        f"City count mismatch: source={src_city_count} db={db_cities}"
    )


async def test_seed_is_idempotent(db_session):
    """Re-running seed_geo_master against a populated DB should insert zero
    new rows and update at most active-flag toggles."""
    first = await seed_geo_master(db_session)
    # Second call must be a no-op on inserts.
    second = await seed_geo_master(db_session)
    assert second.states_inserted == 0
    assert second.cities_inserted == 0
    # And still the same source cardinality.
    assert first.source_states == second.source_states
    assert first.source_cities == second.source_cities


async def test_repository_returns_active_only_and_sorted(db_session):
    repo = GeoRepository(db_session)
    states = await repo.list_active_states()
    names = [s.name for s in states]
    assert names == sorted(names), "list_active_states must be alphabetical"
    assert all(s.is_active for s in states)


async def test_repository_cities_scoped_and_sorted(db_session):
    repo = GeoRepository(db_session)
    ka = await repo.get_state_by_code("KARNATAKA")
    assert ka is not None
    cities = await repo.list_active_cities_for(ka.id)
    names = [c.name for c in cities]
    assert names == sorted(names)
    assert "Bangalore" in names


async def test_odisha_resolves_and_obsolete_orissa_code_does_not(db_session):
    """The authoritative workbook lists Sambalpur (and every other Odisha
    city) under "Odisha" only — the pre-2011 name "Orissa" is not a
    separate state in the current source and must not resolve."""
    repo = GeoRepository(db_session)
    odisha = await repo.get_state_by_code("ODISHA")
    orissa = await repo.get_state_by_code("ORISSA")
    assert odisha is not None
    assert orissa is None
    sambalpur = await repo.find_city(state_id=odisha.id, name="Sambalpur")
    assert sambalpur is not None


# --------------------------------------------------------------------------- validator


async def test_resolve_state_and_city_happy_path(db_session):
    loc = await resolve_state_and_city(db_session, "KARNATAKA", "bangalore")
    assert loc.state.code == "KARNATAKA"
    assert loc.city.name == "Bangalore"


async def test_resolve_state_and_city_rejects_unknown_state(db_session):
    with pytest.raises(AppError) as exc:
        await resolve_state_and_city(db_session, "ZZ_NOWHERE", "Bangalore")
    assert exc.value.code == "STATE_INVALID"


async def test_resolve_state_and_city_rejects_city_from_wrong_state(db_session):
    with pytest.raises(AppError) as exc:
        await resolve_state_and_city(db_session, "TAMIL_NADU", "Bangalore")
    assert exc.value.code == "CITY_INVALID_FOR_STATE"


async def test_resolve_state_and_city_rejects_inactive_state(db_session):
    from sqlalchemy import select

    from app.modules.identity.models.geo import State

    st = (await db_session.execute(select(State).where(State.code == "KARNATAKA"))).scalar_one()
    st.is_active = False
    await db_session.flush()
    try:
        with pytest.raises(AppError) as exc:
            await resolve_state_and_city(db_session, "KARNATAKA", "Bangalore")
        assert exc.value.code == "STATE_INVALID"
    finally:
        st.is_active = True
        await db_session.flush()


async def test_resolve_state_and_city_rejects_inactive_city(db_session):
    from sqlalchemy import select

    from app.modules.identity.models.geo import City, State

    st = (await db_session.execute(select(State).where(State.code == "KARNATAKA"))).scalar_one()
    city = (
        await db_session.execute(select(City).where(City.state_id == st.id, City.name == "Bangalore"))
    ).scalar_one()
    city.is_active = False
    await db_session.flush()
    try:
        with pytest.raises(AppError) as exc:
            await resolve_state_and_city(db_session, "KARNATAKA", "Bangalore")
        assert exc.value.code == "CITY_INVALID_FOR_STATE"
    finally:
        city.is_active = True
        await db_session.flush()


# --------------------------------------------------------------------------- mobile normalizer


def test_normalize_accepts_bare_10_digit_starting_6_9():
    assert normalize_indian_mobile("9876543210") == "+919876543210"
    assert normalize_indian_mobile("6000000000") == "+916000000000"


def test_normalize_accepts_prefixed_forms():
    assert normalize_indian_mobile("+919876543210") == "+919876543210"
    assert normalize_indian_mobile("919876543210") == "+919876543210"
    assert normalize_indian_mobile("09876543210") == "+919876543210"
    assert normalize_indian_mobile("+91 98765-43210") == "+919876543210"


def test_normalize_rejects_invalid_lead_digit():
    with pytest.raises(AppError) as exc:
        normalize_indian_mobile("5876543210")
    assert exc.value.code == "MOBILE_INVALID"


def test_normalize_rejects_short_and_empty():
    for bad in ("", "12345", "abcdefghij", "9876"):
        with pytest.raises(AppError) as exc:
            normalize_indian_mobile(bad)
        assert exc.value.code == "MOBILE_INVALID"
