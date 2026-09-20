"""SYLLABUS-GATE-001 — NEET-UG-2026 syllabus parser, scope gate, pre-LLM blocking."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.cms.syllabus import (
    EXPECTED_UNIT_COUNTS,
    SyllabusParseError,
    assert_blueprint_neet_syllabus_scope,
    clear_neet_2026_registry_cache,
    load_neet_2026_registry,
    parse_neet_syllabus_file,
    parse_neet_syllabus_text,
)
from app.modules.cms.services.content_factory_generation_service import (
    ContentFactoryGenerationService,
    GenerationStats,
)

REPO = Path(__file__).resolve().parents[3]
SYLLABUS = REPO / "NEETSyllabus.txt"


@pytest.fixture(autouse=True)
def _clear_registry_cache():
    clear_neet_2026_registry_cache()
    yield
    clear_neet_2026_registry_cache()


# ---------------------------------------------------------------------------
# A. Parser
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SYLLABUS.exists(), reason="NEETSyllabus.txt missing")
def test_parser_unit_counts_20_20_10():
    reg = parse_neet_syllabus_file(SYLLABUS)
    assert reg.unit_counts() == EXPECTED_UNIT_COUNTS
    assert EXPECTED_UNIT_COUNTS == {"PHYSICS": 20, "CHEMISTRY": 20, "BIOLOGY": 10}


@pytest.mark.skipif(not SYLLABUS.exists(), reason="NEETSyllabus.txt missing")
def test_parser_deterministic_and_complete():
    a = parse_neet_syllabus_file(SYLLABUS)
    b = parse_neet_syllabus_file(SYLLABUS)
    assert a.source_sha256 == b.source_sha256
    assert a.unit_counts() == b.unit_counts()
    assert list(a.topics_by_id.keys()) == list(b.topics_by_id.keys())
    assert len(a.units) == 50
    assert all(u.topics for u in a.units)


def test_parser_missing_file_fails():
    with pytest.raises(SyllabusParseError, match="missing"):
        parse_neet_syllabus_file(Path("/nonexistent/NEETSyllabus.txt"))


def test_parser_corrupt_partial_fails():
    with pytest.raises(SyllabusParseError):
        parse_neet_syllabus_text("## 1. PHYSICS SYLLABUS\n* **UNIT 1: ONLY ONE**\n* topic\n")


# ---------------------------------------------------------------------------
# B. Valid blueprints (explicit exact bindings)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SYLLABUS.exists(), reason="NEETSyllabus.txt missing")
@pytest.mark.parametrize(
    "subject,unit_number,unit_name",
    [
        ("PHYSICS", 9, "KINETIC THEORY OF GASES"),
        ("PHYSICS", 6, "GRAVITATION"),
        ("PHYSICS", 4, "WORK, ENERGY, AND POWER"),
        ("CHEMISTRY", 8, "CHEMICAL KINETICS"),
        ("CHEMISTRY", 19, "BIOMOLECULES"),
        ("BIOLOGY", 6, "Reproduction"),
        ("BIOLOGY", 4, "Plant Physiology"),
    ],
)
def test_valid_scope_via_topic_id(subject, unit_number, unit_name):
    reg = load_neet_2026_registry(str(SYLLABUS.resolve()))
    unit = reg.units_by_id[f"{subject}:U{unit_number:02d}"]
    assert unit.unit_name == unit_name or unit.unit_name.casefold() == unit_name.casefold()
    topic = unit.topics[0]
    result = assert_blueprint_neet_syllabus_scope(
        {
            "neet_ug_2026": {
                "subject": subject,
                "unit_number": unit_number,
                "unit_name": unit.unit_name,
                "topic_id": topic.topic_id,
            }
        },
        academic_subject_code="BOTANY" if subject == "BIOLOGY" else subject,
        registry=reg,
    )
    assert result.status == "IN_SYLLABUS"
    assert result.topic_id == topic.topic_id


@pytest.mark.skipif(not SYLLABUS.exists(), reason="NEETSyllabus.txt missing")
def test_human_reproduction_and_photosynthesis_topics_present():
    reg = load_neet_2026_registry(str(SYLLABUS.resolve()))
    # Exact topic membership checks against parsed bullets (terminology preserved).
    plant = reg.units_by_id["BIOLOGY:U04"]
    repro = reg.units_by_id["BIOLOGY:U06"]
    plant_blob = " ".join(t.topic for t in plant.topics).casefold()
    repro_blob = " ".join(t.topic for t in repro.topics).casefold()
    assert "photosynthesis" in plant_blob
    assert "reproduction" in repro_blob or "human" in repro_blob


# ---------------------------------------------------------------------------
# C. Out-of-scope / ambiguous
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SYLLABUS.exists(), reason="NEETSyllabus.txt missing")
def test_invalid_subject_out_of_scope():
    r = assert_blueprint_neet_syllabus_scope(
        {"neet_ug_2026": {"subject": "ASTRONOMY", "unit_number": 1, "topic": "Stars"}},
        registry=load_neet_2026_registry(str(SYLLABUS.resolve())),
    )
    assert r.status == "SYLLABUS_OUT_OF_SCOPE"


@pytest.mark.skipif(not SYLLABUS.exists(), reason="NEETSyllabus.txt missing")
def test_invalid_unit_out_of_scope():
    r = assert_blueprint_neet_syllabus_scope(
        {"neet_ug_2026": {"subject": "PHYSICS", "unit_number": 99, "topic_id": "PHYSICS:U99:T01"}},
        registry=load_neet_2026_registry(str(SYLLABUS.resolve())),
    )
    assert r.status == "SYLLABUS_OUT_OF_SCOPE"


@pytest.mark.skipif(not SYLLABUS.exists(), reason="NEETSyllabus.txt missing")
def test_invented_topic_out_of_scope():
    r = assert_blueprint_neet_syllabus_scope(
        {
            "neet_ug_2026": {
                "subject": "PHYSICS",
                "unit_number": 6,
                "topic": "String theory compactification on Calabi-Yau manifolds",
            }
        },
        registry=load_neet_2026_registry(str(SYLLABUS.resolve())),
    )
    assert r.status == "SYLLABUS_OUT_OF_SCOPE"


@pytest.mark.skipif(not SYLLABUS.exists(), reason="NEETSyllabus.txt missing")
def test_old_deleted_topic_out_of_scope():
    # Pre-rationalisation style topic not present as exact syllabus bullet.
    r = assert_blueprint_neet_syllabus_scope(
        {
            "neet_ug_2026": {
                "subject": "PHYSICS",
                "unit_number": 16,
                "topic": "Optical instruments: microscope and telescope (ray diagram construction only — invented)",
            }
        },
        registry=load_neet_2026_registry(str(SYLLABUS.resolve())),
    )
    assert r.status == "SYLLABUS_OUT_OF_SCOPE"


def test_missing_mapping_requires_review():
    r = assert_blueprint_neet_syllabus_scope({"question_format": "MCQ_4"})
    assert r.status == "SYLLABUS_MAPPING_REVIEW_REQUIRED"
    assert r.blocks_provider is True


@pytest.mark.skipif(not SYLLABUS.exists(), reason="NEETSyllabus.txt missing")
def test_missing_topic_requires_review():
    r = assert_blueprint_neet_syllabus_scope(
        {"neet_ug_2026": {"subject": "CHEMISTRY", "unit_number": 8}},
        registry=load_neet_2026_registry(str(SYLLABUS.resolve())),
    )
    assert r.status == "SYLLABUS_MAPPING_REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# D/E. Pre-LLM blocking + gate order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_out_of_scope_blueprint_zero_provider_calls():
    """Mandatory: SYLLABUS_OUT_OF_SCOPE ⇒ provider_call_count == 0."""
    provider_calls = {"n": 0}

    async def _never_generate(*args, **kwargs):
        provider_calls["n"] += 1
        raise AssertionError("provider must not be called")

    service = ContentFactoryGenerationService.__new__(ContentFactoryGenerationService)
    service.mcq_provider = MagicMock()
    service.mcq_provider.selection = MagicMock(routing_policy="fixed")
    service.session = AsyncMock()
    service._load_context = AsyncMock(
        return_value={
            "subject_name": "Physics",
            "subject_code": "PHYSICS",
            "chapter_name": "X",
            "topic_name": "Y",
            "concept_name": "Z",
            "concept_summary": None,
            "objective_title": "obj",
            "objective_description": None,
            "family_name": "fam",
            "family_intent": "apply",
            "family_key": "fam",
            "concept_id": None,
        }
    )
    service._existing_stem_hashes = AsyncMock(return_value=set())
    service._batch_created_stems = AsyncMock(return_value=[])
    service._resolve_generation_evidence = AsyncMock(
        side_effect=AssertionError("NCERT evidence must not run before syllabus pass")
    )
    service._generate_with_backoff = _never_generate

    blueprint = MagicMock()
    blueprint.id = "bp"
    blueprint.blueprint_version = 1
    blueprint.concept_id = "c"
    blueprint.difficulty = "medium"
    blueprint.constraints = {
        "neet_ug_2026": {
            "subject": "PHYSICS",
            "unit_number": 99,
            "topic": "Invented topic outside NEET 2026",
        }
    }

    batch = MagicMock()
    batch.id = "b"
    batch.status = "CREATED"
    job = MagicMock()
    job.id = "j"
    job.started_at = None
    job.status = "CREATED"
    run = MagicMock()
    run.id = "r"
    run.status = "CREATED"

    with patch(
        "app.modules.cms.services.content_factory_generation_service.settings"
    ) as settings:
        settings.factory_max_pilot_attempt_multiplier = 2
        settings.factory_max_pilot_cost_usd = 10.0
        stats: GenerationStats = await ContentFactoryGenerationService._execute_run(
            service,
            batch=batch,
            job=job,
            run=run,
            blueprint=blueprint,
            target_count=1,
            actor_id="a",
        )

    assert stats.stop_reason == "SYLLABUS_OUT_OF_SCOPE"
    assert stats.attempted == 0
    assert provider_calls["n"] == 0


@pytest.mark.asyncio
async def test_ambiguous_mapping_zero_provider_calls():
    provider_calls = {"n": 0}

    async def _never_generate(*args, **kwargs):
        provider_calls["n"] += 1
        raise AssertionError("provider must not be called")

    service = ContentFactoryGenerationService.__new__(ContentFactoryGenerationService)
    service.mcq_provider = MagicMock()
    service.mcq_provider.selection = MagicMock(routing_policy="fixed")
    service.session = AsyncMock()
    service._load_context = AsyncMock(
        return_value={
            "subject_name": "Physics",
            "subject_code": "PHYSICS",
            "chapter_name": "X",
            "topic_name": "Y",
            "concept_name": "Z",
            "concept_summary": None,
            "objective_title": "obj",
            "objective_description": None,
            "family_name": "fam",
            "family_intent": "apply",
            "family_key": "fam",
            "concept_id": None,
        }
    )
    service._existing_stem_hashes = AsyncMock(return_value=set())
    service._batch_created_stems = AsyncMock(return_value=[])
    service._resolve_generation_evidence = AsyncMock(
        side_effect=AssertionError("evidence after syllabus only")
    )
    service._generate_with_backoff = _never_generate

    blueprint = MagicMock()
    blueprint.id = "bp"
    blueprint.blueprint_version = 1
    blueprint.concept_id = "c"
    blueprint.difficulty = "medium"
    blueprint.constraints = {}  # missing binding → review required

    batch = MagicMock()
    batch.id = "b"
    batch.status = "CREATED"
    job = MagicMock()
    job.id = "j"
    job.started_at = None
    job.status = "CREATED"
    run = MagicMock()
    run.id = "r"

    with patch(
        "app.modules.cms.services.content_factory_generation_service.settings"
    ) as settings:
        settings.factory_max_pilot_attempt_multiplier = 2
        settings.factory_max_pilot_cost_usd = 10.0
        stats = await ContentFactoryGenerationService._execute_run(
            service,
            batch=batch,
            job=job,
            run=run,
            blueprint=blueprint,
            target_count=1,
            actor_id="a",
        )

    assert stats.stop_reason == "SYLLABUS_MAPPING_REVIEW_REQUIRED"
    assert provider_calls["n"] == 0


@pytest.mark.asyncio
async def test_syllabus_then_ncert_order_before_provider():
    """Valid syllabus → NCERT evidence; provider never before both gates."""
    order: list[str] = []

    async def _evidence(*args, **kwargs):
        order.append("ncert")
        pack = MagicMock()
        pack.requires_ncert = True
        pack.is_ready = False
        pack.detail = "insufficient for order test"
        pack.relative_posix = None
        pack.evidence_text = ""
        pack.section_heading = None
        pack.page_numbers = []
        pack.ku_id = None
        return pack

    async def _never_generate(*args, **kwargs):
        order.append("provider")
        raise AssertionError("provider must not be called when evidence insufficient")

    reg = load_neet_2026_registry(str(SYLLABUS.resolve())) if SYLLABUS.exists() else None
    if reg is None:
        pytest.skip("syllabus missing")
    topic = reg.units_by_id["PHYSICS:U09"].topics[0]

    service = ContentFactoryGenerationService.__new__(ContentFactoryGenerationService)
    service.mcq_provider = MagicMock()
    service.mcq_provider.selection = MagicMock(routing_policy="fixed")
    service.session = AsyncMock()
    service._load_context = AsyncMock(
        return_value={
            "subject_name": "Physics",
            "subject_code": "PHYSICS",
            "chapter_name": "Kinetic Theory",
            "topic_name": "Gases",
            "concept_name": "RMS",
            "concept_summary": None,
            "objective_title": "obj",
            "objective_description": None,
            "family_name": "fam",
            "family_intent": "apply",
            "family_key": "fam",
            "concept_id": None,
        }
    )
    service._existing_stem_hashes = AsyncMock(return_value=set())
    service._batch_created_stems = AsyncMock(return_value=[])
    service._resolve_generation_evidence = _evidence
    service._generate_with_backoff = _never_generate

    blueprint = MagicMock()
    blueprint.id = "bp"
    blueprint.blueprint_version = 1
    blueprint.concept_id = "c"
    blueprint.difficulty = "medium"
    blueprint.constraints = {
        "neet_ug_2026": {
            "subject": "PHYSICS",
            "unit_number": 9,
            "topic_id": topic.topic_id,
        }
    }

    batch = MagicMock()
    batch.id = "b"
    batch.status = "CREATED"
    job = MagicMock()
    job.id = "j"
    job.started_at = None
    run = MagicMock()
    run.id = "r"

    with patch(
        "app.modules.cms.services.content_factory_generation_service.settings"
    ) as settings:
        settings.factory_max_pilot_attempt_multiplier = 2
        settings.factory_max_pilot_cost_usd = 10.0
        stats = await ContentFactoryGenerationService._execute_run(
            service,
            batch=batch,
            job=job,
            run=run,
            blueprint=blueprint,
            target_count=1,
            actor_id="a",
        )

    assert order == ["ncert"]
    assert "provider" not in order
    assert stats.stop_reason == "NCERT_EVIDENCE_INSUFFICIENT"
