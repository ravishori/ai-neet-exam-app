"""BULK-MODE-001 — verifies bulk_mode=True skips only the synchronous NCERT
evidence-sufficiency gate and the claim-level NCERT grounding check, while
SYLLABUS-GATE-001 and structural validation remain fully active regardless.

Mirrors the mocking scaffold in tests/test_syllabus_gate_001.py
(test_syllabus_then_ncert_order_before_provider) — no live provider/DB call.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.cms.services.content_factory_generation_service import (
    ContentFactoryGenerationService,
)
from app.modules.cms.syllabus import load_neet_2026_registry

pytestmark = pytest.mark.asyncio(loop_scope="session")

REPO = Path(__file__).resolve().parents[3]
SYLLABUS = REPO / "NEETSyllabus.txt"


def _make_service_and_blueprint(*, order: list[str], provider_should_be_called: bool):
    async def _evidence(*args, **kwargs):
        order.append("ncert")
        pack = MagicMock()
        pack.requires_ncert = True
        pack.is_ready = False
        pack.detail = "insufficient for bulk-mode test"
        pack.relative_posix = None
        pack.evidence_text = ""
        pack.section_heading = None
        pack.page_numbers = []
        pack.ku_id = None
        return pack

    async def _generate(*args, **kwargs):
        order.append("provider")
        if not provider_should_be_called:
            raise AssertionError("provider must not be called when evidence insufficient and bulk_mode=False")
        raise RuntimeError("stop-after-provider-reached")  # cheap sentinel, no real call made

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
    service._generate_with_backoff = _generate

    blueprint = MagicMock()
    blueprint.id = "bp"
    blueprint.blueprint_version = 1
    blueprint.concept_id = "c"
    blueprint.difficulty = "medium"
    blueprint.constraints = {
        "neet_ug_2026": {"subject": "PHYSICS", "unit_number": 9, "topic_id": topic.topic_id}
    }

    batch = MagicMock()
    batch.id = "b"
    batch.status = "CREATED"
    job = MagicMock()
    job.id = "j"
    job.started_at = None
    run = MagicMock()
    run.id = "r"
    return service, blueprint, batch, job, run


async def test_bulk_mode_false_still_blocks_on_insufficient_evidence():
    """Default (non-bulk) behavior is completely unchanged — must be the
    same as the pre-existing test_syllabus_gate_001 assertion."""
    order: list[str] = []
    service, blueprint, batch, job, run = _make_service_and_blueprint(
        order=order, provider_should_be_called=False
    )

    with patch(
        "app.modules.cms.services.content_factory_generation_service.settings"
    ) as settings:
        settings.factory_max_pilot_attempt_multiplier = 2
        settings.factory_max_pilot_cost_usd = 10.0
        stats = await ContentFactoryGenerationService._execute_run(
            service, batch=batch, job=job, run=run, blueprint=blueprint,
            target_count=1, actor_id="a",
        )

    assert order == ["ncert"]
    assert stats.stop_reason == "NCERT_EVIDENCE_INSUFFICIENT"


async def test_bulk_mode_true_skips_evidence_gate_and_reaches_provider():
    """bulk_mode=True must NOT hard-block on insufficient evidence — the
    run proceeds to attempt provider generation instead of stopping."""
    order: list[str] = []
    service, blueprint, batch, job, run = _make_service_and_blueprint(
        order=order, provider_should_be_called=True
    )

    with patch(
        "app.modules.cms.services.content_factory_generation_service.settings"
    ) as settings:
        settings.factory_max_pilot_attempt_multiplier = 2
        settings.factory_max_pilot_cost_usd = 10.0
        stats = await ContentFactoryGenerationService._execute_run(
            service, batch=batch, job=job, run=run, blueprint=blueprint,
            target_count=1, actor_id="a", bulk_mode=True,
        )

    # Retries may call the sentinel provider more than once (unrelated to
    # bulk_mode); what matters is the evidence gate did not short-circuit.
    assert order[0] == "ncert"
    assert "provider" in order
    assert stats.stop_reason != "NCERT_EVIDENCE_INSUFFICIENT"


async def test_bulk_mode_true_does_not_weaken_syllabus_gate():
    """SYLLABUS-GATE-001 must still block regardless of bulk_mode — bulk
    mode only affects NCERT evidence/grounding gates, never syllabus scope."""
    order: list[str] = []
    service, blueprint, batch, job, run = _make_service_and_blueprint(
        order=order, provider_should_be_called=False
    )
    blueprint.constraints = {}  # no neet_ug_2026 binding at all → out of scope

    with patch(
        "app.modules.cms.services.content_factory_generation_service.settings"
    ) as settings:
        settings.factory_max_pilot_attempt_multiplier = 2
        settings.factory_max_pilot_cost_usd = 10.0
        stats = await ContentFactoryGenerationService._execute_run(
            service, batch=batch, job=job, run=run, blueprint=blueprint,
            target_count=1, actor_id="a", bulk_mode=True,
        )

    assert order == []  # never even reached the NCERT evidence step
    assert stats.stop_reason == "SYLLABUS_MAPPING_REVIEW_REQUIRED"
