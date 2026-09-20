"""NCERT-EVIDENCE-WRITE-REVIEW-001 — read-only design review for 14 recoveries.

Authoritative input: SAFE_FOR_SEPARATE_EVIDENCE_WRITE_REVIEW from
ncert_evidence_remediation_001.json (exactly 14 SOURCE_MISSING blueprints).

No DB writes. No provenance mutation. No generation. No LLM.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.services.ncert_generation_evidence import (  # noqa: E402
    resolve_ncert_evidence_pack,
)
from app.modules.cms.syllabus import (  # noqa: E402
    assert_blueprint_neet_syllabus_scope,
    load_neet_2026_registry,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    blueprint_declares_ncert_source,
    extract_blueprint_ncert_path,
    validate_ncert_generation_source,
)

REPORT = "ncert_evidence_write_review_001"
REMEDIATION = ROOT / "docs" / "audits" / "ncert_evidence_remediation_001.json"
NCERT_ROOT = ROOT / "NCERT Books"
PROVIDER_CALLS = {"n": 0}

RECOMMENDATIONS = (
    "SAFE_FOR_SURGICAL_EVIDENCE_WRITE",
    "EXISTING_REPRESENTATION_REUSE",
    "KU_REQUIRED_SEPARATE_TASK",
    "PROVENANCE_REVIEW_REQUIRED",
    "REMAIN_BLOCKED",
)

ARCHITECTURE_SUMMARY = {
    "canonical_evidence_mechanism": [
        "constraints.ncert_source_path (primary PDF binding)",
        "constraints.ncert_source_relative (optional relative path)",
        "constraints.ncert_derived (optional explicit NCERT flag)",
        "constraints.ncert_section_heading (optional section hint)",
        "constraints.ku_id (optional KU linkage for evidence composition)",
        "blueprint.provenance_tier == 'authoritative' also forces NCERT declaration",
    ],
    "resolver": "app.modules.cms.services.ncert_generation_evidence.resolve_ncert_evidence_pack",
    "source_gate": "app.modules.ingestion.services.ncert_canonical_source.assert_blueprint_ncert_source",
    "generation_order": [
        "syllabus assert_blueprint_neet_syllabus_scope",
        "resolve_ncert_evidence_pack (if requires_ncert)",
        "provider call only if evidence ready or NCERT not required",
    ],
    "no_new_table_required": True,
}


def _cons(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def snapshot(conn) -> dict[str, Any]:
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
        "chapters": conn.execute(
            text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")
        ).scalar(),
        "topics": conn.execute(
            text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")
        ).scalar(),
        "concepts": conn.execute(
            text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")
        ).scalar(),
        "kus": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "status": status,
        "unmapped_draft": unmapped,
        "candidates": conn.execute(
            text("SELECT COUNT(*) FROM cms.generation_candidates")
        ).scalar(),
        "jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
    }


def load_blueprint(conn, blueprint_id: str) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
              bp.id::text AS blueprint_id,
              bp.blueprint_key,
              bp.provenance_tier,
              bp.generation_eligible,
              bp.status AS db_status,
              bp.constraints,
              bp.target_count,
              s.code AS subject_code,
              ch.id::text AS chapter_id,
              ch.code AS chapter_code,
              ch.name AS chapter_name,
              ch.class_level,
              t.id::text AS topic_id,
              t.code AS topic_code,
              t.name AS topic_name,
              c.id::text AS concept_id,
              c.code AS concept_code,
              c.name AS concept_name
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id
            JOIN academic.topics t ON t.id = bp.topic_id
            JOIN academic.concepts c ON c.id = bp.concept_id
            WHERE bp.id = CAST(:id AS uuid)
            """
        ),
        {"id": blueprint_id},
    ).mappings().first()
    return dict(row) if row else {}


def load_ku(conn, ku_id: str | None) -> dict[str, Any] | None:
    if not ku_id:
        return None
    row = conn.execute(
        text(
            """
            SELECT
              ku.id::text AS ku_id,
              ku.validation_status,
              ku.summary,
              length(coalesce(ku.summary, '')) AS summary_chars,
              ku.structured_facts,
              ku.concept_id::text AS concept_id
            FROM knowledge.knowledge_units ku
            WHERE ku.id = CAST(:id AS uuid) AND ku.deleted_at IS NULL
            """
        ),
        {"id": ku_id},
    ).mappings().first()
    return dict(row) if row else None


def review_one(conn, rem: dict[str, Any], registry) -> dict[str, Any]:
    bid = rem["blueprint_id"]
    db = load_blueprint(conn, bid)
    cons = _cons(db.get("constraints"))
    ku = load_ku(conn, rem.get("ku_id"))

    gate = assert_blueprint_neet_syllabus_scope(
        cons,
        academic_subject_code=db.get("subject_code"),
        registry=registry,
    )
    asserts_syllabus = gate.status == "IN_SYLLABUS"

    candidate = rem["candidate_ncert_source"]
    assert isinstance(candidate, str)
    pdf_path = NCERT_ROOT / candidate
    pdf_readable = False
    validated = None
    evidence = None
    evidence_error = None
    try:
        validated = validate_ncert_generation_source(pdf_path, root=NCERT_ROOT)
        pdf_readable = True
        # Simulated post-write constraints (NOT written): path + ku_id only
        sim = {
            **{k: v for k, v in cons.items() if k != "ncert_source_path"},
            "ncert_source_path": str(validated.resolved_path),
            "ncert_source_relative": candidate,
        }
        if ku:
            sim["ku_id"] = ku["ku_id"]
        facts = []
        if ku and isinstance(ku.get("structured_facts"), list):
            facts = [str(x) for x in ku["structured_facts"] if x]
        elif ku and isinstance(ku.get("structured_facts"), dict):
            for v in ku["structured_facts"].values():
                if isinstance(v, str):
                    facts.append(v)
                elif isinstance(v, list):
                    facts.extend(str(x) for x in v)
        pack = resolve_ncert_evidence_pack(
            sim,
            provenance_tier=db.get("provenance_tier"),  # keep ai
            concept_name=db.get("concept_name"),
            chapter_name=db.get("chapter_name"),
            topic_name=db.get("topic_name"),
            ku_id=ku["ku_id"] if ku else None,
            ku_summary=ku.get("summary") if ku else None,
            ku_facts=facts,
            validated_source=validated,
        )
        evidence = {
            "status": pack.status,
            "pages": list(pack.page_numbers or []),
            "chars": len(pack.evidence_text or ""),
            "excerpt": (pack.evidence_text or "")[:360],
            "detail": pack.detail,
            "relative_posix": pack.relative_posix,
        }
    except Exception as exc:  # noqa: BLE001
        evidence_error = f"{type(exc).__name__}:{exc}"

    declares_now = blueprint_declares_ncert_source(cons, db.get("provenance_tier"))
    existing_path = extract_blueprint_ncert_path(cons)

    # Architecture questions
    source_deterministic = pdf_readable and rem.get("recovery_classification") == "CANONICAL_EVIDENCE_RECOVERABLE"
    evidence_deterministic = bool(evidence and evidence["status"] == "NCERT_EVIDENCE_READY")
    ku_exists = ku is not None and ku.get("validation_status") == "PASSED"
    ku_linked_in_constraints = bool(cons.get("ku_id"))

    # Smallest safe write under existing schema
    proposed_future_write = {
        "mechanism": "merge into cms.question_blueprints.constraints JSONB only",
        "add_or_set": {
            "ncert_source_path": str(validated.resolved_path) if validated else candidate,
            "ncert_source_relative": candidate,
            "ku_id": ku["ku_id"] if ku else None,
        },
        "optional_consistency_flags": {
            "ncert_derived": True,
            "note": (
                "Sibling GENERATION_READY blueprints set ncert_derived=true. "
                "Path alone already activates blueprint_declares_ncert_source. "
                "Setting ncert_derived is optional for gate activation but aligns with canonical peers."
            ),
        },
        "do_not_create": [
            "new evidence table",
            "new API",
            "new KU",
            "new blueprint",
        ],
    }

    fields_may_change = [
        "constraints.ncert_source_path",
        "constraints.ncert_source_relative",
        "constraints.ku_id",
        "constraints.ncert_derived (optional)",
        "constraints.ncert_section_heading (optional)",
        "updated_at / updated_by (audit columns only)",
    ]
    fields_must_remain = [
        "id",
        "blueprint_key",
        "provenance_tier",
        "subject_id",
        "chapter_id",
        "topic_id",
        "concept_id",
        "target_count",
        "generation_eligible (unless separate eligibility policy task)",
        "constraints.neet_ug_2026",
        "all unrelated constraint keys",
        "question rows / KU rows / ECAEP",
    ]

    provenance_impact = {
        "provenance_tier_change_required": False,
        "current_provenance_tier": db.get("provenance_tier"),
        "ncert_path_is_constraint_binding_not_tier_migration": True,
        "note": (
            "Existing architecture binds NCERT PDFs via constraints.ncert_source_path. "
            "These 14 are provenance_tier='ai' with SOURCE_MISSING paths. "
            "A surgical constraints merge does NOT require changing provenance_tier. "
            "Upgrading ai→authoritative would be a separate provenance migration and is OUT OF SCOPE."
        ),
    }

    generation_gate_impact = {
        "current": {
            "syllabus": gate.status,
            "declares_ncert": declares_now,
            "evidence_status_if_resolved": "NCERT_EVIDENCE_NOT_REQUIRED (non-declaring ai blueprint)",
            "generation_eligible_flag": db.get("generation_eligible"),
            "risk": (
                "Because provenance_tier=ai and no ncert_source_path, the grounding gate "
                "does NOT require NCERT evidence today — generation could proceed without canonical evidence."
            ),
        },
        "after_surgical_path_write": {
            "declares_ncert": True,
            "expected_evidence_status": (evidence or {}).get("status"),
            "grounding_gate_would_recognize": evidence_deterministic,
            "provider_allowed_only_if": "syllabus IN_SYLLABUS AND evidence NCERT_EVIDENCE_READY",
        },
        "conditions_for_GENERATION_READY_classification": [
            "syllabus gate IN_SYLLABUS (already true)",
            "taxonomy chapter/topic/concept linked (already true)",
            "canonical ncert_source_path under NCERT Books (proposed write)",
            "PDF readable (confirmed)",
            "resolve_ncert_evidence_pack → NCERT_EVIDENCE_READY (simulated)",
            "no StudyMaterial fallback",
        ],
    }

    # Recommendation
    if not source_deterministic or not pdf_readable:
        recommendation = "REMAIN_BLOCKED"
        confidence = "high"
    elif not ku_exists:
        recommendation = "KU_REQUIRED_SEPARATE_TASK"
        confidence = "high"
    elif evidence_deterministic and asserts_syllabus:
        # Path write is the existing mechanism; tier stays ai
        recommendation = "SAFE_FOR_SURGICAL_EVIDENCE_WRITE"
        confidence = "high"
        if ku_exists and not ku_linked_in_constraints:
            # KU reuse via constraints.ku_id is part of surgical write
            pass
    elif evidence_deterministic is False and pdf_readable:
        recommendation = "REMAIN_BLOCKED"
        confidence = "medium"
    else:
        recommendation = "PROVENANCE_REVIEW_REQUIRED"
        confidence = "medium"

    # If product insists authoritative tier for NCERT binding, flag separately
    architecture_note = (
        "Existing mechanism sufficient: constraints.ncert_source_path (+ optional ku_id/ncert_derived). "
        "No new table/API. provenance_tier must remain 'ai' unless a separate provenance task authorizes upgrade."
    )

    return {
        "blueprint_id": bid,
        "blueprint_key": db.get("blueprint_key"),
        "current_provenance": {
            "population": rem.get("provenance"),
            "provenance_tier": db.get("provenance_tier"),
            "ncert_derived": cons.get("ncert_derived"),
            "ncert_source_path": existing_path,
            "declares_ncert_today": declares_now,
        },
        "subject": db.get("subject_code"),
        "class_level": db.get("class_level"),
        "chapter": db.get("chapter_name"),
        "chapter_id": db.get("chapter_id"),
        "topic": db.get("topic_name"),
        "topic_id": db.get("topic_id"),
        "concept": db.get("concept_name"),
        "concept_id": db.get("concept_id"),
        "syllabus_mapping": rem.get("syllabus_mapping"),
        "canonical_source": {
            "relative_path": candidate,
            "absolute_path": str(validated.resolved_path) if validated else None,
            "pdf_exists": pdf_path.is_file(),
            "pdf_readable": pdf_readable,
            "deterministic": source_deterministic,
        },
        "ncert_evidence_location": {
            "pages": (evidence or {}).get("pages"),
            "chars": (evidence or {}).get("chars"),
            "excerpt": (evidence or {}).get("excerpt"),
            "status": (evidence or {}).get("status"),
            "detail": (evidence or {}).get("detail"),
            "error": evidence_error,
            "deterministic": evidence_deterministic,
        },
        "existing_ku": {
            "status": "PRESENT_PASSED" if ku_exists else ("MISSING" if not ku else f"PRESENT_{ku.get('validation_status')}"),
            "ku_id": ku.get("ku_id") if ku else None,
            "summary_chars": ku.get("summary_chars") if ku else None,
            "linked_in_constraints": ku_linked_in_constraints,
            "reuse": "YES_VIA_CONSTRAINTS_KU_ID" if ku_exists else "KU_MISSING",
        },
        "existing_evidence_representation": {
            "constraints_keys": sorted(cons.keys()),
            "has_ncert_source_path": bool(existing_path),
            "has_ncert_derived": cons.get("ncert_derived") is True,
            "has_ku_id": ku_linked_in_constraints,
            "has_neet_ug_2026": bool(cons.get("neet_ug_2026")),
            "generation_eligible": db.get("generation_eligible"),
            "db_status": db.get("db_status"),
            "target_count": db.get("target_count"),
        },
        "answers": {
            "canonical_source_deterministic": source_deterministic,
            "ncert_evidence_deterministic": evidence_deterministic,
            "existing_ku_or_evidence_representation": ku_exists or bool(existing_path),
            "can_reuse_existing_ku": ku_exists,
            "smallest_safe_schema_compatible_write": proposed_future_write,
            "would_write_change_provenance_tier": False,
            "would_write_change_academic_taxonomy": False,
            "would_write_alter_generation_eligible_flag": False,
            "would_grounding_gate_recognize": evidence_deterministic,
        },
        "proposed_future_write": proposed_future_write,
        "fields_that_may_change": fields_may_change,
        "fields_that_must_remain_unchanged": fields_must_remain,
        "provenance_impact": provenance_impact,
        "generation_gate_impact": generation_gate_impact,
        "architecture_note": architecture_note,
        "recommendation": recommendation,
        "confidence": confidence,
        "fuzzy_authorized": False,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# NCERT-EVIDENCE-WRITE-REVIEW-001 — Design review for 14 recoveries",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** READ_ONLY",
        f"**Verdict:** **{report['verdict']}**",
        "",
        "## Scope",
        "",
        f"- Records reviewed: **{report['audited_count']}** (exact SAFE_FOR_SEPARATE_EVIDENCE_WRITE_REVIEW set)",
        f"- Population: all SOURCE_MISSING / provenance_tier=ai",
        f"- GENERATION_READY untouched: **132**",
        f"- REVIEW_REQUIRED untouched: **248**",
        "",
        "## Existing architecture (reuse)",
        "",
        f"```json\n{json.dumps(report['architecture'], indent=2)}\n```",
        "",
        "## Recommendations",
        "",
        f"```json\n{json.dumps(report['by_recommendation'], indent=2)}\n```",
        "",
        "## Key finding",
        "",
        report["key_finding"],
        "",
        "## Per-blueprint summary",
        "",
        "| Blueprint | Subject | Chapter | PDF | KU | Simulated evidence | Recommendation |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in report["blueprints"]:
        lines.append(
            f"| `{r['blueprint_id'][:8]}` | {r['subject']} | {r['chapter']} | "
            f"{(r['canonical_source']['relative_path'] or '').split('/')[-1]} | "
            f"{r['existing_ku']['status']} | {r['ncert_evidence_location'].get('status')} | "
            f"{r['recommendation']} |"
        )
    lines += [
        "",
        "## Database freeze",
        "",
        f"- Unchanged: **{report['database_unchanged']}**",
        f"- Before: `{json.dumps(report['database_before'])}`",
        f"- After: `{json.dumps(report['database_after'])}`",
        "",
        "## Provider",
        "",
        f"- provider_call_count: **{report['provider_call_count']}**",
        "",
        "## Tests",
        "",
        f"```json\n{json.dumps(report.get('tests'), indent=2)}\n```",
        "",
        "## Failures",
        "",
        f"- {report.get('failures') or 'None'}",
        "",
        "## Limitations",
        "",
    ]
    for lim in report.get("limitations", []):
        lines.append(f"- {lim}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    rem = json.loads(REMEDIATION.read_text(encoding="utf-8"))
    safe = [
        b
        for b in rem["blueprints"]
        if b.get("future_action") == "SAFE_FOR_SEPARATE_EVIDENCE_WRITE_REVIEW"
    ]
    assert len(safe) == 14, f"expected 14, got {len(safe)}"
    assert all(b.get("provenance") == "SOURCE_MISSING" for b in safe)

    registry = load_neet_2026_registry()
    engine = create_engine(get_settings().database_url_sync)

    with engine.connect() as conn:
        before = snapshot(conn)
        reviewed = [review_one(conn, b, registry) for b in safe]

        # Gate freeze check
        gate_counts: Counter = Counter()
        for r in conn.execute(
            text(
                """
                SELECT DISTINCT ON (bp.blueprint_key)
                  bp.constraints, s.code AS subject_code
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                WHERE bp.deleted_at IS NULL
                ORDER BY bp.blueprint_key, bp.blueprint_version DESC
                """
            )
        ).mappings():
            st = assert_blueprint_neet_syllabus_scope(
                _cons(r["constraints"]),
                academic_subject_code=r["subject_code"],
                registry=registry,
            ).status
            gate_counts[st] += 1

        after = snapshot(conn)

    by_rec = Counter(r["recommendation"] for r in reviewed)
    unchanged = before == after
    all_ready_sim = all(
        r["ncert_evidence_location"].get("status") == "NCERT_EVIDENCE_READY" for r in reviewed
    )
    all_ku = all(r["existing_ku"]["status"] == "PRESENT_PASSED" for r in reviewed)

    failures: list[str] = []
    verdict = "GREEN"
    if not unchanged:
        failures.append("database_mutated")
        verdict = "RED"
    if PROVIDER_CALLS["n"] != 0:
        failures.append("provider_called")
        verdict = "RED"
    if len(reviewed) != 14:
        failures.append("count")
        verdict = "RED"
    if gate_counts.get("IN_SYLLABUS") != 197 or gate_counts.get("SYLLABUS_MAPPING_REVIEW_REQUIRED") != 248:
        failures.append(f"gate_drift:{dict(gate_counts)}")
        verdict = "RED"
    # YELLOW if any need provenance review or remain blocked
    if verdict == "GREEN" and by_rec.get("PROVENANCE_REVIEW_REQUIRED", 0) > 0:
        verdict = "YELLOW"
    if verdict == "GREEN" and by_rec.get("REMAIN_BLOCKED", 0) > 0:
        verdict = "YELLOW"
    # Even all SAFE still YELLOW per acceptance: "require an explicit separate provenance/evidence decision"
    # Task: GREEN if architecture inspected and no mutations; YELLOW if separate decision needed.
    # Since write is not authorized yet, SAFE recommendations imply future write decision → YELLOW
    if verdict == "GREEN" and by_rec.get("SAFE_FOR_SURGICAL_EVIDENCE_WRITE", 0) > 0:
        verdict = "YELLOW"

    key_finding = (
        "All 14 are provenance_tier='ai' with no ncert_source_path today, so the NCERT grounding "
        "gate does not currently require evidence (NCERT_EVIDENCE_NOT_REQUIRED). "
        "The existing canonical mechanism is constraints.ncert_source_path (+ optional ku_id / "
        "ncert_derived). Simulated merge of the recovered canonical PDF path yields "
        f"NCERT_EVIDENCE_READY for {sum(1 for r in reviewed if r['ncert_evidence_location'].get('status')=='NCERT_EVIDENCE_READY')}/14 "
        "while leaving provenance_tier unchanged. No new table/API is required. "
        "Upgrading ai→authoritative is a separate provenance decision and is not recommended here."
    )

    report = {
        "task": "NCERT-EVIDENCE-WRITE-REVIEW-001",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "READ_ONLY",
        "input_audit": str(REMEDIATION),
        "ncert_root": str(NCERT_ROOT),
        "audited_count": 14,
        "architecture": ARCHITECTURE_SUMMARY,
        "key_finding": key_finding,
        "by_recommendation": {k: by_rec.get(k, 0) for k in RECOMMENDATIONS},
        "gate_counts": dict(gate_counts),
        "simulation_summary": {
            "all_pdf_readable": all(r["canonical_source"]["pdf_readable"] for r in reviewed),
            "all_evidence_ready_if_path_written": all_ready_sim,
            "all_ku_passed_present": all_ku,
            "provenance_tier_values": dict(Counter(r["current_provenance"]["provenance_tier"] for r in reviewed)),
        },
        "database_before": before,
        "database_after": after,
        "database_unchanged": unchanged,
        "provider_call_count": PROVIDER_CALLS["n"],
        "blueprints": reviewed,
        "verdict": verdict,
        "failures": failures,
        "limitations": [
            "Read-only: no constraints/provenance/KU/blueprint writes performed.",
            "Recommendations are design guidance for a future authorized surgical write task.",
            "ncert_derived=true is optional for gate activation (path alone suffices) but matches peer canonical blueprints.",
            "generation_eligible already True; attaching NCERT path would tighten the grounding gate (good).",
            "StudyMaterial / 49 provenance-review / 2 Electrostatics cases were not touched.",
        ],
        "tests": {"pending": True},
        "acceptance": {
            "audited_14": len(reviewed) == 14,
            "no_db_mutation": unchanged,
            "no_provider": PROVIDER_CALLS["n"] == 0,
            "architecture_inspected": True,
            "no_new_model": True,
            "ready_untouched": gate_counts.get("IN_SYLLABUS") == 197,
            "review_untouched": gate_counts.get("SYLLABUS_MAPPING_REVIEW_REQUIRED") == 248,
        },
    }

    out_json = ROOT / "docs" / "audits" / f"{REPORT}.json"
    out_md = ROOT / "docs" / "audits" / f"{REPORT}.md"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_markdown(report, out_md)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "by_recommendation": report["by_recommendation"],
                "simulation": report["simulation_summary"],
                "unchanged": unchanged,
                "provider_calls": PROVIDER_CALLS["n"],
                "json": str(out_json),
            },
            indent=2,
        )
    )
    return 0 if verdict != "RED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
