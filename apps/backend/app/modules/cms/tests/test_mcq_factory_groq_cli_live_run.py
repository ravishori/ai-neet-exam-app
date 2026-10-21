"""CLI-level integration tests for scripts/mcq_factory_groq_bulk_run.py's
live-run wiring (``run_live`` / ``default_live_dependencies``).

ZERO real AI/API calls, ZERO real database writes, ZERO real GROQ_API_KEY
anywhere in this file:

- Every ``Settings`` object used here is constructed explicitly in-test
  with dummy/placeholder values (``groq_api_key="dummy-test-key-not-real"``
  etc.) — never the real local ``.env``.
- "Successful execution" / "budget exhaustion" / "interruption+resume"
  tests pass a FAKE ``dependencies_factory`` into ``run_live`` directly —
  the real ``default_live_dependencies`` (which would construct an
  ``AsyncSession``/``AIGateway``) is never called in those tests.
- The "no production writes" tests exercise ``default_live_dependencies``
  itself, but with ``app.core.database.AsyncSessionLocal``/``engine`` and
  every provider-construction helper monkeypatched to in-memory fakes —
  no real socket, no real Postgres connection, ever opened.
- The one real local-filesystem I/O in this file is writing/reading a tiny
  PDF via ``fitz`` to ``tmp_path`` (same pattern already used by
  ``test_mcq_factory_groq_orchestrator.py``) and writing/reading a JSON
  fact-pack file to ``tmp_path`` — plain local file I/O, not network or DB.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import fitz
import pytest

import scripts.mcq_factory_groq_bulk_run as cli
from app.core.config import Settings
from app.modules.ai.gateway.pricing import PriceRate, register_rate
from app.modules.cms.mcq_factory_groq.validators import InMemoryTaxonomyResolver
from app.modules.cms.services.generation_staging_store import NotLocalDatabaseError
from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry, NeetSyllabusTopic, NeetSyllabusUnit

pytestmark = pytest.mark.asyncio

SUBJECT_ID = "s1"
CHAPTER_ID = "c1"
TOPIC_ID = "t1"

PAGE_TEXT = (
    "Newtons second law of motion states that the force acting on an object "
    "is equal to the mass of that object multiplied by its acceleration. "
    "This fundamental principle of classical mechanics explains how objects "
    "respond to applied forces and is written as force equals mass times "
    "acceleration in standard physics textbooks used for NEET preparation."
)
QUOTED_SNIPPET = (
    "force acting on an object is equal to the mass of that object multiplied by its acceleration"
)

# Fake, clearly-non-real provider/model strings so cost math in these tests
# is exact and never depends on (or risks colliding with) real Groq pricing.
GEN_MODEL = "test-fake-cli-live-run-gen-model"
VERIFY_MODEL = "test-fake-cli-live-run-verify-model"
register_rate("groq", GEN_MODEL, PriceRate(1_000_000.0, 0.0))
register_rate("groq", VERIFY_MODEL, PriceRate(1_000_000.0, 0.0))


def _write_pdf(path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(36, 36, page.rect.width - 36, page.rect.height - 36)
    page.insert_textbox(rect, PAGE_TEXT, fontsize=11)
    doc.save(str(path))
    doc.close()


def _syllabus_registry() -> NeetSyllabusRegistry:
    topic = NeetSyllabusTopic(
        subject="PHYSICS",
        unit_number=1,
        unit_name="Laws of Motion",
        topic_index=1,
        topic="force and acceleration",
        subtopic=None,
        topic_id="PHYSICS:U01:T01",
        source_line=1,
    )
    unit = NeetSyllabusUnit(
        subject="PHYSICS", unit_number=1, unit_name="Laws of Motion", unit_id="PHYSICS:U01", source_line=1, topics=[topic]
    )
    return NeetSyllabusRegistry(
        source_path="fixture",
        source_sha256="0" * 64,
        units=[unit],
        topics_by_id={topic.topic_id: topic},
        units_by_id={unit.unit_id: unit},
    )


@pytest.fixture(autouse=True)
def _fixture_syllabus_registry(monkeypatch):
    """Every fact built below uses FactSpec.syllabus_registry=None (the
    CLI's fact-pack loader does not expose that field), so
    check_generation_topic_in_syllabus falls back to
    neet_2026_scope.load_neet_2026_registry(). Monkeypatch THAT to a tiny
    fixture registry instead of the real on-disk NEETSyllabus.txt, so these
    CLI tests never depend on (or are made fragile by) that file's exact
    wording — the real deterministic matching code is still exercised
    unmodified, just fed a controlled registry."""
    monkeypatch.setattr(
        "app.modules.cms.syllabus.neet_2026_scope.load_neet_2026_registry",
        lambda *a, **kw: _syllabus_registry(),
    )


def _fact_dict(fact_id: str) -> dict:
    return {
        "fact_id": fact_id,
        "subject": "PHYSICS",
        "unit_number": 1,
        "chapter": "Laws of Motion",
        "topic": "force and acceleration",
        "class_level": "11",
        "taxonomy": {"subject_id": SUBJECT_ID, "chapter_id": CHAPTER_ID, "topic_id": TOPIC_ID, "concept_id": None},
    }


def _write_fact_pack(tmp_path, fact_ids: list[str]):
    path = tmp_path / "fact_pack.json"
    path.write_text(json.dumps([_fact_dict(fid) for fid in fact_ids]), encoding="utf-8")
    return path


def _generated_candidate_json(*, doc_id: str, correct_option: str = "A") -> dict:
    return {
        "stem": "According to the evidence, what does Newton's second law equate force to?",
        "options": [
            {"label": "A", "text": "Mass times acceleration"},
            {"label": "B", "text": "Mass times velocity"},
            {"label": "C", "text": "Mass divided by acceleration"},
            {"label": "D", "text": "Velocity times time"},
        ],
        "correct_option": correct_option,
        "explanation": "Newton's second law states that force equals mass multiplied by acceleration, as given directly in the evidence chunk.",
        "source_evidence": {"doc_id": doc_id, "page": 1, "quoted_snippet": QUOTED_SNIPPET},
        "taxonomy": {"subject_id": SUBJECT_ID, "chapter_id": CHAPTER_ID, "topic_id": TOPIC_ID, "concept_id": None},
        "difficulty": "medium",
    }


def _ai_response(payload, *, model: str, prompt_tokens: int = 1, completion_tokens: int = 1):
    from app.modules.ai.gateway.base import AIResponse

    return AIResponse(
        text=json.dumps(payload),
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider="groq",
        provider_request_id="req-1",
        finish_reason="stop",
        is_fallback=False,
    )


def _verification_response(*, answer_supported: bool = True, ambiguous: bool = False, prompt_tokens: int = 1):
    return _ai_response(
        {"answer_supported": answer_supported, "ambiguous": ambiguous, "unsupported_claims": [], "notes": "ok"},
        model=VERIFY_MODEL,
        prompt_tokens=prompt_tokens,
    )


class ScriptedCaller:
    """Plain async callable standing in for a provider call site — never an
    httpx client, never a real OpenAIProvider. Same pattern as
    test_mcq_factory_groq_orchestrator.py's ScriptedCaller."""

    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.call_count = 0

    async def __call__(self, *, system_prompt: str, user_prompt: str, max_tokens: int):
        self.call_count += 1
        idx = min(self.call_count - 1, len(self._outcomes) - 1)
        outcome = self._outcomes[idx]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _fake_pub_gate_session():
    return SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))


def _taxonomy_resolver() -> InMemoryTaxonomyResolver:
    return InMemoryTaxonomyResolver(
        subjects={SUBJECT_ID: None}, chapters={CHAPTER_ID: SUBJECT_ID}, topics={TOPIC_ID: CHAPTER_ID}, concepts={}
    )


def _fake_dependencies_factory(*, gen_caller, verify_caller, writer_calls: list):
    async def _writer(record) -> bool:
        writer_calls.append(record)
        return True

    @asynccontextmanager
    async def _factory(settings):
        yield cli.LiveDependencies(
            session=SimpleNamespace(),
            generation_caller=gen_caller,
            verification_caller=verify_caller,
            taxonomy_resolver=_taxonomy_resolver(),
            staging_writer=_writer,
            publication_gate_session=_fake_pub_gate_session(),
        )

    return _factory


def _settings(**overrides) -> Settings:
    base = dict(
        groq_enabled=True,
        groq_api_key="dummy-test-key-not-real",
        mcq_provider="groq",
        groq_generation_model=GEN_MODEL,
        groq_verification_model=VERIFY_MODEL,
        mcq_factory_groq_pilot_max_spend_usd=1000.0,
        mcq_factory_groq_max_generation_tokens=10,
        mcq_factory_groq_max_verification_tokens=10,
        mcq_factory_groq_max_retries=2,
        mcq_factory_groq_rate_limit_rpm=10_000,
        mcq_factory_groq_rate_limit_tpm=10_000_000,
    )
    base.update(overrides)
    return Settings(**base)


def _args(*, batch_id, fact_pack, evidence_pdf, checkpoint_path, count=None, budget_profile="pilot"):
    return cli.build_arg_parser().parse_args(
        [
            "--batch-id",
            batch_id,
            "--fact-pack",
            str(fact_pack),
            "--evidence-pdf",
            str(evidence_pdf),
            "--checkpoint-path",
            str(checkpoint_path),
            "--budget-profile",
            budget_profile,
            *(["--count", str(count)] if count is not None else []),
            "--no-dry-run",
            "--i-understand-this-calls-a-live-paid-api",
        ]
    )


# ---------------------------------------------------------------------------
# 1. Successful mocked end-to-end execution
# ---------------------------------------------------------------------------


async def test_successful_live_execution_mocked_end_to_end(tmp_path, capsys):
    pdf_path = tmp_path / "evidence.pdf"
    _write_pdf(pdf_path)
    fact_pack = _write_fact_pack(tmp_path, ["fact-1"])
    checkpoint_path = tmp_path / "checkpoint.json"

    from app.modules.cms.mcq_factory_groq.pdf_text_index import index_pdf

    doc_id = index_pdf(pdf_path).doc_id

    gen = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=doc_id), model=GEN_MODEL)])
    verify = ScriptedCaller([_verification_response()])
    writer_calls: list = []
    settings = _settings()
    args = _args(batch_id="live-success", fact_pack=fact_pack, evidence_pdf=pdf_path, checkpoint_path=checkpoint_path)

    rc = await cli.run_live(
        args, settings, dependencies_factory=_fake_dependencies_factory(gen_caller=gen, verify_caller=verify, writer_calls=writer_calls)
    )

    assert rc == 0
    assert gen.call_count == 1
    assert verify.call_count == 1
    assert len(writer_calls) == 1
    assert writer_calls[0].outcome == "ACCEPTED"
    out = capsys.readouterr().out
    assert "processed 1/1 facts" in out
    assert "accepted=1" in out


# ---------------------------------------------------------------------------
# 2. Missing/invalid configuration — fail closed
# ---------------------------------------------------------------------------


async def test_missing_groq_api_key_fails_closed(tmp_path, capsys):
    pdf_path = tmp_path / "evidence.pdf"
    _write_pdf(pdf_path)
    fact_pack = _write_fact_pack(tmp_path, ["fact-1"])
    settings = _settings(groq_api_key="")  # explicitly empty — never the real .env value
    args = _args(
        batch_id="live-badconfig",
        fact_pack=fact_pack,
        evidence_pdf=pdf_path,
        checkpoint_path=tmp_path / "checkpoint.json",
    )

    called = {"n": 0}

    def _should_never_be_called(settings):  # pragma: no cover - guards against a real wiring attempt
        called["n"] += 1
        raise AssertionError("dependencies_factory must never be invoked when config fails closed")

    rc = await cli.run_live(args, settings, dependencies_factory=_should_never_be_called)

    assert rc == 4
    assert called["n"] == 0
    err = capsys.readouterr().err
    assert "GROQ_API_KEY" in err
    assert "REFUSING TO RUN LIVE" in err


async def test_wrong_generation_provider_fails_closed(tmp_path):
    """GROQ_ENABLED=true and a key configured, but
    MCQ_FACTORY_GENERATION_PROVIDER (the knob
    build_mcq_factory_generation_caller / _check_required_live_config
    actually resolve from — see NEET-MCQ-FACTORY-OPENROUTER-
    PRODUCTIONIZED-20261013) resolves to something this CLI does not
    support for a live run — must refuse rather than silently generating
    against an unsupported provider."""
    pdf_path = tmp_path / "evidence.pdf"
    _write_pdf(pdf_path)
    fact_pack = _write_fact_pack(tmp_path, ["fact-1"])
    settings = _settings(mcq_factory_generation_provider="anthropic")
    args = _args(
        batch_id="live-wrongprovider",
        fact_pack=fact_pack,
        evidence_pdf=pdf_path,
        checkpoint_path=tmp_path / "checkpoint.json",
    )

    async def _should_never_be_called(settings):  # pragma: no cover
        raise AssertionError("must never reach dependency construction")

    rc = await cli.run_live(args, settings, dependencies_factory=_should_never_be_called)
    assert rc == 4


async def test_malformed_fact_pack_fails_closed(tmp_path):
    bad_path = tmp_path / "fact_pack.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    pdf_path = tmp_path / "evidence.pdf"
    _write_pdf(pdf_path)
    settings = _settings()
    args = _args(
        batch_id="live-badpack", fact_pack=bad_path, evidence_pdf=pdf_path, checkpoint_path=tmp_path / "checkpoint.json"
    )

    rc = await cli.run_live(args, settings)
    assert rc == 4


# ---------------------------------------------------------------------------
# 3. Budget exhaustion mid-run
# ---------------------------------------------------------------------------


async def test_budget_exhaustion_mid_run_stops_cleanly_reports_partial(tmp_path, capsys):
    pdf_path = tmp_path / "evidence.pdf"
    _write_pdf(pdf_path)
    fact_pack = _write_fact_pack(tmp_path, ["fact-1", "fact-2", "fact-3"])
    checkpoint_path = tmp_path / "checkpoint.json"

    from app.modules.cms.mcq_factory_groq.pdf_text_index import index_pdf

    doc_id = index_pdf(pdf_path).doc_id

    # $1/token (registered rate), gen+verify token cap = 1 each => $1 each.
    # Ceiling of $2 allows exactly one fact's gen+verify, never a second.
    gen = ScriptedCaller(
        [
            _ai_response(_generated_candidate_json(doc_id=doc_id), model=GEN_MODEL, prompt_tokens=1),
            _ai_response(_generated_candidate_json(doc_id=doc_id), model=GEN_MODEL, prompt_tokens=1),
        ]
    )
    verify = ScriptedCaller([_verification_response(prompt_tokens=1), _verification_response(prompt_tokens=1)])
    writer_calls: list = []
    settings = _settings(
        mcq_factory_groq_pilot_max_spend_usd=2.0,
        mcq_factory_groq_max_generation_tokens=1,
        mcq_factory_groq_max_verification_tokens=1,
    )
    args = _args(batch_id="live-budget", fact_pack=fact_pack, evidence_pdf=pdf_path, checkpoint_path=checkpoint_path)

    rc = await cli.run_live(
        args, settings, dependencies_factory=_fake_dependencies_factory(gen_caller=gen, verify_caller=verify, writer_calls=writer_calls)
    )

    assert rc == 0  # the CLI itself ran successfully; the BATCH stopped early (reported, not a crash)
    assert len(writer_calls) == 2  # third fact never attempted / never written
    assert writer_calls[0].outcome == "ACCEPTED"
    assert writer_calls[1].outcome == "REJECTED"
    assert "BUDGET_EXHAUSTED" in writer_calls[1].rejection_details["reason"]

    captured = capsys.readouterr()
    assert "processed 2/3 facts" in captured.out
    assert "BUDGET CEILING REACHED" in captured.err
    # Spend never exceeds the configured ceiling.
    assert float(settings.mcq_factory_groq_pilot_max_spend_usd) == 2.0


# ---------------------------------------------------------------------------
# 4. Interruption / resume — checkpoint correctness, no double-spend
# ---------------------------------------------------------------------------


async def test_interruption_and_resume_through_cli_entrypoint_no_double_spend(tmp_path, capsys):
    pdf_path = tmp_path / "evidence.pdf"
    _write_pdf(pdf_path)
    fact_pack = _write_fact_pack(tmp_path, ["fact-1"])
    checkpoint_path = tmp_path / "checkpoint.json"

    from app.modules.cms.mcq_factory_groq.pdf_text_index import index_pdf

    doc_id = index_pdf(pdf_path).doc_id
    settings = _settings()
    args = _args(batch_id="live-resume", fact_pack=fact_pack, evidence_pdf=pdf_path, checkpoint_path=checkpoint_path)

    # "Process 1": runs to completion.
    gen1 = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=doc_id), model=GEN_MODEL)])
    verify1 = ScriptedCaller([_verification_response()])
    writer_calls_1: list = []
    rc1 = await cli.run_live(
        args, settings, dependencies_factory=_fake_dependencies_factory(gen_caller=gen1, verify_caller=verify1, writer_calls=writer_calls_1)
    )
    assert rc1 == 0
    assert gen1.call_count == 1
    assert len(writer_calls_1) == 1

    # "Process 2": a brand-new CLI invocation (fresh caller instances),
    # same --checkpoint-path and --batch-id, simulating a restart.
    gen2 = ScriptedCaller([_ai_response(_generated_candidate_json(doc_id=doc_id), model=GEN_MODEL)])
    verify2 = ScriptedCaller([_verification_response()])
    writer_calls_2: list = []
    rc2 = await cli.run_live(
        args, settings, dependencies_factory=_fake_dependencies_factory(gen_caller=gen2, verify_caller=verify2, writer_calls=writer_calls_2)
    )

    assert rc2 == 0
    # Zero new provider calls and zero new staging writes — the fact was
    # already checkpointed by "process 1" and must never be re-spent.
    assert gen2.call_count == 0
    assert verify2.call_count == 0
    assert writer_calls_2 == []
    out = capsys.readouterr().out
    assert "processed 1/1 facts" in out


# ---------------------------------------------------------------------------
# 5. Explicit prevention of production writes
# ---------------------------------------------------------------------------


async def test_default_live_dependencies_only_writes_through_staging_store(tmp_path, monkeypatch):
    """The ONLY write default_live_dependencies' staging_writer can ever
    issue is generation_staging_store.insert_staging_candidate — confirmed
    by monkeypatching that exact function and asserting it (and nothing
    else) is called, with zero real DB connection ever opened."""
    fake_session = SimpleNamespace(commit=AsyncMock())

    class _FakeSessionCtx:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, *exc):
            return False

    class _FakeEngine:
        url = "postgresql+asyncpg://user:pass@localhost:5432/neet_dev"

    insert_mock = AsyncMock(return_value=True)

    monkeypatch.setattr("app.core.database.engine", _FakeEngine())
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _FakeSessionCtx())
    monkeypatch.setattr(
        "app.modules.cms.services.generation_staging_store.insert_staging_candidate", insert_mock
    )
    monkeypatch.setattr(
        "app.modules.cms.mcq_factory_groq.orchestrator.build_mcq_factory_generation_caller",
        lambda session, settings=None: ScriptedCaller([]),
    )
    monkeypatch.setattr(
        "app.modules.cms.mcq_factory_groq.orchestrator.build_mcq_factory_verification_caller",
        lambda session, settings=None: None,
    )
    monkeypatch.setattr(
        "app.modules.cms.mcq_factory_groq.validators.build_taxonomy_resolver_from_session",
        AsyncMock(return_value=_taxonomy_resolver()),
    )

    settings = _settings()
    fake_record = SimpleNamespace(batch_id="b", fact_id="f", attempt_number=1)

    async with cli.default_live_dependencies(settings) as deps:
        ok = await deps.staging_writer(fake_record)

    assert ok is True
    insert_mock.assert_awaited_once_with(fake_session, fake_record)
    fake_session.commit.assert_awaited_once()


async def test_default_live_dependencies_refuses_non_local_database_before_any_session(tmp_path, monkeypatch):
    """A non-local DB target must raise BEFORE AsyncSessionLocal is ever
    constructed — never falls back to attempting the write anyway."""

    class _FakeEngine:
        url = "postgresql+asyncpg://user:pass@prod-db.example.com:5432/neet_prod"

    def _must_not_be_called():  # pragma: no cover - guards the refusal
        raise AssertionError("AsyncSessionLocal must never be constructed for a non-local DB target")

    monkeypatch.setattr("app.core.database.engine", _FakeEngine())
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", _must_not_be_called)

    settings = _settings()
    with pytest.raises(NotLocalDatabaseError):
        async with cli.default_live_dependencies(settings):
            pass  # pragma: no cover - never reached
