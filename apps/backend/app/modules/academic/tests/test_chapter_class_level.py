"""RS-003-B-1: academic.chapters.class_level durable evidence.

Verifies the NCERT class taxonomy landed by migration
rs003b1_chapter_cls + Chapter model + academic.seed_academic:

  · column exists, is VARCHAR(2), and remains NULLABLE
  · CHECK constraint accepts '11', '12', NULL and rejects other values
  · the authorized chapter codes have the expected class assignment
  · Biology XI Biomolecules is BOTANY / class 11 (CF-C4b owner decision)
  · migration + seed agree on the baseline mappings
  · published QUESTION rows can derive class via the chapter chain
    (READ-ONLY probe — nothing is modified)
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.seed import (
    BOTANY_CHAPTERS,
    CHEMISTRY_CHAPTERS,
    PHYSICS_CHAPTERS,
    ZOOLOGY_CHAPTERS,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


EXPECTED_CLASS_11 = {
    "PHYSICS": {
        "units-and-measurement",
        "kinematics",
        "laws-of-motion",
        "work-energy-power",
        "systems-of-particles-rotational-motion",
        "gravitation",
        "mechanical-properties-of-solids",
        "mechanical-properties-of-fluids",
        "thermodynamics-physics",
        "kinetic-theory",
    },
    "CHEMISTRY": {
        "basic-concepts-chemistry",
        "structure-of-atom",
        "chemical-bonding",
        "thermodynamics-chemistry",
        "equilibrium",
        "redox-reactions",
        "organic-chemistry-basics",
    },
    "BOTANY": {
        "the-living-world",
        "plant-kingdom",
        "morphology-flowering-plants",
        "cell-unit-of-life",
        "photosynthesis",
        "plant-growth-development",
        "biomolecules",
    },
    "ZOOLOGY": {
        "animal-kingdom",
        "structural-organisation-animals",
        "digestion-absorption",
        "breathing-exchange-of-gases",
        "body-fluids-circulation",
    },
}

EXPECTED_CLASS_12 = {
    "PHYSICS": {"electrostatics", "current-electricity", "optics"},
    "CHEMISTRY": {"electrochemistry"},
    "BOTANY": {"sexual-reproduction-flowering-plants"},
    "ZOOLOGY": {"human-reproduction"},
}


async def test_column_exists_and_is_nullable_varchar_2(db_session: AsyncSession):
    row = (
        await db_session.execute(
            text(
                """
                SELECT data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'academic'
                  AND table_name = 'chapters'
                  AND column_name = 'class_level'
                """
            )
        )
    ).one_or_none()
    assert row is not None, "class_level column missing on academic.chapters"
    assert row[0] == "character varying"
    assert row[1] == 2
    assert row[2] == "YES", "class_level MUST remain NULLABLE in RS-003-B-1"


async def test_check_constraint_present(db_session: AsyncSession):
    count = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.check_constraints
                WHERE constraint_name = 'ck_chapters_class_level_allowed'
                """
            )
        )
    ).scalar_one()
    assert count == 1, "CK ck_chapters_class_level_allowed missing"


async def test_check_constraint_accepts_valid_values(db_session: AsyncSession):
    # Runs inside the SAVEPOINT-isolated session; no data persists.
    for cls in ("11", "12", None):
        params = {"cls": cls}
        await db_session.execute(
            text(
                """
                UPDATE academic.chapters
                SET class_level = :cls
                WHERE code = 'kinematics'
                """
            ),
            params,
        )
    # SAVEPOINT rollback at test end restores the original row.


# Only fits-in-VARCHAR(2) values reach the CHECK constraint; longer strings
# would be rejected by the type-length before the CHECK ever runs, which
# tests a different guarantee.
@pytest.mark.parametrize("bad", ["10", "13", "X", "AB"])
async def test_check_constraint_rejects_invalid_value(bad: str):
    """Uses a dedicated short-lived connection because the CHECK-constraint
    IntegrityError disturbs the SAVEPOINT-isolated db_session fixture and
    would prevent iterating over multiple bad values in one test."""
    from sqlalchemy.ext.asyncio import AsyncSession as _S
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_test_db",
        poolclass=NullPool,
    )
    try:
        async with _S(bind=engine) as sess:
            async with sess.begin():
                with pytest.raises(IntegrityError):
                    await sess.execute(
                        text(
                            "UPDATE academic.chapters SET class_level = :bad WHERE code = 'kinematics'"
                        ),
                        {"bad": bad},
                    )
    finally:
        await engine.dispose()


async def test_all_34_expected_class_11_rows_are_11(db_session: AsyncSession):
    for subject, codes in EXPECTED_CLASS_11.items():
        rows = (
            await db_session.execute(
                text(
                    """
                    SELECT ch.code, ch.class_level
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE s.code = :subj AND ch.code = ANY(:codes)
                    """
                ),
                {"subj": subject, "codes": list(codes)},
            )
        ).all()
        assert len(rows) == len(codes), f"{subject}: missing chapters {codes - {r[0] for r in rows}}"
        for code, cls in rows:
            assert cls == "11", f"{subject}/{code} expected class 11, got {cls!r}"


async def test_all_expected_class_12_rows_are_12(db_session: AsyncSession):
    for subject, codes in EXPECTED_CLASS_12.items():
        rows = (
            await db_session.execute(
                text(
                    """
                    SELECT ch.code, ch.class_level
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE s.code = :subj AND ch.code = ANY(:codes)
                    """
                ),
                {"subj": subject, "codes": list(codes)},
            )
        ).all()
        assert len(rows) == len(codes), f"{subject}: missing chapters {codes - {r[0] for r in rows}}"
        for code, cls in rows:
            assert cls == "12", f"{subject}/{code} expected class 12, got {cls!r}"


async def test_biomolecules_is_botany_class_11(db_session: AsyncSession):
    """CF-C4b owner decision: Biology XI Biomolecules → BOTANY / 11."""
    row = (
        await db_session.execute(
            text(
                """
                SELECT s.code, ch.class_level
                FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.code = 'biomolecules' AND ch.deleted_at IS NULL
                """
            )
        )
    ).one()
    assert row[0] == "BOTANY", f"biomolecules subject expected BOTANY, got {row[0]!r}"
    assert row[1] == "11", f"biomolecules class_level expected '11', got {row[1]!r}"

    zoo = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code = 'ZOOLOGY' AND ch.code = 'biomolecules' AND ch.deleted_at IS NULL
                """
            )
        )
    ).scalar_one()
    assert zoo == 0, "ZOOLOGY must not retain a biomolecules chapter after CF-C4b"


async def test_rs003b1_baseline_populated_and_biomolecules_resolved(db_session: AsyncSession):
    """RS-003-B-1A baseline remains populated; Biomolecules is resolved (CF-C4b)."""
    total = (
        await db_session.execute(text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL"))
    ).scalar_one()
    assert total >= 35, f"expected at least 35 chapters, got {total}"

    populated = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM academic.chapters WHERE class_level IS NOT NULL AND deleted_at IS NULL")
        )
    ).scalar_one()
    assert populated >= 35, f"expected all resolved chapters populated; got {populated}"

    nulls = (
        await db_session.execute(
            text(
                """
                SELECT s.code, ch.code FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.class_level IS NULL AND ch.deleted_at IS NULL
                ORDER BY s.code, ch.code
                """
            )
        )
    ).all()
    assert nulls == [], f"unexpected NULL class_level chapters after CF-C4b: {nulls}"


async def test_seed_and_migration_agree_on_all_34_mappings():
    """The seed tuples MUST assign the same class as the migration UPDATE.
    Purely in-process check — no DB touch."""
    all_tuples = {
        "PHYSICS": PHYSICS_CHAPTERS,
        "CHEMISTRY": CHEMISTRY_CHAPTERS,
        "BOTANY": BOTANY_CHAPTERS,
        "ZOOLOGY": ZOOLOGY_CHAPTERS,
    }
    seen_11: set[tuple[str, str]] = set()
    seen_12: set[tuple[str, str]] = set()
    biomol: tuple[str, object] | None = None
    for subj, chs in all_tuples.items():
        for tup in chs:
            assert len(tup) == 5, f"{subj} chapter tuple must be 5-length; got {tup!r}"
            code, _name, _weight, cls, _topics = tup
            if code == "biomolecules":
                biomol = (subj, cls)
            if cls == "11":
                seen_11.add((subj, code))
            elif cls == "12":
                seen_12.add((subj, code))
            else:
                assert cls is None, f"{subj}/{code} unexpected class_level {cls!r}"

    expected_11 = {(s, c) for s, cs in EXPECTED_CLASS_11.items() for c in cs}
    expected_12 = {(s, c) for s, cs in EXPECTED_CLASS_12.items() for c in cs}
    # RS-003-B-1A / CF-B baseline is asserted as a subset — CF-C1 and later
    # authorised additions may add further Class-12 chapters (e.g. Chem 12
    # Solutions). No baseline row may be dropped or reclassified.
    assert expected_11 <= seen_11, f"class-11 baseline regressed: missing={expected_11 - seen_11}"
    assert expected_12 <= seen_12, f"class-12 baseline regressed: missing={expected_12 - seen_12}"
    assert biomol == ("BOTANY", "11"), f"biomolecules seed ownership expected BOTANY/11, got {biomol!r}"
    assert not any(ch[0] == "biomolecules" for ch in ZOOLOGY_CHAPTERS)


async def test_published_questions_can_derive_class_read_only(db_session: AsyncSession):
    """READ-ONLY probe: every published QUESTION whose chapter has class_level
    set must derive that class through the concept → topic → chapter chain
    in one join. No writes; nothing modified."""
    (total_pub, derivable) = (
        await db_session.execute(
            text(
                """
                WITH published AS (
                    SELECT ci.id, ci.concept_id
                    FROM cms.content_items ci
                    WHERE ci.content_type = 'QUESTION'
                      AND ci.status = 'PUBLISHED'
                      AND ci.deleted_at IS NULL
                )
                SELECT
                    (SELECT COUNT(*) FROM published) AS total_published,
                    (SELECT COUNT(*)
                     FROM published p
                     JOIN academic.concepts c ON c.id = p.concept_id AND c.deleted_at IS NULL
                     JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                     JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                     WHERE ch.class_level IS NOT NULL) AS derivable
                """
            )
        )
    ).one()
    assert derivable == total_pub, (
        f"{total_pub - derivable} published questions cannot derive class "
        "through chapter.class_level — investigate before widening the gate."
    )
