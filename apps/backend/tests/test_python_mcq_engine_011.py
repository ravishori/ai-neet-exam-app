"""Focused tests for PYTHON-MCQ-ENGINE-011 fact-type expansion analysis."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACK_010 = Path(__file__).parent / "fixtures/python_mcq_engine_010_reviewed_corpus.json"
PACK_006 = Path(__file__).parent / "fixtures/python_mcq_engine_006_reviewed_100.json"
CANDIDATES = (
    Path(__file__).parent / "fixtures/python_mcq_engine_011_fact_type_candidates.json"
)
AUDIT = ROOT / "docs/audits/python_mcq_engine_011.json"
RETIRED = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)


def test_baseline_and_no_auto_eligibility_promotion():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["baseline"]["mcq_eligible_total"] == 414
    assert audit["safely_mcq_eligible_now"] == 0
    assert audit["genuinely_reviewable_candidates"] > 0
    assert audit["provider_api_calls"] == 0
    assert audit["production_db_mutations"] == 0
    assert audit["fixture_mutations"]["engine_006_modified"] is False
    assert audit["fixture_mutations"]["engine_010_modified"] is False


def test_candidate_fixture_has_no_mcq_eligible_or_retired_facts():
    payload = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    facts = payload["pack"]["facts"]
    assert facts
    assert all(fact["review_status"] in {"EXTRACTED", "REVIEW_REQUIRED"} for fact in facts)
    assert RETIRED not in {fact["fact_id"] for fact in facts}
    assert all(fact.get("question_template") is None for fact in facts)


def test_engine010_and_006_fixtures_untouched():
    # Existence + stable pack IDs as mutation smoke check.
    pack010 = json.loads(PACK_010.read_text(encoding="utf-8"))
    pack006 = json.loads(PACK_006.read_text(encoding="utf-8"))
    assert pack010["pack_id"] == "python-mcq-engine-010-reviewed-corpus-v1"
    assert pack006["pack_id"] == "python-mcq-engine-006-reviewed-multisubject-v1"
    assert len(pack010["facts"]) == 414


def test_recommended_types_are_schema_ready():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    recommended = audit["recommended_fact_types_for_next_curation_wave"]
    assert "DIRECT_FACT" in recommended
    assert "CONTROLLED_ASSOCIATION" in recommended
    for category in recommended:
        meta = audit["fact_type_expansion_opportunities"][category]
        assert meta["schema_ready"] is True
        assert meta["potentially_reviewable"] > 0
