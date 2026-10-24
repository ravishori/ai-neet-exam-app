"""Admin question-editing workflow: PATCH /content-items/{id} for QUESTION
bodies, covering legacy dict options, answer verification, concept mapping,
permissions, version history, audit logs, and save/reload behavior."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")

_UNSET = object()


async def _concept_id(db_session) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).limit(1))
    return str(result.scalar_one())


async def _other_concept_id(db_session, exclude: str) -> str:
    from app.modules.academic.models import Concept

    result = await db_session.execute(select(Concept.id).where(Concept.id != uuid.UUID(exclude)).limit(1))
    return str(result.scalar_one())


async def _create_question(client, concept_id: str, *, correct_option: str = "A") -> dict:
    resp = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": f"Edit Q {uuid.uuid4().hex[:6]}",
            "slug": f"edit-q-{uuid.uuid4().hex[:10]}",
            "language": "en",
            "body": publishable_question_body(correct_option=correct_option),
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _publish_question(client, concept_id: str, *, correct_option: str = "A") -> dict:
    item = await _create_question(client, concept_id, correct_option=correct_option)
    item_id = item["id"]
    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{item_id}/review", json={"decision": "approve"}, headers=csrf_headers(client)
    )
    pub = await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    assert pub.status_code == 200, pub.text
    return pub.json()["data"]


async def _force_dict_options(
    db_session, item_id: str, *, correct_option=None, explanation=_UNSET, answer_status=_UNSET
) -> None:
    """Direct DB mutation -- simulates the legacy PYQ-import shape (F-17),
    the only way to construct this state since the create/publish API
    always validates options as an array. `explanation`/`answer_status`
    optionally reproduce the exact production item (7fb11a6b-9295-40e7-
    b85c-146c8bcfd69f): explanation=None and answer_status="ANSWER_VERIFIED"
    with no ncert_evidence -- a legacy row that claims a verified answer
    without ever having recorded what verified it."""
    from app.modules.cms.models import ContentVersion

    result = await db_session.execute(
        select(ContentVersion).where(ContentVersion.content_item_id == uuid.UUID(item_id))
    )
    version = result.scalar_one()
    body = dict(version.body)
    body["options"] = {o["label"]: o["text"] for o in body["options"]}
    if correct_option is not None:
        body["correct_option"] = correct_option
    if explanation is not _UNSET:
        body["explanation"] = explanation
    if answer_status is not _UNSET:
        body["answer_status"] = answer_status
    version.body = body
    db_session.add(version)
    await db_session.commit()


# ---------------------------------------------------------------------------
# Legacy dict options
# ---------------------------------------------------------------------------


async def test_edit_normalizes_legacy_dict_options_on_save(client, db_session, register_user):
    """An admin correcting a legacy dict-shaped PUBLISHED question submits
    the normalized array shape (as read from the already-normalized
    review-packet, per F-17) -- the save must accept and persist it as a
    proper array, not re-introduce the dict shape."""
    user = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    published = await _publish_question(client, concept_id)
    item_id = published["id"]
    await _force_dict_options(db_session, item_id)

    packet = await client.get(f"/api/v1/cms/content-items/{item_id}/review-packet")
    assert packet.status_code == 200, packet.text
    options = packet.json()["data"]["question"]["options"]
    assert isinstance(options, list) and len(options) == 4

    new_body = publishable_question_body(
        stem="Corrected stem.", options=options, correct_option=options[1]["label"]
    )
    patch = await client.patch(
        f"/api/v1/cms/content-items/{item_id}",
        json={"body": new_body, "change_summary": "Fixed legacy dict-shaped options"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text
    latest_body = patch.json()["data"]["latest_version"]["body"]
    assert isinstance(latest_body["options"], list)
    assert latest_body["options"] == options
    assert user  # registered for auth cookies only


# ---------------------------------------------------------------------------
# Answer verification
# ---------------------------------------------------------------------------


async def test_edit_blocks_answer_verified_without_evidence(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)

    body = publishable_question_body(correct_option="B", ncert_evidence=None, answer_status="ANSWER_VERIFIED")
    patch = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={"body": body, "change_summary": "Attempt to mark verified without evidence"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 422, patch.text
    # The save/edit path (unlike publish's deliberately generic message)
    # must surface specifically why -- not just "failed quality gates".
    # This is a whole-body (model-level) validator, so Pydantic reports no
    # single field loc for it; the specific message still comes through.
    errors = patch.json()["errors"]
    assert any("evidence" in e["message"] for e in errors)
    assert "Content body failed publishing quality gates" not in patch.text


async def test_edit_blocks_answer_verified_without_valid_correct_option(client, db_session, register_user):
    """correct_option must match an actual option label -- never inferred,
    never left dangling."""
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)

    body = publishable_question_body(correct_option="Z", answer_status="ANSWER_VERIFIED")
    patch = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={"body": body, "change_summary": "Invalid correct_option"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 422, patch.text


async def test_edit_allows_answer_verified_with_valid_option_and_evidence(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)

    body = publishable_question_body(correct_option="C", answer_status="ANSWER_VERIFIED")
    patch = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={"body": body, "change_summary": "Verified against NCERT section"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["data"]["latest_version"]["body"]["answer_status"] == "ANSWER_VERIFIED"


async def test_edit_save_error_is_actionable_not_generic(client, db_session, register_user):
    """Regression, reproduces the exact reported production failure on
    7fb11a6b-9295-40e7-b85c-146c8bcfd69f: a legacy row with explanation=None
    AND answer_status="ANSWER_VERIFIED" with no ncert_evidence. Before this
    fix, update_draft() used assert_body_publishable() (the publish-time
    gate, deliberately generic by design) for the SAVE path too, so every
    failure surfaced as the same opaque "Content body failed publishing
    quality gates" with no indication of which field was wrong -- the admin
    had no way to know what to fix, experienced as "Save does not work"."""
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)
    item_id = item["id"]
    await _force_dict_options(db_session, item_id, explanation=None, answer_status="ANSWER_VERIFIED")

    # Submit the body exactly as the review-packet's normalized/prefilled
    # question would be re-serialized by the edit form, still carrying the
    # same (now-invalid) explanation=None forward -- the admin hasn't
    # touched the explanation field yet.
    packet = await client.get(f"/api/v1/cms/content-items/{item_id}/review-packet")
    question = packet.json()["data"]["question"]
    assert question["explanation"] is None
    assert question["answer_status"] == "ANSWER_VERIFIED"

    body = {
        "stem": question["stem"],
        "options": question["options"],
        "correct_option": question["correct_option"],
        "explanation": question["explanation"],
        "answer_status": question["answer_status"],
    }
    patch = await client.patch(
        f"/api/v1/cms/content-items/{item_id}",
        json={"body": body, "change_summary": "Attempted edit without fixing explanation first"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 422, patch.text
    errors = patch.json()["errors"]
    # Specific and field-attributed -- the admin is told exactly what to fix.
    assert any(e.get("field") == "explanation" for e in errors)
    assert "Content body failed publishing quality gates" not in patch.text


async def test_edit_legacy_published_question_saves_after_fixing_explanation_and_concept(
    client, db_session, register_user
):
    """The actual "legitimate edit must succeed" case: an admin fixing the
    real gaps (explanation, concept mapping) on this exact legacy shape,
    without touching answer verification, must be able to save -- proving
    the fix doesn't just produce a better error message but actually
    unblocks saving once the admin addresses what's flagged."""
    admin = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    other_concept_id = await _other_concept_id(db_session, concept_id)
    published = await _publish_question(client, concept_id)
    item_id = published["id"]
    await _force_dict_options(db_session, item_id, explanation=None, answer_status="ANSWER_VERIFIED")

    packet = await client.get(f"/api/v1/cms/content-items/{item_id}/review-packet")
    question = packet.json()["data"]["question"]
    assert isinstance(question["options"], list) and len(question["options"]) == 4

    body = {
        "stem": question["stem"],
        "options": question["options"],
        "correct_option": question["correct_option"],
        "explanation": "Filled in by SME during correction.",
        # Mirrors the frontend's safe default: don't re-assert ANSWER_VERIFIED
        # since there's no recorded evidence backing the legacy claim.
        "answer_status": "ANSWER_PENDING",
    }
    patch = await client.patch(
        f"/api/v1/cms/content-items/{item_id}",
        json={"body": body, "change_summary": "Filled missing explanation; reassigned concept", "concept_id": other_concept_id},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()["data"]
    assert data["concept_id"] == other_concept_id
    assert data["latest_version"]["body"]["explanation"] == "Filled in by SME during correction."

    reget = await client.get(f"/api/v1/cms/content-items/{item_id}")
    reloaded = reget.json()["data"]
    assert reloaded["concept_id"] == other_concept_id
    assert reloaded["latest_version"]["body"]["explanation"] == "Filled in by SME during correction."
    assert admin  # registered for auth cookies only


# ---------------------------------------------------------------------------
# Concept mapping
# ---------------------------------------------------------------------------


async def test_edit_updates_concept_mapping(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    other_concept_id = await _other_concept_id(db_session, concept_id)
    item = await _create_question(client, concept_id)

    patch = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={
            "body": publishable_question_body(),
            "change_summary": "Reassign concept mapping",
            "concept_id": other_concept_id,
        },
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["data"]["concept_id"] == other_concept_id

    reloaded = await client.get(f"/api/v1/cms/content-items/{item['id']}/review-packet")
    assert reloaded.json()["data"]["structural"]["issues"] == [] or "Missing academic concept mapping" not in (
        reloaded.json()["data"]["structural"]["issues"]
    )


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


async def test_content_manager_cannot_edit_published_question(client, db_session, register_user):
    """content.edit_own_draft (CONTENT_MANAGER has it) is not enough to
    correct a PUBLISHED item -- that needs content.force_edit_published,
    ADMIN/SUPER_ADMIN only."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    published = await _publish_question(client, concept_id)

    patch = await client.patch(
        f"/api/v1/cms/content-items/{published['id']}",
        json={"body": publishable_question_body(stem="Attempted edit"), "change_summary": "Should be forbidden"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 403, patch.text


async def test_admin_can_edit_published_question(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    published = await _publish_question(client, concept_id)

    patch = await client.patch(
        f"/api/v1/cms/content-items/{published['id']}",
        json={"body": publishable_question_body(stem="Admin-corrected stem"), "change_summary": "Admin fix"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text


async def test_content_manager_can_edit_own_draft(client, db_session, register_user):
    """Sanity: the existing own-draft path still works unchanged."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)

    patch = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={"body": publishable_question_body(stem="Own-draft edit"), "change_summary": "Fixing my own draft"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text


async def test_edit_requires_non_empty_change_summary(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)

    patch = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={"body": publishable_question_body(), "change_summary": ""},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 422, patch.text


# ---------------------------------------------------------------------------
# Version history + live content never silently changes
# ---------------------------------------------------------------------------


async def test_edit_published_question_creates_new_version_without_changing_live_content(
    client, db_session, register_user
):
    """Correcting a PUBLISHED question must never change what students are
    already being served -- current_version_id stays put; only
    latest_version_id (and status, back to DRAFT pending re-review) moves."""
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    published = await _publish_question(client, concept_id)
    item_id = published["id"]
    original_current_version_id = published["current_version"]["id"]

    from app.modules.cms.models import ContentItem

    patch = await client.patch(
        f"/api/v1/cms/content-items/{item_id}",
        json={"body": publishable_question_body(stem="New draft stem, not yet live"), "change_summary": "Correction pending review"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()["data"]
    assert data["status"] == "DRAFT"
    assert data["latest_version"]["id"] != original_current_version_id

    item_row = await db_session.get(ContentItem, uuid.UUID(item_id))
    assert str(item_row.current_version_id) == original_current_version_id
    assert str(item_row.current_version_id) != str(item_row.latest_version_id)


async def test_edit_published_question_students_still_served_original_stem(client, db_session, register_user):
    """Stronger than the DB-column check above: exercises the real
    student-facing serving path (assessment_router._public_question ->
    get_content_body(), which reads item.current_version_id) end to end --
    a student with an already-generated attempt referencing this question
    (attempts are not status-filtered, unlike browse/search) must still see
    the ORIGINAL stem after an admin edits it, not the new draft stem."""
    admin = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    original_stem = "Original, still-live stem."
    published = await _publish_question(client, concept_id)
    item_id = published["id"]

    # Re-author with a known, checkable stem before generating the attempt.
    from app.modules.cms.models import ContentItem, ContentVersion

    version = (
        await db_session.execute(select(ContentVersion).where(ContentVersion.id == uuid.UUID(published["current_version"]["id"])))
    ).scalar_one()
    body = dict(version.body)
    body["stem"] = original_stem
    version.body = body
    db_session.add(version)
    await db_session.commit()

    generate = await client.post(
        "/api/v1/assessments/practice",
        json={"scope_type": "CONCEPT", "scope_id": concept_id},
        headers=csrf_headers(client),
    )
    assert generate.status_code == 201, generate.text
    assessment_id = generate.json()["data"]["id"]
    start = await client.post(f"/api/v1/assessments/{assessment_id}/attempts", headers=csrf_headers(client))
    assert start.status_code == 201, start.text
    attempt_id = start.json()["data"]["id"]

    before = await client.get(f"/api/v1/attempts/{attempt_id}")
    assert before.status_code == 200, before.text
    served_before = next(q for q in before.json()["data"]["questions"] if q["content_item_id"] == item_id)
    assert served_before["stem"] == original_stem

    patch = await client.patch(
        f"/api/v1/cms/content-items/{item_id}",
        json={
            "body": publishable_question_body(stem="EDITED stem, pending review, must not be served yet"),
            "change_summary": "Correction pending review",
        },
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["data"]["status"] == "DRAFT"

    item_row = await db_session.get(ContentItem, uuid.UUID(item_id))
    assert item_row.status == "DRAFT"  # confirms the edit really did flip status, same as above

    after = await client.get(f"/api/v1/attempts/{attempt_id}")
    assert after.status_code == 200, after.text
    served_after = next(q for q in after.json()["data"]["questions"] if q["content_item_id"] == item_id)
    assert served_after["stem"] == original_stem
    assert served_after["stem"] != "EDITED stem, pending review, must not be served yet"
    assert admin  # registered for auth cookies only


async def test_edit_creates_a_new_content_version_row_preserving_history(client, db_session, register_user):
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)

    from app.modules.cms.models import ContentVersion

    before = (
        await db_session.execute(select(ContentVersion).where(ContentVersion.content_item_id == uuid.UUID(item["id"])))
    ).scalars().all()
    assert len(before) == 1

    patch = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={"body": publishable_question_body(stem="v2 stem"), "change_summary": "v2"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text

    after = (
        await db_session.execute(select(ContentVersion).where(ContentVersion.content_item_id == uuid.UUID(item["id"])))
    ).scalars().all()
    assert len(after) == 2
    assert {v.version_no for v in after} == {1, 2}
    # The v1 row is untouched, not overwritten.
    v1 = next(v for v in after if v.version_no == 1)
    assert v1.body["stem"] != "v2 stem"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


async def test_edit_writes_audit_log_entry_with_actor_and_changed_fields(client, db_session, register_user):
    user = await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)

    patch = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={"body": publishable_question_body(stem="Audited edit"), "change_summary": "Testing audit log"},
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text

    from app.modules.system.models.audit_log import AuditLog

    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == uuid.UUID(item["id"]), AuditLog.action == "content.update_draft")
        )
    ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert str(row.actor_user_id) == user["id"]
    assert row.log_metadata["change_summary"] == "Testing audit log"
    assert "stem" in row.log_metadata["fields_changed"]


# ---------------------------------------------------------------------------
# Save/reload
# ---------------------------------------------------------------------------


async def test_edit_save_then_reload_reflects_persisted_changes(client, db_session, register_user):
    """Not just the PATCH response -- a fresh GET afterward must also show
    the edited fields, proving the write actually persisted."""
    await register_user(client, role_codes=["ADMIN"], db_session=db_session)
    concept_id = await _concept_id(db_session)
    item = await _create_question(client, concept_id)

    patch = await client.patch(
        f"/api/v1/cms/content-items/{item['id']}",
        json={
            "body": publishable_question_body(stem="Reloaded stem", correct_option="D"),
            "change_summary": "Save/reload check",
        },
        headers=csrf_headers(client),
    )
    assert patch.status_code == 200, patch.text

    reget = await client.get(f"/api/v1/cms/content-items/{item['id']}")
    assert reget.status_code == 200, reget.text
    reloaded_body = reget.json()["data"]["latest_version"]["body"]
    assert reloaded_body["stem"] == "Reloaded stem"
    assert reloaded_body["correct_option"] == "D"
