"""Server-side validators for profile fields introduced with mobile OTP login.

Callers get typed AppError with stable codes:
* MOBILE_INVALID           — not a 10-digit Indian mobile (starts 6-9).
* STATE_INVALID            — state_code not found or inactive in master data.
* CITY_INVALID_FOR_STATE   — city does not belong to the given state / inactive.

The State/City authoritative source is ``identity.states`` and
``identity.cities`` (seeded from Cities-List.xlsx via ``geo_seed``). Do NOT
introduce a parallel Python list of valid states/cities — validators must
consult the database so runtime data stays in sync with the source of truth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.identity.models.geo import City, State
from app.modules.identity.repositories.geo_repository import GeoRepository

# 10-digit Indian mobile, first digit 6-9 (post-2015 TRAI numbering plan).
_INDIAN_10 = re.compile(r"^[6-9]\d{9}$")
# Accept an optional +91 / 91 / 0 prefix, then 10 digits starting 6-9.
_LOOSE = re.compile(r"^(?:\+?91|0)?([6-9]\d{9})$")


def normalize_indian_mobile(raw: str) -> str:
    """Return the E.164 form ``+91XXXXXXXXXX`` or raise MOBILE_INVALID."""
    if not raw:
        raise AppError("Mobile number is required", code="MOBILE_INVALID", status_code=422)
    stripped = re.sub(r"[\s\-()]", "", raw)
    match = _LOOSE.match(stripped)
    if not match:
        raise AppError(
            "Enter a valid 10-digit Indian mobile number",
            code="MOBILE_INVALID",
            status_code=422,
        )
    ten = match.group(1)
    if not _INDIAN_10.match(ten):
        raise AppError(
            "Enter a valid 10-digit Indian mobile number",
            code="MOBILE_INVALID",
            status_code=422,
        )
    return "+91" + ten


@dataclass(frozen=True)
class ValidatedLocation:
    state: State
    city: City


async def resolve_state_and_city(
    session: AsyncSession, state_code: str, city: str
) -> ValidatedLocation:
    """Look up ``state_code`` and ``city`` in the master tables. Validates:
    state is known + active, city is known + active AND belongs to that state.
    Case-insensitive on ``state_code`` and ``city``.
    """
    repo = GeoRepository(session)

    st = await repo.get_state_by_code(state_code)
    if st is None or not st.is_active:
        raise AppError(
            "Select a valid Indian State or Union Territory",
            code="STATE_INVALID",
            status_code=422,
        )
    matched_city = await repo.find_city(state_id=st.id, name=city)
    if matched_city is None or not matched_city.is_active:
        raise AppError(
            "Selected city does not belong to the chosen State/UT",
            code="CITY_INVALID_FOR_STATE",
            status_code=422,
        )
    return ValidatedLocation(state=st, city=matched_city)
