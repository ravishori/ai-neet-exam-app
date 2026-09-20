"""Regression test for the pilot driver's terminal batch-state bug.

The driver previously never transitioned a batch's status when it finished
successfully — batch pilot-400-subjectquota-20260919b stayed GENERATING
even after 400/400 accepted. Fixed via
`mark_batch_complete_if_target_reached()`, which advances GENERATING → QA
(the project's canonical "generation phase complete" state — there is no
separate COMPLETED status in BATCH_TRANSITIONS) using the existing,
already-tested `ContentFactoryService.transition_batch`.

This test exercises the actual helper the driver calls — not the full
live_run() loop, so no provider/generation call is made. DB-only: creates
one throwaway batch via the normal service API, never touches existing
content_items or the prod-5k-* batches.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.modules.academic.models import Subject
from app.modules.cms.schemas.content_factory import ContentBatchCreateRequest
from app.modules.cms.services.content_factory_service import ContentFactoryService

pytestmark = pytest.mark.asyncio(loop_scope="session")

_DRIVER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prod_5k_run_002_subject_quota.py"


def _load_driver_module():
    spec = importlib.util.spec_from_file_location("prod_5k_run_002_subject_quota_terminal_test", _DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


async def _subject_id(db_session) -> uuid.UUID:
    result = await db_session.execute(select(Subject.id).limit(1))
    return result.scalar_one()


async def _make_batch(db_session, register_user, client, *, status: str = "GENERATING"):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    actor_id = uuid.UUID(user["id"])
    subject_id = await _subject_id(db_session)
    service = ContentFactoryService(db_session)
    batch, _ = await service.create_batch(
        ContentBatchCreateRequest(
            batch_key=f"terminal-state-test-{uuid.uuid4().hex[:10]}",
            name="Terminal state regression",
            subject_id=subject_id,
            target_count=10,
        ),
        actor_id=actor_id,
    )
    if status != "CREATED":
        from app.modules.cms.schemas.content_factory import BatchStatusTransitionRequest

        batch = await service.transition_batch(
            batch.id, BatchStatusTransitionRequest(to_status=status), actor_id=actor_id
        )
    return service, batch, actor_id


async def test_batch_transitions_to_qa_when_target_reached(db_session, register_user, client):
    driver = _load_driver_module()
    service, batch, actor_id = await _make_batch(db_session, register_user, client, status="GENERATING")

    transitioned = await driver.mark_batch_complete_if_target_reached(
        service, batch_id=batch.id, actor_id=actor_id, accepted_now=10, target=10
    )
    assert transitioned is True

    reloaded = await service.repo.get_batch(batch.id)
    assert reloaded.status == "QA"


async def test_batch_transitions_to_qa_when_target_exceeded(db_session, register_user, client):
    """Resume scenario: accepted_now can overshoot target slightly (e.g. a
    call's created count lands past target) — must still transition."""
    driver = _load_driver_module()
    service, batch, actor_id = await _make_batch(db_session, register_user, client, status="GENERATING")

    transitioned = await driver.mark_batch_complete_if_target_reached(
        service, batch_id=batch.id, actor_id=actor_id, accepted_now=12, target=10
    )
    assert transitioned is True
    reloaded = await service.repo.get_batch(batch.id)
    assert reloaded.status == "QA"


async def test_batch_left_untouched_when_target_not_reached(db_session, register_user, client):
    """Timeout/under-target exit — preserves prior semantics exactly: the
    batch stays in whatever state it was in (GENERATING), no forced FAILED
    transition, no COMPLETED, nothing."""
    driver = _load_driver_module()
    service, batch, actor_id = await _make_batch(db_session, register_user, client, status="GENERATING")

    transitioned = await driver.mark_batch_complete_if_target_reached(
        service, batch_id=batch.id, actor_id=actor_id, accepted_now=3, target=10
    )
    assert transitioned is False

    reloaded = await service.repo.get_batch(batch.id)
    assert reloaded.status == "GENERATING"


async def test_batch_transition_from_created_raises_invalid_state(db_session, register_user, client):
    """CREATED → QA is not a valid direct transition (CREATED only allows
    GENERATING/FAILED/QUARANTINED per BATCH_TRANSITIONS). The helper must
    not swallow this — it should surface as the same AppError the driver's
    caller catches and logs, never silently succeed."""
    driver = _load_driver_module()
    service, batch, actor_id = await _make_batch(db_session, register_user, client, status="CREATED")

    with pytest.raises(AppError) as exc:
        await driver.mark_batch_complete_if_target_reached(
            service, batch_id=batch.id, actor_id=actor_id, accepted_now=10, target=10
        )
    assert exc.value.code == "INVALID_STATE_TRANSITION"

    reloaded = await service.repo.get_batch(batch.id)
    assert reloaded.status == "CREATED"
