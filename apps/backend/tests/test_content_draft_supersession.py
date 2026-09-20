"""Tests for ContentItem DRAFT supersession + metadata updates."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from helpers_publishable_question import publishable_question_body
from app.modules.cms.acquisition.gemini_jsonl_draft_importer import (
    GeminiJsonlDraftImporter,
    import_slug,
    load_jsonl,
)
from app.modules.cms.acquisition.gemini_jsonl_supersede import load_replacement_lineage
from app.modules.cms.models import ContentItem
from app.modules.cms.models.content_item import STUDENT_VISIBLE_STATUSES
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.content_workflow_service import ContentWorkflowError, ContentWorkflowService

pytestmark = pytest.mark.asyncio(loop_scope="session")

REPO_ROOT = Path(__file__).resolve().parents[3]
BIO_REPAIRED = (
    REPO_ROOT
    / "docs"
    / "acquisition"
    / "batches"
    / "20260911-BIO11-CH01-B001"
    / "questions_repaired.jsonl"
)
BIO_LINEAGE = BIO_REPAIRED.parent / "replacement_lineage.json"


def _minimal_body(stem: str | None = None) -> dict:
    return publishable_question_body(stem=stem or f"Supersede test stem {uuid.uuid4().hex}?")


async def _create_draft(service: ContentWorkflowService, author_id: uuid.UUID, *, slug: str | None = None) -> ContentItem:
    eid = slug or f"gemini-UNIT-{uuid.uuid4().hex[:10]}"
    return await service.create_item(
        content_type="QUESTION",
        concept_id=None,
        title=f"Title {eid}",
        slug=eid[:320],
        tags=["unit-test", "supersede"],
        language="en",
        body=_minimal_body(),
        author_id=author_id,
    )


async def test_supersede_draft_success(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)
    old = await _create_draft(service, author_id)
    replacement = await _create_draft(service, author_id)

    old2, rep2 = await service.supersede_draft(old.id, replacement_item_id=replacement.id, author_id=author_id)
    assert old2.status == "SUPERSEDED"
    assert rep2.status == "DRAFT"
    assert rep2.replaces_id == old.id
    assert old2.status not in STUDENT_VISIBLE_STATUSES
    assert rep2.status not in STUDENT_VISIBLE_STATUSES

    found = await service.get_replacement_for(old.id)
    assert found is not None and found.id == replacement.id


async def test_supersede_rejects_published(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)
    old = await _create_draft(service, author_id)
    replacement = await _create_draft(service, author_id)
    old.status = "PUBLISHED"
    await db_session.flush()

    with pytest.raises(ContentWorkflowError, match="Cannot supersede"):
        await service.supersede_draft(old.id, replacement_item_id=replacement.id, author_id=author_id)


async def test_supersede_rejects_self_and_cycle(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)
    a = await _create_draft(service, author_id)
    b = await _create_draft(service, author_id)

    with pytest.raises(ContentWorkflowError, match="itself"):
        await service.supersede_draft(a.id, replacement_item_id=a.id, author_id=author_id)

    await service.supersede_draft(a.id, replacement_item_id=b.id, author_id=author_id)
    # a is SUPERSEDED; trying to make a replace b would require a DRAFT — recreate chain:
    c = await _create_draft(service, author_id)
    # b.replaces_id = a; if c supersedes something that eventually points to c
    # Set b (DRAFT) to replace c first? b already replaces a.
    # Cycle: make c replace b, then try to supersede c with b — b already has replaces_id.
    with pytest.raises(ContentWorkflowError):
        await service.supersede_draft(c.id, replacement_item_id=b.id, author_id=author_id)


async def test_supersede_idempotent(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)
    old = await _create_draft(service, author_id)
    replacement = await _create_draft(service, author_id)
    await service.supersede_draft(old.id, replacement_item_id=replacement.id, author_id=author_id)
    old2, rep2 = await service.supersede_draft(old.id, replacement_item_id=replacement.id, author_id=author_id)
    assert old2.status == "SUPERSEDED"
    assert rep2.replaces_id == old.id


async def test_update_draft_metadata_tags_and_title(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)
    item = await _create_draft(service, author_id)
    updated = await service.update_draft_metadata(
        item.id,
        author_id=author_id,
        title="Retitled draft",
        tags=["unit-test", "question_type:factual", "batch:x"],
    )
    assert updated.title == "Retitled draft"
    assert "question_type:factual" in updated.tags

    item.status = "PUBLISHED"
    await db_session.commit()
    with pytest.raises(ContentWorkflowError, match="metadata"):
        await service.update_draft_metadata(item.id, author_id=author_id, tags=["nope"])


async def test_update_draft_accepts_tags(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)
    item = await _create_draft(service, author_id)
    before_vid = item.latest_version_id
    body = _minimal_body("Updated body stem for metadata?")
    updated = await service.update_draft(
        item.id,
        body=body,
        change_summary="tag+body",
        author_id=author_id,
        title="New title",
        tags=["question_type:application"],
    )
    assert updated.title == "New title"
    assert updated.tags == ["question_type:application"]
    assert updated.latest_version_id != before_vid


def test_load_biology_replacement_lineage():
    assert BIO_LINEAGE.is_file()
    lineage = load_replacement_lineage(BIO_LINEAGE)
    assert len(lineage.mapping) == 5
    assert lineage.mapping["GEMINI-20260911-BIO11-CH01-B001-000095"].endswith("R000095")


@pytest.mark.skipif(not BIO_REPAIRED.is_file(), reason="repaired biology JSONL missing")
def test_biology_repaired_jsonl_and_lineage_shape():
    """Offline contract: 100 repaired records, 5 explicit replacements, no originals in JSONL."""
    records, malformed = load_jsonl(BIO_REPAIRED)
    assert not malformed
    assert len(records) == 100
    lineage = load_replacement_lineage(BIO_LINEAGE)
    ids = {str(r.get("external_question_id") or "") for r in records}
    for old, new in lineage.mapping.items():
        assert old not in ids
        assert new in ids
    assert len(lineage.mapping) == 5
    assert len(ids) - len(lineage.mapping) == 95


async def test_supersede_mode_dry_run_plan_counts(db_session, register_user, client, tmp_path: Path):
    """Synthetic dry-run: 2 in-place + 1 replacement create/supersede; zero writes."""
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)

    old_eid = f"GEMINI-SYN-{uuid.uuid4().hex[:6]}-000001"
    new_eid = f"GEMINI-SYN-{uuid.uuid4().hex[:6]}-R000001"
    s1 = f"GEMINI-SYN-{uuid.uuid4().hex[:6]}-000002"
    s2 = f"GEMINI-SYN-{uuid.uuid4().hex[:6]}-000003"
    await _create_draft(service, author_id, slug=import_slug(old_eid))
    await _create_draft(service, author_id, slug=import_slug(s1))
    await _create_draft(service, author_id, slug=import_slug(s2))

    def _rec(eid: str, stem: str) -> dict:
        return {
            "external_question_id": eid,
            "subject": "Biology",
            "class_level": "11",
            "chapter": "The Living World",
            "topic": "Test",
            "concept": "NoExactMatchXYZ",
            "question_type": "factual",
            "difficulty": "easy",
            "stem": stem,
            "options": {"A": "a1", "B": "b1", "C": "c1", "D": "d1"},
            "correct_option": "A",
            "explanation": "a1 is correct for supersede dry-run plan counts.",
            "source": {
                "source_file": "ncert-books-class-11-biology-chapter-1.pdf",
                "chapter": "The Living World",
                "section": "Test",
                "page_number": None,
                "source_evidence": "Supersede dry-run plan evidence sentence long enough.",
            },
            "provenance": {
                "provider": "gemini",
                "generation_source": "unit_test",
                "generation_batch_id": "UNIT-SYN-SUPERSEDE",
                "model": "unit",
            },
            "visual": {"visual_required": False, "visual_type": None, "visual_description": None},
            "numerical": {"is_numerical": False, "calculation_check": None},
            "tags": ["unit-test"],
        }

    path = tmp_path / "syn.jsonl"
    lin = tmp_path / "replacement_lineage.json"
    path.write_text(
        "\n".join(
            [
                json.dumps(_rec(s1, f"Stable one {uuid.uuid4().hex}?")),
                json.dumps(_rec(s2, f"Stable two {uuid.uuid4().hex}?")),
                json.dumps(_rec(new_eid, f"Replacement {uuid.uuid4().hex}?")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    lin.write_text(
        json.dumps(
            {
                "batch_id": "UNIT-SYN-SUPERSEDE",
                "replacements": [
                    {
                        "original_external_question_id": old_eid,
                        "replacement_external_question_id": new_eid,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    before = (
        await db_session.execute(select(ContentItem.id).where(ContentItem.deleted_at.is_(None)))
    ).scalars().all()
    importer = GeminiJsonlDraftImporter(db_session)
    report = await importer.run(
        input_path=path,
        author_id=author_id,
        dry_run=True,
        supersede_existing=True,
        lineage_path=lin,
    )
    assert report.rejected == 0
    assert report.db_writes == 0
    meta = (report.taxonomy_summary or {}).get("supersede") or {}
    assert meta.get("would_update") == 2
    assert meta.get("would_create_replacement") == 1
    assert meta.get("would_supersede") == 1
    after = (
        await db_session.execute(select(ContentItem.id).where(ContentItem.deleted_at.is_(None)))
    ).scalars().all()
    assert set(after) == set(before)


async def test_ordinary_commit_still_create_only(db_session, register_user, client, tmp_path: Path):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)
    existing = await _create_draft(service, author_id, slug=f"gemini-ORD-{uuid.uuid4().hex[:8]}")
    # Build a one-row jsonl that would collide on slug if create attempted
    # Use a fresh id so ordinary import creates once, second is already_exists
    eid = f"GEMINI-ORD-{uuid.uuid4().hex[:8]}-000001"
    rec = {
        "external_question_id": eid,
        "subject": "Biology",
        "class_level": "11",
        "chapter": "The Living World",
        "topic": "Test",
        "concept": "NoExactMatchXYZ",
        "question_type": "factual",
        "difficulty": "easy",
        "stem": f"Ordinary import stem {uuid.uuid4().hex}?",
        "options": {"A": "a1", "B": "b1", "C": "c1", "D": "d1"},
        "correct_option": "A",
        "explanation": "a1 is correct for the ordinary importer regression.",
        "source": {
            "source_file": "ncert-books-class-11-biology-chapter-1.pdf",
            "chapter": "The Living World",
            "section": "Test",
            "page_number": None,
            "source_evidence": "Ordinary importer regression evidence sentence long enough.",
        },
        "provenance": {
            "provider": "gemini",
            "generation_source": "unit_test",
            "generation_batch_id": "UNIT-ORD-COMMIT",
            "model": "unit",
        },
        "visual": {"visual_required": False, "visual_type": None, "visual_description": None},
        "numerical": {"is_numerical": False, "calculation_check": None},
        "tags": ["unit-test"],
    }
    path = tmp_path / "ord.jsonl"
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    importer = GeminiJsonlDraftImporter(db_session)
    r1 = await importer.run(input_path=path, author_id=author_id, dry_run=False, atomic=True)
    assert r1.created == 1
    r2 = await importer.run(input_path=path, author_id=author_id, dry_run=False, atomic=True)
    assert r2.created == 0
    assert r2.already_exists == 1
    # Ensure we did not invent supersede side effects on unrelated existing
    refreshed = await CmsRepository(db_session).get_item(existing.id)
    assert refreshed.status == "DRAFT"
    assert refreshed.replaces_id is None


async def test_supersede_atomic_rollback(db_session, register_user, client, tmp_path: Path, monkeypatch):
    """If supersede_draft fails mid-batch, no in-place updates or replacements remain."""
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)

    old_eid = f"GEMINI-RB-{uuid.uuid4().hex[:6]}-000001"
    new_eid = f"GEMINI-RB-{uuid.uuid4().hex[:6]}-R000001"
    stable_eid = f"GEMINI-RB-{uuid.uuid4().hex[:6]}-000002"
    old = await _create_draft(service, author_id, slug=import_slug(old_eid))
    stable = await _create_draft(service, author_id, slug=import_slug(stable_eid))
    stable_title_before = stable.title
    old_status_before = old.status
    old_id = old.id
    stable_id = stable.id

    def _rec(eid: str, stem: str) -> dict:
        return {
            "external_question_id": eid,
            "subject": "Biology",
            "class_level": "11",
            "chapter": "The Living World",
            "topic": "Test",
            "concept": "NoExactMatchXYZ",
            "question_type": "factual",
            "difficulty": "easy",
            "stem": stem,
            "options": {"A": "a1", "B": "b1", "C": "c1", "D": "d1"},
            "correct_option": "A",
            "explanation": "a1 is correct for atomic rollback test case.",
            "source": {
                "source_file": "ncert-books-class-11-biology-chapter-1.pdf",
                "chapter": "The Living World",
                "section": "Test",
                "page_number": None,
                "source_evidence": "Atomic rollback regression evidence sentence long enough.",
            },
            "provenance": {
                "provider": "gemini",
                "generation_source": "unit_test",
                "generation_batch_id": "UNIT-RB-SUPERSEDE",
                "model": "unit",
            },
            "visual": {"visual_required": False, "visual_type": None, "visual_description": None},
            "numerical": {"is_numerical": False, "calculation_check": None},
            "tags": ["unit-test"],
        }

    lineage = {
        "batch_id": "UNIT-RB-SUPERSEDE",
        "replacements": [
            {
                "original_external_question_id": old_eid,
                "replacement_external_question_id": new_eid,
            }
        ],
    }
    path = tmp_path / "rb.jsonl"
    lin_path = tmp_path / "replacement_lineage.json"
    path.write_text(
        json.dumps(_rec(stable_eid, f"Stable repaired stem {uuid.uuid4().hex}?"))
        + "\n"
        + json.dumps(_rec(new_eid, f"Replacement stem {uuid.uuid4().hex}?"))
        + "\n",
        encoding="utf-8",
    )
    lin_path.write_text(json.dumps(lineage), encoding="utf-8")

    importer = GeminiJsonlDraftImporter(db_session)

    async def boom(*args, **kwargs):
        raise RuntimeError("forced_supersede_failure")

    monkeypatch.setattr(importer.workflow, "supersede_draft", boom)

    with pytest.raises(RuntimeError, match="forced_supersede_failure"):
        await importer.run(
            input_path=path,
            author_id=author_id,
            dry_run=False,
            supersede_existing=True,
            lineage_path=lin_path,
        )

    # Do not session.rollback() — fixture owns the outer transaction (see conftest).
    refreshed_old = (
        await db_session.execute(select(ContentItem.status).where(ContentItem.id == old_id))
    ).scalar_one()
    refreshed_stable = (
        await db_session.execute(
            select(ContentItem.title, ContentItem.status).where(ContentItem.id == stable_id)
        )
    ).one()
    assert refreshed_old == old_status_before
    assert refreshed_stable.title == stable_title_before
    assert refreshed_stable.status == "DRAFT"
    assert (
        await db_session.execute(
            select(ContentItem.id).where(
                ContentItem.slug == import_slug(new_eid),
                ContentItem.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none() is None


async def test_student_browse_excludes_superseded(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    service = ContentWorkflowService(db_session)
    old = await _create_draft(service, author_id)
    replacement = await _create_draft(service, author_id)
    await service.supersede_draft(old.id, replacement_item_id=replacement.id, author_id=author_id)

    repo = CmsRepository(db_session)
    published = await repo.list_published_questions(limit=100, offset=0) if hasattr(repo, "list_published_questions") else None
    # Canonical student path uses PUBLISHED-only listing
    items = await repo.list_items(content_type="QUESTION", status="PUBLISHED")
    ids = {i.id for i in items}
    assert old.id not in ids
    assert replacement.id not in ids
    drafts = await repo.list_items(content_type="QUESTION", status="DRAFT")
    draft_ids = {i.id for i in drafts}
    assert replacement.id in draft_ids
    assert old.id not in draft_ids  # SUPERSEDED, not DRAFT
