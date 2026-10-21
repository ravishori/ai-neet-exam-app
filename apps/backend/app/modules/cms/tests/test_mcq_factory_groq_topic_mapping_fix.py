"""Tests for NEET-MCQ-FACTORY-TOPIC-MAPPING-FIX-20261012.

Covers, with ZERO real network/API calls anywhere in this file:

1. A fact with a resolved ``syllabus_topic_id`` mapping passes the
   syllabus gate and reaches generation (the gate is the ONLY thing
   gating dispatch here — see ``GroqFactoryOrchestrator.process_fact``'s
   step 1).
2. A fact with NO mapping (genuinely unresolved) is correctly blocked by
   the gate — never force-matched, never fuzzy-authorized — and never
   reaches generation.
3. The real ``fact_pack.json`` pilot data resolves to exactly the
   reviewed 94-resolved / 6-blocked split documented in
   ``docs/quality/neet_mcq_factory_TOPIC_MAPPING_FIX_20261012.md``, using
   the REAL on-disk NEETSyllabus.txt registry (not a fixture) — this is
   the actual end-to-end proof that the pilot's "10/10 rejected" failure
   is fixed.
4. ``syllabus_topic_mapping.py``'s lookup table is internally consistent:
   every mapped topic_id actually exists in the real registry and
   belongs to the fact's own (subject, unit_number).
5. The ``candidate_kind``/``evidence_relocation_confirmed`` schema fix
   (migration ``ee40bf25d73d``, applied to local trinetra_test_db in this
   same task) actually works end to end: a real local-DB insert with
   ``candidate_kind="GENERATED_PRACTICE"`` succeeds and reads back
   correctly, using the project's own ``db_session`` SAVEPOINT-rollback
   fixture (see ``tests/test_generation_staging_store.py`` for the
   established pattern this reuses — never a bespoke DB connection).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from app.modules.ai.gateway.base import AIResponse
from app.modules.ai.gateway.pricing import PriceRate, register_rate
from app.modules.cms.mcq_factory_groq.orchestrator import (
    STATUS_REJECTED,
    FactSpec,
    GroqFactoryOrchestrator,
)
from app.modules.cms.mcq_factory_groq.schemas import TaxonomyIds
from app.modules.cms.mcq_factory_groq.syllabus_gate import check_generation_topic_in_syllabus
from app.modules.cms.mcq_factory_groq.syllabus_topic_mapping import (
    FACT_ID_TO_SYLLABUS_TOPIC_ID,
    UNRESOLVED_FACT_IDS,
    resolve_syllabus_topic_id,
)
from app.modules.cms.mcq_factory_groq.validators import InMemoryTaxonomyResolver
from app.modules.cms.services.generation_staging_store import (
    StagingCandidateRecord,
    insert_staging_candidate,
)
from app.modules.cms.services.mcq_factory_groq_controls import (
    GroqFactoryCheckpoint,
    GroqFactoryLimits,
)
from app.modules.cms.syllabus.neet_2026_parser import (
    NeetSyllabusRegistry,
    NeetSyllabusTopic,
    NeetSyllabusUnit,
)
from app.modules.cms.syllabus.neet_2026_registry import load_neet_2026_registry

pytestmark = pytest.mark.asyncio

register_rate("fake-groq", "fake-gen-model", PriceRate(1_000_000.0, 0.0))
register_rate("fake-groq", "fake-verify-model", PriceRate(1_000_000.0, 0.0))

BACKEND_ROOT = Path(__file__).resolve().parents[4]
FACT_PACK_PATH = BACKEND_ROOT / "data" / "generated_mcqs" / "mcq_factory_pilot" / "fact_pack.json"
# NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-20261013 added this second pack (34
# more facts, all resolved in FACT_ID_TO_SYLLABUS_TOPIC_ID) — referenced only
# by test_lookup_table_topic_ids_all_exist_in_real_registry_and_match_unit
# below, which must look fact_ids up in BOTH packs now that the lookup
# table's real total is 128 (94 from fact_pack.json + 34 from this file).
FACT_PACK_BATCH2_PATH = BACKEND_ROOT / "data" / "generated_mcqs" / "mcq_factory_pilot" / "fact_pack_batch2.json"


# ---------------------------------------------------------------------------
# A tiny fixture registry whose topic BLOCK text deliberately does NOT
# equal the fact's fine-grained free-text topic -- this is what forces
# the gate's old free-text-only path to fail, and proves the new
# topic_id path is what actually authorizes it.
# ---------------------------------------------------------------------------


def _fixture_registry() -> NeetSyllabusRegistry:
    topic = NeetSyllabusTopic(
        subject="BIOLOGY",
        unit_number=3,
        unit_name="Cell Structure and Function",
        topic_index=1,
        topic=(
            "Cell theory and cell as the basic unit of life; Structure of "
            "prokaryotic and eukaryotic cell; Nucleus-nuclear membrane, "
            "chromatin, nucleolus."
        ),
        subtopic=None,
        topic_id="BIOLOGY:U03:T01",
        source_line=1,
    )
    unit = NeetSyllabusUnit(
        subject="BIOLOGY",
        unit_number=3,
        unit_name="Cell Structure and Function",
        unit_id="BIOLOGY:U03",
        source_line=1,
        topics=[topic],
    )
    return NeetSyllabusRegistry(
        source_path="fixture",
        source_sha256="0" * 64,
        units=[unit],
        topics_by_id={topic.topic_id: topic},
        units_by_id={unit.unit_id: unit},
    )


def _taxonomy_resolver() -> InMemoryTaxonomyResolver:
    return InMemoryTaxonomyResolver(
        subjects={"s1": None}, chapters={"c1": "s1"}, topics={"t1": "c1"}, concepts={}
    )


def _fake_session():
    return SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))


async def _noop_sleep(_seconds: float) -> None:
    return None


def _build_orchestrator(tmp_path, *, gen_caller, writer_calls: list):
    limits = GroqFactoryLimits(
        max_total_spend_usd=1000.0,
        max_generation_tokens_per_question=10,
        max_verification_tokens_per_question=10,
        max_retries_per_call=2,
        rate_limit_requests_per_minute=10_000,
        rate_limit_tokens_per_minute=10_000_000,
    )
    checkpoint = GroqFactoryCheckpoint(tmp_path / "checkpoint.json", batch_id="batch-topic-mapping")

    async def writer(record) -> bool:
        writer_calls.append(record)
        return True

    return GroqFactoryOrchestrator(
        batch_id="batch-topic-mapping",
        limits=limits,
        checkpoint=checkpoint,
        generation_caller=gen_caller,
        generation_provider_name="fake-groq",
        generation_model="fake-gen-model",
        verification_caller=None,
        verification_provider_name="fake-groq",
        verification_model="fake-verify-model",
        taxonomy_resolver=_taxonomy_resolver(),
        staging_writer=writer,
        publication_gate_session=_fake_session(),
        sleep_fn=_noop_sleep,
    )


class _NeverCalled:
    """Generation caller that fails the test if it is ever invoked —
    proves a blocked fact never reaches a (paid) generation call."""

    def __init__(self) -> None:
        self.call_count = 0

    async def __call__(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> AIResponse:
        self.call_count += 1
        raise AssertionError("generation caller must never be invoked for a syllabus-blocked fact")


class _CountingCaller:
    """Generation caller that just counts invocations; we only care
    whether the syllabus gate let the fact through to generation, not
    about generation succeeding (no evidence PDF is wired up in these
    tests, so it is fine/expected for this call to error out downstream)."""

    def __init__(self) -> None:
        self.call_count = 0

    async def __call__(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> AIResponse:
        self.call_count += 1
        raise RuntimeError("stop here -- we only care that generation was attempted")


def _fact_spec(**overrides) -> FactSpec:
    base = dict(
        fact_id="bio-cell-001",
        subject="BIOLOGY",
        unit_number=3,
        chapter="UNIT 03: Cell Structure and Function",
        topic="Cell Structure and Organelles",  # fine-grained -- deliberately
        # does NOT equal the fixture registry's whole topic-block text
        class_level="11",
        taxonomy=TaxonomyIds(subject_id="s1", chapter_id="c1", topic_id="t1", concept_id=None),
        unit_name="Cell Structure and Function",
        syllabus_registry=_fixture_registry(),
    )
    base.update(overrides)
    return FactSpec(**base)


# ---------------------------------------------------------------------------
# 1. Resolved topic_id -> gate passes -> generation is attempted
# ---------------------------------------------------------------------------


async def test_resolved_syllabus_topic_id_passes_gate_and_reaches_generation(tmp_path):
    writer_calls: list = []
    gen = _CountingCaller()
    orch = _build_orchestrator(tmp_path, gen_caller=gen, writer_calls=writer_calls)

    # No evidence PDF is indexed in this test; a bare SimpleNamespace with
    # no pages stands in for "no evidence found", which would normally
    # reject the fact at the (separate, zero-cost) evidence-selection step
    # -- but that step runs AFTER the syllabus gate, so if the syllabus
    # gate is what's broken, this fact must be rejected with
    # OUT_OF_SYLLABUS_SCOPE, never with EVIDENCE_NOT_GROUNDABLE. We assert
    # the opposite is NOT seen, and separately prove the gate itself
    # returns IN_SYLLABUS for exactly this spec.
    spec = _fact_spec(syllabus_topic_id="BIOLOGY:U03:T01")

    scope = check_generation_topic_in_syllabus(
        subject=spec.subject,
        unit_number=spec.unit_number,
        topic=None,  # topic_id path -- see orchestrator.py's own reasoning
        topic_id=spec.syllabus_topic_id,
        unit_name=None,
        registry=spec.syllabus_registry,
    )
    assert scope.is_in_scope, scope.detail
    assert scope.status == "IN_SYLLABUS"
    assert scope.topic_id == "BIOLOGY:U03:T01"

    # And the orchestrator itself must not reject this fact at the
    # syllabus-gate step -- it must get far enough to attempt generation.
    document = SimpleNamespace(pages=[])
    record = await orch.process_fact(spec, document)
    assert "OUT_OF_SYLLABUS_SCOPE" not in record.reason


async def test_fine_grained_free_text_alone_would_have_failed_without_topic_id():
    """Sanity check that this fact genuinely needed the topic_id fix --
    without it, the free-text topic never matches the whole semicolon-
    joined block, exactly reproducing the pilot's original failure."""
    scope = check_generation_topic_in_syllabus(
        subject="BIOLOGY",
        unit_number=3,
        topic="Cell Structure and Organelles",
        topic_id=None,
        unit_name="Cell Structure and Function",
        registry=_fixture_registry(),
    )
    assert not scope.is_in_scope
    assert scope.status == "SYLLABUS_OUT_OF_SCOPE"


# ---------------------------------------------------------------------------
# 2. Unresolved fact (no mapping) -> correctly blocked, never force-matched
# ---------------------------------------------------------------------------


async def test_unmapped_fact_is_blocked_not_force_matched(tmp_path):
    writer_calls: list = []
    gen = _NeverCalled()
    orch = _build_orchestrator(tmp_path, gen_caller=gen, writer_calls=writer_calls)

    # No syllabus_topic_id, and the free-text topic does not exact-match
    # the fixture block either -- this fact has no confirmed mapping.
    spec = _fact_spec(fact_id="bio-repro-001", syllabus_topic_id=None)
    document = SimpleNamespace(pages=[])

    record = await orch.process_fact(spec, document)

    assert record.status == STATUS_REJECTED
    assert "OUT_OF_SYLLABUS_SCOPE" in record.reason
    assert gen.call_count == 0  # never dispatched -- $0 spent
    assert writer_calls[0].outcome == STATUS_REJECTED


def test_each_deliberately_unresolved_fact_is_confirmed_out_of_scope():
    """Every fact_id this task left out of the lookup table must still be
    rejected by the real gate when given no topic_id and its own
    (non-matching) free-text topic -- i.e. nothing elsewhere in the
    pipeline accidentally authorizes them some other way."""
    facts_by_id = {f["fact_id"]: f for f in json.loads(FACT_PACK_PATH.read_text(encoding="utf-8"))}
    registry = load_neet_2026_registry()
    for fact_id in UNRESOLVED_FACT_IDS:
        fact = facts_by_id[fact_id]
        assert fact_id not in FACT_ID_TO_SYLLABUS_TOPIC_ID
        scope = check_generation_topic_in_syllabus(
            subject=fact["subject"],
            unit_number=fact["unit_number"],
            topic=fact["topic"],
            topic_id=None,
            unit_name=None,
            registry=registry,
        )
        assert not scope.is_in_scope, f"{fact_id} unexpectedly in scope via free text alone"


# ---------------------------------------------------------------------------
# 3. Real fact_pack.json end-to-end: exactly 94 resolved / 6 blocked
# ---------------------------------------------------------------------------


def test_real_fact_pack_resolves_to_94_in_syllabus_6_blocked():
    registry = load_neet_2026_registry()
    facts = json.loads(FACT_PACK_PATH.read_text(encoding="utf-8"))
    assert len(facts) == 100

    in_scope_count = 0
    blocked_count = 0
    for fact in facts:
        syllabus_topic_id = resolve_syllabus_topic_id(fact["fact_id"])
        scope = check_generation_topic_in_syllabus(
            subject=fact["subject"],
            unit_number=fact["unit_number"],
            topic=fact["topic"] if syllabus_topic_id is None else None,
            topic_id=syllabus_topic_id,
            unit_name=fact.get("unit_name") if syllabus_topic_id is None else None,
            academic_subject_code=fact.get("academic_subject_code"),
            registry=registry,
        )
        if syllabus_topic_id is not None:
            assert scope.is_in_scope, f"{fact['fact_id']} has a mapping but gate rejected it: {scope.detail}"
            in_scope_count += 1
        else:
            assert not scope.is_in_scope, f"{fact['fact_id']} has no mapping but gate authorized it anyway"
            blocked_count += 1

    assert in_scope_count == 94
    assert blocked_count == 6


# ---------------------------------------------------------------------------
# 4. Lookup-table self-consistency against the REAL registry
# ---------------------------------------------------------------------------


def test_lookup_table_topic_ids_all_exist_in_real_registry_and_match_unit():
    registry = load_neet_2026_registry()
    facts_by_id = {f["fact_id"]: f for f in json.loads(FACT_PACK_PATH.read_text(encoding="utf-8"))}
    # NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-20261013 added fact_pack_batch2.json
    # (34 more facts, all resolved into FACT_ID_TO_SYLLABUS_TOPIC_ID too) —
    # merge both packs so every fact_id this lookup table now covers can
    # actually be found below; fact_pack.json/fact_pack_batch2.json have
    # disjoint fact_id namespaces (confirmed in
    # docs/quality/neet_mcq_factory_OPENROUTER_WIRING_20261013.md), so this
    # merge can never silently shadow one pack's fact with the other's.
    facts_by_id.update({f["fact_id"]: f for f in json.loads(FACT_PACK_BATCH2_PATH.read_text(encoding="utf-8"))})

    # This assertion was stale (still asserting the pre-expansion 94) — fixed
    # as part of NEET-MCQ-FACTORY-OPENROUTER-PRODUCTIONIZED-20261013 per the
    # stale-assertion flag raised in
    # docs/quality/neet_mcq_factory_OPENROUTER_WIRING_20261013.md. Fixing the
    # count alone (94 -> 128) also required the facts_by_id merge above —
    # the lookup table now resolves fact_ids from BOTH packs, so the lookup
    # loop below needs both to avoid a KeyError on a batch-2 fact_id.
    assert len(FACT_ID_TO_SYLLABUS_TOPIC_ID) == 128
    assert len(UNRESOLVED_FACT_IDS) == 6
    assert set(FACT_ID_TO_SYLLABUS_TOPIC_ID) & UNRESOLVED_FACT_IDS == set()

    for fact_id, topic_id in FACT_ID_TO_SYLLABUS_TOPIC_ID.items():
        topic = registry.topics_by_id.get(topic_id)
        assert topic is not None, f"{fact_id} maps to {topic_id}, which does not exist in the real registry"
        fact = facts_by_id[fact_id]
        expected_unit_id = f"{fact['subject']}:U{fact['unit_number']:02d}"
        actual_unit_id = f"{topic.subject}:U{topic.unit_number:02d}"
        assert actual_unit_id == expected_unit_id, (
            f"{fact_id}'s mapped topic_id {topic_id} belongs to unit "
            f"{actual_unit_id}, not its own declared unit {expected_unit_id}"
        )


# ---------------------------------------------------------------------------
# 5. candidate_kind / evidence_relocation_confirmed schema fix -- real
#    local-DB insert (SAVEPOINT-rolled-back by the shared db_session
#    fixture, exactly like tests/test_generation_staging_store.py).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_candidate_kind_column_insert_and_read_back(db_session):
    batch_id = f"TEST-TOPICMAP-{uuid.uuid4().hex[:12]}"
    record = StagingCandidateRecord(
        batch_id=batch_id,
        sequence_in_batch=1,
        fact_id="bio-cell-001",
        outcome="ACCEPTED",
        generation_method="mcq_factory_groq_orchestrator",
        question_text="Which organelle is the site of aerobic respiration?",
        candidate_kind="GENERATED_PRACTICE",
        evidence_relocation_confirmed=True,
    )
    inserted = await insert_staging_candidate(db_session, record)
    await db_session.commit()
    assert inserted is True

    result = await db_session.execute(
        text(
            "SELECT candidate_kind, evidence_relocation_confirmed "
            "FROM generation_staging.candidates WHERE batch_id = :b AND fact_id = :f"
        ),
        {"b": batch_id, "f": "bio-cell-001"},
    )
    row = result.first()
    assert row is not None
    assert row.candidate_kind == "GENERATED_PRACTICE"
    assert row.evidence_relocation_confirmed is True


@pytest.mark.asyncio(loop_scope="session")
async def test_candidate_kind_null_for_non_groq_producers_is_still_accepted(db_session):
    """Pre-existing producers (deterministic_batch_runner) never set
    candidate_kind -- the column must stay nullable and NULL must read
    back as NULL, never a default that would mislabel old data."""
    batch_id = f"TEST-TOPICMAP-{uuid.uuid4().hex[:12]}"
    record = StagingCandidateRecord(
        batch_id=batch_id,
        sequence_in_batch=1,
        fact_id="ncert-fact-no-candidate-kind",
        outcome="ACCEPTED",
        generation_method="deterministic_fact_engine",
        question_text="Legacy producer row",
    )
    inserted = await insert_staging_candidate(db_session, record)
    await db_session.commit()
    assert inserted is True

    result = await db_session.execute(
        text(
            "SELECT candidate_kind, evidence_relocation_confirmed "
            "FROM generation_staging.candidates WHERE batch_id = :b AND fact_id = :f"
        ),
        {"b": batch_id, "f": "ncert-fact-no-candidate-kind"},
    )
    row = result.first()
    assert row is not None
    assert row.candidate_kind is None
    assert row.evidence_relocation_confirmed is None
