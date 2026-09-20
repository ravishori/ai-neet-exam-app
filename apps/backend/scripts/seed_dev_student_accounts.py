#!/usr/bin/env python3
"""Create the 5 DEV/TEST student accounts (student01..05@test.neetprep.dev).

Reuses the existing registration path (AuthService.register) — the same
code that /api/v1/auth/register runs — so password hashing (argon2) and
STUDENT role assignment happen exactly as they do for a real signup. No
second RBAC system, no ad-hoc SQL, no plaintext password storage.

Idempotent: if an account already exists (EMAIL_TAKEN), it is left
untouched and reported as "existing" rather than re-created or modified.

Uses the `.dev` TLD, not `.local` — pydantic's EmailStr (via
email-validator) rejects `.local` as a reserved/special-use TLD at the
HTTP schema layer on both /register and /login, which made the previous
.local accounts impossible to authenticate through the real API even
though they existed correctly in the database. `.dev` is a real,
ICANN-delegated TLD and passes EmailStr's deliverability checks.

DEV/TEST use only — reads DATABASE_URL from the environment exactly like
the running app; run this against a dev/test database only.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.modules.identity.repositories.user_repository import UserRepository
from app.modules.identity.services.auth_service import AuthService

ACCOUNTS = [
    {"n": "01", "email": "student01@test.neetprep.dev", "password": "N3et!Test01#2026"},
    {"n": "02", "email": "student02@test.neetprep.dev", "password": "N3et!Test02#2026"},
    {"n": "03", "email": "student03@test.neetprep.dev", "password": "N3et!Test03#2026"},
    {"n": "04", "email": "student04@test.neetprep.dev", "password": "N3et!Test04#2026"},
    {"n": "05", "email": "student05@test.neetprep.dev", "password": "N3et!Test05#2026"},
]

# Emails these accounts previously used under the rejected .local TLD —
# cleaned up from the DEV DB by this script's main() before (re)creating
# the .dev accounts, so no orphaned unusable rows are left behind.
OBSOLETE_LOCAL_EMAILS = [
    "student01@test.neetprep.local",
    "student02@test.neetprep.local",
    "student03@test.neetprep.local",
    "student04@test.neetprep.local",
    "student05@test.neetprep.local",
]

# Distinct, valid-format Indian mobile numbers — registration requires a
# unique mobile per user just like email.
MOBILES = ["9800000001", "9800000002", "9800000003", "9800000004", "9800000005"]


async def main() -> int:
    settings = get_settings()
    dbname = settings.database_url.rsplit("/", 1)[-1].split("?")[0]
    if "prod" in dbname.lower():
        print(f"STOP: refusing to run against a database named {dbname!r} (looks like production).", file=sys.stderr)
        return 2
    print(f"Target database: {dbname}")

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    results = []
    async with AsyncSession(bind=engine, expire_on_commit=False) as session:
        # Clean up the old, unusable .local accounts first — they were
        # never reachable via the real HTTP API (EmailStr rejects .local),
        # and their mobile numbers are reused by the .dev replacements
        # below, so they must be gone before registration runs.
        users_repo = UserRepository(session)
        removed_local = 0
        for old_email in OBSOLETE_LOCAL_EMAILS:
            old_user = await users_repo.get_by_email(old_email)
            if old_user is not None:
                await session.delete(old_user)
                removed_local += 1
        if removed_local:
            await session.commit()
        print(f"Removed {removed_local} obsolete .local account(s).")

        service = AuthService(session)
        for acct, mobile in zip(ACCOUNTS, MOBILES):
            try:
                user = await service.register(
                    email=acct["email"],
                    first_name=f"Student{acct['n']}",
                    last_name="Test",
                    mobile=mobile,
                    state_code="KARNATAKA",
                    city="Bangalore",
                    password=acct["password"],
                )
                results.append((acct["email"], "created", str(user.id)))
            except AppError as exc:
                if exc.code == "EMAIL_TAKEN":
                    results.append((acct["email"], "existing", None))
                else:
                    results.append((acct["email"], f"FAILED:{exc.code}", None))
            # Each register() commits internally; roll back any failed
            # attempt's partial session state before the next iteration.
            await session.rollback()

    await engine.dispose()

    for email, status, user_id in results:
        print(f"{email}: {status}" + (f" ({user_id})" if user_id else ""))

    failed = [r for r in results if r[1].startswith("FAILED")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
