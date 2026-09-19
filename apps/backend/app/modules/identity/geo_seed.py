"""Idempotent import of the Cities-List.xlsx master data.

The authoritative source is committed as ``india_cities_source.json`` next
to this module (produced by ``scripts/geo/import_cities_xlsx.py``). Do not
maintain a second competing source of truth.

Callable from three places:
1. Alembic migration ``f7b2c3d4e5f6_identity_geo_master_tables`` — invoked
   inline after the DDL so a fresh database comes up with master data.
2. The identity test seed (``conftest.py`` → ``seed_identity`` → this).
3. Ad-hoc: ``python -m app.modules.identity.geo_seed``.

Contract:
* Zero destructive operations. Never deletes states / cities.
* Upserts by natural key (state.name, (state_id, city.name)).
* Reports counts so callers can reconcile against the source.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.geo import City, State, slug_state_code

_SOURCE_PATH = Path(__file__).with_name("data") / "india_cities_source.json"


@dataclass
class GeoSeedResult:
    source_states: int
    source_cities: int
    states_inserted: int
    states_updated: int
    cities_inserted: int
    cities_updated: int
    duplicates_skipped: int


def load_source() -> dict:
    with _SOURCE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


async def seed_geo_master(session: AsyncSession) -> GeoSeedResult:
    source = load_source()
    states_by_name: dict[str, State] = {
        s.name: s
        for s in (await session.execute(select(State))).scalars().all()
    }

    src_state_names: list[str] = [row["name"] for row in source["states"]]
    seen_states: set[tuple[str, str]] = set()
    seen_city_pairs: set[tuple[str, str]] = set()  # (state.name, city.name)

    states_inserted = 0
    states_updated = 0
    cities_inserted = 0
    cities_updated = 0
    dedup_source_rows = 0
    total_source_cities = 0

    for row in source["states"]:
        state_name = row["name"].strip()
        code = slug_state_code(state_name)
        key = (state_name, code)
        if key in seen_states:
            dedup_source_rows += 1
            continue
        seen_states.add(key)

        st = states_by_name.get(state_name)
        if st is None:
            st = State(name=state_name, code=code, is_active=True)
            session.add(st)
            await session.flush()
            states_inserted += 1
        else:
            changed = False
            if st.code != code:
                st.code = code
                changed = True
            if st.is_active is not True:
                st.is_active = True
                changed = True
            if changed:
                states_updated += 1
        states_by_name[state_name] = st

        existing_cities = {
            c.name: c
            for c in (
                await session.execute(select(City).where(City.state_id == st.id))
            ).scalars().all()
        }
        for city_name in row.get("cities", []):
            city_name = city_name.strip()
            total_source_cities += 1
            pair = (state_name, city_name)
            if pair in seen_city_pairs:
                dedup_source_rows += 1
                continue
            seen_city_pairs.add(pair)

            existing = existing_cities.get(city_name)
            if existing is None:
                session.add(City(state_id=st.id, name=city_name, is_active=True))
                cities_inserted += 1
            else:
                if existing.is_active is not True:
                    existing.is_active = True
                    cities_updated += 1

    await session.commit()
    return GeoSeedResult(
        source_states=len(src_state_names),
        source_cities=total_source_cities,
        states_inserted=states_inserted,
        states_updated=states_updated,
        cities_inserted=cities_inserted,
        cities_updated=cities_updated,
        duplicates_skipped=dedup_source_rows,
    )


async def _cli() -> None:  # pragma: no cover
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await seed_geo_master(session)
        print(result)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_cli())
