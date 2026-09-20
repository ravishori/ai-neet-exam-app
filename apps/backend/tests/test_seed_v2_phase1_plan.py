"""Validate Production Seed V2 Phase 1 planning artifact (no generation)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

PLAN = Path(__file__).resolve().parents[3] / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"


def _plan() -> dict:
    assert PLAN.is_file(), f"missing {PLAN}"
    return json.loads(PLAN.read_text(encoding="utf-8"))


def test_seed_v2_plan_counts_and_uniqueness():
    p = _plan()
    slots = p["slots"]
    assert p["status"] == "PLANNING_ONLY"
    assert len(slots) == 100
    subj = Counter(s["subject"] for s in slots)
    assert subj["Physics"] == 35
    assert subj["Chemistry"] == 35
    assert subj["Botany"] == 15
    assert subj["Zoology"] == 15
    bps = [s["blueprint_id"] for s in slots]
    assert len(set(bps)) == 100
    diff = Counter(s["difficulty"] for s in slots)
    assert diff["easy"] == 25
    assert diff["medium"] == 60
    assert diff["hard"] == 15


def test_seed_v2_plan_academic_and_ncert_mapping():
    p = _plan()
    for s in p["slots"]:
        assert s["chapter_id"]
        assert s["ncert_source_available"] is True
        assert s["page_verified"] is False
        assert s["planning_status"] == "ACTIVE"


def test_seed_v2_plan_chemistry_breadth_and_forbidden_templates():
    p = _plan()
    chem = [s for s in p["slots"] if s["subject"] == "Chemistry"]
    assert len({s["chapter"] for s in chem}) >= 5
    lattice = [s for s in chem if (s.get("concept_code") == "lattice-energy")]
    assert len(lattice) == 1
    abo = [s for s in p["slots"] if "abo" in (s.get("concept_code") or "").lower()]
    assert abo == []
    ohms = [s for s in p["slots"] if s.get("concept_code") == "ohms-law-concept"]
    assert ohms == []


def test_seed_v2_plan_no_generation_flags():
    p = _plan()
    assert p["generation_not_run"] is True
    assert p["generation_feasibility"]["gemini_called"] is False
    assert p["protected_population_integrity"]["cms_writes_this_phase"] == 0
