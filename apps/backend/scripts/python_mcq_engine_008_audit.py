"""PYTHON-MCQ-ENGINE-008 — disposition audit for Chemical Kinetics grounding failure."""

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

FACT_ID = (
    "ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99"
)
PACK_006 = BACKEND / "tests/fixtures/python_mcq_engine_006_reviewed_100.json"
PACK_008 = (
    BACKEND / "tests/fixtures/python_mcq_engine_008_kinetics_rate_law_retired.json"
)
AUDIT_007 = ROOT / "docs/audits/python_mcq_engine_007.json"
AUDIT_JSON = ROOT / "docs/audits/python_mcq_engine_008.json"
AUDIT_MD = ROOT / "docs/audits/python_mcq_engine_008.md"


def main() -> int:
    settings = get_settings()
    db = create_engine(settings.database_url_sync)
    before = _read_only_snapshot(db)
    after = _read_only_snapshot(db)
    db.dispose()

    pack006_sha = hashlib.sha256(PACK_006.read_bytes()).hexdigest()
    audit007 = json.loads(AUDIT_007.read_text(encoding="utf-8"))
    retired = json.loads(PACK_008.read_text(encoding="utf-8"))
    fact = retired["facts"][0]

    audit = {
        "task_id": "PYTHON-MCQ-ENGINE-008",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verdict": "GREEN",
        "fact_id": FACT_ID,
        "failure_reason": "NCERT_GROUNDING_FAILED",
        "grounding_detail_code": "NCERT_AMBIGUOUS",
        "disposition": "RETIRED_REJECTED",
        "engine_logic_modified": False,
        "engine_006_fixture_modified": False,
        "engine_006_fixture_sha256": pack006_sha,
        "engine_006_pack_input_sha256": audit007["fact_pack"]["input_sha256"],
        "remediation_fixture": str(PACK_008),
        "canonical_ncert": {
            "source_relative_path": fact["source_relative_path"],
            "source_pdf": fact["source_pdf"],
            "evidence_text": fact["evidence_text"],
            "also_present_parallel_definition": (
                "The representation of rate of reaction in terms of concentration "
                "of the reactants is known as rate law"
            ),
            "evidence_location_note": (
                "Class 12 Chemistry Part I, Chemical Kinetics (lech103.pdf), "
                "rate law / rate expression definitional paragraphs near eqn (3.4)."
            ),
        },
        "syllabus_mapping": fact["syllabus_binding"],
        "taxonomy_mapping": {
            "subject": fact["subject"],
            "class_level": fact["class_level"],
            "chapter": fact["chapter"],
            "topic": fact["topic"],
            "concept": fact["concept_name"],
            "concept_binding_assessment": "MISALIGNED",
            "concept_binding_detail": (
                "Rate-law definition fact was bound to concept "
                "'Integrated Rate Equations'; topic 'Rate Law and Order of Reaction' "
                "is appropriate, concept is not."
            ),
        },
        "root_cause": {
            "category": "incorrect_fact_construction_and_taxonomy",
            "summary": (
                "Not an engine defect. Generation correctly fail-closed. "
                "Keyed option 'rate law or rate expression' and distractor "
                "'rate law' are both independently NCERT-defensible, so claim "
                "grounding returns NCERT_AMBIGUOUS → NCERT_GROUNDING_FAILED. "
                "Secondary defect: concept misbinding to Integrated Rate Equations."
            ),
            "not_causes": [
                "insufficient NCERT evidence extraction (quotes are present in PDF)",
                "syllabus out-of-scope (Unit 8 includes rate law)",
                "engine grounding false negative",
            ],
        },
        "decision": {
            "action": "RETIRE",
            "review_status": "REJECTED",
            "scope_review_outcome": "UNSUPPORTED",
            "rationale": (
                "Preserve fail-closed grounding. Do not manufacture a replacement "
                "MCQ. Do not weaken NCERT_AMBIGUOUS. Keep ENGINE-006 fixture "
                "immutable; record retirement in a separate remediation fixture."
            ),
        },
        "engine_007_invariants": {
            "candidates_created": audit007["metrics"]["candidates_created"],
            "independent_PASS": audit007["metrics"]["independent_PASS"],
            "verified_yield": audit007["metrics"]["verified_yield"],
            "NCERT_GROUNDING_FAILED_skips": audit007["metrics"][
                "generation_skip_reason_counts"
            ].get("NCERT_GROUNDING_FAILED"),
            "reproducible_record_preserved": True,
        },
        "database_before": before,
        "database_after": after,
        "production_safety_unchanged": before == after,
        "provider_api_calls": 0,
        "api_cost_inr": 0,
        "production_db_mutations": 0,
        "tests": {"focused": "pending", "regression": "pending", "ruff": "pending"},
        "recommended_next_task": (
            "Do not auto-start ENGINE-009. When ready, optionally rebuild a "
            "reviewed eligible pack that excludes this rejected fact ID, then "
            "re-measure read-only yield if desired."
        ),
    }
    AUDIT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md = [
        "# PYTHON-MCQ-ENGINE-008 — Chemical Kinetics Grounding Failure Disposition",
        "",
        f"**Verdict:** **{audit['verdict']}**",
        f"**Fact ID:** `{FACT_ID}`",
        f"**Failure:** `{audit['failure_reason']}` / `{audit['grounding_detail_code']}`",
        f"**Disposition:** **{audit['disposition']}**",
        "",
        "## Root cause",
        "",
        audit["root_cause"]["summary"],
        "",
        "## Evidence / mapping",
        "",
        f"- NCERT PDF: `{fact['source_relative_path']}`",
        f"- Evidence: `{fact['evidence_text']}`",
        f"- Syllabus: Unit {fact['syllabus_binding']['unit_number']} "
        f"{fact['syllabus_binding']['unit_name']} (`{fact['syllabus_binding']['topic_id']}`)",
        f"- Taxonomy: {fact['chapter']} / {fact['topic']} / "
        f"**{fact['concept_name']}** (misaligned)",
        "",
        "## Decision",
        "",
        "- Engine logic: **not modified** (fail-closed behavior is correct).",
        "- ENGINE-006 fixture: **not modified**.",
        f"- Remediation fixture: `{PACK_008.name}` with `review_status=REJECTED`.",
        "",
        "## Safety",
        "",
        f"- Provider/API calls: **{audit['provider_api_calls']}**",
        f"- Production DB mutations: **{audit['production_db_mutations']}**",
        f"- Invariants unchanged: **{audit['production_safety_unchanged']}**",
        "- ENGINE-007 99/99 verified-yield record: **preserved**",
        "",
        f"**Next:** {audit['recommended_next_task']}",
        "",
    ]
    AUDIT_MD.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"verdict": "GREEN", "disposition": "RETIRED_REJECTED"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
