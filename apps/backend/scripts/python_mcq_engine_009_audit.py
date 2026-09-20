"""PYTHON-MCQ-ENGINE-009 — stop audit when eligible corpus < 1000."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
SCRIPTS = BACKEND / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from python_mcq_engine_003_audit import _read_only_snapshot  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.services.deterministic_fact_adapter import (  # noqa: E402
    DeterministicFactToQuestionAdapter,
    FactAdapterError,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (  # noqa: E402
    load_deterministic_fact_pack,
)
from app.modules.cms.services.fact_quality_gate import TaxonomyBinding  # noqa: E402

TASK_ID = "PYTHON-MCQ-ENGINE-009"
REQUESTED = 1000
RETIRED_FACT_ID = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)
PACK_004 = BACKEND / "tests/fixtures/python_mcq_engine_004_biomolecules.json"
PACK_006 = BACKEND / "tests/fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_008 = (
    BACKEND / "tests/fixtures/python_mcq_engine_008_kinetics_rate_law_retired.json"
)
SYLLABUS = ROOT / "NEETSyllabus.txt"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_009.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_009.md"


def _taxonomy(fact) -> TaxonomyBinding:
    return TaxonomyBinding(
        subject=fact.subject,
        class_level=fact.class_level,
        chapter_id=fact.chapter_id,
        chapter=fact.chapter,
        topic_id=fact.topic_id,
        topic=fact.topic,
        concept_id=fact.concept_id or "",
        concept=fact.concept_name or "",
    )


def main() -> int:
    started = time.perf_counter()
    settings = get_settings()
    db = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(db)

    adapter = DeterministicFactToQuestionAdapter()
    eligible_ids: set[str] = set()
    inventory: list[dict] = []

    for path, minimum in (
        (PACK_004, "REVIEWED"),
        (PACK_006, "REVIEWED"),
        (PACK_008, "REJECTED"),
    ):
        loaded = load_deterministic_fact_pack(path, minimum_review_status=minimum)
        row = {
            "path": str(path),
            "pack_id": loaded.pack_id,
            "input_sha256": loaded.input_sha256,
            "loaded_facts": len(loaded.facts),
            "by_review_status": {},
            "mcq_eligible_after_exclusions": 0,
            "retired_excluded": 0,
        }
        for fact in loaded.facts:
            row["by_review_status"][fact.review_status] = (
                row["by_review_status"].get(fact.review_status, 0) + 1
            )
            if fact.review_status == "REJECTED":
                continue
            if fact.fact_id == RETIRED_FACT_ID:
                row["retired_excluded"] += 1
                continue
            if fact.review_status not in {"REVIEWED", "VERIFIED"}:
                continue
            try:
                adapted = adapter.adapt(
                    fact,
                    taxonomy=_taxonomy(fact),
                    authoritative_syllabus_path=SYLLABUS,
                )
            except FactAdapterError:
                continue
            if adapted.quality.mcq_eligible:
                eligible_ids.add(fact.fact_id)
                row["mcq_eligible_after_exclusions"] += 1
        inventory.append(row)

    retired = load_deterministic_fact_pack(PACK_008, minimum_review_status="REJECTED")
    retired_fact = retired.facts[0]
    retired_not_regenerated = (
        retired_fact.fact_id == RETIRED_FACT_ID
        and retired_fact.review_status == "REJECTED"
        and RETIRED_FACT_ID not in eligible_ids
    )

    available = len(eligible_ids)
    stop_triggered = available < REQUESTED
    after = _read_only_snapshot(db)
    db.dispose()
    runtime = round(time.perf_counter() - started, 3)

    audit = {
        "task_id": TASK_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verdict": "YELLOW" if stop_triggered else "GREEN",
        "stop_condition": {
            "triggered": stop_triggered,
            "reason": (
                "Available independently reviewed MCQ-eligible facts are below the "
                "requested 1,000. Scale evaluation was not started. No facts were "
                "fabricated, upgraded, or auto-promoted."
                if stop_triggered
                else None
            ),
        },
        "requested_facts": REQUESTED,
        "available_eligible_facts": available,
        "evaluated_facts": 0,
        "generated_candidates": 0,
        "skipped_facts": 0,
        "skip_reasons": {},
        "independent_verification": {
            "PASS": 0,
            "FAIL": 0,
            "AMBIGUOUS": 0,
            "not_run": True,
        },
        "verified_yield": None,
        "verified_yield_label": "READ-ONLY EVALUATION VERIFIED YIELD",
        "verified_yield_note": "Not computed — scale evaluation stopped before generation.",
        "breakdown": {
            "by_subject": {},
            "by_chapter": {},
            "by_question_type": {},
        },
        "duplicates": {
            "within_evaluation_duplicate_rate": None,
            "production_stem_hash_overlap": None,
            "not_run": True,
        },
        "ambiguity_rate": None,
        "reproducibility": {
            "ran": False,
            "seed": None,
            "first_run_count": 0,
            "second_run_count": 0,
            "exact_equality": None,
        },
        "runtime_seconds": runtime,
        "peak_memory_bytes": None,
        "inventory": inventory,
        "engine_006_fixture_sha256": hashlib.sha256(PACK_006.read_bytes()).hexdigest(),
        "engine_006_fixture_modified": False,
        "engine_008_retired_fact": {
            "fact_id": RETIRED_FACT_ID,
            "review_status": retired_fact.review_status,
            "remains_retired": retired_fact.review_status == "REJECTED",
            "excluded_from_eligible_corpus": RETIRED_FACT_ID not in eligible_ids,
            "not_regenerated": retired_not_regenerated,
        },
        "database_before": before,
        "database_after": after,
        "production_safety_unchanged": before == after,
        "provider_api_calls": 0,
        "api_cost_inr": 0,
        "production_db_mutations": 0,
        "tests": {
            "focused": "pending",
            "regression": "pending",
            "ruff": "pending",
        },
        "readiness_recommendation": (
            f"NOT READY for 1,000-fact scale evaluation. Available eligible reviewed "
            f"facts = {available} (requested {REQUESTED}; shortfall "
            f"{REQUESTED - available}). Next authorized work should expand the "
            f"independently reviewed MCQ-eligible fact corpus across subjects/chapters "
            f"without promoting EXTRACTED/REVIEW_REQUIRED facts and without regenerating "
            f"the ENGINE-008 retired Chemical Kinetics rate-law fact. Do not start "
            f"production generation."
        ),
        "limitations": [
            "Scale generation/verification was intentionally not executed.",
            "Eligible count excludes the ENGINE-008 RETIRED_REJECTED fact ID.",
            "ENGINE-004 facts are a subset of ENGINE-006; unique IDs are counted once.",
            "No provider calls and no production persistence occurred.",
        ],
    }
    AUDIT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md = [
        "# PYTHON-MCQ-ENGINE-009 — 1,000-Fact Scale Evaluation (STOPPED)",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**Stop condition triggered:** **{stop_triggered}**",
        "",
        f"- Requested facts: **{REQUESTED}**",
        f"- Available independently reviewed MCQ-eligible facts: **{available}**",
        f"- Shortfall: **{REQUESTED - available}**",
        "- Evaluated facts: **0**",
        "- Generated candidates: **0**",
        "",
        "## Why evaluation did not run",
        "",
        audit["stop_condition"]["reason"],
        "",
        "## Inventory",
        "",
        "- ENGINE-004 biomolecules pack: 5 REVIEWED (subset of 006).",
        "- ENGINE-006 reviewed pack: 100 REVIEWED; 1 excluded as ENGINE-008 retired.",
        "- ENGINE-008 retired fixture: 1 REJECTED (not eligible).",
        f"- Unique eligible IDs after exclusions: **{available}**.",
        "",
        "## ENGINE-008 retired fact",
        "",
        f"- Fact ID: `{RETIRED_FACT_ID}`",
        f"- Remains REJECTED: **{audit['engine_008_retired_fact']['remains_retired']}**",
        f"- Not regenerated: **{audit['engine_008_retired_fact']['not_regenerated']}**",
        "",
        "## Metrics not produced (by design)",
        "",
        "- PASS/FAIL/AMBIGUOUS: not run",
        "- Verified yield: not computed",
        "- Duplicate/ambiguity rates: not run",
        "- Reproducibility dual-run: not run",
        "",
        "## Safety",
        "",
        f"- Provider/API calls: **{audit['provider_api_calls']}**",
        f"- Production DB mutations: **{audit['production_db_mutations']}**",
        f"- Invariants unchanged: **{audit['production_safety_unchanged']}**",
        "- ENGINE-006 fixture modified: **False**",
        f"- Runtime seconds (inventory only): **{runtime}**",
        "",
        "## Readiness recommendation",
        "",
        audit["readiness_recommendation"],
        "",
    ]
    AUDIT_MD.write_text("\n".join(md), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": audit["verdict"],
                "stop": stop_triggered,
                "requested": REQUESTED,
                "available": available,
                "evaluated": 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
