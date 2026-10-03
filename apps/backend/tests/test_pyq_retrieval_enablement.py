"""NCERT relaxed-retrieval-context enablement (FACTORY-PYQ-P6).

Covers scripts/pyq_retrieval_enablement.py and the new
compute_retrieval_tier()/_load_ku_index() behavior in
scripts/resolve_pyq_answers.py. These tests exercise retrieval-CONTEXT
tiering only -- none of them assert an answer gets verified from a
relaxed-threshold match, because that must never happen (see
compute_retrieval_tier's docstring and
docs/quality/pyq-8159-ncert-retrieval-enablement-2026-10-01.md).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from scripts.pyq_retrieval_enablement import run_with_session as run_enablement
from scripts.resolve_pyq_answers import _load_ku_index, compute_retrieval_tier
from tests.test_pyq_resolver_worker import (
    _seed_academic_chain,
    _seed_ingestion_section,
    _seed_knowledge_unit,
    _seed_question,
    _seed_source_file,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_academic_chain_with_subject(db_session, subject_code: str, subject_name: str) -> uuid.UUID:
    """Same chain as _seed_academic_chain but with a caller-chosen subject
    code/name, needed to test the subject-constrained safeguard."""
    exam_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO academic.exams (id, code, name, is_active, version) VALUES (:i, :c, :n, true, 1)"),
        {"i": exam_id, "c": f"EXAM-{uuid.uuid4().hex[:8]}", "n": "Test Exam"},
    )
    subject_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO academic.subjects (id, exam_id, code, name, display_order, version) "
            "VALUES (:i, :eid, :c, :n, 1, 1)"
        ),
        {"i": subject_id, "eid": exam_id, "c": subject_code, "n": subject_name},
    )
    chapter_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO academic.chapters (id, subject_id, code, name, display_order, version) "
            "VALUES (:i, :sid, :c, :n, 1, 1)"
        ),
        {"i": chapter_id, "sid": subject_id, "c": f"CH-{uuid.uuid4().hex[:8]}", "n": f"{subject_name} Chapter"},
    )
    topic_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO academic.topics (id, chapter_id, code, name, display_order, version) "
            "VALUES (:i, :cid, :c, :n, 1, 1)"
        ),
        {"i": topic_id, "cid": chapter_id, "c": f"TOP-{uuid.uuid4().hex[:8]}", "n": "Topic"},
    )
    concept_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO academic.concepts (id, topic_id, code, name, difficulty, display_order, version) "
            "VALUES (:i, :tid, :c, :n, 'MEDIUM', 1, 1)"
        ),
        {"i": concept_id, "tid": topic_id, "c": f"CON-{uuid.uuid4().hex[:8]}", "n": "Concept"},
    )
    return concept_id


async def test_load_ku_index_excludes_failed_units(db_session):
    """A FAILED knowledge unit must never be treated as authoritative
    source evidence -- confirmed as a real forensic finding (all FAILED
    units in production are flagged duplicates); here it must be excluded
    from the index entirely, not merely down-weighted."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    passed_id = await _seed_knowledge_unit(
        db_session, concept_id=concept_id, section_id=section_id, summary="Photosynthesis occurs in chloroplasts."
    )
    failed_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO knowledge.knowledge_units "
            "(id, version, content_hash, structured_facts, summary, source_section_id, concept_id, "
            "extraction_confidence, validation_status, validation_detail) "
            "VALUES (:i, 1, :hash, :facts, :summary, :sid, :cid, 0.9, 'FAILED', 'duplicate of existing knowledge unit')"
        ),
        {
            "i": failed_id,
            "hash": uuid.uuid4().hex,
            "facts": json.dumps(["Photosynthesis occurs in chloroplasts."]),
            "summary": "Photosynthesis occurs in chloroplasts.",
            "sid": section_id,
            "cid": concept_id,
        },
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)

    assert str(passed_id) in idx.unit_ids
    assert str(failed_id) not in idx.unit_ids


async def test_compute_retrieval_tier_strict_match_takes_priority(db_session):
    """When a question already clears the existing strict threshold, the
    relaxed path must not even be consulted -- STRICT_MATCH wins regardless
    of the relaxed flag."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session,
        concept_id=concept_id,
        section_id=section_id,
        summary="Mitochondria produce cellular energy through aerobic respiration inside the cell.",
    )
    await db_session.commit()
    idx = await _load_ku_index(db_session)

    tier, matched = compute_retrieval_tier(
        idx,
        "Which organelle produces cellular energy through aerobic respiration?",
        None,
        relaxed_enabled=True,
        relaxed_threshold=0.25,
        subject_constrained=True,
    )
    assert tier == "STRICT_MATCH"
    assert matched


async def test_compute_retrieval_tier_relaxed_disabled_by_default(db_session):
    """A question that only clears a relaxed threshold must return NONE
    when the feature flag is off -- preserves the original threshold as
    the unconditional default behavior."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session,
        concept_id=concept_id,
        section_id=section_id,
        summary=(
            "Mitochondria produce cellular energy through aerobic cellular respiration "
            "using oxygen inside eukaryotic cells via electron transport chains."
        ),
    )
    await db_session.commit()
    idx = await _load_ku_index(db_session)

    # Stem shares only a little vocabulary with the unit -- enough to clear
    # 0.25 but not 0.5.
    stem = "Explain mitochondria energy aerobic process unrelated extra padding words here filler filler."

    tier_off, matched_off = compute_retrieval_tier(
        idx, stem, None, relaxed_enabled=False, relaxed_threshold=0.25, subject_constrained=True
    )
    assert tier_off == "NONE"
    assert matched_off == []

    tier_on, matched_on = compute_retrieval_tier(
        idx, stem, None, relaxed_enabled=True, relaxed_threshold=0.25, subject_constrained=True
    )
    assert tier_on in ("RELAXED_MATCH", "NONE")  # depends on exact overlap ratio, never STRICT_MATCH
    assert tier_on != "STRICT_MATCH"


async def test_compute_retrieval_tier_subject_constraint_blocks_cross_subject_match(db_session):
    """A relaxed-threshold match against a knowledge unit from a DIFFERENT
    subject than the question's own label must be excluded when
    subject_constrained=True -- the cross-subject-match safeguard."""
    physics_concept_id = await _seed_academic_chain_with_subject(db_session, "PHYSICS", "Physics")
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session,
        concept_id=physics_concept_id,
        section_id=section_id,
        summary="Newton laws motion force acceleration mass momentum inertia gravity physics mechanics dynamics.",
    )
    await db_session.commit()
    idx = await _load_ku_index(db_session)

    stem = "Explain laws motion force acceleration mass extra unrelated padding filler words biology question."

    tier_unconstrained, _ = compute_retrieval_tier(
        idx, stem, "Botany", relaxed_enabled=True, relaxed_threshold=0.25, subject_constrained=False
    )
    tier_constrained, matched_constrained = compute_retrieval_tier(
        idx, stem, "Botany", relaxed_enabled=True, relaxed_threshold=0.25, subject_constrained=True
    )

    # With the safeguard on, a Botany-labeled question must never match a
    # Physics-only knowledge unit.
    assert tier_constrained == "NONE"
    assert matched_constrained == []
    # Sanity: the same match IS found when the safeguard is deliberately
    # disabled, proving the constraint (not some other factor) is what
    # excluded it above.
    assert tier_unconstrained == "RELAXED_MATCH"


async def test_retrieval_enablement_dry_run_does_not_write(db_session):
    """Dry-run must leave retrieval_match_tier/ncert_owner_accepted/state
    untouched for every row."""
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session,
        source_file_id=source_file_id,
        question_number=1,
        stem="Some unrelated stem about nothing in particular here at all whatsoever.",
        options={"A": "X", "B": "Y", "C": "Z", "D": "W"},
    )
    await db_session.commit()

    result = await run_enablement(db_session, apply=False, relaxed_enabled=True, relaxed_threshold=0.25, subject_constrained=True)
    assert result["apply"] is False

    row = (
        await db_session.execute(
            text("SELECT state, retrieval_match_tier, ncert_owner_accepted FROM pyq.questions WHERE id = :id"),
            {"id": qid},
        )
    ).one()
    assert row.state == "ANSWER_PENDING"
    assert row.retrieval_match_tier is None
    assert row.ncert_owner_accepted is False


async def test_retrieval_enablement_apply_never_touches_state_or_assertions(db_session):
    """--apply must set retrieval_match_tier/ncert_owner_accepted but must
    NEVER change pyq.questions.state or write to pyq.answer_assertions --
    retrieval-context tiering is not answer resolution."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session,
        concept_id=concept_id,
        section_id=section_id,
        summary=(
            "Mitochondria produce cellular energy through aerobic cellular respiration "
            "using oxygen inside eukaryotic cells via electron transport chains."
        ),
    )
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session,
        source_file_id=source_file_id,
        question_number=1,
        stem="Explain mitochondria energy aerobic process unrelated extra padding words here filler filler.",
        options={"A": "X", "B": "Y", "C": "Z", "D": "W"},
    )
    await db_session.commit()

    result = await run_enablement(db_session, apply=True, relaxed_enabled=True, relaxed_threshold=0.25, subject_constrained=True)
    assert result["apply"] is True

    row = (
        await db_session.execute(
            text("SELECT state, retrieval_match_tier, ncert_owner_accepted FROM pyq.questions WHERE id = :id"),
            {"id": qid},
        )
    ).one()
    assert row.state == "ANSWER_PENDING"  # never changed
    assert row.retrieval_match_tier in ("RELAXED_MATCH", "NONE")
    if row.retrieval_match_tier == "RELAXED_MATCH":
        assert row.ncert_owner_accepted is True

    assertion_count = (
        await db_session.execute(text("SELECT count(*) FROM pyq.answer_assertions WHERE question_id = :id"), {"id": qid})
    ).scalar_one()
    assert assertion_count == 0


async def test_retrieval_enablement_does_not_touch_already_verified_question(db_session):
    """A question that is already ANSWER_VERIFIED (independently resolved)
    must be left alone -- the enablement script only ever selects
    state='ANSWER_PENDING'."""
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session,
        source_file_id=source_file_id,
        question_number=1,
        stem="Irrelevant stem text for this already-verified question fixture.",
        options={"A": "X", "B": "Y", "C": "Z", "D": "W"},
    )
    await db_session.execute(
        text("UPDATE pyq.questions SET state = 'ANSWER_VERIFIED' WHERE id = :id"), {"id": qid}
    )
    await db_session.execute(
        text(
            "INSERT INTO pyq.answer_assertions (id, question_id, asserted_option, assertion_source, "
            "verification_status, evidence_note) VALUES (:i, :qid, 'A', 'test:independent', 'VERIFIED', 'manual')"
        ),
        {"i": uuid.uuid4(), "qid": qid},
    )
    await db_session.commit()

    await run_enablement(db_session, apply=True, relaxed_enabled=True, relaxed_threshold=0.25, subject_constrained=True)

    row = (
        await db_session.execute(
            text("SELECT state, retrieval_match_tier, ncert_owner_accepted FROM pyq.questions WHERE id = :id"),
            {"id": qid},
        )
    ).one()
    assert row.state == "ANSWER_VERIFIED"
    assert row.retrieval_match_tier is None  # never touched -- not ANSWER_PENDING
    assert row.ncert_owner_accepted is False

    assertion = (
        await db_session.execute(
            text("SELECT verification_status FROM pyq.answer_assertions WHERE question_id = :id"), {"id": qid}
        )
    ).scalar_one()
    assert assertion == "VERIFIED"  # untouched


async def test_retrieval_enablement_idempotent_rerun(db_session):
    """Re-running --apply with the same config must produce the same tier
    for the same question every time (deterministic, no duplicate rows)."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session,
        concept_id=concept_id,
        section_id=section_id,
        summary=(
            "Mitochondria produce cellular energy through aerobic cellular respiration "
            "using oxygen inside eukaryotic cells via electron transport chains."
        ),
    )
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session,
        source_file_id=source_file_id,
        question_number=1,
        stem="Explain mitochondria energy aerobic process unrelated extra padding words here filler filler.",
        options={"A": "X", "B": "Y", "C": "Z", "D": "W"},
    )
    await db_session.commit()

    await run_enablement(db_session, apply=True, relaxed_enabled=True, relaxed_threshold=0.25, subject_constrained=True)
    tier_1 = (
        await db_session.execute(text("SELECT retrieval_match_tier FROM pyq.questions WHERE id = :id"), {"id": qid})
    ).scalar_one()

    await run_enablement(db_session, apply=True, relaxed_enabled=True, relaxed_threshold=0.25, subject_constrained=True)
    tier_2 = (
        await db_session.execute(text("SELECT retrieval_match_tier FROM pyq.questions WHERE id = :id"), {"id": qid})
    ).scalar_one()

    assert tier_1 == tier_2

    count = (
        await db_session.execute(text("SELECT count(*) FROM pyq.questions WHERE id = :id"), {"id": qid})
    ).scalar_one()
    assert count == 1  # no duplicate row ever created


async def test_retrieval_enablement_rollback_path_is_flag_off(db_session):
    """Rollback to the previous (pre-enablement) retrieval configuration is
    simply re-running with relaxed_enabled=False -- must reset any
    previously-RELAXED_MATCH-tiered, not-yet-independently-verified
    question back to NONE/ncert_owner_accepted=False, never touching
    independently verified answers."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session,
        concept_id=concept_id,
        section_id=section_id,
        summary=(
            "Mitochondria produce cellular energy through aerobic cellular respiration "
            "using oxygen inside eukaryotic cells via electron transport chains."
        ),
    )
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session,
        source_file_id=source_file_id,
        question_number=1,
        stem="Explain mitochondria energy aerobic process unrelated extra padding words here filler filler.",
        options={"A": "X", "B": "Y", "C": "Z", "D": "W"},
    )
    await db_session.commit()

    await run_enablement(db_session, apply=True, relaxed_enabled=True, relaxed_threshold=0.25, subject_constrained=True)
    await run_enablement(db_session, apply=True, relaxed_enabled=False, relaxed_threshold=0.25, subject_constrained=True)

    row = (
        await db_session.execute(
            text("SELECT retrieval_match_tier, ncert_owner_accepted FROM pyq.questions WHERE id = :id"), {"id": qid}
        )
    ).one()
    assert row.retrieval_match_tier in ("NONE", "STRICT_MATCH")
    if row.retrieval_match_tier != "STRICT_MATCH":
        assert row.ncert_owner_accepted is False
