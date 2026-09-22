"""NCERT-EVIDENCE-WRITE-002 — focused regression (no production DB).

Uses audit artifacts + canonical NCERT PDFs + in-process preflight mocks.
Pytest points at trinetra_test_db (see apps/backend/conftest.py); these tests
must not require the 14 production blueprint rows.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.cms.services.content_factory_generation_service import (
    ContentFactoryGenerationService,
)
from app.modules.cms.services.ncert_generation_evidence import resolve_ncert_evidence_pack
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope, load_neet_2026_registry
from app.modules.ingestion.services.ncert_canonical_source import validate_ncert_generation_source

pytestmark = pytest.mark.asyncio(loop_scope="session")

REPO = Path(__file__).resolve().parents[3]
REVIEW = REPO / "docs" / "audits" / "ncert_evidence_write_review_001.json"
WRITE = REPO / "docs" / "audits" / "ncert_evidence_write_002.json"
NCERT = REPO / "NCERT Books"


def _cons(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


@pytest.mark.skipif(not REVIEW.is_file() or not WRITE.is_file(), reason="write-002 audits missing")
@pytest.mark.skipif(not NCERT.is_dir(), reason="NCERT Books missing")
def test_write_002_audit_fourteen_targets_and_evidence_ready_from_artifacts():
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    write = json.loads(WRITE.read_text(encoding="utf-8"))
    targets = [
        b
        for b in review["blueprints"]
        if b.get("recommendation") == "SAFE_FOR_SURGICAL_EVIDENCE_WRITE"
    ]
    assert len(targets) == 14
    assert set(write["target_ids"]) == {t["blueprint_id"] for t in targets}
    assert write.get("ncert_derived_written") is False
    assert write.get("idempotency", {}).get("ok") is True
    assert len(write.get("changed_blueprints") or []) == 14
    assert write.get("database_unchanged") is True
    assert write.get("provider_call_count") == 0

    by_id = {t["blueprint_id"]: t for t in targets}
    for row in write["changed_blueprints"]:
        bid = row["blueprint_id"]
        assert bid in by_id
        assert row.get("provenance_after") == "ai"
        assert row.get("provenance_before") == "ai"
        assert "ncert_derived" not in (row.get("after_constraints") or {})
        rel = row["ncert_source_relative"]
        assert rel == by_id[bid]["canonical_source"]["relative_path"]
        assert str(row["ku_id"]) == by_id[bid]["existing_ku"]["ku_id"]
        gate_after = row.get("gate_after") or {}
        assert gate_after.get("evidence") == "NCERT_EVIDENCE_READY"

        validated = validate_ncert_generation_source(NCERT / rel, root=NCERT)
        cons = {
            "ncert_source_path": str(validated.resolved_path),
            "ncert_source_relative": rel,
            "ku_id": row["ku_id"],
            "neet_ug_2026": row.get("syllabus_binding_after")
            or by_id[bid].get("syllabus_mapping"),
        }
        pack = resolve_ncert_evidence_pack(
            cons,
            provenance_tier="ai",
            concept_name=by_id[bid].get("concept"),
            chapter_name=by_id[bid].get("chapter"),
            topic_name=by_id[bid].get("topic"),
            ku_id=str(row["ku_id"]),
            validated_source=validated,
        )
        assert pack.status == "NCERT_EVIDENCE_READY", (bid, pack.status, pack.detail)


@pytest.mark.asyncio
async def test_write_002_review_required_still_blocks_provider():
    registry = load_neet_2026_registry()
    # Explicit missing binding → REVIEW_REQUIRED (fail-closed)
    cons = {"question_format": "single_correct"}
    gate = assert_blueprint_neet_syllabus_scope(
        cons,
        academic_subject_code="PHYSICS",
        registry=registry,
    )
    assert gate.status == "SYLLABUS_MAPPING_REVIEW_REQUIRED"

    provider_calls = {"n": 0}

    async def _never(*_a, **_k):
        provider_calls["n"] += 1
        raise AssertionError("provider must not be called")

    service = ContentFactoryGenerationService.__new__(ContentFactoryGenerationService)
    service.mcq_provider = MagicMock()
    service.mcq_provider.selection = MagicMock(routing_policy="fixed")
    service.session = AsyncMock()
    service._load_context = AsyncMock(
        return_value={
            "subject_name": "PHYSICS",
            "subject_code": "PHYSICS",
            "chapter_name": "x",
            "topic_name": "y",
            "concept_name": "z",
            "concept_summary": None,
            "objective_title": "o",
            "objective_description": None,
            "family_name": "f",
            "family_intent": "a",
            "family_key": "f",
            "concept_id": None,
        }
    )
    service._existing_stem_hashes = AsyncMock(return_value=set())
    service._batch_created_stems = AsyncMock(return_value=[])
    service._resolve_generation_evidence = AsyncMock(
        side_effect=AssertionError("must not reach evidence")
    )
    service._generate_with_backoff = _never
    bp = MagicMock()
    bp.id = "bp"
    bp.blueprint_version = 1
    bp.concept_id = "c"
    bp.difficulty = "medium"
    bp.constraints = cons

    with patch(
        "app.modules.cms.services.content_factory_generation_service.settings"
    ) as settings:
        settings.factory_max_pilot_attempt_multiplier = 2
        settings.factory_max_pilot_cost_usd = 10.0
        stats = await ContentFactoryGenerationService._execute_run(
            service,
            batch=MagicMock(id="b", status="CREATED"),
            job=MagicMock(id="j", started_at=None, status="CREATED"),
            run=MagicMock(id="r"),
            blueprint=bp,
            target_count=1,
            actor_id=uuid.uuid4(),
        )
    assert stats.stop_reason == "SYLLABUS_MAPPING_REVIEW_REQUIRED"
    assert provider_calls["n"] == 0


@pytest.mark.skipif(not WRITE.is_file(), reason="write-002 audit missing")
def test_write_002_audit_records_review_required_freeze():
    write = json.loads(WRITE.read_text(encoding="utf-8"))
    before = write["database_before"]["syllabus_gate"]
    after = write["database_after"]["syllabus_gate"]
    assert before.get("SYLLABUS_MAPPING_REVIEW_REQUIRED") == 248
    assert after.get("SYLLABUS_MAPPING_REVIEW_REQUIRED") == 248
    assert after.get("IN_SYLLABUS") == 197
    assert write["population_evidence_after"].get("IN_SYLLABUS_EVIDENCE_READY") == 146
