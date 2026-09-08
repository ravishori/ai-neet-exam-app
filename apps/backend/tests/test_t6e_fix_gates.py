"""RS-001-A2-B — durable publication-gate behavioural evidence.

These tests exercise the committed ContentWorkflowService.publish path
(commit 05b354d, fix(cms): enforce publication gates) end-to-end. They
MUST NOT mock publication_gates.py, bypass the workflow service, or set
item status manually — the point is to prove that the wired gates
reject the exact scenarios they claim to.

Covers:
  Case A — missing NCERT evidence → publish denied
  Case B — duplicate normalized stem → second publish denied
  Case C — PAGE_VERIFIED without a page number is refused at schema level
  Case E (happy branch) — a fully-gated body reaches PUBLISHED
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.modules.cms.schemas.question_evidence import NcertEvidence
from app.modules.cms.services.publication_gates import build_test_provenance
from conftest import csrf_headers
from helpers_publishable_question import publishable_question_body

pytestmark = pytest.mark.asyncio(loop_scope="session")


def test_ncert_rejects_fabricated_page_claim():
    """Case C — a PAGE_VERIFIED claim without a page_number is refused by
    the NcertEvidence schema itself, so a fabricated verification level
    cannot even reach the workflow gate."""
    with pytest.raises(ValidationError):
        NcertEvidence(
            verification_level="PAGE_VERIFIED",
            source_document="NCERT",
            class_level="11",
            chapter="Ch 2",
            section="2.4",
            page_number=None,
            verification_method="fabricated",
        )


async def test_publish_denies_missing_ncert_and_allows_full(client, db_session, register_user):
    """Case A + Case E — a QUESTION lacking NCERT evidence is denied at
    publish with PUBLICATION_GATES_FAILED / ncert:missing_evidence; an
    incomplete-numerical body is also denied at publish; a body built
    from the shared publishable_question_body helper reaches PUBLISHED."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    from sqlalchemy import select

    from app.modules.academic.models import Concept

    concept_id = str((await db_session.execute(select(Concept.id).limit(1))).scalar_one())

    # A — missing NCERT evidence
    bare = {
        "stem": f"Bare publish probe {uuid.uuid4().hex[:8]}",
        "options": [
            {"label": "A", "text": "1"},
            {"label": "B", "text": "2"},
            {"label": "C", "text": "3"},
            {"label": "D", "text": "4"},
        ],
        "correct_option": "A",
        "explanation": "Needs gates.",
        "difficulty": "easy",
        "provenance": build_test_provenance(),
    }
    create = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Missing NCERT",
            "slug": f"a2b-miss-ncert-{uuid.uuid4().hex[:8]}",
            "language": "en",
            "body": bare,
        },
        headers=csrf_headers(client),
    )
    assert create.status_code == 201, create.text
    item_id = create.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{item_id}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    denied = await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))
    assert denied.status_code == 422
    err = denied.json()["errors"][0]
    assert err["code"] == "PUBLICATION_GATES_FAILED"
    assert "ncert:missing_evidence" in err["message"]

    # Scientific gate — incomplete numerical calculation
    incomplete = publishable_question_body(
        stem=f"Incomplete calc {uuid.uuid4().hex[:8]}",
        calculation_check={"W": 40},
        numerical_evidence={"status": "NUMERICAL_INCOMPLETE", "calculation_check": {"W": 40}},
    )
    create2 = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Incomplete calc",
            "slug": f"a2b-miss-sci-{uuid.uuid4().hex[:8]}",
            "language": "en",
            "body": incomplete,
        },
        headers=csrf_headers(client),
    )
    assert create2.status_code == 201, create2.text
    id2 = create2.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{id2}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{id2}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    denied2 = await client.post(f"/api/v1/cms/content-items/{id2}/publish", headers=csrf_headers(client))
    assert denied2.status_code == 422
    assert denied2.json()["errors"][0]["code"] == "PUBLICATION_GATES_FAILED"

    # E — fully-gated QUESTION reaches PUBLISHED
    ok_body = publishable_question_body(stem=f"Fully gated {uuid.uuid4().hex[:8]}")
    create3 = await client.post(
        "/api/v1/cms/content-items",
        json={
            "content_type": "QUESTION",
            "concept_id": concept_id,
            "title": "Fully gated",
            "slug": f"a2b-ok-{uuid.uuid4().hex[:8]}",
            "language": "en",
            "body": ok_body,
        },
        headers=csrf_headers(client),
    )
    assert create3.status_code == 201, create3.text
    id3 = create3.json()["data"]["id"]
    await client.post(f"/api/v1/cms/content-items/{id3}/submit", headers=csrf_headers(client))
    await client.post(
        f"/api/v1/cms/content-items/{id3}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    allowed = await client.post(f"/api/v1/cms/content-items/{id3}/publish", headers=csrf_headers(client))
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["status"] == "PUBLISHED"


async def test_duplicate_publish_denied(client, db_session, register_user):
    """Case B — two QUESTIONs with the same normalized stem cannot both
    become PUBLISHED; the second publish is rejected with
    PUBLICATION_GATES_FAILED / duplicate:published_stem."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    from sqlalchemy import select

    from app.modules.academic.models import Concept

    concept_id = str((await db_session.execute(select(Concept.id).limit(1))).scalar_one())
    stem = f"Unique duplicate probe stem {uuid.uuid4().hex}"

    async def _pub(slug: str):
        create = await client.post(
            "/api/v1/cms/content-items",
            json={
                "content_type": "QUESTION",
                "concept_id": concept_id,
                "title": slug,
                "slug": slug,
                "language": "en",
                "body": publishable_question_body(stem=stem),
            },
            headers=csrf_headers(client),
        )
        assert create.status_code == 201, create.text
        item_id = create.json()["data"]["id"]
        await client.post(f"/api/v1/cms/content-items/{item_id}/submit", headers=csrf_headers(client))
        await client.post(
            f"/api/v1/cms/content-items/{item_id}/review",
            json={"decision": "approve"},
            headers=csrf_headers(client),
        )
        return await client.post(f"/api/v1/cms/content-items/{item_id}/publish", headers=csrf_headers(client))

    first = await _pub(f"a2b-dup-a-{uuid.uuid4().hex[:8]}")
    assert first.status_code == 200, first.text
    second = await _pub(f"a2b-dup-b-{uuid.uuid4().hex[:8]}")
    assert second.status_code == 422
    err = second.json()["errors"][0]
    assert err["code"] == "PUBLICATION_GATES_FAILED"
    assert "duplicate:published_stem" in err["message"]
