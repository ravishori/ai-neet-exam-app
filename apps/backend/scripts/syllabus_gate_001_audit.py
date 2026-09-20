"""SYLLABUS-GATE-001 audit — safety baseline + coverage gaps (read-only CMS)."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.syllabus import (  # noqa: E402
    assert_blueprint_neet_syllabus_scope,
    load_neet_2026_registry,
    parse_neet_syllabus_file,
)

SYLLABUS = ROOT / "NEETSyllabus.txt"
CAPACITY = ROOT / "docs" / "audits" / "mcq_capacity_matrix_001.json"
EVIDENCE = ROOT / "docs" / "audits" / "mcq_evidence_coverage_001.json"
REPORT = "syllabus_gate_001"


def snapshot(conn) -> dict:
    status = {
        r[0]: r[1]
        for r in conn.execute(
            text(
                """
                SELECT status, COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
        )
    }
    unmapped = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM cms.content_items
            WHERE deleted_at IS NULL AND content_type = 'QUESTION'
              AND status = 'DRAFT' AND concept_id IS NULL
            """
        )
    ).scalar()
    return {
        "status": status,
        "unmapped_draft": unmapped,
        "kus": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "candidates": conn.execute(text("SELECT COUNT(*) FROM cms.generation_candidates")).scalar(),
        "jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
    }


def main() -> int:
    before = None
    after = None
    engine = create_engine(get_settings().database_url_sync)
    with engine.connect() as conn:
        before = snapshot(conn)

    reg = parse_neet_syllabus_file(SYLLABUS)
    sha = hashlib.sha256(SYLLABUS.read_bytes()).hexdigest()

    # Existing blueprint explicit-scope scan (no mutation)
    missing_scope = 0
    in_scope = 0
    out_scope = 0
    review = 0
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT bp.blueprint_key, s.code AS subject_code, bp.constraints
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                WHERE bp.deleted_at IS NULL
                """
            )
        ).mappings()
        for r in rows:
            cons = r["constraints"] if isinstance(r["constraints"], dict) else json.loads(r["constraints"] or "{}")
            result = assert_blueprint_neet_syllabus_scope(
                cons,
                academic_subject_code=r["subject_code"],
                registry=reg,
            )
            if result.status == "IN_SYLLABUS":
                in_scope += 1
            elif result.status == "SYLLABUS_OUT_OF_SCOPE":
                out_scope += 1
            else:
                review += 1
                if "missing_neet_ug_2026_scope" in result.reasons:
                    missing_scope += 1

    gaps = []
    if CAPACITY.exists():
        cap = json.loads(CAPACITY.read_text(encoding="utf-8"))
        gaps = cap.get("capacity_matrix", {}).get("uncovered_units_or_concepts") or []

    with engine.connect() as conn:
        after = snapshot(conn)

    report = {
        "task": "SYLLABUS-GATE-001",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "syllabus_source_path": str(SYLLABUS.resolve()),
        "syllabus_sha256": sha,
        "unit_counts": reg.unit_counts(),
        "topic_count": len(reg.topics_by_id),
        "parser": "app.modules.cms.syllabus.neet_2026_parser",
        "registry": "app.modules.cms.syllabus.neet_2026_registry",
        "blueprint_gate": "app.modules.cms.syllabus.neet_2026_scope.assert_blueprint_neet_syllabus_scope",
        "pre_llm_enforcement": (
            "content_factory_generation_service._execute_run: "
            "syllabus gate → NCERT evidence gate → provider"
        ),
        "existing_blueprint_scope_scan": {
            "in_syllabus": in_scope,
            "out_of_scope": out_scope,
            "mapping_review_required": review,
            "missing_explicit_neet_ug_2026_binding": missing_scope,
            "note": "Existing blueprints were not rewritten; missing bindings block generation until explicit scope is added.",
        },
        "coverage_gaps_from_capacity_matrix": gaps,
        "database_before": before,
        "database_after": after,
        "database_unchanged": before == after,
        "safety": {
            "questions_mutated": False,
            "publication": False,
            "certification": False,
            "ecaep_mutated": False,
            "frozen_drafts_mutated": False,
        },
        "authorization_rule": (
            "Exact match only via constraints.neet_ug_2026 "
            "(subject + unit_number + topic_id|topic). Fuzzy match never authorizes."
        ),
    }

    out_json = ROOT / "docs" / "audits" / f"{REPORT}.json"
    out_md = ROOT / "docs" / "audits" / f"{REPORT}.md"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    lines = [
        "# SYLLABUS-GATE-001 — Hard NEET-UG-2026 pre-generation gate",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Syllabus:** `{report['syllabus_source_path']}`",
        f"**SHA-256:** `{sha}`",
        "",
        "## Unit counts",
        "",
        f"- Physics: **{report['unit_counts']['PHYSICS']}**",
        f"- Chemistry: **{report['unit_counts']['CHEMISTRY']}**",
        f"- Biology: **{report['unit_counts']['BIOLOGY']}**",
        f"- Topics parsed: **{report['topic_count']}**",
        "",
        "## Implementation",
        "",
        f"- Parser: `{report['parser']}`",
        f"- Registry: `{report['registry']}`",
        f"- Gate: `{report['blueprint_gate']}`",
        f"- Pre-LLM: `{report['pre_llm_enforcement']}`",
        "",
        "## Authorization rule",
        "",
        report["authorization_rule"],
        "",
        "## Existing blueprint scan (no mutation)",
        "",
        f"- IN_SYLLABUS: **{in_scope}**",
        f"- SYLLABUS_OUT_OF_SCOPE: **{out_scope}**",
        f"- SYLLABUS_MAPPING_REVIEW_REQUIRED: **{review}**",
        f"- Missing explicit `neet_ug_2026` binding: **{missing_scope}**",
        "",
        "## 13 capacity-matrix coverage gaps",
        "",
        f"Count from capacity matrix: **{len(gaps)}**",
        "",
    ]
    for g in gaps:
        lines.append(
            f"- {g.get('subject')} Unit {g.get('unit_number')}: {g.get('unit_title')} "
            f"— {g.get('reason')} (usable target {g.get('target_usable_assigned')})"
        )
    lines += [
        "",
        "Blocker class: **blueprint coverage / explicit syllabus binding** "
        "(not fabricated in this task).",
        "",
        "## Database before/after",
        "",
        f"- Unchanged: **{report['database_unchanged']}**",
        f"- Before: `{json.dumps(before)}`",
        f"- After: `{json.dumps(after)}`",
        "",
        "## Safety",
        "",
        "- No question mutation",
        "- No publication / certification / ECAEP change",
        "- Frozen unmapped DRAFTs unchanged",
        "- No MCQ generation",
        "- No commit/push",
        "",
        "## Known limitations",
        "",
        "- Existing production blueprints mostly lack `constraints.neet_ug_2026`; "
        "they now correctly fail closed with `SYLLABUS_MAPPING_REVIEW_REQUIRED` until "
        "explicit bindings are added in a later remediation task.",
        "- Exact topic text match is strict (casefold + whitespace only).",
        "- NCERT VERIFY-001 n=5 yield remains low-confidence for capacity planning "
        "(unchanged by this gate).",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"json": str(out_json), "md": str(out_md), "unchanged": before == after, "scan": report["existing_blueprint_scope_scan"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
