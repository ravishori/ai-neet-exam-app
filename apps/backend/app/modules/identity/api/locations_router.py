"""Public read-only master-data endpoints for the client's State/City pickers.

* ``GET /api/v1/locations/states`` — active states, alphabetical.
* ``GET /api/v1/locations/states/{state_id}/cities`` — active cities under
  a given state, alphabetical. 404 for unknown / inactive states.

No write endpoints — master data is populated exclusively by
``seed_geo_master`` from the authoritative source file.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.identity.repositories.geo_repository import GeoRepository
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/locations", tags=["locations"])


@router.get("/states")
async def list_states(db: AsyncSession = Depends(get_db)):
    repo = GeoRepository(db)
    states = await repo.list_active_states()
    return envelope(
        success=True,
        data=[
            {"id": str(s.id), "code": s.code, "name": s.name} for s in states
        ],
        meta={"total": len(states)},
    )


@router.get("/states/{state_id}/cities")
async def list_cities(state_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = GeoRepository(db)
    st = await repo.get_state_by_id(state_id)
    if st is None or not st.is_active:
        raise NotFoundError("State not found")
    cities = await repo.list_active_cities_for(state_id)
    return envelope(
        success=True,
        data=[{"id": str(c.id), "name": c.name} for c in cities],
        meta={"total": len(cities), "state_id": str(state_id), "state_code": st.code},
    )
