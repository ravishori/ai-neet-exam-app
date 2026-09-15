"""Focused tests for PYTHON-MCQ-ENGINE-014 expanded cohort evaluation."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACK_006 = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_010 = Path(__file__).parent / "fixtures/python_mcq_engine_010_reviewed_corpus.json"
PACK_012 = (
    Path(__file__).parent / "fixtures/python_mcq_engine_012_reviewed_nondef_v1.json"
)
PACK_013 = (
    Path(__file__).parent / "fixtures/python_mcq_engine_013_reviewed_nondef_v1.json"
)
AUDIT = ROOT / "docs/audits/python_mcq_engine_014.json"
RETIRED = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)


def test_cohort_inventory_and_safety():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    inv = audit["cohort_inventory"]
    assert audit["cohort_size"] == inv["unique_cohort_size"]
    assert audit["facts_evaluated"] == audit["cohort_size"]
    assert (
        inv["engine_007_cohort_excluding_retired"]
        + inv["engine_012_eligible"]
        + inv["engine_013_eligible"]
        == inv["unique_cohort_size"]
    )
    assert audit["provider_api_calls"] == 0
    assert audit["production_db_mutations"] == 0
    assert audit["production_safety_unchanged"] is True
    assert audit["engine_008_retired_excluded"] is True
    assert audit["engine_008_retired_regenerated"] is False
    assert audit["fixture_mutations"]["all_source_fixtures_unchanged"] is True


def test_metrics_consistency():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    m = audit["metrics"]
    assert m["candidates_generated"] == (
        m["independent_PASS"] + m["independent_FAIL"] + m["independent_AMBIGUOUS"]
    )
    assert m["facts_evaluated"] == m["candidates_generated"] + m["generation_skips"]
    assert 0.0 <= m["verified_yield"] <= 1.0
    assert m["reproducible"] is True
    for row in audit["fail_ambiguous_records"]:
        assert row["classification"] in {"FAIL", "AMBIGUOUS"}
        assert row["reason"]


def test_retired_fact_absent_and_no_relationship_formula():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    ids = {row["fact_id"] for row in audit["candidate_records"]}
    ids |= {row["fact_id"] for row in audit["quality_results"]}
    assert RETIRED not in ids
    cats = audit["metrics"]["fact_type_breakdown"]["analysis_category_cohort"]
    assert cats.get("RELATIONSHIP_FORMULA", 0) == 0


def test_source_fixtures_unchanged():
    pack006 = json.loads(PACK_006.read_text(encoding="utf-8"))
    pack010 = json.loads(PACK_010.read_text(encoding="utf-8"))
    pack012 = json.loads(PACK_012.read_text(encoding="utf-8"))
    pack013 = json.loads(PACK_013.read_text(encoding="utf-8"))
    assert pack006["pack_id"] == "python-mcq-engine-006-reviewed-multisubject-v1"
    assert len(pack010["facts"]) == 414
    assert pack012["pack"]["pack_id"] == "python-mcq-engine-012-reviewed-nondef-v1"
    assert len(pack012["pack"]["facts"]) == 58
    assert pack013["pack"]["pack_id"] == "python-mcq-engine-013-reviewed-nondef-v1"
    assert len(pack013["pack"]["facts"]) == 77
