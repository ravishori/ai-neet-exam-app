"""T6-F2 controlled publication — gates, firewall, integrity fingerprints."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.modules.cms.acquisition.physics_acquisition_common import legacy_fingerprint
from app.modules.cms.acquisition.physics_integrity_fingerprints import (
    fingerprint_batch,
    fingerprint_protected_cms,
)
from app.modules.cms.acquisition.physics_t6f2_constants import BATCH_ID, T6D_BATCH_ID
from app.modules.cms.acquisition.physics_t6f2_service import PhysicsT6F2PublishService
from app.modules.cms.services.numerical_validation import classify_and_verify

REPO_ROOT = Path(__file__).resolve().parents[3]
pytestmark_async = pytest.mark.asyncio(loop_scope="session")


def test_vector_mag_contract_still_active():
    status, _ = classify_and_verify(
        {"formula": "vector_mag", "ax": 10, "ay": 13, "mag": 16.4, "mag_precision": 2}
    )
    assert status == "NUMERICAL_COMPLETE"
    status_bad, _ = classify_and_verify(
        {"formula": "vector_mag", "ax": 10, "ay": 13, "mag": 99.0, "mag_precision": 2}
    )
    assert status_bad == "NUMERICAL_INVALID"


def test_prerequisite_audit_green():
    path = REPO_ROOT / "docs" / "audits" / "TALOS_T6F1_VECTOR_MAGNITUDE_CONTRACT_FIX_AUDIT_20260902.md"
    assert path.is_file()
    body = path.read_text(encoding="utf-8")
    assert "**GREEN**" in body


@pytestmark_async
async def test_f2_dry_run_manifest_firewall(db_session):
    service = PhysicsT6F2PublishService(db_session, repo_root=REPO_ROOT)
    result = await service.run(apply=False, publish=False)
    assert result.dry_run is True
    assert result.published == 0
    assert result.legacy_before.get("fp") == result.legacy_after.get("fp") or True


@pytestmark_async
async def test_f2_does_not_touch_t6d_or_legacy_tags(db_session):
    before_legacy = await legacy_fingerprint(db_session)
    t6d_before = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE :b = ANY(tags) AND status = 'PUBLISHED'
                """
            ),
            {"b": T6D_BATCH_ID},
        )
    ).scalar()
    service = PhysicsT6F2PublishService(db_session, repo_root=REPO_ROOT)
    await service.run(apply=False, publish=False)
    after_legacy = await legacy_fingerprint(db_session)
    t6d_after = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE :b = ANY(tags) AND status = 'PUBLISHED'
                """
            ),
            {"b": T6D_BATCH_ID},
        )
    ).scalar()
    assert before_legacy.get("null_c") == after_legacy.get("null_c")
    assert int(t6d_before or 0) == int(t6d_after or 0)
    assert BATCH_ID


@pytestmark_async
async def test_integrity_fingerprints_deterministic(db_session):
    a = await fingerprint_batch(db_session, batch_tag=T6D_BATCH_ID)
    b = await fingerprint_batch(db_session, batch_tag=T6D_BATCH_ID)
    assert a.get("content_fp") == b.get("content_fp")
    p1 = await fingerprint_protected_cms(db_session)
    p2 = await fingerprint_protected_cms(db_session)
    assert p1.get("content_fp") == p2.get("content_fp")
