"""Securely provision the initial SUPER_ADMIN account. Run from apps/backend:

    python scripts/bootstrap_super_admin.py --email you@example.com

Password source (in order): SUPER_ADMIN_BOOTSTRAP_PASSWORD env var, else an
interactive hidden prompt (getpass) with confirmation. Never accepted as a
CLI argument, never logged, never echoed, never printed on success/failure.

Safety gates (see bootstrap_super_admin() below for exact semantics):
  - Refuses to create a second SUPER_ADMIN if one already exists, unless
    --allow-additional is passed.
  - Refuses to silently promote an existing non-SUPER_ADMIN account, unless
    --promote-existing is passed.
  - Idempotent: re-running with the same email once that exact account is
    already SUPER_ADMIN is a no-op, not an error and not a duplicate.
"""

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.modules.identity.models.user import User  # noqa: E402
from app.modules.identity.repositories.role_repository import RoleRepository  # noqa: E402
from app.modules.identity.repositories.user_repository import UserRepository  # noqa: E402
from app.modules.identity.services.password_service import hash_password, validate_password_policy  # noqa: E402

logger = get_logger("bootstrap_super_admin")


class BootstrapError(Exception):
    """Raised for any safety-gate failure or invalid input. Message text is
    always safe to print — never includes the password."""


async def bootstrap_super_admin(
    session,
    *,
    email: str,
    password: str,
    allow_additional: bool = False,
    promote_existing: bool = False,
) -> tuple[str, bool]:
    """Returns (user_id, created). Never logs or returns the password."""
    email = email.strip().lower()
    if not email:
        raise BootstrapError("Email is required")

    user_repo = UserRepository(session)
    role_repo = RoleRepository(session)

    role = await role_repo.get_by_code("SUPER_ADMIN")
    if not role:
        raise BootstrapError(
            "SUPER_ADMIN role does not exist — run `python scripts/seed.py` first "
            "to seed roles/permissions."
        )

    target = await user_repo.get_by_email(email)
    if target and "SUPER_ADMIN" in target.role_codes:
        logger.info("super_admin_bootstrap_noop_already_provisioned", email=email)
        return str(target.id), False

    _existing, super_admin_count = await user_repo.list_paginated(role_code="SUPER_ADMIN", limit=1)
    if super_admin_count > 0 and not allow_additional:
        raise BootstrapError(
            f"A SUPER_ADMIN account already exists ({super_admin_count} found). Refusing "
            "to create another one without --allow-additional, to prevent accidental "
            "proliferation of privileged accounts."
        )

    if target and not promote_existing:
        raise BootstrapError(
            f"An account with email {email} already exists but is not SUPER_ADMIN. "
            "Refusing to silently promote it. Pass --promote-existing to explicitly "
            "confirm you want to grant SUPER_ADMIN to this existing account."
        )

    validate_password_policy(password)

    if target:
        role_repo.assign_role(target.id, role.id)
        await session.commit()
        logger.info("super_admin_bootstrap_promoted_existing", email=email, user_id=str(target.id))
        return str(target.id), False

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=email.split("@")[0],
        email_verified=True,
    )
    user_repo.add(user)
    await user_repo.flush()
    role_repo.assign_role(user.id, role.id)
    await session.commit()
    logger.info("super_admin_bootstrap_created", email=email, user_id=str(user.id))
    return str(user.id), True


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--email", help="SUPER_ADMIN email. Falls back to SUPER_ADMIN_BOOTSTRAP_EMAIL env var."
    )
    parser.add_argument(
        "--allow-additional",
        action="store_true",
        help="Allow creating a SUPER_ADMIN even if one already exists.",
    )
    parser.add_argument(
        "--promote-existing",
        action="store_true",
        help="Allow granting SUPER_ADMIN to an existing (non-SUPER_ADMIN) account.",
    )
    args = parser.parse_args()

    email = args.email or os.environ.get("SUPER_ADMIN_BOOTSTRAP_EMAIL")
    if not email:
        print("ERROR: --email or SUPER_ADMIN_BOOTSTRAP_EMAIL is required.", file=sys.stderr)
        return 2

    password = os.environ.get("SUPER_ADMIN_BOOTSTRAP_PASSWORD")
    if not password:
        password = getpass.getpass("SUPER_ADMIN password (input hidden, never echoed/logged): ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("ERROR: passwords did not match.", file=sys.stderr)
            return 2

    async with AsyncSessionLocal() as session:
        try:
            user_id, created = await bootstrap_super_admin(
                session,
                email=email,
                password=password,
                allow_additional=args.allow_additional,
                promote_existing=args.promote_existing,
            )
        except BootstrapError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    action = "Created" if created else "Already provisioned (idempotent no-op) / promoted"
    print(f"{action} SUPER_ADMIN account (user_id={user_id}). Password was never logged or displayed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
