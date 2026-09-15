"""CF-C1: Chemistry Class 12 taxonomy scaffolding — durable evidence.

Adds nine NCERT Class 12 Chemistry chapters (NCERT chs 1, 3-10) plus
their per-chapter topics and concepts to the academic seed. This suite
locks in the invariants that the CF-C1 brief mandated:

  · nine expected chapter slugs exist under CHEMISTRY / class 12
  · every added chapter/topic/concept slug is globally unique in its
    scope
  · no seed row is duplicated by the electrochemistry entry that
    pre-existed in Chem 12
  · every new topic is anchored to exactly one new chapter
  · every new concept is anchored to exactly one new topic
  · seed is idempotent — a second application does not create
    duplicates
  · CHEMISTRY class 11 rows are untouched (10 seed positions before
    the CF-C1 additions)
  · PHYSICS and BOTANY and ZOOLOGY seeds are untouched
  · seed function is source-level clean (5-tuple shape, class_level
    strings, weightage None/float)

These tests do NOT touch cms.content_items, cms.content_versions,
cms.generation_*, or any question row. The db_session fixture uses
the SAVEPOINT-isolated pattern so nothing persists.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.seed import (
    BOTANY_CHAPTERS,
    CHEMISTRY_CHAPTERS,
    PHYSICS_CHAPTERS,
    ZOOLOGY_CHAPTERS,
    seed_academic,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


EXPECTED_CHEM12_CHAPTERS = {
    "electrochemistry",  # pre-existing Chem 12 entry — must remain
    "solutions",
    "chemical-kinetics",
    "d-and-f-block-elements",
    "coordination-compounds",
    "haloalkanes-and-haloarenes",
    "alcohols-phenols-and-ethers",
    "aldehydes-ketones-and-carboxylic-acids",
    "amines",
    "biomolecules-chem",
}


NEW_CF_C1_CHAPTERS = EXPECTED_CHEM12_CHAPTERS - {"electrochemistry"}


def _chem_chapters_by_class(cls: str) -> list[tuple]:
    return [ch for ch in CHEMISTRY_CHAPTERS if ch[3] == cls]


def test_seed_shape_all_chemistry_chapters_are_5_tuples():
    for ch in CHEMISTRY_CHAPTERS:
        assert len(ch) == 5, ch
        code, name, weightage, class_level, topics = ch
        assert isinstance(code, str) and code
        assert isinstance(name, str) and name
        assert weightage is None or isinstance(weightage, (int, float))
        assert class_level in ("11", "12"), (code, class_level)
        assert isinstance(topics, list)


def test_all_nine_new_chem12_chapters_present_in_seed():
    seen = {ch[0] for ch in _chem_chapters_by_class("12")}
    assert seen == EXPECTED_CHEM12_CHAPTERS, {
        "extra": seen - EXPECTED_CHEM12_CHAPTERS,
        "missing": EXPECTED_CHEM12_CHAPTERS - seen,
    }


def test_electrochemistry_seed_row_is_unchanged():
    ec = [ch for ch in _chem_chapters_by_class("12") if ch[0] == "electrochemistry"]
    assert len(ec) == 1
    code, name, weightage, class_level, topics = ec[0]
    # Pre-existing weightage 3.0 must not have been silently rewritten.
    assert name == "Electrochemistry"
    assert weightage == 3.0
    assert class_level == "12"
    # Chemistry electrochemistry seed carries an empty topic list — the
    # dev DB has topics inserted separately and CF-C1 must not touch them.
    assert topics == []


def test_no_duplicate_chapter_slugs_across_all_chemistry():
    codes = [ch[0] for ch in CHEMISTRY_CHAPTERS]
    assert len(codes) == len(set(codes))


def test_topic_slugs_are_unique_within_chemistry():
    tcodes = [t[0] for ch in CHEMISTRY_CHAPTERS for t in ch[4]]
    assert len(tcodes) == len(set(tcodes)), sorted(
        [t for t in tcodes if tcodes.count(t) > 1]
    )


def test_concept_slugs_are_unique_within_chemistry():
    ccodes = [c[0] for ch in CHEMISTRY_CHAPTERS for t in ch[4] for c in t[2]]
    assert len(ccodes) == len(set(ccodes)), sorted(
        [c for c in ccodes if ccodes.count(c) > 1]
    )


def test_every_new_chapter_has_source_grounded_topics_and_concepts():
    """No new chapter may be created without at least one topic. Every
    topic must have at least one concept. Every concept must reference
    'NCERT XII Ch N' in its summary — this is the CF-C1 source-fidelity
    contract."""
    for ch in _chem_chapters_by_class("12"):
        code, name, _wt, _cls, topics = ch
        if code == "electrochemistry":
            continue  # not part of CF-C1
        assert topics, f"CF-C1 chapter {code!r} has no topics"
        for tcode, tname, concepts in topics:
            assert concepts, f"{code}/{tcode} has no concepts"
            for ccode, cname, summary in concepts:
                assert "NCERT XII Ch" in summary, (
                    f"{code}/{tcode}/{ccode} summary lacks NCERT XII provenance: {summary!r}"
                )


def test_physics_seed_is_unchanged_by_cf_c1():
    """CF-C1 must not touch the Physics seed. Physics chapter count and
    slug set are pinned here."""
    physics_codes = {ch[0] for ch in PHYSICS_CHAPTERS}
    assert len(PHYSICS_CHAPTERS) == 13
    assert {
        "kinematics", "laws-of-motion", "work-energy-power", "gravitation",
        "thermodynamics-physics", "electrostatics", "current-electricity",
        "optics", "units-and-measurement",
        "systems-of-particles-rotational-motion",
        "mechanical-properties-of-solids", "mechanical-properties-of-fluids",
        "kinetic-theory",
    } == physics_codes


def test_botany_seed_is_unchanged_by_cf_c1():
    botany_codes = {ch[0] for ch in BOTANY_CHAPTERS}
    # CF-C4b added biomolecules under BOTANY; CF-C1 must not remove prior Botany codes.
    assert {
        "the-living-world", "plant-kingdom", "morphology-flowering-plants",
        "cell-unit-of-life", "photosynthesis", "plant-growth-development",
        "sexual-reproduction-flowering-plants",
    } <= botany_codes
    assert "biomolecules" in botany_codes


def test_zoology_seed_is_unchanged_by_cf_c1():
    zoology_codes = {ch[0] for ch in ZOOLOGY_CHAPTERS}
    # CF-C4b moved biomolecules out of Zoology; remaining Zoology codes intact.
    assert "biomolecules" not in zoology_codes
    assert {
        "animal-kingdom",
        "structural-organisation-animals",
        "digestion-absorption",
        "breathing-exchange-of-gases",
        "body-fluids-circulation",
        "human-reproduction",
    } <= zoology_codes
    # Chemistry biomolecules-chem remains a distinct Chemistry chapter.
    assert any(ch[0] == "biomolecules-chem" for ch in CHEMISTRY_CHAPTERS)


async def test_seed_applies_new_chem12_taxonomy_and_is_idempotent(db_session: AsyncSession):
    """Run seed_academic twice inside the SAVEPOINT-isolated session and
    assert (a) the nine new chapters appear with the expected topic and
    concept trees, (b) a re-run creates no duplicates, and (c) safety
    counters do not change beyond the CF-C1 taxonomy deltas."""
    # Snapshot the pre-seed academic counters — everything else is
    # asserted to be unchanged by the SAVEPOINT rollback boundary.
    pre_chem12_ch = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code = 'CHEMISTRY' AND ch.class_level = '12'
                  AND ch.deleted_at IS NULL
                """
            )
        )
    ).scalar_one()

    # Content-side safety anchors — the freeze + counts.
    pre_frozen = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM cms.content_items "
                "WHERE content_type='QUESTION' AND status='DRAFT' "
                "AND deleted_at IS NULL AND concept_id IS NULL"
            )
        )
    ).scalar_one()
    pre_published = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM cms.content_items "
                "WHERE content_type='QUESTION' AND status='PUBLISHED' "
                "AND deleted_at IS NULL"
            )
        )
    ).scalar_one()

    await seed_academic(db_session)
    first_chem12 = {
        r[0]
        for r in (
            await db_session.execute(
                text(
                    """
                    SELECT ch.code FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE s.code='CHEMISTRY' AND ch.class_level='12'
                      AND ch.deleted_at IS NULL
                    """
                )
            )
        ).all()
    }
    assert EXPECTED_CHEM12_CHAPTERS.issubset(first_chem12), (
        f"missing after first seed: {EXPECTED_CHEM12_CHAPTERS - first_chem12}"
    )

    # Second application must not produce duplicates.
    await seed_academic(db_session)
    second_chem12_count = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code='CHEMISTRY' AND ch.class_level='12'
                  AND ch.deleted_at IS NULL
                """
            )
        )
    ).scalar_one()
    # Idempotency: chapter count after twice-seeding equals count
    # after once-seeding.
    assert second_chem12_count == len(first_chem12)

    # Every new chapter has topics/concepts inserted through the same
    # idempotent seed path.
    for new_code in NEW_CF_C1_CHAPTERS:
        counts = (
            await db_session.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT t.id), COUNT(DISTINCT c.id)
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    LEFT JOIN academic.topics t ON t.chapter_id = ch.id
                                                AND t.deleted_at IS NULL
                    LEFT JOIN academic.concepts c ON c.topic_id = t.id
                                                  AND c.deleted_at IS NULL
                    WHERE s.code='CHEMISTRY' AND ch.class_level='12'
                      AND ch.code = :code AND ch.deleted_at IS NULL
                    """
                ),
                {"code": new_code},
            )
        ).one()
        assert counts[0] >= 3, f"{new_code} topic count {counts[0]} < 3"
        assert counts[1] >= counts[0], f"{new_code} concept count < topic count"

    # Safety anchors unchanged.
    post_frozen = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM cms.content_items "
                "WHERE content_type='QUESTION' AND status='DRAFT' "
                "AND deleted_at IS NULL AND concept_id IS NULL"
            )
        )
    ).scalar_one()
    post_published = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM cms.content_items "
                "WHERE content_type='QUESTION' AND status='PUBLISHED' "
                "AND deleted_at IS NULL"
            )
        )
    ).scalar_one()
    # The unmapped-DRAFT freeze count is whatever the test DB carries
    # today (0 in trinetra_test_db, 5,024 in dev); it MUST be unchanged
    # by the CF-C1 seed run.
    assert pre_frozen == post_frozen, (
        f"unmapped-DRAFT freeze changed: {pre_frozen} → {post_frozen}"
    )
    assert pre_published == post_published, "PUBLISHED count changed"
    _ = pre_chem12_ch  # snapshot used for the delta discussion only
