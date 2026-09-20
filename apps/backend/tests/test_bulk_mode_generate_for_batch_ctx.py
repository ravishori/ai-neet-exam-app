"""Regression test for a real bug caught while wiring BULK-MODE-001:
`generate_for_batch` previously forwarded ALL of `**ctx` to
`attach_blueprint_to_batch`, `create_job`, and `request_run` — none of
which accept a `bulk_mode` kwarg, so passing `bulk_mode=True` through the
shared `**ctx` would have raised `TypeError: unexpected keyword argument
'bulk_mode'` the first time bulk mode was actually used.

Fixed by giving `generate_for_batch` (and `_execute_run`) an explicit
`bulk_mode` parameter, kept out of the `**ctx` spread to those three
sub-calls, and passed explicitly only to `_execute_run`.

Pure mock-based test — no DB, no provider call.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.modules.cms.services.content_factory_generation_service import (
    ContentFactoryGenerationService,
    GenerationStats,
)


def _make_service():
    service = ContentFactoryGenerationService.__new__(ContentFactoryGenerationService)
    service.session = AsyncMock()
    service.mcq_provider = MagicMock()
    service.mcq_provider.selection = MagicMock(routing_policy="fixed")

    bp = MagicMock()
    bp.blueprint_version = 1
    bp.blueprint_key = "bp-key"
    service._assert_blueprint_eligible = AsyncMock(return_value=bp)

    service.planning = MagicMock()
    service.planning.attach_blueprint_to_batch = AsyncMock(return_value=(MagicMock(), True))

    batch = MagicMock()
    batch.id = "batch-1"
    service.factory_repo = MagicMock()
    service.factory_repo.get_batch = AsyncMock(return_value=batch)

    job = MagicMock()
    job.id = "job-1"
    job.blueprint_id = "bp-1"
    job.blueprint_version = 1
    service.factory = MagicMock()
    service.factory.create_job = AsyncMock(return_value=(job, True))

    run = MagicMock()
    run.id = "run-1"
    service.factory.request_run = AsyncMock(return_value=run)

    stats = GenerationStats(created=1, attempted=1)
    service._execute_run = AsyncMock(return_value=stats)
    service.factory.complete_run = AsyncMock()
    service.audit = MagicMock()
    service.audit.add = MagicMock()

    return service, batch, job, run


async def test_bulk_mode_not_leaked_into_attach_create_job_or_request_run():
    service, batch, job, run = _make_service()
    import uuid

    try:
        await service.generate_for_batch(
            batch.id,
            blueprint_id=uuid.uuid4(),
            target_count=1,
            actor_id=uuid.uuid4(),
            bulk_mode=True,
        )
    except TypeError as exc:
        raise AssertionError(f"bulk_mode leaked into a sub-call signature: {exc}") from exc

    # None of these three received bulk_mode in their kwargs.
    _, attach_kwargs = service.planning.attach_blueprint_to_batch.call_args
    assert "bulk_mode" not in attach_kwargs

    _, job_kwargs = service.factory.create_job.call_args
    assert "bulk_mode" not in job_kwargs

    _, run_kwargs = service.factory.request_run.call_args
    assert "bulk_mode" not in run_kwargs


async def test_bulk_mode_true_passed_explicitly_to_execute_run():
    service, batch, job, run = _make_service()
    import uuid

    await service.generate_for_batch(
        batch.id,
        blueprint_id=uuid.uuid4(),
        target_count=1,
        actor_id=uuid.uuid4(),
        bulk_mode=True,
    )

    _, execute_kwargs = service._execute_run.call_args
    assert execute_kwargs.get("bulk_mode") is True


async def test_bulk_mode_defaults_false_when_omitted():
    service, batch, job, run = _make_service()
    import uuid

    await service.generate_for_batch(
        batch.id,
        blueprint_id=uuid.uuid4(),
        target_count=1,
        actor_id=uuid.uuid4(),
    )

    _, execute_kwargs = service._execute_run.call_args
    assert execute_kwargs.get("bulk_mode") is False
