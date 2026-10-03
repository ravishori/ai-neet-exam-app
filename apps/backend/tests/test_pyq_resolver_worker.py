"""Background PYQ answer-resolution worker (FACTORY-PYQ-P5).

These tests seed the minimal FK chain a real question needs
(exam -> subject -> chapter -> topic -> concept -> knowledge_unit,
plus ingestion_job -> ingestion_section, plus pyq source -> batch ->
source_file -> questions) with deliberately overlapping vocabulary so the
existing, unmodified grounding check (is_fact_grounded) actually resolves
something — no new resolution logic is exercised here, only the new
batching/ordering/lock/metadata wrapper around it.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.modules.cms.pyq import pyq_resolver_worker
from scripts.resolve_pyq_answers import RESOLVER_VERSION, RESOLVER_VERSION_STAGE2, _load_ku_index, resolve_up_to

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_academic_chain(db_session) -> uuid.UUID:
    # id/version have no DB-side default (assigned by the app's ORM mixin in
    # normal request flow) — raw SQL fixtures must supply both explicitly.
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


async def _seed_knowledge_unit(db_session, *, concept_id: uuid.UUID, section_id: uuid.UUID, summary: str) -> uuid.UUID:
    ku_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO knowledge.knowledge_units "
            "(id, version, content_hash, structured_facts, summary, source_section_id, concept_id, "
            "extraction_confidence, validation_status) "
            "VALUES (:i, 1, :hash, :facts, :summary, :sid, :cid, 0.9, 'PASSED')"
        ),
        {
            "i": ku_id,
            "hash": uuid.uuid4().hex,
            "facts": json.dumps([summary]),
            "summary": summary,
            "sid": section_id,
            "cid": concept_id,
        },
    )
    return ku_id


async def _seed_source_file(db_session) -> uuid.UUID:
    source_id = (
        await db_session.execute(
            text(
                "INSERT INTO pyq.sources (source_key, name, authority_type) "
                "VALUES (:k, 'Test Source', 'OFFICIAL_NEET_PAPER') "
                "ON CONFLICT (source_key) DO UPDATE SET name = EXCLUDED.name RETURNING id"
            ),
            {"k": f"TEST-SOURCE-{uuid.uuid4().hex[:8]}"},
        )
    ).scalar_one()
    batch_id = (
        await db_session.execute(
            text(
                "INSERT INTO pyq.import_batches (source_id, pipeline_stage, zip_sha256, manifest_path) "
                "VALUES (:sid, 'test', :sha, 'test.json') RETURNING id"
            ),
            {"sid": source_id, "sha": uuid.uuid4().hex},
        )
    ).scalar_one()
    source_file_id = (
        await db_session.execute(
            text(
                "INSERT INTO pyq.source_files (batch_id, paper_id, relative_path, file_sha256) "
                "VALUES (:bid, :pid, 'test.pdf', :sha) RETURNING id"
            ),
            {"bid": batch_id, "pid": uuid.uuid4().hex[:16], "sha": uuid.uuid4().hex},
        )
    ).scalar_one()
    return source_file_id


async def _seed_question(
    db_session, *, source_file_id: uuid.UUID, question_number: int, stem: str, options: dict,
    created_at: datetime | None = None,
) -> uuid.UUID:
    qid = (
        await db_session.execute(
            text(
                "INSERT INTO pyq.questions "
                "(source_file_id, question_number, staging_id, question_hash, normalized_question_hash, "
                "raw_stem, raw_options, state, created_at) "
                "VALUES (:sfid, :qn, :stg, :qh, :nqh, :stem, CAST(:opts AS jsonb), 'ANSWER_PENDING', "
                "COALESCE(:created_at, now())) RETURNING id"
            ),
            {
                "sfid": source_file_id,
                "qn": question_number,
                "stg": uuid.uuid4().hex,
                "qh": uuid.uuid4().hex,
                "nqh": uuid.uuid4().hex,
                "stem": stem,
                "opts": json.dumps(options),
                "created_at": created_at,
            },
        )
    ).scalar_one()
    return qid


async def test_resolve_up_to_verifies_a_clearly_grounded_question(db_session):
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session,
        concept_id=concept_id,
        section_id=section_id,
        summary="Mitochondria produce cellular energy through aerobic respiration inside the cell.",
    )
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session,
        source_file_id=source_file_id,
        question_number=1,
        stem="Which organelle produces cellular energy through aerobic respiration?",
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    report = await resolve_up_to(db_session, idx, max_total=10, apply=True)

    assert report.total_scanned == 1
    assert report.answered == 1
    assert report.conflicts == 0

    row = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :id"), {"id": qid})
    ).scalar_one()
    assert row == "ANSWER_VERIFIED"

    assertion = (
        await db_session.execute(
            text(
                "SELECT asserted_option, verification_status, resolver_version, explanation "
                "FROM pyq.answer_assertions WHERE question_id = :id"
            ),
            {"id": qid},
        )
    ).one()
    assert assertion.asserted_option == "A"
    assert assertion.verification_status == "VERIFIED"
    assert assertion.resolver_version == RESOLVER_VERSION
    assert assertion.explanation and "Mitochondria" in assertion.explanation


async def test_resolve_up_to_leaves_ungrounded_question_pending(db_session):
    """No knowledge unit at all overlaps this stem — must stay ANSWER_PENDING,
    never guessed."""
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session,
        source_file_id=source_file_id,
        question_number=1,
        stem="Completely unrelated stem about quantum entanglement experiments.",
        options={"A": "Photon", "B": "Electron", "C": "Neutron", "D": "Proton"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    report = await resolve_up_to(db_session, idx, max_total=10, apply=True)

    assert report.answered == 0
    assert report.conflicts == 0
    row = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :id"), {"id": qid})
    ).scalar_one()
    assert row == "ANSWER_PENDING"


async def test_resolve_up_to_respects_max_total_and_oldest_first_order(db_session):
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session,
        concept_id=concept_id,
        section_id=section_id,
        summary="Mitochondria produce cellular energy through aerobic respiration inside the cell.",
    )
    source_file_id = await _seed_source_file(db_session)

    now = datetime.now(UTC)
    older_qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1,
        stem="Which organelle produces cellular energy through aerobic respiration?",
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
        created_at=now - timedelta(days=1),
    )
    newer_qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=2,
        stem="Which organelle produces cellular energy through aerobic respiration?",
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
        created_at=now,
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    report = await resolve_up_to(db_session, idx, max_total=1, apply=True)

    assert report.total_scanned == 1
    older_state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :id"), {"id": older_qid})
    ).scalar_one()
    newer_state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :id"), {"id": newer_qid})
    ).scalar_one()
    assert older_state == "ANSWER_VERIFIED"  # oldest processed first
    assert newer_state == "ANSWER_PENDING"  # left for the next batch


async def test_resolve_up_to_never_touches_already_verified_question(db_session):
    """Idempotency / never-overwrite: resolve_up_to only ever selects
    state='ANSWER_PENDING' — running it again must not revisit a row that
    already reached ANSWER_VERIFIED."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session,
        concept_id=concept_id,
        section_id=section_id,
        summary="Mitochondria produce cellular energy through aerobic respiration inside the cell.",
    )
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1,
        stem="Which organelle produces cellular energy through aerobic respiration?",
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    first = await resolve_up_to(db_session, idx, max_total=10, apply=True)
    assert first.answered == 1

    second = await resolve_up_to(db_session, idx, max_total=10, apply=True)
    assert second.total_scanned == 0  # nothing left in ANSWER_PENDING

    count = (
        await db_session.execute(
            text("SELECT count(*) FROM pyq.answer_assertions WHERE question_id = :id"), {"id": qid}
        )
    ).scalar_one()
    assert count == 1  # no duplicate assertion from the second run


async def test_stage2_provider_failure_never_verifies(db_session):
    """A provider error (auth failure, timeout, rate limit — all raised as
    ProviderError by the real gateway/providers) must never be treated as
    an answer. Covers the failure path generically since every one of
    those cases hits the exact same `except ProviderError` branch."""
    from app.modules.ai.gateway.base import PROVIDER_RATE_LIMITED, ProviderError

    class _FailingGateway:
        def __init__(self):
            self.calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            raise ProviderError(PROVIDER_RATE_LIMITED, "rate limited", provider="fake", retryable=True)

    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    stem, summary = _seed_stage1_dead_end_question_kwargs()
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=summary)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1, stem=stem,
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    failing_gateway = _FailingGateway()
    report = await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=failing_gateway)

    assert failing_gateway.calls == 1  # the call was attempted
    assert report.stage2_answered == 0
    assert report.stage2_conflicts == 0
    assert report.stage2_unresolved == 1  # failure treated as unresolved, not an answer
    state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})
    ).scalar_one()
    assert state == "ANSWER_PENDING"  # never verified off a failed call
    count = (
        await db_session.execute(
            text("SELECT count(*) FROM pyq.answer_assertions WHERE question_id = :i"), {"i": qid}
        )
    ).scalar_one()
    assert count == 0  # no assertion at all from a failed call


async def test_stage2_fallback_response_never_verifies(db_session):
    """If no AI provider is configured/available, AIGateway returns a
    fallback stub response (is_fallback=True) instead of raising — that
    must also never be treated as real evidence-derived synthesis."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    stem, summary = _seed_stage1_dead_end_question_kwargs()
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=summary)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1, stem=stem,
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    fallback_gateway = _FakeAIGateway(
        json.dumps({"supported_options": ["A"], "reasoning": "would be an answer, but this is a fallback"}),
        is_fallback=True,
    )
    report = await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=fallback_gateway)

    assert report.stage2_answered == 0
    assert report.stage2_unresolved == 1
    state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})
    ).scalar_one()
    assert state == "ANSWER_PENDING"


class _FakeAIResponse:
    def __init__(self, text: str, *, model: str = "fake-model", is_fallback: bool = False):
        self.text = text
        self.model = model
        self.is_fallback = is_fallback


class _FakeAIGateway:
    """Stands in for AIGateway in resolve_stage2_batch — only implements the
    one method (`generate`) Stage 2 actually calls, matching AIGateway's
    real signature. Never touches a network or a real provider."""

    def __init__(self, response_text: str, *, is_fallback: bool = False):
        self._response_text = response_text
        self._is_fallback = is_fallback
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeAIResponse(self._response_text, is_fallback=self._is_fallback)


def _seed_stage1_dead_end_question_kwargs():
    """A stem+knowledge-unit pair Stage 1 cannot resolve: the unit describes
    the correct organelle's function without ever using the word
    "Mitochondria" (or any option word) — Stage 1's literal word-overlap
    check finds no option text in the evidence at all. A human (or a model
    reading semantically) would recognize the described function as
    mitochondrial respiration despite the wording difference."""
    stem = "Which organelle is described as the site of aerobic cellular respiration and ATP generation?"
    summary = (
        "This double-membrane-bound organelle is the primary site where aerobic "
        "cellular respiration occurs, generating most of the cell's usable "
        "chemical energy through oxidative phosphorylation."
    )
    return stem, summary


async def test_stage2_semantic_synthesis_verifies_despite_wording_difference(db_session):
    """Stage 1 must genuinely fail first (no literal option-word overlap),
    then Stage 2's AI synthesis — restricted to the same trusted indexed
    NCERT corpus — recognizes the semantic match despite different
    wording and verifies it."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    stem, summary = _seed_stage1_dead_end_question_kwargs()
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=summary)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1, stem=stem,
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    fake_gateway = _FakeAIGateway(
        json.dumps({
            "supported_options": ["A"],
            "reasoning": "The excerpt describes the site of aerobic respiration and ATP "
                         "generation via oxidative phosphorylation, which is the mitochondrion.",
        })
    )
    report = await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=fake_gateway)

    assert report.answered == 0  # Stage 1 genuinely found no literal option match
    assert report.unresolved_no_option_grounded == 1
    assert report.stage2_answered == 1
    assert len(fake_gateway.calls) == 1  # the model was actually invoked, once

    state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})
    ).scalar_one()
    assert state == "ANSWER_VERIFIED"

    assertion = (
        await db_session.execute(
            text(
                "SELECT asserted_option, verification_status, resolver_version, explanation "
                "FROM pyq.answer_assertions WHERE question_id = :i"
            ),
            {"i": qid},
        )
    ).one()
    assert assertion.asserted_option == "A"
    assert assertion.resolver_version == RESOLVER_VERSION_STAGE2
    assert "aerobic respiration" in assertion.explanation
    # One-pass Gemini answers are tagged AI_RESOLVED, never VERIFIED — they
    # must not be represented as independently NCERT-verified (Stage 1's
    # deterministic grounding check is the only path that writes VERIFIED).
    assert assertion.verification_status == "AI_RESOLVED"


async def test_stage2_run_id_recorded_in_evidence_note(db_session) -> None:
    """A processing-run identifier (docs/quality/pyq-gemini-one-pass-resolution-*.md
    provenance requirement) is embedded in evidence_note when the caller
    supplies one — no schema change needed since this is free-text
    provenance, not a new queryable column."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    stem, summary = _seed_stage1_dead_end_question_kwargs()
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=summary)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1, stem=stem,
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    fake_gateway = _FakeAIGateway(
        json.dumps({"supported_options": ["A"], "reasoning": "site of aerobic respiration"})
    )
    await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=fake_gateway, run_id="pilot-2026-10-01-001")

    evidence_note = (
        await db_session.execute(
            text("SELECT evidence_note FROM pyq.answer_assertions WHERE question_id = :i"), {"i": qid}
        )
    ).scalar_one()
    assert "run=pilot-2026-10-01-001" in evidence_note


async def test_stage2_conflict_assertions_remain_disputed_not_ai_resolved(db_session) -> None:
    """Multi-option-supported Stage 2 outcomes stay DISPUTED — AI_RESOLVED
    is reserved for the single-clean-answer case only."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    stem, summary = _seed_stage1_dead_end_question_kwargs()
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=summary)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1, stem=stem,
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    fake_gateway = _FakeAIGateway(
        json.dumps({"supported_options": ["A", "B"], "reasoning": "ambiguous evidence"})
    )
    await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=fake_gateway)

    statuses = {
        row[0]
        for row in (
            await db_session.execute(
                text("SELECT verification_status FROM pyq.answer_assertions WHERE question_id = :i"), {"i": qid}
            )
        ).all()
    }
    assert statuses == {"DISPUTED"}


async def test_stage2_unsupported_answer_stays_pending(db_session):
    """The model, restricted to the same trusted corpus, explicitly finds
    insufficient evidence (empty supported_options) — must stay
    ANSWER_PENDING, never guessed."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    stem, summary = _seed_stage1_dead_end_question_kwargs()
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=summary)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1, stem=stem,
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    fake_gateway = _FakeAIGateway(json.dumps({"supported_options": [], "reasoning": "Insufficient evidence."}))
    report = await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=fake_gateway)

    assert report.stage2_answered == 0
    assert report.stage2_conflicts == 0
    assert report.stage2_unresolved == 1
    state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})
    ).scalar_one()
    assert state == "ANSWER_PENDING"


async def test_stage2_never_invokes_model_with_zero_retrieved_evidence(db_session):
    """A stem sharing no vocabulary with the indexed corpus at all must
    never reach the model — there's nothing to synthesize from."""
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1,
        stem="Completely unrelated stem about quantum entanglement experiments.",
        options={"A": "Photon", "B": "Electron", "C": "Neutron", "D": "Proton"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    fake_gateway = _FakeAIGateway(json.dumps({"supported_options": ["A"], "reasoning": "should never be used"}))
    report = await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=fake_gateway)

    assert report.stage2_unresolved == 1
    assert fake_gateway.calls == []  # never invoked — no evidence, no call
    state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})
    ).scalar_one()
    assert state == "ANSWER_PENDING"


async def test_stage2_conflicting_source_evidence_marks_conflict(db_session):
    """The model itself reports the excerpts support more than one
    option — a contradiction the corpus itself contains, not something
    Stage 2 invents — must become ANSWER_CONFLICT with one DISPUTED
    assertion per reported option."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    stem, summary = _seed_stage1_dead_end_question_kwargs()
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=summary)
    source_file_id = await _seed_source_file(db_session)
    qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1, stem=stem,
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    fake_gateway = _FakeAIGateway(
        json.dumps({
            "supported_options": ["A", "B"],
            "reasoning": "The excerpts contain contradictory statements supporting both organelles.",
        })
    )
    report = await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=fake_gateway)

    assert report.stage2_conflicts == 1
    state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": qid})
    ).scalar_one()
    assert state == "ANSWER_CONFLICT"
    count = (
        await db_session.execute(
            text("SELECT count(*) FROM pyq.answer_assertions WHERE question_id = :i AND verification_status='DISPUTED'"),
            {"i": qid},
        )
    ).scalar_one()
    assert count == 2


async def test_stage2_never_invoked_for_already_verified_question(db_session):
    """Never overwrite VERIFIED: a question Stage 1 already resolved
    literally must never reach Stage 2 / the model at all, even when other
    still-pending questions in the same batch do."""
    concept_id = await _seed_academic_chain(db_session)
    section_id = await _seed_ingestion_section(db_session)
    await _seed_knowledge_unit(
        db_session, concept_id=concept_id, section_id=section_id,
        summary="Mitochondria produce cellular energy through aerobic respiration inside the cell.",
    )
    source_file_id = await _seed_source_file(db_session)
    verified_qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=1,
        stem="Which organelle produces cellular energy through aerobic respiration?",
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    stage2_stem, stage2_summary = _seed_stage1_dead_end_question_kwargs()
    await _seed_knowledge_unit(db_session, concept_id=concept_id, section_id=section_id, summary=stage2_summary)
    pending_qid = await _seed_question(
        db_session, source_file_id=source_file_id, question_number=2, stem=stage2_stem,
        options={"A": "Mitochondria", "B": "Ribosome", "C": "Golgi apparatus", "D": "Lysosome"},
    )
    await db_session.commit()

    idx = await _load_ku_index(db_session)
    fake_gateway = _FakeAIGateway(json.dumps({"supported_options": ["A"], "reasoning": "semantic match"}))
    report = await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=fake_gateway)

    assert report.answered == 1  # verified_qid, by Stage 1 literal match
    assert report.stage2_answered == 1  # pending_qid, by Stage 2 only
    assert len(fake_gateway.calls) == 1  # exactly one call — never for verified_qid

    verified_state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": verified_qid})
    ).scalar_one()
    pending_state = (
        await db_session.execute(text("SELECT state FROM pyq.questions WHERE id = :i"), {"i": pending_qid})
    ).scalar_one()
    assert verified_state == "ANSWER_VERIFIED"
    assert pending_state == "ANSWER_VERIFIED"  # resolved by Stage 2 this run

    # Re-running must not touch either — no duplicate assertions, no re-invocation.
    fake_gateway.calls.clear()
    second_report = await resolve_up_to(db_session, idx, max_total=10, apply=True, ai_gateway=fake_gateway)
    assert second_report.total_scanned == 0
    assert fake_gateway.calls == []


async def test_worker_loop_never_ticks_again_immediately_after_a_full_batch(monkeypatch):
    """Strict rate limit: even when a tick scans a full batch (backlog
    likely remains), the worker must wait the full interval before its
    next tick — no catch-up-immediately behavior."""
    from app.core.config import get_settings

    settings = get_settings()
    slept: list[float] = []

    async def fake_tick():
        return settings.pyq_resolver_batch_size  # pretend a full batch was processed

    async def fake_sleep(seconds):
        slept.append(seconds)
        raise asyncio.CancelledError  # stop the infinite loop after one tick

    monkeypatch.setattr(pyq_resolver_worker, "run_one_tick", fake_tick)
    monkeypatch.setattr(pyq_resolver_worker.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await pyq_resolver_worker.run_worker_loop()

    assert slept == [settings.pyq_resolver_interval_hours * 3600]


class _FakeRedis:
    """Minimal stand-in for the one Redis operation the worker's lock uses —
    SET NX with a TTL, plus DELETE. Enough to prove the lock semantics
    without needing a real Redis server in the test suite."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True

    async def delete(self, key):
        self._store.pop(key, None)


async def test_worker_lock_prevents_concurrent_acquisition(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(pyq_resolver_worker, "get_redis", lambda: fake)

    first = await pyq_resolver_worker._try_acquire_lock()
    second = await pyq_resolver_worker._try_acquire_lock()
    assert first is True
    assert second is False  # already held — no concurrent processing

    await pyq_resolver_worker._release_lock()
    third = await pyq_resolver_worker._try_acquire_lock()
    assert third is True  # released cleanly, safe to restart


async def test_worker_tick_skipped_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr(pyq_resolver_worker, "get_redis", lambda: None)
    scanned = await pyq_resolver_worker.run_one_tick()
    assert scanned == 0  # fails closed rather than risking concurrent runs
