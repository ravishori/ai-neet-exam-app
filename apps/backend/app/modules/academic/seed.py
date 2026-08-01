"""Seed the NEET academic hierarchy.

Chapter lists are the real NTA NEET syllabus (a representative subset per
subject, not the full ~20 chapters each — see docs/decisions/ADR-0012 and
the CTO review's "seed one chapter completely before scaling" guidance).
One chapter per subject is fully fleshed out with topics + concepts to
prove the pipeline; the rest exist as chapters only, ready for Sprint 3's
ECAEP content authoring to fill in.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Exam, Subject, Topic

logger = get_logger("seed")

# (code, name, weightage_percent, topics)
# topics: list of (code, name, concepts) — only populated for the one
# "fully fleshed" chapter per subject; every other chapter has topics=[].
PHYSICS_CHAPTERS = [
    ("kinematics", "Kinematics", 3.0, []),
    ("laws-of-motion", "Laws of Motion", 3.0, []),
    ("work-energy-power", "Work, Energy and Power", 4.0, []),
    ("gravitation", "Gravitation", 2.0, []),
    ("thermodynamics-physics", "Thermodynamics", 4.0, []),
    ("electrostatics", "Electrostatics", 5.0, []),
    (
        "current-electricity",
        "Current Electricity",
        4.0,
        [
            (
                "ohms-law",
                "Electric Current and Ohm's Law",
                [
                    ("ohms-law-concept", "Ohm's Law", "V = IR relationship between voltage, current, and resistance."),
                    ("drift-velocity", "Drift Velocity", "Average velocity of free electrons under an applied electric field."),
                ],
            ),
            (
                "resistance-resistivity",
                "Resistance and Resistivity",
                [
                    ("factors-affecting-resistance", "Factors Affecting Resistance", "Dependence of resistance on length, area, material, and temperature."),
                ],
            ),
            (
                "kirchhoffs-laws",
                "Kirchhoff's Laws",
                [
                    ("kcl-kvl", "Kirchhoff's Current and Voltage Laws", "Conservation of charge and energy applied to electrical circuits."),
                ],
            ),
        ],
    ),
    ("optics", "Optics", 5.0, []),
]

CHEMISTRY_CHAPTERS = [
    ("basic-concepts-chemistry", "Some Basic Concepts of Chemistry", 3.0, []),
    ("structure-of-atom", "Structure of Atom", 3.0, []),
    (
        "chemical-bonding",
        "Chemical Bonding and Molecular Structure",
        5.0,
        [
            (
                "ionic-bonding",
                "Ionic Bonding",
                [
                    ("lattice-energy", "Lattice Energy", "Energy released when gaseous ions combine to form an ionic solid."),
                ],
            ),
            (
                "covalent-bonding-vsepr",
                "Covalent Bonding and VSEPR Theory",
                [
                    ("vsepr-theory", "VSEPR Theory", "Predicting molecular geometry from electron pair repulsion."),
                ],
            ),
            (
                "hybridization",
                "Hybridization",
                [
                    ("sp-sp2-sp3", "sp, sp2, sp3 Hybridization", "Mixing of atomic orbitals to form new hybrid orbitals of equal energy."),
                ],
            ),
        ],
    ),
    ("thermodynamics-chemistry", "Thermodynamics", 4.0, []),
    ("equilibrium", "Equilibrium", 4.0, []),
    ("redox-reactions", "Redox Reactions", 2.0, []),
    ("organic-chemistry-basics", "Organic Chemistry - Basic Principles", 4.0, []),
    ("electrochemistry", "Electrochemistry", 3.0, []),
]

BOTANY_CHAPTERS = [
    ("the-living-world", "The Living World", 2.0, []),
    ("plant-kingdom", "Plant Kingdom", 3.0, []),
    ("morphology-flowering-plants", "Morphology of Flowering Plants", 3.0, []),
    ("cell-unit-of-life", "Cell - The Unit of Life", 4.0, []),
    (
        "photosynthesis",
        "Photosynthesis in Higher Plants",
        4.0,
        [
            (
                "light-reaction",
                "Light Reaction",
                [
                    ("photophosphorylation", "Photophosphorylation", "ATP synthesis driven by the light-dependent electron transport chain."),
                ],
            ),
            (
                "dark-reaction",
                "Dark Reaction (Calvin Cycle)",
                [
                    ("c3-c4-pathway", "C3 vs C4 Pathway", "Two biochemical routes for carbon fixation with different efficiency under heat/light stress."),
                ],
            ),
            (
                "factors-affecting-photosynthesis",
                "Factors Affecting Photosynthesis",
                [
                    ("photorespiration", "Photorespiration", "Wasteful oxygenation pathway competing with carbon fixation in C3 plants."),
                ],
            ),
        ],
    ),
    ("plant-growth-development", "Plant Growth and Development", 3.0, []),
    ("sexual-reproduction-flowering-plants", "Sexual Reproduction in Flowering Plants", 3.0, []),
]

ZOOLOGY_CHAPTERS = [
    ("animal-kingdom", "Animal Kingdom", 4.0, []),
    ("structural-organisation-animals", "Structural Organisation in Animals", 2.0, []),
    ("biomolecules", "Biomolecules", 3.0, []),
    ("digestion-absorption", "Digestion and Absorption", 2.0, []),
    ("breathing-exchange-of-gases", "Breathing and Exchange of Gases", 3.0, []),
    (
        "body-fluids-circulation",
        "Body Fluids and Circulation",
        4.0,
        [
            (
                "blood-and-blood-groups",
                "Blood and Blood Groups",
                [
                    ("abo-blood-grouping", "ABO Blood Grouping System", "Classification of blood based on antigens present on red blood cells."),
                ],
            ),
            (
                "cardiac-cycle",
                "Cardiac Cycle",
                [
                    ("cardiac-cycle-phases", "Cardiac Cycle Phases", "Systole and diastole phases governing one heartbeat."),
                ],
            ),
            (
                "human-heart-anatomy",
                "Human Heart Anatomy",
                [
                    ("heart-structure", "Structure of the Human Heart", "Four chambers, valves, and major vessels of the heart."),
                ],
            ),
        ],
    ),
    ("human-reproduction", "Human Reproduction", 3.0, []),
]

SUBJECTS = [
    ("PHYSICS", "Physics", PHYSICS_CHAPTERS),
    ("CHEMISTRY", "Chemistry", CHEMISTRY_CHAPTERS),
    ("BOTANY", "Botany", BOTANY_CHAPTERS),
    ("ZOOLOGY", "Zoology", ZOOLOGY_CHAPTERS),
]


async def seed_academic(session: AsyncSession) -> None:
    result = await session.execute(select(Exam).where(Exam.code == "NEET"))
    exam = result.scalar_one_or_none()
    if not exam:
        exam = Exam(code="NEET", name="NEET UG", description="National Eligibility cum Entrance Test (Undergraduate)")
        session.add(exam)
        await session.flush()
        logger.info("exam_seeded", code="NEET")

    for subject_order, (subject_code, subject_name, chapters) in enumerate(SUBJECTS):
        result = await session.execute(
            select(Subject).where(Subject.exam_id == exam.id, Subject.code == subject_code)
        )
        subject = result.scalar_one_or_none()
        if not subject:
            subject = Subject(exam_id=exam.id, code=subject_code, name=subject_name, display_order=subject_order)
            session.add(subject)
            await session.flush()
            logger.info("subject_seeded", code=subject_code)

        for chapter_order, (chapter_code, chapter_name, weightage, topics) in enumerate(chapters):
            result = await session.execute(
                select(Chapter).where(Chapter.subject_id == subject.id, Chapter.code == chapter_code)
            )
            chapter = result.scalar_one_or_none()
            if not chapter:
                chapter = Chapter(
                    subject_id=subject.id,
                    code=chapter_code,
                    name=chapter_name,
                    display_order=chapter_order,
                    neet_weightage_percent=weightage,
                )
                session.add(chapter)
                await session.flush()
                logger.info("chapter_seeded", code=chapter_code)

            for topic_order, (topic_code, topic_name, concepts) in enumerate(topics):
                result = await session.execute(
                    select(Topic).where(Topic.chapter_id == chapter.id, Topic.code == topic_code)
                )
                topic = result.scalar_one_or_none()
                if not topic:
                    topic = Topic(chapter_id=chapter.id, code=topic_code, name=topic_name, display_order=topic_order)
                    session.add(topic)
                    await session.flush()
                    logger.info("topic_seeded", code=topic_code)

                for concept_order, (concept_code, concept_name, summary) in enumerate(concepts):
                    result = await session.execute(
                        select(Concept).where(Concept.topic_id == topic.id, Concept.code == concept_code)
                    )
                    concept = result.scalar_one_or_none()
                    if not concept:
                        session.add(
                            Concept(
                                topic_id=topic.id,
                                code=concept_code,
                                name=concept_name,
                                summary=summary,
                                display_order=concept_order,
                            )
                        )
                        logger.info("concept_seeded", code=concept_code)

    await session.commit()
    logger.info("academic_seed_complete")
