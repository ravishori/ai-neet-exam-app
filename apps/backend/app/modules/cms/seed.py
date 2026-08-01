"""Seed real content for the Sprint 2 "fully fleshed" concepts, pushed all
the way to PUBLISHED so the student app has something real to show.

Uses a dedicated seed content-author account (not meant to be logged into)
so this seed is reproducible from a fresh database, rather than depending
on whichever test user happens to have been promoted to CONTENT_MANAGER by
hand during manual testing.
"""

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.academic.models import Concept
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.identity.models.role import UserRole
from app.modules.identity.models.user import User
from app.modules.identity.repositories.role_repository import RoleRepository
from app.modules.identity.services.password_service import hash_password

logger = get_logger("seed")

SEED_AUTHOR_EMAIL = "content-seed@trinetra.local"

# concept_code -> (title, body)
CONCEPT_NOTES = {
    "ohms-law-concept": (
        "Ohm's Law",
        {
            "ncert_ref": "NCERT Physics Part 2, Ch 3 — Current Electricity",
            "summary": "Ohm's Law states that the current through a conductor between two points is directly proportional to the voltage across those two points, provided physical conditions (especially temperature) remain constant: V = IR.",
            "sections": [
                "Statement of Ohm's Law",
                "V = IR and the role of resistance",
                "Limitations — Ohm's Law fails for non-ohmic devices (diodes, transistors)",
            ],
        },
    ),
    "sp-sp2-sp3": (
        "sp, sp2, sp3 Hybridization",
        {
            "ncert_ref": "NCERT Chemistry Part 1, Ch 4 — Chemical Bonding and Molecular Structure",
            "summary": "Hybridization is the mixing of atomic orbitals of similar energy to form new, equivalent hybrid orbitals. sp gives linear geometry, sp2 gives trigonal planar, sp3 gives tetrahedral.",
            "sections": ["Why hybridization is needed", "sp / sp2 / sp3 geometries", "Identifying hybridization from Lewis structures"],
        },
    ),
    "c3-c4-pathway": (
        "C3 vs C4 Pathway",
        {
            "ncert_ref": "NCERT Biology, Ch 13 — Photosynthesis in Higher Plants",
            "summary": "C3 plants fix CO2 directly via RuBisCO into a 3-carbon compound; C4 plants first fix CO2 in mesophyll cells into a 4-carbon compound, concentrating CO2 in bundle sheath cells to suppress photorespiration under heat/light stress.",
            "sections": ["The Calvin cycle (C3 pathway)", "The Hatch-Slack pathway (C4)", "Why C4 plants outperform C3 in hot, dry climates"],
        },
    ),
    "abo-blood-grouping": (
        "ABO Blood Grouping System",
        {
            "ncert_ref": "NCERT Biology, Ch 18 — Body Fluids and Circulation",
            "summary": "The ABO system classifies blood into A, B, AB, or O based on antigens on red blood cell surfaces and antibodies in plasma, determining transfusion compatibility.",
            "sections": ["Antigens and antibodies", "Universal donor/recipient rules", "Rh factor"],
        },
    ),
}

QUESTIONS = {
    "ohms-law-concept": {
        "stem": "A conductor has a resistance of 5 ohm. What current flows through it when a potential difference of 10 V is applied across it?",
        "options": [
            {"label": "A", "text": "0.5 A"},
            {"label": "B", "text": "2 A"},
            {"label": "C", "text": "5 A"},
            {"label": "D", "text": "50 A"},
        ],
        "correct_option": "B",
        "explanation": "By Ohm's Law, I = V/R = 10/5 = 2 A.",
        "difficulty": "easy",
        "bloom_level": "application",
    },
    "abo-blood-grouping": {
        "stem": "A person with blood group AB is often called the 'universal recipient' because:",
        "options": [
            {"label": "A", "text": "Their plasma contains both anti-A and anti-B antibodies"},
            {"label": "B", "text": "Their plasma contains neither anti-A nor anti-B antibodies"},
            {"label": "C", "text": "Their RBCs carry no antigens"},
            {"label": "D", "text": "Their RBCs carry the Rh antigen only"},
        ],
        "correct_option": "B",
        "explanation": "AB plasma has no anti-A or anti-B antibodies, so it won't reject incoming A or B antigens from donor blood.",
        "difficulty": "medium",
        "bloom_level": "understanding",
    },
    "kcl-kvl": {
        "stem": "Kirchhoff's Voltage Law is a direct consequence of which conservation principle?",
        "options": [
            {"label": "A", "text": "Conservation of charge"},
            {"label": "B", "text": "Conservation of energy"},
            {"label": "C", "text": "Conservation of momentum"},
            {"label": "D", "text": "Conservation of mass"},
        ],
        "correct_option": "B",
        "explanation": "KVL states the algebraic sum of potential differences around a closed loop is zero — this follows from energy conservation.",
        "difficulty": "medium",
        "bloom_level": "understanding",
    },
    "factors-affecting-resistance": {
        "stem": "If the length of a wire is doubled and its radius is halved, its resistance becomes:",
        "options": [
            {"label": "A", "text": "2 times"},
            {"label": "B", "text": "4 times"},
            {"label": "C", "text": "8 times"},
            {"label": "D", "text": "Unchanged"},
        ],
        "correct_option": "C",
        "explanation": "R ∝ L/A. Doubling L doubles R; halving radius quarters the area, quadrupling R. Combined: 2 × 4 = 8 times.",
        "difficulty": "hard",
        "bloom_level": "application",
    },
    "vsepr-theory": {
        "stem": "According to VSEPR theory, the shape of the ammonia (NH3) molecule is:",
        "options": [
            {"label": "A", "text": "Tetrahedral"},
            {"label": "B", "text": "Trigonal pyramidal"},
            {"label": "C", "text": "Trigonal planar"},
            {"label": "D", "text": "Linear"},
        ],
        "correct_option": "B",
        "explanation": "NH3 has 3 bond pairs and 1 lone pair around N; the lone pair distorts the tetrahedral arrangement into trigonal pyramidal.",
        "difficulty": "medium",
        "bloom_level": "application",
    },
    "photorespiration": {
        "stem": "Photorespiration primarily occurs in which type of plants, reducing photosynthetic efficiency?",
        "options": [
            {"label": "A", "text": "C4 plants only"},
            {"label": "B", "text": "C3 plants"},
            {"label": "C", "text": "CAM plants only"},
            {"label": "D", "text": "None — it aids all plants equally"},
        ],
        "correct_option": "B",
        "explanation": "In C3 plants, RuBisCO can bind O2 instead of CO2 under high temperature/light, wastefully consuming energy via photorespiration.",
        "difficulty": "medium",
        "bloom_level": "understanding",
    },
    "cardiac-cycle-phases": {
        "stem": "During which phase of the cardiac cycle are both the atrioventricular and semilunar valves closed?",
        "options": [
            {"label": "A", "text": "Atrial systole"},
            {"label": "B", "text": "Isovolumic ventricular contraction"},
            {"label": "C", "text": "Ventricular ejection"},
            {"label": "D", "text": "Atrial diastole only"},
        ],
        "correct_option": "B",
        "explanation": "During isovolumic contraction, ventricular pressure rises but hasn't yet exceeded arterial pressure, so both valve sets remain shut.",
        "difficulty": "hard",
        "bloom_level": "analysis",
    },
    "heart-structure": {
        "stem": "Which chamber of the human heart pumps deoxygenated blood to the lungs?",
        "options": [
            {"label": "A", "text": "Left atrium"},
            {"label": "B", "text": "Left ventricle"},
            {"label": "C", "text": "Right ventricle"},
            {"label": "D", "text": "Right atrium"},
        ],
        "correct_option": "C",
        "explanation": "The right ventricle pumps deoxygenated blood through the pulmonary artery to the lungs for oxygenation.",
        "difficulty": "easy",
        "bloom_level": "knowledge",
    },
}


async def _get_or_create_seed_author(session: AsyncSession) -> User:
    result = await session.execute(select(User).where(User.email == SEED_AUTHOR_EMAIL))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        email=SEED_AUTHOR_EMAIL,
        password_hash=hash_password(secrets.token_urlsafe(32)),  # not meant to be logged into
        first_name="Content",
        last_name="Seed",
        display_name="Content Seed Bot",
        status="active",
        email_verified=True,
    )
    session.add(user)
    await session.flush()

    role_repo = RoleRepository(session)
    role = await role_repo.get_by_code("CONTENT_MANAGER")
    if role:
        session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    logger.info("seed_author_created", email=SEED_AUTHOR_EMAIL)
    return user


async def _publish_through_workflow(service: ContentWorkflowService, item_id: uuid.UUID, author_id: uuid.UUID) -> None:
    await service.submit_for_review(item_id)
    await service.review(item_id, reviewer_id=author_id, decision="approve", comment="Seed content — auto-approved.")
    await service.publish(item_id)


async def seed_cms(session: AsyncSession) -> None:
    author = await _get_or_create_seed_author(session)
    service = ContentWorkflowService(session)

    for concept_code, (title, body) in CONCEPT_NOTES.items():
        result = await session.execute(select(Concept).where(Concept.code == concept_code))
        concept = result.scalar_one_or_none()
        if not concept:
            continue

        existing = await service.repo.list_items(concept_id=concept.id, content_type="CONCEPT_NOTE")
        if existing:
            continue

        item = await service.create_item(
            content_type="CONCEPT_NOTE",
            concept_id=concept.id,
            title=f"{title} — Concept Note",
            slug=f"{concept_code}-note",
            tags=[],
            language="en",
            body=body,
            author_id=author.id,
        )
        await _publish_through_workflow(service, item.id, author.id)
        logger.info("concept_note_published", concept_code=concept_code)

    for concept_code, body in QUESTIONS.items():
        result = await session.execute(select(Concept).where(Concept.code == concept_code))
        concept = result.scalar_one_or_none()
        if not concept:
            continue

        existing = await service.repo.list_items(concept_id=concept.id, content_type="QUESTION")
        if existing:
            continue

        item = await service.create_item(
            content_type="QUESTION",
            concept_id=concept.id,
            title=f"Practice question — {concept_code}",
            slug=f"{concept_code}-q1",
            tags=[],
            language="en",
            body=body,
            author_id=author.id,
        )
        await _publish_through_workflow(service, item.id, author.id)
        logger.info("question_published", concept_code=concept_code)

    logger.info("cms_seed_complete")
