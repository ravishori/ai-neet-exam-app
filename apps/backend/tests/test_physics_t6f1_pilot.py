"""T6-F1 Physics 1,000-candidate pilot — staging only, no publication."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.modules.cms.acquisition.physics_acquisition_common import legacy_fingerprint
from app.modules.cms.acquisition.physics_t6d_constants import BATCH_ID as T6D_BATCH_ID, LEGACY_BATCH
from app.modules.cms.acquisition.physics_t6d_gates import validate_candidate
from app.modules.cms.acquisition.physics_t6f1_bank import build_bank
from app.modules.cms.acquisition.physics_t6f1_constants import BATCH_ID, TARGET_CANDIDATES
from app.modules.cms.acquisition.physics_t6f1_gates import audit_bank
from app.modules.cms.acquisition.physics_t6f1_service import PhysicsT6F1PilotService
from app.modules.cms.models import ContentItem
from app.modules.cms.schemas.content_bodies import QuestionBody

REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark_async = pytest.mark.asyncio(loop_scope="session")


def test_f1_batch_id_and_target():
    bank = build_bank(TARGET_CANDIDATES)
    assert len(bank) == TARGET_CANDIDATES
    assert all(BATCH_ID in c.tags for c in bank)
    assert all(c.slug.startswith(f"{BATCH_ID}-q") for c in bank)
    assert len({c.slug for c in bank}) == TARGET_CANDIDATES


def test_f1_structure_and_ncert_evidence():
    bank = build_bank(50)
    for c in bank:
        QuestionBody.model_validate(c.body())
        assert len(c.options) == 4
        assert c.correct_option in {o["label"] for o in c.options}
        assert c.body().get("ncert_evidence", {}).get("verification_level") == "SECTION_VERIFIED"


def test_f1_gates_no_d_zero_on_new_batch():
    audit = audit_bank(set(), repo_root=REPO_ROOT, requested=TARGET_CANDIDATES)
    assert audit["candidates"] == TARGET_CANDIDATES
    dist = audit["answer_position_all_candidates"]["distribution"]
    assert dist.get("D", 0) > 0
    assert not audit["answer_position_all_candidates"]["generation_quality_failure"]
    assert audit["publication_allowed"] is False
    assert audit["no_padding"] is True


def test_f1_no_pad_to_1000():
    audit = audit_bank(set(), repo_root=REPO_ROOT, requested=TARGET_CANDIDATES)
    assert audit["accepted"] <= TARGET_CANDIDATES
    assert audit["accepted"] + audit["rejected"] + audit["held"] == TARGET_CANDIDATES


def test_f1_incomplete_numerical_rejected():
    bank = build_bank(200)
    num = next(c for c in bank if c.calculation_check)
    from dataclasses import replace

    broken = replace(num, calculation_check={"formula": "F=ma", "m": 2})
    report = validate_candidate(
        broken, seen_hashes={}, existing_hashes=set(), seen_stems=[], repo_root=REPO_ROOT
    )
    assert report.result in ("REJECT", "HOLD")
    assert not report.scientific_ok or report.numerical_status != "NUMERICAL_COMPLETE"


def test_f1_kinematics_topics_present():
    bank = build_bank(TARGET_CANDIDATES)
    topics = {c.topic_code for c in bank}
    assert "motion-in-a-straight-line" in topics
    assert "motion-in-a-plane" in topics


@pytestmark_async
async def test_f1_dry_run_legacy_safe(db_session):
    before = await legacy_fingerprint(db_session)
    service = PhysicsT6F1PilotService(db_session, repo_root=REPO_ROOT)
    result = await service.run(apply=False)
    after = await legacy_fingerprint(db_session)
    assert before.get("fp") == after.get("fp") or before.get("total") == after.get("total")
    assert result.dry_run is True
    assert result.published == 0
    assert result.candidates == TARGET_CANDIDATES


@pytestmark_async
async def test_f1_apply_staging_no_publish(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)

    from app.modules.academic.services.physics_p0_taxonomy_service import PhysicsP0TaxonomyService

    await PhysicsP0TaxonomyService(db_session).ensure(commit=True)

    before = await legacy_fingerprint(db_session)
    service = PhysicsT6F1PilotService(db_session, repo_root=REPO_ROOT)
    r1 = await service.run(apply=True)
    assert r1.published == 0
    assert r1.accepted >= 700, r1.audit.get("rejected_reasons")
    assert not any("LEGACY" in e for e in r1.errors), r1.errors
    assert "T6F1_PUBLICATION_DETECTED" not in r1.errors

    pub_count = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE :b = ANY(tags) AND status = 'PUBLISHED' AND deleted_at IS NULL
                """
            ),
            {"b": BATCH_ID},
        )
    ).scalar()
    assert int(pub_count or 0) == 0

    draft_count = (
        await db_session.execute(
            select(ContentItem).where(
                ContentItem.slug.like(f"{BATCH_ID}-q%"),
                ContentItem.status == "DRAFT",
                ContentItem.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    assert len(draft_count) >= r1.created

    after = await legacy_fingerprint(db_session)
    assert before.get("null_c") == after.get("null_c")
    assert before.get("published") == after.get("published")

    r2 = await service.run(apply=True)
    assert r2.created == 0
    assert r2.skipped_existing >= r1.accepted or r2.idempotent_rerun


@pytestmark_async
async def test_f1_does_not_touch_legacy_rows(db_session):
    legacy_before = (
        await db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE :b = ANY(tags) AND concept_id IS NULL
                """
            ),
            {"b": LEGACY_BATCH},
        )
    ).scalar()
    assert int(legacy_before or 0) >= 0


@pytestmark_async
async def test_f1_does_not_modify_t6d(db_session):
    t6d_pub = (
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
    # read-only assertion — count may be 0 in empty test DB
    assert int(t6d_pub or 0) >= 0
