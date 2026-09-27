"""One-time Gemini Stage-2 PYQ backfill (FACTORY-PYQ-P5 batch orchestrator).

Uses the same minimal-FK-chain seeding pattern as test_pyq_resolver_worker.py
(duplicated here rather than imported, to keep this file independently
runnable). A fake AI gateway stands in for the real Gemini call — no
network, no cost, no real Batch API involved (that path is separately
flagged as unverified in pyq_gemini_backfill.py's own module docstring).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from app.modules.cms.pyq.pyq_gemini_backfill import (
    BackfillAlreadyRunning,
    get_backfill_status,
    run_backfill,
    start_full_backfill,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_academic_chain(db_session) -> uuid.UUID:
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
        {"i": subject_id, "eid": exam_id, "c": f"SUB-{uuid.uuid4().hex[:8]}", "n": "Biology"},
    )
    chapter_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO academic.chapters (id, subject_id, code, name, display_order, version) "
            "VALUES (:i, :sid, :c, :n, 1, 1)"
        ),
        {"i": chapter_id, "sid": subject_id, "c": f"CH-{uuid.uuid4().hex[:8]}", "n": "Cell Biology"},
    )
    topic_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO academic.topics (id, chapter_id, code, name, display_order, version) "
            "VALUES (:i, :cid, :c, :n, 1, 1)"
        ),
        {"i": topic_id, "cid": chapter_id, "c": f"TOP-{uuid.uuid4().hex[:8]}", "n": "Organelles"},
    )
    concept_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO academic.concepts (id, topic_id, code, name, difficulty, display_order, version) "
            "VALUES (:i, :tid, :c, :n, 'MEDIUM', 1, 1)"
        ),
        {"i": concept_id, "tid": topic_id, "c": f"CON-{uuid.uuid4().hex[:8]}", "n": "Mitochondria"},
    )
    return concept_id


async def _seed_ingestion_section(db_session) -> uuid.UUID:
    job_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO ingestion.ingestion_jobs "
            "(id, source_file_path, file_checksum, status, sections_detected, questions_generated, "
            "questions_deduped, version, flashcards_generated, notes_generated, revision_sheets_generated, "
            "knowledge_units_created, knowledge_units_rejected, generation_skipped_no_knowledge_unit, "
            "visual_assets_detected, visual_assets_needing_review) "
            "VALUES (:i, 'test.pdf', :chk, 'COMPLETED', 0,0,0,1,0,0,0,0,0,0,0,0)"
        ),
        {"i": job_id, "chk": uuid.uuid4().hex},
    )
    section_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO ingestion.ingestion_sections "
            "(id, job_id, heading, source_page, raw_text, questions_generated, version) "
            "VALUES (:i, :jid, 'Test Section', 1, 'raw text', 0, 1)"
        ),
        {"i": section_id, "jid": job_id},
    )
    return section_id


async def _seed_knowledge_unit(db_session, *, concept_id, section_id, summary: str) -> uuid.UUID:
    ku_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO knowledge.knowledge_units "
            "(id, version, content_hash, structured_facts, summary, source_section_id, concept_id, "
            "extraction_confidence, validation_status) "
            "VALUES (:i, 1, :hash, :facts, :summary, :sid, :cid, 0.9, 'VALIDATED')"
        ),
        {
            "i": ku_id, "hash": uuid.uuid4().hex, "facts": json.dumps([summary]), "summary": summary,
            "sid": section_id, "cid": concept_id,
        },
    )
    return ku_id


async def _seed_source_file(db_session) -> uuid.UUID:
    source_id = (
        await db_session.execute(
            text(
                "INSERT INTO pyq.sources (source_key, name, authority_type) "
                "VALUES (:k, 'Test Source', 'OFFICIAL_NEET_PAPER') RETURNING id"
            ),
            {"k": f"SRC-{uuid.uuid4().hex[:8]}"},
        )
    ).scalar_one()
    batch_id = (
        await db_session.execute(
            text(
                "INSERT INTO pyq.import_batches (source_id, pipeline_stage, zip_sha256, manifest_path) "
                "VALUES (:s, 'test', :z, 'm') RETURNING id"
            ),
            {"s": source_id, "z": uuid.uuid4().hex},
        )
    ).scalar_one()
    return (
        await db_session.execute(
            text(
                "INSERT INTO pyq.source_files (batch_id, paper_id, relative_path, file_sha256) "
                "VALUES (:b, :p, 't.pdf', :sh) RETURNING id"
            ),
            {"b": batch_id, "p": uuid.uuid4().hex[:16], "sh": uuid.uuid4().hex},
        )
    ).scalar_one()


async def _seed_question(db_session, *, source_file_id, question_number, stem, options, state="ANSWER_PENDING"):
    return (
        await db_session.execute(
            text(
                "INSERT INTO pyq.questions "
                "(source_file_id, question_number, staging_id, question_hash, normalized_question_hash, "
                "raw_stem, raw_options, state) "
                "VALUES (:sf, :qn, :stg, :qh, :nqh, :stem, CAST(:opts AS jsonb), :state) RETURNING id"
            ),
            {
                "sf": source_file_id, "qn": question_number, "stg": uuid.uuid4().hex, "qh": uuid.uuid4().hex,
                "nqh": uuid.uuid4().hex, "stem": stem, "opts": json.dumps(options), "state": state,
            },
        )
    ).scalar_one()


_STEM = "Which organelle is described as the site of aerobic cellular respiration and ATP generation?"
_SUMMARY = (
    "This double-membrane-bound organelle is the primary site where aerobic "
    "cellular respiration occurs, generating most of the cell's usable "
    "chemical energy through oxidative phosphorylation."
)
_OPTIONS = {"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"}


class _FakeAIResponse:
    def __init__(self, text: str, *, is_fallback: bool = False):
        self.text = text
        self.model = "fake-gemini"
        self.is_fallback = is_fallback


class _FakeAIGateway:
    def __init__(self, response_text: str, *, is_fallback: bool = False):
        self._response_text = response_text
        self._is_fallback = is_fallback
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeAIResponse(self._response_text, is_fallback=self._is_fallback)


async def test_start_full_backfill_only_includes_answer_pending_questions(db_session):
    """A question already VERIFIED/CONFLICT before the backfill starts must
    never even be included in the job — not just excluded at apply time."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=_SUMMARY)
    source_file_id = await _seed_source_file(db_session)
    await _seed_question(db_session, source_file_id=source_file_id, question_number=1, stem=_STEM, options=_OPTIONS)
    await _seed_question(
        db_session, source_file_id=source_file_id, question_number=2, stem="already done",
        options={"A": "X", "B": "Y", "C": "Z", "D": "W"}, state="ANSWER_VERIFIED",
    )
    await db_session.commit()

    job_id = await start_full_backfill(db_session)
    status = await get_backfill_status(db_session, job_id)
    assert status["question_count"] == 1  # only the pending one


async def test_duplicate_launch_is_hard_blocked(db_session):
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=_SUMMARY)
    source_file_id = await _seed_source_file(db_session)
    await _seed_question(db_session, source_file_id=source_file_id, question_number=1, stem=_STEM, options=_OPTIONS)
    await db_session.commit()

    await start_full_backfill(db_session)
    with pytest.raises(BackfillAlreadyRunning):
        await start_full_backfill(db_session)


async def test_run_backfill_verifies_and_records_provenance(db_session):
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    ku_id = await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=_SUMMARY)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(db_session, source_file_id=source_file_id, question_number=1, stem=_STEM, options=_OPTIONS)
    await db_session.commit()

    job_id = await start_full_backfill(db_session)
    fake_gw = _FakeAIGateway(
        json.dumps({
            "supported_options": ["A"], "reasoning": "matches mitochondria",
            "confidence": 0.95, "supporting_knowledge_unit_ids": [str(ku_id)[:8]],
        })
    )
    status = await run_backfill(db_session, job_id, ai_gateway=fake_gw)

    assert status["job_status"] == "COMPLETED"
    assert status["verified"] == 1
    assert status["completion_pct"] == 100.0
    assert len(fake_gw.calls) == 1

    state = (await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})).scalar_one()
    assert state == "ANSWER_VERIFIED"
    assertion = (
        await db_session.execute(
            text("SELECT resolver_version, evidence_note FROM pyq.answer_assertions WHERE question_id = :i"), {"i": qid}
        )
    ).one()
    assert "gemini_backfill" in assertion.evidence_note
    assert str(ku_id) in assertion.evidence_note or str(ku_id)[:8] in assertion.evidence_note


async def test_resuming_a_completed_job_is_a_pure_noop(db_session):
    """Idempotent/resumable: calling run_backfill again after completion
    must not re-invoke the model or touch the question a second time."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=_SUMMARY)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(db_session, source_file_id=source_file_id, question_number=1, stem=_STEM, options=_OPTIONS)
    await db_session.commit()

    job_id = await start_full_backfill(db_session)
    fake_gw = _FakeAIGateway(json.dumps({"supported_options": ["A"], "reasoning": "x", "confidence": 0.9, "supporting_knowledge_unit_ids": []}))
    await run_backfill(db_session, job_id, ai_gateway=fake_gw)
    assert len(fake_gw.calls) == 1

    second = await run_backfill(db_session, job_id, ai_gateway=fake_gw)
    assert len(fake_gw.calls) == 1  # unchanged — no re-invocation
    assert second["job_status"] == "COMPLETED"

    count = (
        await db_session.execute(text("SELECT count(*) FROM pyq.answer_assertions WHERE question_id = :i"), {"i": qid})
    ).scalar_one()
    assert count == 1  # no duplicate assertion


async def test_never_overwrites_a_question_resolved_by_something_else_mid_run(db_session):
    """If another process (the ongoing worker, a human reviewer) resolves
    the question between job start and this item being processed, the
    backfill must skip it rather than overwrite."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=_SUMMARY)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(db_session, source_file_id=source_file_id, question_number=1, stem=_STEM, options=_OPTIONS)
    await db_session.commit()

    job_id = await start_full_backfill(db_session)

    # Simulate a concurrent resolution landing after the job was created
    # but before run_backfill processes this item.
    await db_session.execute(
        text("UPDATE pyq.questions SET state = 'ANSWER_CONFLICT', updated_at = now() WHERE id = :i"), {"i": qid}
    )
    await db_session.commit()

    fake_gw = _FakeAIGateway(json.dumps({"supported_options": ["A"], "reasoning": "would overwrite", "confidence": 0.99, "supporting_knowledge_unit_ids": []}))
    status = await run_backfill(db_session, job_id, ai_gateway=fake_gw)

    assert len(fake_gw.calls) == 0  # never even called — skipped before the model
    assert status["conflict"] == 1
    assert status["verified"] == 0
    state = (await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})).scalar_one()
    assert state == "ANSWER_CONFLICT"  # untouched, not overwritten
    count = (
        await db_session.execute(text("SELECT count(*) FROM pyq.answer_assertions WHERE question_id = :i"), {"i": qid})
    ).scalar_one()
    assert count == 0


async def test_retryable_error_is_retried_with_backoff_then_succeeds(db_session):
    """429/timeout/unavailable-style errors get bounded exponential-backoff
    retries; a question must not be marked FAILED just because an early
    attempt hit a transient error."""
    from app.modules.ai.gateway.base import PROVIDER_RATE_LIMITED, ProviderError

    class _RetryThenSucceedGateway:
        def __init__(self, fail_times: int, response_text: str):
            self.fail_times = fail_times
            self.response_text = response_text
            self.calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            if self.calls <= self.fail_times:
                raise ProviderError(PROVIDER_RATE_LIMITED, "rate limited", provider="fake", retryable=True)
            return _FakeAIResponse(self.response_text)

    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=_SUMMARY)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(db_session, source_file_id=source_file_id, question_number=1, stem=_STEM, options=_OPTIONS)
    await db_session.commit()

    job_id = await start_full_backfill(db_session)
    gateway = _RetryThenSucceedGateway(
        fail_times=2, response_text=json.dumps({"supported_options": ["A"], "reasoning": "x"})
    )
    status = await run_backfill(db_session, job_id, ai_gateway=gateway)

    assert gateway.calls == 3  # 2 failed attempts + 1 success — bounded, not indefinite
    assert status["job_status"] == "COMPLETED"
    assert status["verified"] == 1
    assert status["failed"] == 0
    state = (await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})).scalar_one()
    assert state == "ANSWER_VERIFIED"


async def test_non_retryable_error_fails_immediately_without_retry_loop(db_session):
    """Auth failure / invalid-model-style errors must never be retried
    indefinitely — they fail the item on the first attempt, leaving the
    question ANSWER_PENDING (never a false VERIFIED)."""
    from app.modules.ai.gateway.base import PROVIDER_AUTH_FAILED, ProviderError

    class _AlwaysAuthFailGateway:
        def __init__(self):
            self.calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            raise ProviderError(PROVIDER_AUTH_FAILED, "auth failed", provider="fake", retryable=False)

    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=_SUMMARY)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(db_session, source_file_id=source_file_id, question_number=1, stem=_STEM, options=_OPTIONS)
    await db_session.commit()

    job_id = await start_full_backfill(db_session)
    gateway = _AlwaysAuthFailGateway()
    status = await run_backfill(db_session, job_id, ai_gateway=gateway)

    assert gateway.calls == 1  # no retries at all — non-retryable
    assert status["job_status"] == "PARTIAL"
    assert status["failed"] == 1
    state = (await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})).scalar_one()
    assert state == "ANSWER_PENDING"  # never falsely verified
    count = (
        await db_session.execute(text("SELECT count(*) FROM pyq.answer_assertions WHERE question_id = :i"), {"i": qid})
    ).scalar_one()
    assert count == 0


async def test_insufficient_evidence_leaves_question_pending(db_session):
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1,
        stem="Completely unrelated stem about quantum entanglement.",
        options={"A": "Photon", "B": "Electron", "C": "Neutron", "D": "Proton"},
    )
    await db_session.commit()

    job_id = await start_full_backfill(db_session)
    fake_gw = _FakeAIGateway(json.dumps({"supported_options": ["A"], "reasoning": "should never be used"}))
    status = await run_backfill(db_session, job_id, ai_gateway=fake_gw)

    assert len(fake_gw.calls) == 0  # zero retrieved evidence — never invoked
    assert status["pending"] == 1
    state = (await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})).scalar_one()
    assert state == "ANSWER_PENDING"
