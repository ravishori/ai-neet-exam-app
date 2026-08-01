from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.identity.models.role import Permission, Role, RolePermission
from app.modules.identity.repositories.role_repository import RoleRepository

logger = get_logger("seed")

ROLES = [
    ("SUPER_ADMIN", "Super Admin", "Full platform access, bypasses permission checks"),
    ("ADMIN", "Admin", "Operational administration"),
    ("CONTENT_MANAGER", "Content Manager", "Creates and reviews academic content"),
    ("TEACHER", "Teacher", "Creates questions, views student reports"),
    ("STUDENT", "Student", "Default role for every self-registered user"),
    ("SUPPORT", "Support", "Read-only access for support tickets"),
]

PERMISSIONS = [
    ("questions.read", "View questions"),
    ("questions.create", "Create questions"),
    ("questions.update", "Edit questions"),
    ("questions.delete", "Delete questions"),
    ("users.manage", "Manage user accounts and roles"),
    ("reports.view", "View student/performance reports"),
    ("analytics.view", "View analytics dashboards"),
    ("ai.use", "Use AI Tutor / Planner / Question Generator"),
    # ECAEP (Sprint 3) — see docs/architecture/ecaep.md
    ("content.create", "Create content drafts (concept notes, questions, flashcards, ...)"),
    ("content.edit_own_draft", "Edit your own draft/changes-requested content"),
    ("content.submit_for_review", "Submit a draft for AI check + review"),
    ("content.review", "Review submitted content"),
    ("content.approve", "Approve reviewed content"),
    ("content.publish", "Publish approved content"),
    ("content.archive", "Archive published content"),
    ("content.force_edit_published", "Hotfix published content, bypassing the review pipeline"),
]

ROLE_PERMISSIONS = {
    "SUPER_ADMIN": [code for code, _ in PERMISSIONS],
    "ADMIN": [
        "questions.read", "questions.create", "questions.update", "questions.delete",
        "users.manage", "reports.view", "analytics.view",
        "content.create", "content.edit_own_draft", "content.submit_for_review",
        "content.review", "content.approve", "content.publish", "content.archive",
        "content.force_edit_published",
    ],
    "CONTENT_MANAGER": [
        "questions.read", "questions.create", "questions.update",
        "content.create", "content.edit_own_draft", "content.submit_for_review",
        "content.review", "content.approve", "content.publish", "content.archive",
    ],
    "TEACHER": [
        "questions.read", "questions.create", "reports.view",
        "content.create", "content.edit_own_draft", "content.submit_for_review",
    ],
    "STUDENT": ["questions.read", "ai.use"],
    "SUPPORT": ["reports.view"],
}


async def seed_identity(session: AsyncSession) -> None:
    repo = RoleRepository(session)

    role_by_code: dict[str, Role] = {}
    for code, name, description in ROLES:
        role = await repo.get_by_code(code)
        if not role:
            role = Role(code=code, name=name, description=description)
            session.add(role)
            await session.flush()
            logger.info("role_seeded", code=code)
        role_by_code[code] = role

    permission_by_code: dict[str, Permission] = {}
    for code, description in PERMISSIONS:
        from sqlalchemy import select

        result = await session.execute(select(Permission).where(Permission.code == code))
        permission = result.scalar_one_or_none()
        if not permission:
            permission = Permission(code=code, description=description)
            session.add(permission)
            await session.flush()
            logger.info("permission_seeded", code=code)
        permission_by_code[code] = permission

    for role_code, permission_codes in ROLE_PERMISSIONS.items():
        role = role_by_code[role_code]
        for permission_code in permission_codes:
            permission = permission_by_code[permission_code]

            from sqlalchemy import select

            existing = await session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role.id, RolePermission.permission_id == permission.id
                )
            )
            if not existing.scalar_one_or_none():
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))

    await session.commit()
    logger.info("identity_seed_complete")
