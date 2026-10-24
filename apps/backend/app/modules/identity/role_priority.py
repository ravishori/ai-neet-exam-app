"""Shared role-priority ordering for picking a default ``active_role``
claim when a login doesn't request one, and for falling back a stale or
tampered claim found on an existing access token.

SUPER_ADMIN's priority here is purely about which role is highlighted in
the UI by default for an account holding multiple roles -- it does NOT
affect authorization, which always checks the full ``user.role_codes``
set (see ``_has_permission``/``require_permission`` in
``app.modules.identity.dependencies`` and ``app.modules.cms.api.cms_router``),
never ``active_role`` alone. Switching the active role is a display/UX
choice, not a privilege change.
"""

ROLE_PRIORITY = ["SUPER_ADMIN", "ADMIN", "CONTENT_MANAGER", "TEACHER", "SUPPORT", "STUDENT"]


def default_active_role(role_codes: list[str]) -> str:
    for code in ROLE_PRIORITY:
        if code in role_codes:
            return code
    return role_codes[0] if role_codes else "STUDENT"
