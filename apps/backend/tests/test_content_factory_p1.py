"""FACTORY-P1: ContentBatch / GenerationJob / GenerationRun foundation tests."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.modules.cms.schemas.content_factory import ContentBatchCreateRequest
from app.modules.cms.services.content_factory_service import ContentFactoryService
from app.modules.system.models.audit_log import AuditLog
from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")

TEST_DB = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_test_db"


async def _subject_id(db_session) -> str:
    from app.modules.academic.models import Subject

    result = await db_session.execute(select(Subject.id).limit(1))
    return str(result.scalar_one())


async def _chapter_for_subject(db_session, subject_id: str):
    from app.modules.academic.models import Chapter

    result = await db_session.execute(
        select(Chapter).where(Chapter.subject_id == uuid.UUID(subject_id)).limit(1)
    )
    return result.scalar_one()


async def _foreign_chapter(db_session, subject_id: str):
    from app.modules.academic.models import Chapter

    result = await db_session.execute(
        select(Chapter).where(Chapter.subject_id != uuid.UUID(subject_id)).limit(1)
    )
    return result.scalar_one_or_none()


async def test_student_denied_factory_apis(client, register_user, db_session):
    await register_user(client)  # STUDENT
    resp = await client.get("/api/v1/cms/content-batches")
    assert resp.status_code == 403


async def test_teacher_denied_factory_create(client, register_user, db_session):
    await register_user(client, role_codes=["TEACHER"], db_session=db_session)
    subject_id = await _subject_id(db_session)
    resp = await client.post(
        "/api/v1/cms/content-batches",
        json={
            "batch_key": f"teacher-denied-{uuid.uuid4().hex[:8]}",
            "name": "Should fail",
            "subject_id": subject_id,
            "target_count": 10,
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 403


async def test_batch_job_run_lifecycle_idempotency_audit(client, register_user, db_session):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    subject_id = await _subject_id(db_session)
    chapter = await _chapter_for_subject(db_session, subject_id)
    batch_key = f"factory-p1-{uuid.uuid4().hex[:10]}"

    create = await client.post(
        "/api/v1/cms/content-batches",
        json={
            "batch_key": batch_key,
            "name": "Factory P1 batch",
            "description": "orchestration only",
            "subject_id": subject_id,
            "chapter_id": str(chapter.id),
            "source_type": "HUMAN",
            "source_tier": "human",
            "target_count": 25,
            "initial_job": {
                "job_key": "gen-chapter-1",
                "job_type": "GENERATE",
                "requested_count": 25,
                "max_retries": 2,
            },
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["success"] is True
    assert body["meta"]["created"] is True
    batch = body["data"]
    assert batch["status"] == "CREATED"
    assert batch["batch_key"] == batch_key
    assert batch["job_count"] == 1
    batch_id = batch["id"]
    job_id = batch["jobs"][0]["id"]

    # Idempotent re-create
    again = await client.post(
        "/api/v1/cms/content-batches",
        json={
            "batch_key": batch_key,
            "name": "Factory P1 batch",
            "subject_id": subject_id,
            "target_count": 25,
        },
        headers=csrf_headers(client),
    )
    assert again.status_code == 200, again.text
    assert again.json()["meta"]["idempotent"] is True
    assert again.json()["data"]["id"] == batch_id

    # Job idempotency
    job_again = await client.post(
        f"/api/v1/cms/content-batches/{batch_id}/jobs",
        json={"job_key": "gen-chapter-1", "job_type": "GENERATE", "requested_count": 25},
        headers=csrf_headers(client),
    )
    assert job_again.status_code == 200
    assert job_again.json()["meta"]["idempotent"] is True
    assert job_again.json()["data"]["id"] == job_id

    # Valid batch transition
    tr = await client.post(
        f"/api/v1/cms/content-batches/{batch_id}/status",
        json={"to_status": "GENERATING"},
        headers=csrf_headers(client),
    )
    assert tr.status_code == 200, tr.text
    assert tr.json()["data"]["status"] == "GENERATING"

    # Invalid skip
    bad = await client.post(
        f"/api/v1/cms/content-batches/{batch_id}/status",
        json={"to_status": "RELEASED"},
        headers=csrf_headers(client),
    )
    assert bad.status_code == 409
    assert bad.json()["errors"][0]["code"] == "INVALID_STATE_TRANSITION"

    # Run create + fail + retry + succeed
    run1 = await client.post(
        f"/api/v1/cms/generation-jobs/{job_id}/runs",
        json={"reason": "first attempt"},
        headers=csrf_headers(client),
    )
    assert run1.status_code == 201, run1.text
    run1_id = run1.json()["data"]["id"]
    assert run1.json()["data"]["attempt_number"] == 1

    fail = await client.post(
        f"/api/v1/cms/generation-runs/{run1_id}/complete",
        json={
            "status": "FAILED",
            "processed_count": 3,
            "success_count": 0,
            "failure_count": 3,
            "error_summary": "simulated failure",
            "error_code": "SIMULATED",
        },
        headers=csrf_headers(client),
    )
    assert fail.status_code == 200, fail.text

    run2 = await client.post(
        f"/api/v1/cms/generation-jobs/{job_id}/runs",
        json={"reason": "retry"},
        headers=csrf_headers(client),
    )
    assert run2.status_code == 201, run2.text
    assert run2.json()["data"]["attempt_number"] == 2
    run2_id = run2.json()["data"]["id"]

    ok = await client.post(
        f"/api/v1/cms/generation-runs/{run2_id}/complete",
        json={"status": "SUCCEEDED", "processed_count": 25, "success_count": 25, "failure_count": 0},
        headers=csrf_headers(client),
    )
    assert ok.status_code == 200, ok.text

    # No duplicate successful work
    blocked = await client.post(
        f"/api/v1/cms/generation-jobs/{job_id}/runs",
        json={},
        headers=csrf_headers(client),
    )
    assert blocked.status_code == 409
    assert blocked.json()["errors"][0]["code"] == "JOB_ALREADY_SUCCEEDED"

    job = await client.get(f"/api/v1/cms/generation-jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["data"]["status"] == "SUCCEEDED"
    assert job.json()["data"]["retry_count"] == 1
    assert len(job.json()["data"]["runs"]) == 2

    # Audit events present
    audits = (
        await db_session.execute(
            select(AuditLog.action).where(AuditLog.action.like("factory.%")).order_by(AuditLog.created_at)
        )
    ).scalars().all()
    assert "factory.batch.created" in audits
    assert "factory.job.created" in audits
    assert "factory.batch.status_changed" in audits
    assert "factory.run.created" in audits
    assert "factory.run.failed" in audits
    assert "factory.run.retry_requested" in audits
    assert "factory.run.completed" in audits

    # Regression: no QUESTION rows created by factory ops
    qcount = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM cms.content_items WHERE content_type='QUESTION' AND deleted_at IS NULL")
        )
    ).scalar_one()
    # Seeded test DB may have 0 questions from prior tests in same savepoint — just ensure factory didn't insert
    factory_q = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE content_type='QUESTION' AND deleted_at IS NULL
                  AND created_at > now() - interval '1 minute'
                  AND title LIKE 'Factory%'
                """
            )
        )
    ).scalar_one()
    assert factory_q == 0
    assert qcount is not None


async def test_invalid_hierarchy_rejected(client, register_user, db_session):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    subject_id = await _subject_id(db_session)
    foreign = await _foreign_chapter(db_session, subject_id)
    if not foreign:
        pytest.skip("Need at least two subjects with chapters")
    resp = await client.post(
        "/api/v1/cms/content-batches",
        json={
            "batch_key": f"bad-hier-{uuid.uuid4().hex[:8]}",
            "name": "Bad hierarchy",
            "subject_id": subject_id,
            "chapter_id": str(foreign.id),
            "target_count": 5,
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "INVALID_HIERARCHY"


async def test_retry_limit_enforced(client, register_user, db_session):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    subject_id = await _subject_id(db_session)
    batch_key = f"retry-limit-{uuid.uuid4().hex[:8]}"
    create = await client.post(
        "/api/v1/cms/content-batches",
        json={
            "batch_key": batch_key,
            "name": "Retry limit",
            "subject_id": subject_id,
            "target_count": 1,
            "initial_job": {
                "job_key": "job-validate-1",
                "job_type": "VALIDATE",
                "requested_count": 1,
                "max_retries": 1,
            },
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    job_id = create.json()["data"]["jobs"][0]["id"]

    async def fail_once():
        r = await client.post(
            f"/api/v1/cms/generation-jobs/{job_id}/runs",
            json={},
            headers=csrf_headers(client),
        )
        assert r.status_code == 201, r.text
        c = await client.post(
            f"/api/v1/cms/generation-runs/{r.json()['data']['id']}/complete",
            json={"status": "FAILED", "failure_count": 1, "error_code": "X"},
            headers=csrf_headers(client),
        )
        assert c.status_code == 200, c.text

    await fail_once()  # attempt 1 fail → retry_count becomes 1 on next request
    await fail_once()  # attempt 2 (retry 1) fail
    blocked = await client.post(
        f"/api/v1/cms/generation-jobs/{job_id}/runs",
        json={},
        headers=csrf_headers(client),
    )
    assert blocked.status_code == 409
    assert blocked.json()["errors"][0]["code"] == "RETRY_LIMIT_EXCEEDED"


async def test_concurrent_batch_key_unique(db_session):
    """Two concurrent inserts with the same batch_key cannot both succeed."""
    from app.modules.academic.models import Subject

    subject_id = (await db_session.execute(select(Subject.id).limit(1))).scalar_one()
    batch_key = f"concurrent-{uuid.uuid4().hex[:10]}"

    async def race_create(name: str) -> str:
        engine = create_async_engine(TEST_DB, poolclass=NullPool)
        async with AsyncSession(bind=engine, expire_on_commit=False) as session:
            service = ContentFactoryService(session)
            batch, created = await service.create_batch(
                ContentBatchCreateRequest(
                    batch_key=batch_key,
                    name=name,
                    subject_id=subject_id,
                    target_count=1,
                ),
                actor_id=None,
            )
            await session.commit()
            await engine.dispose()
            return f"{created}:{batch.id}"

    results = await asyncio.gather(race_create("A"), race_create("B"))
    created_flags = [r.split(":")[0] for r in results]
    ids = {r.split(":")[1] for r in results}
    assert created_flags.count("True") == 1
    assert created_flags.count("False") == 1
    assert len(ids) == 1

    # Cleanup rows created outside the test savepoint
    engine = create_async_engine(TEST_DB, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM cms.content_batches WHERE batch_key = :k"),
            {"k": batch_key},
        )
    await engine.dispose()


async def test_batch_state_machine_happy_path_service(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    subject_id = await _subject_id(db_session)
    service = ContentFactoryService(db_session)
    batch, _ = await service.create_batch(
        ContentBatchCreateRequest(
            batch_key=f"sm-{uuid.uuid4().hex[:8]}",
            name="State machine",
            subject_id=uuid.UUID(subject_id),
            target_count=0,
        ),
        actor_id=uuid.UUID(user["id"]),
    )
    path = ["GENERATING", "QA", "SAMPLING", "CERTIFIED", "RELEASE_CANDIDATE", "RELEASED"]
    from app.core.exceptions import AppError
    from app.modules.cms.schemas.content_factory import BatchStatusTransitionRequest

    for status in path:
        batch = await service.transition_batch(
            batch.id,
            BatchStatusTransitionRequest(to_status=status),
            actor_id=uuid.UUID(user["id"]),
        )
        assert batch.status == status
    with pytest.raises(AppError) as exc:
        await service.transition_batch(
            batch.id,
            BatchStatusTransitionRequest(to_status="CERTIFIED"),
            actor_id=uuid.UUID(user["id"]),
        )
    assert exc.value.code == "INVALID_STATE_TRANSITION"
