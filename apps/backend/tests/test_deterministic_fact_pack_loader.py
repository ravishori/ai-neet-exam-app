"""Focused tests for the read-only deterministic NCERT fact-pack loader."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from app.modules.cms.schemas.deterministic_fact_pack import compute_stable_fact_id
from app.modules.cms.services.deterministic_fact_pack_loader import (
    FactPackLoadError,
    load_deterministic_fact_pack,
)


def _fact(root: Path, *, statement: str = "Sucrose is a non-reducing sugar.") -> dict:
    source = root / "book.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    fact = {
        "schema_version": "ncert_fact_pack_v1",
        "fact_id": "ncert-fact-v1-" + ("0" * 64),
        "subject": "CHEMISTRY",
        "class_level": "12",
        "chapter_id": "933a0d17-537f-4995-b0ae-6ce23a32a449",
        "chapter": "Biomolecules",
        "topic_id": "8927ce2d-26d4-4e3a-aa11-3a3f27279a5a",
        "topic": "Carbohydrates",
        "concept_id": "31b11e9b-e613-4390-a8e8-8edc9818314a",
        "concept_name": "Classification of Carbohydrates",
        "source_pdf": str(source),
        "source_relative_path": "book.pdf",
        "ncert_reference": {"reference_level": "SOURCE_TEXT_ONLY"},
        "evidence_text": f"{statement} Glucose and fructose are alternative carbohydrate terms.",
        "fact_type": "DIRECT_FACT",
        "canonical_fact": statement,
        "allowed_transformations": ["DIRECT_RECALL", "OPTION_PERMUTATION"],
        "allowed_distractors": [
            {
                "value": "Glucose",
                "source": "SAME_EVIDENCE",
                "evidence_text": "Glucose and fructose are alternative carbohydrate terms.",
            }
        ],
        "syllabus_binding": {
            "subject": "CHEMISTRY",
            "unit_number": 19,
            "unit_name": "BIOMOLECULES",
            "topic_id": "CHEMISTRY:U19:T02",
            "syllabus_source": str(Path(__file__).resolve().parents[3] / "NEETSyllabus.txt"),
        },
        "review_status": "REVIEWED",
        "provenance": {
            "origin": "canonical_ncert",
            "extraction_method": "manual_extraction",
            "extracted_by": "test-fixture",
        },
        "review_record": {
            "reviewed_by": "test-reviewer",
            "reviewed_at": "2026-09-14T00:00:00Z",
            "review_method": "exact-source-text-check",
        },
        "scope_review": {
            "outcome": "SUPPORTED",
            "reviewed_by": "test-reviewer",
            "reviewed_at": "2026-09-14T00:00:00Z",
            "review_method": "syllabus-and-taxonomy-check",
            "syllabus_rationale": "Fact is within carbohydrate classification.",
            "taxonomy_rationale": "Fact matches the selected concept.",
        },
    }
    fact["fact_id"] = compute_stable_fact_id(fact)
    return fact


def _write_pack(path: Path, facts: list[dict]) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "ncert_fact_pack_v1",
                "pack_id": "test-pack",
                "facts": facts,
            }
        ),
        encoding="utf-8",
    )
    return path


def _load(path: Path, root: Path):
    facts = json.loads(path.read_text(encoding="utf-8"))["facts"]
    source_text = "\n".join(fact.get("evidence_text") or "" for fact in facts)
    with patch(
        "app.modules.cms.services.deterministic_fact_pack_loader.extract_ncert_source_text",
        return_value=source_text,
    ):
        return load_deterministic_fact_pack(path, source_root=root)


def _restabilize(fact: dict) -> dict:
    fact["fact_id"] = "ncert-fact-v1-" + ("0" * 64)
    fact["fact_id"] = compute_stable_fact_id(fact)
    return fact


def test_valid_reviewed_fact_loads(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    loaded = _load(_write_pack(tmp_path / "pack.json", [_fact(root)]), root)
    assert len(loaded.facts) == 1
    assert loaded.read_only is True
    assert loaded.provider_api_calls == 0
    assert loaded.production_db_mutations == 0


def test_invalid_schema_fails_closed(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    del fact["fact_id"]
    with pytest.raises(FactPackLoadError) as exc:
        _load(_write_pack(tmp_path / "pack.json", [fact]), root)
    assert exc.value.code == "FACT_PACK_SCHEMA_INVALID"


def test_missing_evidence_fails_closed(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    fact["evidence_text"] = ""
    with pytest.raises(FactPackLoadError) as exc:
        _load(_write_pack(tmp_path / "pack.json", [fact]), root)
    assert exc.value.code == "FACT_PACK_SCHEMA_INVALID"


def test_invalid_ncert_source_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    outside = tmp_path / "StudyMaterial" / "legacy.pdf"
    outside.parent.mkdir()
    outside.write_bytes(b"%PDF-1.4\n")
    fact = _fact(root)
    fact["source_pdf"] = str(outside)
    fact = _restabilize(fact)
    with pytest.raises(FactPackLoadError) as exc:
        _load(_write_pack(tmp_path / "pack.json", [fact]), root)
    assert exc.value.code == "NCERT_SOURCE_INVALID"


def test_outside_syllabus_fact_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    fact["syllabus_binding"]["topic_id"] = "CHEMISTRY:U19:T99"
    fact = _restabilize(fact)
    with pytest.raises(FactPackLoadError) as exc:
        _load(_write_pack(tmp_path / "pack.json", [fact]), root)
    assert exc.value.code == "SYLLABUS_OUT_OF_SCOPE"


def test_ambiguous_or_missing_syllabus_binding_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    fact["syllabus_binding"]["topic_id"] = None
    fact["syllabus_binding"]["topic"] = None
    fact = _restabilize(fact)
    with pytest.raises(FactPackLoadError) as exc:
        _load(_write_pack(tmp_path / "pack.json", [fact]), root)
    assert exc.value.code == "SYLLABUS_MAPPING_REVIEW_REQUIRED"


def test_duplicate_fact_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    with pytest.raises(FactPackLoadError) as exc:
        _load(_write_pack(tmp_path / "pack.json", [fact, deepcopy(fact)]), root)
    assert exc.value.code == "DUPLICATE_FACT"


def test_order_is_stable_and_sorted_by_fact_id(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    first = _fact(root, statement="Sucrose is a non-reducing sugar.")
    second = _fact(root, statement="Maltose is a reducing sugar.")
    path = _write_pack(tmp_path / "pack.json", [second, first])
    one = _load(path, root)
    two = _load(path, root)
    ids = [fact.fact_id for fact in one.facts]
    assert ids == sorted(ids)
    assert ids == [fact.fact_id for fact in two.facts]


def test_fact_id_is_stable_and_tampering_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    assert compute_stable_fact_id(fact) == compute_stable_fact_id(deepcopy(fact))
    fact["fact_id"] = "ncert-fact-v1-" + ("f" * 64)
    with pytest.raises(FactPackLoadError) as exc:
        _load(_write_pack(tmp_path / "pack.json", [fact]), root)
    assert exc.value.code == "UNSTABLE_FACT_ID"


def test_malformed_fact_pack_is_rejected(tmp_path):
    path = tmp_path / "pack.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(FactPackLoadError) as exc:
        load_deterministic_fact_pack(path, source_root=tmp_path)
    assert exc.value.code == "MALFORMED_FACT_PACK"


def test_unsupported_transformation_is_rejected(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    fact = _fact(root)
    fact["allowed_transformations"] = ["FREE_FORM_INFERENCE"]
    with pytest.raises(FactPackLoadError) as exc:
        _load(_write_pack(tmp_path / "pack.json", [fact]), root)
    assert exc.value.code == "FACT_PACK_SCHEMA_INVALID"


def test_loader_does_not_modify_input_or_create_other_files(tmp_path):
    root = tmp_path / "ncert"
    root.mkdir()
    path = _write_pack(tmp_path / "pack.json", [_fact(root)])
    before = path.read_bytes()
    files_before = sorted(item.relative_to(tmp_path) for item in tmp_path.rglob("*"))
    _load(path, root)
    assert path.read_bytes() == before
    assert sorted(item.relative_to(tmp_path) for item in tmp_path.rglob("*")) == files_before
