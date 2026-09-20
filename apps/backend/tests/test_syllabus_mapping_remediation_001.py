"""SYLLABUS-MAPPING-REMEDIATION-001 tests — read-only reconciliation logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.modules.cms.syllabus import (
    EXPECTED_UNIT_COUNTS,
    clear_neet_2026_registry_cache,
    load_neet_2026_registry,
    normalize_syllabus_text,
)
from scripts.syllabus_mapping_remediation_001_readonly import (
    classify_population,
    reconcile_blueprint,
)

REPO = Path(__file__).resolve().parents[3]
SYLLABUS = REPO / "NEETSyllabus.txt"
NCERT = REPO / "NCERT Books"


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_neet_2026_registry_cache()
    yield
    clear_neet_2026_registry_cache()


@pytest.mark.skipif(not SYLLABUS.exists(), reason="syllabus missing")
def test_syllabus_structure_20_20_10():
    reg = load_neet_2026_registry(str(SYLLABUS.resolve()))
    assert reg.unit_counts() == EXPECTED_UNIT_COUNTS


@pytest.mark.skipif(not SYLLABUS.exists(), reason="syllabus missing")
def test_exact_valid_mapping_chapter_equals_unit():
    reg = load_neet_2026_registry(str(SYLLABUS.resolve()))
    # Gravitation unit has known name
    unit = reg.units_by_id["PHYSICS:U06"]
    row = {
        "blueprint_id": "x",
        "blueprint_key": "test-gravitation",
        "subject_code": "PHYSICS",
        "chapter_code": "gravitation",
        "chapter_name": unit.unit_name,
        "topic_code": "t",
        "topic_name": "Other",
        "concept_code": "c",
        "concept_name": "Escape velocity",  # phrase likely in unit topics
        "provenance_tier": "authoritative",
        "constraints": {
            "ncert_derived": True,
            "ncert_source_path": str(NCERT / "Class 11" / "Physics" / "keph1dd" / "keph1dd" / "keph101.pdf"),
        },
    }
    out = reconcile_blueprint(row=row, registry=reg, ncert_root=NCERT)
    assert out.status == "SYLLABUS_MAPPING_CONFIRMED"
    assert out.neet_unit_number == 6
    assert out.proposed_neet_ug_2026 is not None
    assert out.proposed_neet_ug_2026["subject"] == "PHYSICS"


@pytest.mark.skipif(not SYLLABUS.exists(), reason="syllabus missing")
def test_invalid_subject_out_of_scope():
    reg = load_neet_2026_registry(str(SYLLABUS.resolve()))
    row = {
        "blueprint_id": "x",
        "blueprint_key": "bad",
        "subject_code": "ASTRONOMY",
        "chapter_code": "c",
        "chapter_name": "Stars",
        "topic_code": "t",
        "topic_name": "Nebulae",
        "concept_code": "c",
        "concept_name": "Quasar",
        "provenance_tier": "ai",
        "constraints": {},
    }
    out = reconcile_blueprint(row=row, registry=reg, ncert_root=NCERT)
    assert out.status == "SYLLABUS_OUT_OF_SCOPE"


@pytest.mark.skipif(not SYLLABUS.exists(), reason="syllabus missing")
def test_ambiguous_mapping_stays_review():
    reg = load_neet_2026_registry(str(SYLLABUS.resolve()))
    row = {
        "blueprint_id": "x",
        "blueprint_key": "vague",
        "subject_code": "BIOLOGY",
        "chapter_code": "x",
        "chapter_name": "Cellular process",
        "topic_code": "y",
        "topic_name": "Stuff",
        "concept_code": "z",
        "concept_name": "Thing",
        "provenance_tier": "ai",
        "constraints": {},
    }
    out = reconcile_blueprint(row=row, registry=reg, ncert_root=NCERT)
    assert out.status == "SYLLABUS_MAPPING_REVIEW_REQUIRED"
    assert out.proposed_neet_ug_2026 is None


@pytest.mark.skipif(not SYLLABUS.exists(), reason="syllabus missing")
def test_no_fuzzy_authorization_for_token_overlap():
    reg = load_neet_2026_registry(str(SYLLABUS.resolve()))
    # Shares tokens with Cell Structure but is not an exact phrase/unit match
    row = {
        "blueprint_id": "x",
        "blueprint_key": "fuzzy",
        "subject_code": "BOTANY",
        "chapter_code": "cellish",
        "chapter_name": "Cellular process overview",
        "topic_code": "t",
        "topic_name": "General cell ideas",
        "concept_code": "c",
        "concept_name": "Cellish notions",
        "provenance_tier": "ai",
        "constraints": {},
    }
    out = reconcile_blueprint(row=row, registry=reg, ncert_root=NCERT)
    assert out.status != "SYLLABUS_MAPPING_CONFIRMED"
    assert out.status == "SYLLABUS_MAPPING_REVIEW_REQUIRED"
    if out.diagnostic_candidate:
        assert out.diagnostic_candidate.get("note") == "diagnostic_only_not_authorization"


def test_legacy_studymaterial_population_preserved():
    cons = {"ncert_source_path": r"D:\ravishori\AI Neet Exam App\StudyMaterial\Physics\x.pdf"}
    assert classify_population(cons, NCERT) == "LEGACY_STUDYMATERIAL"


def test_source_missing_population():
    assert classify_population({}, NCERT) == "SOURCE_MISSING"


@pytest.mark.skipif(not SYLLABUS.exists(), reason="syllabus missing")
def test_source_missing_does_not_invent_ncert_or_force_confirm():
    reg = load_neet_2026_registry(str(SYLLABUS.resolve()))
    row = {
        "blueprint_id": "x",
        "blueprint_key": "missing-src",
        "subject_code": "PHYSICS",
        "chapter_code": "unknown-ch",
        "chapter_name": "Mystery Chapter Not In Syllabus",
        "topic_code": "t",
        "topic_name": "Mystery Topic",
        "concept_code": "c",
        "concept_name": "Mystery Concept",
        "provenance_tier": "ai",
        "constraints": {},
    }
    out = reconcile_blueprint(row=row, registry=reg, ncert_root=NCERT)
    assert out.population == "SOURCE_MISSING"
    assert out.ncert_path in (None, "")
    assert out.status in {"SYLLABUS_MAPPING_REVIEW_REQUIRED", "SYLLABUS_OUT_OF_SCOPE"}
    assert out.status != "SYLLABUS_MAPPING_CONFIRMED" or out.mapping_basis  # only if exact evidence


@pytest.mark.skipif(not SYLLABUS.exists(), reason="syllabus missing")
def test_legacy_provenance_not_rewritten_on_confirm():
    reg = load_neet_2026_registry(str(SYLLABUS.resolve()))
    unit = reg.units_by_id["CHEMISTRY:U08"]
    row = {
        "blueprint_id": "x",
        "blueprint_key": "legacy-kinetics",
        "subject_code": "CHEMISTRY",
        "chapter_code": "chemical-kinetics",
        "chapter_name": unit.unit_name,
        "topic_code": "t",
        "topic_name": "Rate",
        "concept_code": "c",
        "concept_name": "Order of reaction",
        "provenance_tier": "ai",
        "constraints": {
            "ncert_source_path": r"D:\x\StudyMaterial\Chemistry\kinetics.pdf",
        },
    }
    out = reconcile_blueprint(row=row, registry=reg, ncert_root=NCERT)
    assert out.population == "LEGACY_STUDYMATERIAL"
    # If confirmed, path still StudyMaterial — provenance not rewritten
    if out.status == "SYLLABUS_MAPPING_CONFIRMED":
        assert "StudyMaterial" in (out.ncert_path or "")
        assert out.provenance_tier == "ai"


def test_no_database_mutation_contract_in_script():
    src = (REPO / "apps" / "backend" / "scripts" / "syllabus_mapping_remediation_001_readonly.py").read_text(
        encoding="utf-8"
    )
    assert "READ_ONLY" in src or "read-only" in src.lower()
    assert "UPDATE cms.question_blueprints" not in src.lower()
    assert "commit()" not in src
