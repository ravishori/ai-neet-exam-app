"""Focused tests for Gemini JSONL → TALOS DRAFT importer."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.cms.acquisition.gemini_jsonl_draft_importer import (
    ACQUISITION_TO_CANONICAL_QUESTION_TYPE,
    GeminiJsonlDraftImporter,
    TaxonomyResolution,
    build_import_tags,
    build_question_body,
    detect_answer_explanation_contradiction,
    import_slug,
    load_jsonl,
    map_acquisition_question_type,
    options_dict_to_list,
    validate_gemini_record,
)
from app.modules.cms.models import ContentItem

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _valid_record(**overrides):
    base = {
        "external_question_id": f"GEMINI-TEST-{uuid.uuid4().hex[:8]}-000001",
        "subject": "Physics",
        "class_level": "11",
        "chapter": "Motion in a Straight Line",
        "topic": "Acceleration",
        "concept": "Nonexistent Exact Concept Name XYZ",
        "question_type": "conceptual",
        "difficulty": "easy",
        "stem": f"Unique gemini import stem {uuid.uuid4().hex}?",
        "options": {
            "A": "Alpha option text",
            "B": "Beta option text",
            "C": "Gamma option text",
            "D": "Delta option text",
        },
        "correct_option": "C",
        "explanation": "The correct choice is C because gamma is right per NCERT discussion.",
        "source": {
            "source_file": "ncert-books-class-11-physics-chapter-2.pdf",
            "chapter": "Motion in a Straight Line",
            "section": "2.3 Acceleration",
            "page_number": None,
            "source_evidence": "Sign of acceleration depends on choice of positive axis.",
        },
        "provenance": {
            "provider": "gemini",
            "generation_source": "attached_ncert_pdf",
            "generation_batch_id": "20260911-TEST-BATCH",
            "model": "gemini-3.6-flash",
        },
        "visual": {"visual_required": False, "visual_type": None, "visual_description": None},
        "numerical": {"is_numerical": False, "calculation_check": None},
        "tags": ["unit-test"],
    }
    base.update(overrides)
    return base


def test_options_dict_to_canonical_list():
    opts = options_dict_to_list({"A": "a", "B": "b", "C": "c", "D": "d"})
    assert opts == [
        {"label": "A", "text": "a"},
        {"label": "B", "text": "b"},
        {"label": "C", "text": "c"},
        {"label": "D", "text": "d"},
    ]


def test_invalid_option_count():
    with pytest.raises(ValueError):
        options_dict_to_list({"A": "a", "B": "b", "C": "c"})


def test_validate_valid_record():
    normalized, errors, warnings = validate_gemini_record(_valid_record())
    assert errors == []
    assert normalized is not None
    assert normalized["correct_option"] == "C"
    body = build_question_body(normalized)
    assert len(body["options"]) == 4
    assert body["ncert_evidence"]["verification_level"] == "NOT_VERIFIED"
    assert body["provenance"]["batch_id"] == "20260911-TEST-BATCH"


def test_invalid_correct_option():
    _, errors, _ = validate_gemini_record(_valid_record(correct_option="E"))
    assert "invalid_correct_option" in errors


def test_duplicate_option_text():
    _, errors, _ = validate_gemini_record(
        _valid_record(options={"A": "same", "B": "same", "C": "c", "D": "d"})
    )
    assert "duplicate_option_text" in errors


def test_missing_explanation():
    _, errors, _ = validate_gemini_record(_valid_record(explanation="  "))
    assert "missing_explanation" in errors


def test_missing_provenance():
    rec = _valid_record()
    del rec["provenance"]
    _, errors, _ = validate_gemini_record(rec)
    assert "missing_provenance" in errors


def test_missing_source():
    rec = _valid_record()
    del rec["source"]
    _, errors, _ = validate_gemini_record(rec)
    assert "missing_source" in errors


def test_answer_explanation_contradiction_ratio():
    reason = detect_answer_explanation_contradiction(
        correct_option="A",
        options={"A": "3 : 5", "B": "5 : 9", "C": "9 : 25", "D": "1 : 3"},
        explanation="Thus, the ratio of the distance in the 3rd interval to the 5th interval is 5 : 9.",
    )
    assert reason is not None
    assert "contradiction" in reason

    _, errors, _ = validate_gemini_record(
        _valid_record(
            options={"A": "3 : 5", "B": "5 : 9", "C": "9 : 25", "D": "1 : 3"},
            correct_option="A",
            explanation="Thus, the ratio of the distance in the 3rd interval to the 5th interval is 5 : 9.",
        )
    )
    assert any("contradiction" in e for e in errors)


def test_deterministic_slug():
    assert import_slug("GEMINI-BIO11-CH01-000001") == "gemini-GEMINI-BIO11-CH01-000001"


def test_malformed_jsonl(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text("{ok: false}\n", encoding="utf-8")
    records, malformed = load_jsonl(path)
    assert records == []
    assert len(malformed) == 1


def test_numerical_warning_handling():
    _, errors, warnings = validate_gemini_record(
        _valid_record(
            question_type="numerical",
            numerical={"is_numerical": True, "calculation_check": "v=10; avg=15"},
        )
    )
    assert errors == []
    assert "numerical_evidence_unstructured" in warnings


@pytest.mark.parametrize(
    "acq_type",
    [
        "conceptual",
        "numerical",
        "factual",
        "application",
        "comparison",
        "statement_based",
        "assertion_reasoning",
        "match_relationship",
    ],
)
def test_supported_acquisition_question_types(acq_type: str):
    normalized, errors, _ = validate_gemini_record(
        _valid_record(
            question_type=acq_type,
            numerical={
                "is_numerical": acq_type == "numerical",
                "calculation_check": {"formula": "x"} if acq_type == "numerical" else None,
            },
        )
    )
    assert errors == []
    assert normalized is not None
    assert normalized["acquisition_question_type"] == acq_type
    assert normalized["question_type"] == ACQUISITION_TO_CANONICAL_QUESTION_TYPE[acq_type]
    assert map_acquisition_question_type(acq_type) == acq_type


def test_deterministic_question_type_mapping_table():
    """Documented identity map — richer types are NOT collapsed to conceptual."""
    expected = {
        "conceptual": "conceptual",
        "numerical": "numerical",
        "factual": "factual",
        "application": "application",
        "comparison": "comparison",
        "statement_based": "statement_based",
        "assertion_reasoning": "assertion_reasoning",
        "match_relationship": "match_relationship",
    }
    assert ACQUISITION_TO_CANONICAL_QUESTION_TYPE == expected
    for src, dst in expected.items():
        assert map_acquisition_question_type(src) == dst
        assert dst != "conceptual" or src == "conceptual"


def test_unsupported_question_type_rejected():
    _, errors, _ = validate_gemini_record(_valid_record(question_type="essay"))
    assert "invalid_question_type" in errors
    with pytest.raises(ValueError, match="unsupported_acquisition_question_type"):
        map_acquisition_question_type("essay")


def test_question_type_tag_on_import_tags():
    normalized, errors, _ = validate_gemini_record(_valid_record(question_type="factual"))
    assert errors == []
    tags = build_import_tags(normalized, TaxonomyResolution())
    assert "question_type:factual" in tags
    assert "acquisition_question_type:factual" not in tags  # identity → no duplicate provenance tag


def test_mixed_type_batch_validation():
    types = ["factual", "application", "comparison", "conceptual", "statement_based"]
    for t in types:
        normalized, errors, _ = validate_gemini_record(_valid_record(question_type=t))
        assert errors == [], f"{t}: {errors}"
        assert normalized["question_type"] == t


BIO_BATCH_JSONL = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "acquisition"
    / "batches"
    / "20260911-BIO11-CH01-B001"
    / "questions.jsonl"
)


@pytest.mark.skipif(not BIO_BATCH_JSONL.is_file(), reason="Biology batch JSONL not present")
def test_biology_batch_validate_all_100_types():
    records, malformed = load_jsonl(BIO_BATCH_JSONL)
    assert malformed == []
    assert len(records) == 100
    rejected = 0
    type_counts: dict[str, int] = {}
    for raw in records:
        normalized, errors, _ = validate_gemini_record(raw)
        if errors:
            rejected += 1
            continue
        assert normalized is not None
        qt = normalized["question_type"]
        type_counts[qt] = type_counts.get(qt, 0) + 1
        assert "question_type:" + qt in build_import_tags(normalized, TaxonomyResolution())
    assert rejected == 0
    assert sum(type_counts.values()) == 100
    # Mode-B mix from acquisition report
    assert type_counts.get("factual", 0) == 37
    assert type_counts.get("application", 0) == 27
    assert type_counts.get("comparison", 0) == 19
    assert type_counts.get("conceptual", 0) == 13
    assert type_counts.get("statement_based", 0) == 4


@pytest.mark.skipif(not BIO_BATCH_JSONL.is_file(), reason="Biology batch JSONL not present")
async def test_biology_batch_dry_run_100(db_session, register_user, client):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    importer = GeminiJsonlDraftImporter(db_session)
    report = await importer.run(
        input_path=BIO_BATCH_JSONL,
        author_id=author_id,
        dry_run=True,
        batch_id="20260911-BIO11-CH01-B001",
    )
    assert report.input_count == 100
    assert report.would_create == 100
    assert report.rejected == 0
    assert report.created == 0
    assert report.db_writes == 0


def test_batch_id_preservation_in_body():
    normalized, errors, _ = validate_gemini_record(_valid_record())
    assert errors == []
    body = build_question_body(normalized)
    assert body["provenance"]["batch_id"] == "20260911-TEST-BATCH"
    assert body["ncert_evidence"]["verification_level"] == "NOT_VERIFIED"


async def test_dry_run_zero_writes_and_concept_null(db_session, register_user, client, tmp_path: Path):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    rec = _valid_record()
    path = tmp_path / "q.jsonl"
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")

    before = (
        await db_session.execute(select(ContentItem.id).where(ContentItem.slug == import_slug(rec["external_question_id"])))
    ).scalars().all()
    assert before == []

    importer = GeminiJsonlDraftImporter(db_session)
    report = await importer.run(input_path=path, author_id=author_id, dry_run=True)
    assert report.would_create == 1
    assert report.created == 0
    assert report.db_writes == 0
    assert report.outcomes[0].concept_id is None

    after = (
        await db_session.execute(select(ContentItem.id).where(ContentItem.slug == import_slug(rec["external_question_id"])))
    ).scalars().all()
    assert after == []


def IMPORT_TAG_IN_ITEM(item: ContentItem) -> bool:
    return "gemini-jsonl-import" in (item.tags or []) and "concept:unresolved" in (item.tags or [])


async def test_commit_creates_draft_only_idempotent_never_publishes(db_session, register_user, client, tmp_path: Path):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    rec = _valid_record()
    path = tmp_path / "q.jsonl"
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")

    importer = GeminiJsonlDraftImporter(db_session)
    report1 = await importer.run(input_path=path, author_id=author_id, dry_run=False)
    assert report1.created == 1
    assert report1.rejected == 0
    item_id = report1.outcomes[0].item_id
    assert item_id

    item = (
        await db_session.execute(
            select(ContentItem).options(selectinload(ContentItem.versions)).where(ContentItem.id == uuid.UUID(item_id))
        )
    ).scalar_one()
    assert item.status == "DRAFT"
    assert item.concept_id is None
    assert IMPORT_TAG_IN_ITEM(item)
    latest = next(v for v in item.versions if v.id == item.latest_version_id)
    assert latest.workflow_state == "DRAFT"
    assert (latest.body or {}).get("ncert_evidence", {}).get("verification_level") == "NOT_VERIFIED"
    assert (latest.body or {}).get("provenance", {}).get("batch_id") == "20260911-TEST-BATCH"

    report2 = await importer.run(input_path=path, author_id=author_id, dry_run=False)
    assert report2.created == 0
    assert report2.already_exists == 1

    item2 = (await db_session.execute(select(ContentItem).where(ContentItem.id == uuid.UUID(item_id)))).scalar_one()
    assert item2.status == "DRAFT"
def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


async def test_atomic_batch_success_commits_all(db_session, register_user, client, tmp_path: Path):
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    prefix = uuid.uuid4().hex[:10]
    records = [
        _valid_record(external_question_id=f"GEMINI-ATOMIC-OK-{prefix}-{i:06d}")
        for i in range(1, 4)
    ]
    path = tmp_path / "atomic_ok.jsonl"
    _write_jsonl(path, records)

    importer = GeminiJsonlDraftImporter(db_session)
    report = await importer.run(input_path=path, author_id=author_id, dry_run=False, atomic=True)
    assert report.created == 3
    assert report.failed == 0
    assert report.db_writes == 3

    for rec in records:
        slug = import_slug(rec["external_question_id"])
        item = (await db_session.execute(select(ContentItem).where(ContentItem.slug == slug))).scalar_one()
        assert item.status == "DRAFT"


async def test_atomic_batch_rollback_on_mid_batch_failure(db_session, register_user, client, tmp_path: Path, monkeypatch):
    """Q1+Q2 valid, Q3 DB failure, Q4 valid ? ZERO durable creates from the batch."""
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    prefix = uuid.uuid4().hex[:10]
    records = [
        _valid_record(external_question_id=f"GEMINI-ATOMIC-RB-{prefix}-{i:06d}")
        for i in range(1, 5)
    ]
    path = tmp_path / "atomic_rb.jsonl"
    _write_jsonl(path, records)
    slugs = [import_slug(r["external_question_id"]) for r in records]

    importer = GeminiJsonlDraftImporter(db_session)
    real_create = importer.workflow.create_item
    calls = {"n": 0}

    async def flaky_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("simulated_db_failure_on_third_create")
        return await real_create(**kwargs)

    monkeypatch.setattr(importer.workflow, "create_item", flaky_create)

    with pytest.raises(RuntimeError, match="simulated_db_failure"):
        await importer.run(input_path=path, author_id=author_id, dry_run=False, atomic=True)

    for slug in slugs:
        found = (
            await db_session.execute(
                select(ContentItem.id).where(ContentItem.slug == slug, ContentItem.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        assert found is None, f"partial commit leaked for {slug}"


async def test_atomic_rejects_source_defect_and_imports_valid_only(db_session, register_user, client, tmp_path: Path):
    """2 valid + 1 answer contradiction ? 2 DRAFT, rejected absent."""
    user = await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    author_id = uuid.UUID(user["id"])
    prefix = uuid.uuid4().hex[:10]
    good1 = _valid_record(external_question_id=f"GEMINI-ATOMIC-MIX-{prefix}-000001")
    bad = _valid_record(
        external_question_id=f"GEMINI-ATOMIC-MIX-{prefix}-000002",
        options={"A": "3 : 5", "B": "5 : 9", "C": "9 : 25", "D": "1 : 3"},
        correct_option="A",
        explanation="Thus, the ratio of the distance in the 3rd interval to the 5th interval is 5 : 9.",
    )
    good2 = _valid_record(external_question_id=f"GEMINI-ATOMIC-MIX-{prefix}-000003")
    path = tmp_path / "atomic_mix.jsonl"
    _write_jsonl(path, [good1, bad, good2])

    importer = GeminiJsonlDraftImporter(db_session)
    report = await importer.run(input_path=path, author_id=author_id, dry_run=False, atomic=True)
    assert report.created == 2
    assert report.rejected == 1
    assert report.failed == 0
    assert any(o.external_question_id.endswith("000002") and o.status == "rejected" for o in report.outcomes)

    assert (
        await db_session.execute(
            select(ContentItem.id).where(ContentItem.slug == import_slug(bad["external_question_id"]))
        )
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(ContentItem.id).where(ContentItem.slug == import_slug(good1["external_question_id"]))
        )
    ).scalar_one() is not None
