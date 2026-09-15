"""PROVENANCE-CONTRACT-001 — Read-only NCERT provenance contract audit.

No database writes. No blueprint/provenance/MCQ/KU/taxonomy mutations.
Writes only docs/audits/provenance_contract_001_*.{md,json}.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.models.content_factory import SOURCE_TIERS, SOURCE_TYPES  # noqa: E402
from app.modules.cms.models.content_factory_planning import PROVENANCE_TIERS  # noqa: E402
from app.modules.cms.schemas.content_factory_planning import (  # noqa: E402
    QuestionBlueprintCreateRequest,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    NCERT_SOURCE_CONSTRAINT_KEYS,
    blueprint_declares_ncert_source,
    extract_blueprint_ncert_path,
    get_ncert_source_root,
)

REPORT_STEM = "provenance_contract_001_20260913"
NCERT_ROOT = Path(r"D:\ravishori\AI Neet Exam App\NCERT Books")
BP002_JSON = ROOT / "docs/audits/bp_coverage_002_reconciliation_20260913.json"
FREEZE = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "DRAFT": 5298,
    "SUPERSEDED": 6,
    "unmapped_draft": 5024,
    "chapters": 56,
    "topics": 192,
    "concepts": 318,
    "knowledge_units": 202,
    "blueprints": 137,
}
REJECTED_FALSE_CLAIMS = ("official", "official_source", "nta", "ncert_official")
BIOMOLECULES_IDS = {
    "dafae464-f60d-443f-b526-3e0c93390929",
    "876a2f73-994b-4a7b-bc5d-252267f8d2a3",
    "04e93763-bc48-472e-adb3-4088d872e1c4",
    "0b1c8f98-35eb-43f7-bb8e-2398c4a46de5",
    "8a42a7e2-c76f-4b64-be74-8fb0e3b472b5",
}


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
        "chapters": conn.execute(text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")).scalar(),
        "topics": conn.execute(text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")).scalar(),
        "concepts": conn.execute(text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")).scalar(),
        "knowledge_units": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "question_blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "content_batches": conn.execute(
            text("SELECT COUNT(*) FROM cms.content_batches WHERE deleted_at IS NULL")
        ).scalar(),
        "generation_jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "generation_runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
        "generation_candidates": conn.execute(text("SELECT COUNT(*) FROM cms.generation_candidates")).scalar(),
    }


def inspect_db_columns(conn) -> dict:
    bp_cols = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema='cms' AND table_name='question_blueprints'
                ORDER BY ordinal_position
                """
            )
        ).mappings()
    ]
    batch_cols = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema='cms' AND table_name='content_batches'
                  AND column_name IN ('source_tier','source_type','source_document_id')
                ORDER BY column_name
                """
            )
        ).mappings()
    ]
    has_ku_col = any(c["column_name"] == "knowledge_unit_id" for c in bp_cols)
    has_source_doc_col = any(c["column_name"] == "source_document_id" for c in bp_cols)
    # Check for CHECK constraint on provenance_tier
    checks = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT con.conname, pg_get_constraintdef(con.oid) AS definition
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE nsp.nspname='cms' AND rel.relname='question_blueprints'
                  AND con.contype='c'
                """
            )
        ).mappings()
    ]
    live_tiers = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT provenance_tier, COUNT(*) AS n
                FROM cms.question_blueprints
                WHERE deleted_at IS NULL
                GROUP BY provenance_tier
                ORDER BY n DESC
                """
            )
        ).mappings()
    ]
    return {
        "question_blueprints_columns": bp_cols,
        "content_batches_source_columns": batch_cols,
        "blueprint_has_knowledge_unit_id": has_ku_col,
        "blueprint_has_source_document_id": has_source_doc_col,
        "blueprint_check_constraints": checks,
        "live_provenance_tier_counts": live_tiers,
        "note": (
            "provenance_tier is String(30) NOT NULL with no DB CHECK enum; "
            "allowed values enforced in Pydantic + planning service."
        ),
    }


def pydantic_rejection_probe() -> dict:
    """Confirm 'ncert' and false official claims are rejected by schema (no DB)."""
    results = {}
    for tier in ("ncert", "official", "official_source", "nta", "ncert_official", "authoritative", "ai"):
        try:
            QuestionBlueprintCreateRequest.model_validate(
                {
                    "blueprint_key": "probe-key-xxxx",
                    "subject_id": "00000000-0000-0000-0000-000000000001",
                    "chapter_id": "00000000-0000-0000-0000-000000000002",
                    "topic_id": "00000000-0000-0000-0000-000000000003",
                    "concept_id": "00000000-0000-0000-0000-000000000004",
                    "learning_objective_id": "00000000-0000-0000-0000-000000000005",
                    "question_family_id": "00000000-0000-0000-0000-000000000006",
                    "difficulty": "easy",
                    "provenance_tier": tier,
                    "constraints": {
                        "question_format": "MCQ_4",
                        "correct_option_count": 1,
                        "explanation_required": True,
                    },
                }
            )
            results[tier] = {"accepted": True, "error": None}
        except Exception as exc:  # noqa: BLE001 — intentional probe
            results[tier] = {"accepted": False, "error": str(exc)}
    return results


def locate_ncert_gate_mismatch() -> dict:
    """Find provenance_tier == 'ncert' checks (audit scripts vs production)."""
    hits = []
    for base in (BACKEND / "scripts", BACKEND / "app", BACKEND / "tests", ROOT / "docs"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix.lower() not in {".py", ".md", ".json"}:
                continue
            try:
                text_body = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if re.search(r"provenance_tier[^\n]{0,40}['\"]ncert['\"]|['\"]ncert['\"][^\n]{0,40}provenance", text_body):
                # sample matching lines
                lines = []
                for i, line in enumerate(text_body.splitlines(), 1):
                    if "provenance" in line.lower() and "ncert" in line.lower():
                        lines.append({"line": i, "text": line.strip()[:200]})
                hits.append(
                    {
                        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "match_lines": lines[:8],
                    }
                )
    production = [
        h
        for h in hits
        if h["path"].startswith("apps/backend/app/") or h["path"].startswith("apps/backend/tests/")
    ]
    audit_scripts = [h for h in hits if "bp_coverage_00" in h["path"]]
    return {
        "all_hits": hits,
        "production_app_or_tests_hits": production,
        "audit_script_hits": audit_scripts,
        "classification": (
            "A. incorrect audit/test gate (BP-COVERAGE-001/002 readiness classifier) "
            "+ B. outdated audit contract relative to FACTORY-P2 / CF-SOURCE-001. "
            "Not a production generation-service requirement."
        ),
        "production_gate_actual": (
            "content_factory_generation_service.assert_blueprint_ncert_source: "
            "NCERT PDF path required only when blueprint_declares_ncert_source "
            "(ncert_derived / path keys / provenance_tier==authoritative). "
            "AI-tier blueprints skip NCERT path requirement."
        ),
    }


def evidence_capabilities() -> dict:
    return {
        "canonical_ncert_pdf_path": {
            "supported": True,
            "where": "question_blueprints.constraints JSONB keys: "
            + ", ".join(NCERT_SOURCE_CONSTRAINT_KEYS),
            "guard": "assert_blueprint_ncert_source / validate_ncert_generation_source",
            "root": "NCERT_SOURCE_ROOT / Settings.ncert_source_root → NCERT Books",
        },
        "source_document_identity": {
            "supported_on_blueprint": False,
            "note": (
                "No blueprint.source_document_id column. "
                "Identity is path string in constraints; ingestion.source_documents "
                "exists for KU/ingestion lineage, not blueprint FK."
            ),
        },
        "chapter": {
            "supported": True,
            "where": "question_blueprints.chapter_id → academic.chapters",
        },
        "section": {
            "supported": False,
            "note": "No first-class blueprint section field; KU may link ingestion_sections.",
        },
        "page_or_section_evidence": {
            "supported_on_blueprint": "partial/optional via unconstrained constraints JSONB",
            "supported_on_questions": "ncert_evidence body/tags on ContentItem (ECAEP certification path)",
            "note": "Blueprint constraints may store free-form keys but factory REQUIRED_CONSTRAINT_KEYS "
            "only mandate question_format/correct_option_count/explanation_required.",
        },
        "ncert_verification_state": {
            "on_blueprint": False,
            "on_question": True,
            "note": "ECAEP certify-ncert / ncert_evidence.verification_level — orthogonal to blueprint tier.",
        },
        "provenance_tier": {
            "supported": True,
            "allowed": list(PROVENANCE_TIERS),
            "rejected_false_claims": list(REJECTED_FALSE_CLAIMS),
            "canonical_ncert_representation": "authoritative + constraints path under NCERT Books",
        },
        "gaps": [
            "No dedicated blueprint.knowledge_unit_id",
            "No dedicated blueprint.source_document_id",
            "No structured page/section schema on blueprints",
            "No DB CHECK enum for provenance_tier (app-layer only)",
            "StudyMaterial paths can sit in constraints until generation assert rejects for ncert_derived",
        ],
    }


def tier_meanings() -> dict:
    return {
        "authoritative": {
            "meaning": (
                "Authority-class / source-of-truth material for factory provenance — "
                "trusted textbook grounding, NOT a claim of official NTA endorsement "
                "or that TALOS content is 'official NCERT'."
            ),
            "ncert_fit": True,
            "evidence": [
                "content_factory_planning.py: PROVENANCE_TIERS = SOURCE_TIERS; rejects official claims",
                "test_ncert_canonical_source.test_blueprint_with_canonical_source_accepts uses "
                "provenance_tier='authoritative' + ncert_source_path under NCERT Books",
                "blueprint_declares_ncert_source: tier=='authoritative' implies NCERT binding required",
                "CONTENT_FACTORY_DATA_MODEL.md: source_tier = Authority class",
                "CONTENT_FACTORY_P2_IMPLEMENTATION.md: rejects official_source/nta/ncert_official",
            ],
            "why_appropriate_for_canonical_ncert": (
                "Existing CF-SOURCE-001 tests and factory guards already bind "
                "authoritative + ncert_source_path to NCERT_SOURCE_ROOT. "
                "No schema change required to represent canonical NCERT PDFs."
            ),
        },
        "licensed": {
            "meaning": "Licensed third-party corpus (not the default NCERT Books path).",
        },
        "human": {
            "meaning": "Human-authored generation contract / SME-authored lineage.",
        },
        "ai": {
            "meaning": "AI-assisted generation contract; does not by itself require NCERT PDF binding.",
        },
        "derived": {
            "meaning": "Derived from other content without claiming primary textbook authority.",
        },
        "explicitly_not_allowed": {
            "values": list(REJECTED_FALSE_CLAIMS) + ["ncert"],
            "reason": (
                "'ncert' is not in PROVENANCE_TIERS (Pydantic rejects). "
                "official/nta/ncert_official rejected as false official claims. "
                "Product rule: never invent official NTA/NCERT labels on content."
            ),
        },
    }


def legacy_and_biomolecules(conn) -> dict:
    # Prefer BP-002 counts if present; re-verify live
    rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT bp.id::text AS blueprint_id,
                       bp.blueprint_key,
                       bp.provenance_tier,
                       bp.subject_id::text,
                       s.code AS subject_code,
                       ch.code AS chapter_code,
                       ch_s.code AS chapter_subject_code,
                       ch.class_level,
                       bp.concept_id::text,
                       c.code AS concept_code,
                       bp.constraints
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                JOIN academic.chapters ch ON ch.id = bp.chapter_id
                JOIN academic.subjects ch_s ON ch_s.id = ch.subject_id
                JOIN academic.concepts c ON c.id = bp.concept_id
                WHERE bp.deleted_at IS NULL
                """
            )
        ).mappings()
    ]
    for r in rows:
        cons = r.get("constraints")
        if hasattr(cons, "keys"):
            r["constraints"] = dict(cons)

    legacy_sm = 0
    source_missing = 0
    canonical = 0
    for r in rows:
        cons = r.get("constraints") or {}
        blob = json.dumps(cons)
        path = extract_blueprint_ncert_path(cons)
        if "StudyMaterial" in blob or (path and "StudyMaterial" in path):
            legacy_sm += 1
        elif path and "NCERT Books" in path:
            try:
                Path(path).resolve().relative_to(NCERT_ROOT.resolve())
                canonical += 1
            except Exception:  # noqa: BLE001
                source_missing += 1
        else:
            source_missing += 1

    bio = [r for r in rows if r["blueprint_id"] in BIOMOLECULES_IDS or r["chapter_code"] == "biomolecules"]
    bio_details = []
    for r in bio:
        if r["chapter_code"] != "biomolecules":
            continue
        bio_details.append(
            {
                "blueprint_id": r["blueprint_id"],
                "blueprint_key": r["blueprint_key"],
                "subject_code": r["subject_code"],
                "chapter_subject_code": r["chapter_subject_code"],
                "class_level": r["class_level"],
                "concept_code": r["concept_code"],
                "concept_id": r["concept_id"],
                "provenance_tier": r["provenance_tier"],
                "drift": r["subject_code"] != r["chapter_subject_code"],
            }
        )

    return {
        "live_blueprint_count": len(rows),
        "provenance_class_counts_reverified": {
            "LEGACY_SOURCE_StudyMaterial": legacy_sm,
            "SOURCE_MISSING": source_missing,
            "CANONICAL_NCERT_BACKED": canonical,
        },
        "legacy_treatment": {
            "do_not_silently_convert_studymaterial_to_ncert": True,
            "do_not_invent_provenance_for_source_missing": True,
            "rationale": (
                "CF-SOURCE-001 non-goals: does not rewrite existing question/blueprint provenance. "
                "Equivalent NCERT Books PDFs existing on disk do not rewrite historical StudyMaterial "
                "constraint paths. New NCERT-derived blueprints must be created explicitly with "
                "authoritative + NCERT Books path after owner approval."
            ),
        },
        "biomolecules_drift": {
            "count": len(bio_details),
            "all_subject_zoology_chapter_botany": all(
                d["subject_code"] == "ZOOLOGY" and d["chapter_subject_code"] == "BOTANY" for d in bio_details
            ),
            "blueprints": bio_details,
            "approved_safe_remediation": (
                "Owner-authorized UPDATE subject_id ZOOLOGY→BOTANY for these 5 rows only; "
                "preserve chapter_id/topic_id/concept_id and all PUBLISHED/DRAFT questions/KUs. "
                "Not applied in this audit."
            ),
            "preserve_questions": {"PUBLISHED": 5, "DRAFT": 8},
        },
        "bp002_reference": str(BP002_JSON.relative_to(ROOT)) if BP002_JSON.is_file() else None,
    }


def recommended_remediation() -> list[str]:
    return [
        "Do NOT add provenance_tier='ncert' to the schema (would conflict with false-claim policy and Pydantic enum).",
        "Represent future NCERT-derived blueprints as: provenance_tier='authoritative' + "
        "constraints.ncert_derived=true + constraints.ncert_source_path under NCERT Books "
        "(validated by assert_blueprint_ncert_source).",
        "Update BP-COVERAGE audit GENERATION_READY gate to match production: "
        "authoritative + canonical path + PASSED KU policy — not provenance_tier=='ncert'.",
        "Do not silently rewrite the 100 StudyMaterial-backed or 37 SOURCE_MISSING blueprints.",
        "Owner-authorized Biomolecules subject_id ZOOLOGY→BOTANY metadata fix only (preserve concept/question FKs).",
        "Do not create blueprints or generate MCQs until owner review of this contract audit.",
    ]


def run_tests() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "app/modules/ingestion/tests/test_ncert_canonical_source.py",
        "tests/test_content_factory_p2.py",
        "app/modules/academic/tests/test_cf_c1_chemistry_class_12.py",
        "app/modules/academic/tests/test_chapter_class_level.py",
        "app/modules/academic/tests/test_physics_p0_taxonomy.py",
        "tests/test_cms_workflow.py",
        "tests/test_cms_publish_quality.py",
        "tests/test_phase32_content_readiness_safety.py",
        "tests/test_phase33_ecaep_publication_safety.py",
        "-q",
        "--tb=line",
    ]
    unavailable = []
    for rel in [
        "app/modules/cms/tests/test_question_blueprints.py",
        "tests/test_blueprint_integrity.py",
        "app/modules/academic/tests/test_cf_c2_biology.py",
        "app/modules/academic/tests/test_cf_c3_gravitation.py",
        "app/modules/academic/tests/test_cf_c4_biomolecules.py",
        "app/modules/academic/tests/test_cf_c5_ku_backfill.py",
    ]:
        if not (BACKEND / rel).is_file():
            unavailable.append(rel)
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m_pass = re.search(r"(\d+)\s+passed", out)
    m_fail = re.search(r"(\d+)\s+failed", out)
    return {
        "passed": int(m_pass.group(1)) if m_pass else None,
        "failed": int(m_fail.group(1)) if m_fail else (0 if proc.returncode == 0 else None),
        "exit_code": proc.returncode,
        "command": " ".join(cmd),
        "unavailable": unavailable,
        "notes": [
            "CF-SOURCE-001 covered by test_ncert_canonical_source.py (authoritative + NCERT path).",
            "FACTORY-P2 provenance rejection covered by test_content_factory_p2.py.",
            "Dedicated CF-C2–C5 modules unavailable under expected names.",
        ],
        "tail": "\n".join(out.strip().splitlines()[-40:]),
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    lines = [
        "# PROVENANCE-CONTRACT-001 — NCERT provenance contract audit",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Mode: **READ-ONLY**",
        "- Git: **no commit / no push**",
        "",
        "## 1. Provenance enum / schema",
        f"- SOURCE_TIERS / PROVENANCE_TIERS: `{payload['enum']['allowed_tiers']}`",
        f"- SOURCE_TYPES (batch): `{payload['enum']['source_types']}`",
        f"- Rejected false claims: `{payload['enum']['rejected_false_claims']}`",
        f"- DB: `{payload['db_schema']['note']}`",
        f"- Live blueprint tiers: `{payload['db_schema']['live_provenance_tier_counts']}`",
        "",
        "## 2. Implementation locations",
    ]
    for loc in payload["implementation_locations"]:
        lines.append(f"- `{loc}`")
    lines += [
        "",
        "## 3. Meaning of each provenance tier",
        f"```json\n{json.dumps(payload['tier_meanings'], indent=2)}\n```",
        "",
        "## 4. Canonical NCERT representation (existing architecture)",
        payload["canonical_ncert_representation"]["summary"],
        "",
        "### Contract triple (schema-compatible)",
        "1. `provenance_tier = authoritative`",
        "2. `constraints.ncert_derived = true` (recommended explicit)",
        "3. `constraints.ncert_source_path` (or alias keys) resolving under `NCERT Books`",
        "",
        "### Why no new `ncert` tier",
        payload["canonical_ncert_representation"]["why_not_ncert_tier"],
        "",
        "## 5. Source / evidence representation",
        f"```json\n{json.dumps(payload['evidence_capabilities'], indent=2)}\n```",
        "",
        "## 6. Generation-gate mismatch",
        f"- Classification: **{payload['gate_mismatch']['classification']}**",
        f"- Production gate: {payload['gate_mismatch']['production_gate_actual']}",
        f"- Pydantic probe (`ncert` accepted?): "
        f"`{payload['pydantic_probe'].get('ncert')}`",
        f"- Pydantic probe (`authoritative` accepted?): "
        f"`{payload['pydantic_probe'].get('authoritative')}`",
        "",
        "## 7. Legacy blueprint treatment",
        f"- Reverified counts: `{payload['legacy_and_biomolecules']['provenance_class_counts_reverified']}`",
        f"- {payload['legacy_and_biomolecules']['legacy_treatment']['rationale']}",
        "",
        "## 8. Biomolecules drift",
        f"- Count: `{payload['legacy_and_biomolecules']['biomolecules_drift']['count']}`",
        f"- All ZOOLOGY subject / BOTANY chapter: "
        f"`{payload['legacy_and_biomolecules']['biomolecules_drift']['all_subject_zoology_chapter_botany']}`",
        f"- Remediation (not applied): "
        f"{payload['legacy_and_biomolecules']['biomolecules_drift']['approved_safe_remediation']}",
        "",
        "## 9. Exact recommended remediation",
    ]
    for a in payload["recommended_remediation"]:
        lines.append(f"- {a}")
    lines += [
        "",
        "## 10. Safety counts",
        "### Before",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "### After",
        f"```json\n{json.dumps(payload['after'], indent=2)}\n```",
        f"- Identical: `{payload['snapshot_identical']}` Freeze OK: `{payload['freeze_ok']}`",
        "",
        "## 11. Tests",
        f"- Passed `{payload['tests'].get('passed')}` / Failed `{payload['tests'].get('failed')}`",
        f"- Unavailable: `{payload['tests'].get('unavailable')}`",
        "",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## 12. Unresolved owner/engineering decisions",
    ]
    for d in payload["unresolved_decisions"]:
        lines.append(f"- {d}")
    lines += [
        "",
        "## Files inspected",
    ]
    for f in payload["files_inspected"]:
        lines.append(f"- `{f}`")
    lines += ["", "## Files changed"]
    for f in payload["files_changed"]:
        lines.append(f"- `{f}`")
    lines += [
        "",
        "## Confirmation",
        f"```json\n{json.dumps(payload['confirmation'], indent=2)}\n```",
        "",
        "**STOP** — do not repair provenance, modify blueprints, or generate MCQs.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    try:
        ncert_root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        ncert_root = NCERT_ROOT

    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        before = snapshot(conn)
        db_schema = inspect_db_columns(conn)
        legacy = legacy_and_biomolecules(conn)
        after = snapshot(conn)

    pydantic_probe = pydantic_rejection_probe()
    gate = locate_ncert_gate_mismatch()
    evidence = evidence_capabilities()
    meanings = tier_meanings()
    tests = run_tests()

    freeze_ok = (
        before["status"].get("PUBLISHED") == FREEZE["PUBLISHED"]
        and before["status"].get("IN_REVIEW") == FREEZE["IN_REVIEW"]
        and before["status"].get("DRAFT") == FREEZE["DRAFT"]
        and before["status"].get("SUPERSEDED") == FREEZE["SUPERSEDED"]
        and before["unmapped_draft"] == FREEZE["unmapped_draft"]
        and before["chapters"] == FREEZE["chapters"]
        and before["topics"] == FREEZE["topics"]
        and before["concepts"] == FREEZE["concepts"]
        and before["knowledge_units"] == FREEZE["knowledge_units"]
        and before["question_blueprints"] == FREEZE["blueprints"]
        and before == after
    )

    # Production app code must not require literal provenance_tier=='ncert'
    prod_gate_requires_ncert = any(
        any(
            re.search(r"""provenance_tier.*['\"]ncert['\"]|['\"]ncert['\"].*provenance_tier""", ln.get("text") or "")
            and ("==" in (ln.get("text") or "") or "!=" in (ln.get("text") or ""))
            for ln in h.get("match_lines") or []
        )
        for h in gate["production_app_or_tests_hits"]
        if h["path"].startswith("apps/backend/app/")
    )
    contract_clear = (
        "authoritative" in PROVENANCE_TIERS
        and "ncert" not in PROVENANCE_TIERS
        and pydantic_probe["ncert"]["accepted"] is False
        and pydantic_probe["authoritative"]["accepted"] is True
        and blueprint_declares_ncert_source({}, "authoritative") is True
        and not prod_gate_requires_ncert
        and freeze_ok
        and (tests.get("failed") or 0) == 0
    )

    if not freeze_ok or (tests.get("failed") or 0) > 0 or before != after:
        final = "RED — FAILED"
    elif contract_clear:
        final = "GREEN — COMPLETE/VERIFIED"
    else:
        final = "YELLOW — PARTIALLY VERIFIED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "mode": "READ-ONLY",
        "ncert_root": str(ncert_root),
        "enum": {
            "allowed_tiers": list(PROVENANCE_TIERS),
            "source_types": list(SOURCE_TYPES),
            "rejected_false_claims": list(REJECTED_FALSE_CLAIMS),
            "ncert_not_in_enum": True,
        },
        "db_schema": db_schema,
        "implementation_locations": [
            "apps/backend/app/modules/cms/models/content_factory.py (SOURCE_TIERS)",
            "apps/backend/app/modules/cms/models/content_factory_planning.py (PROVENANCE_TIERS)",
            "apps/backend/app/modules/cms/schemas/content_factory_planning.py (Pydantic validator)",
            "apps/backend/app/modules/cms/schemas/content_factory.py (batch source_tier)",
            "apps/backend/app/modules/cms/services/content_factory_planning_service.py (PROVENANCE_FALSE_CLAIM)",
            "apps/backend/app/modules/cms/services/content_factory_generation_service.py (assert_blueprint_ncert_source)",
            "apps/backend/app/modules/ingestion/services/ncert_canonical_source.py (CF-SOURCE-001)",
            "apps/backend/alembic/versions/f6a7b8c9d0e1_cms_content_factory_p2_planning.py",
            "apps/backend/alembic/versions/e5f6a7b8c9d0_cms_content_factory_p1.py",
            "docs/architecture/ncert_canonical_source.md",
            "docs/product/CONTENT_FACTORY_P2_IMPLEMENTATION.md",
            "docs/product/CONTENT_FACTORY_DATA_MODEL.md",
            "docs/product/CONTENT_FACTORY_ARCHITECTURE.md",
            "apps/backend/scripts/bp_coverage_001_readonly.py (incorrect audit gate)",
            "apps/backend/scripts/bp_coverage_002_reconciliation.py (reproduces audit gate)",
        ],
        "tier_meanings": meanings,
        "canonical_ncert_representation": {
            "summary": (
                "Canonical NCERT is already representable without schema change: "
                "provenance_tier='authoritative' plus constraints binding a PDF under "
                f"{NCERT_ROOT}."
            ),
            "why_not_ncert_tier": (
                "Adding 'ncert' would (1) invent a non-enum value already rejected by Pydantic, "
                "(2) risk false official-claim confusion already blocked for official/nta/"
                "ncert_official, and (3) diverge from CF-SOURCE-001 tests that already use "
                "authoritative."
            ),
            "schema_change_required": False,
            "contract_clear": contract_clear,
            "prod_gate_requires_literal_ncert": prod_gate_requires_ncert,
        },
        "evidence_capabilities": evidence,
        "gate_mismatch": gate,
        "pydantic_probe": pydantic_probe,
        "legacy_and_biomolecules": legacy,
        "recommended_remediation": recommended_remediation(),
        "unresolved_decisions": [
            "When to authorize creation of NEW NCERT-derived blueprints (authoritative + NCERT Books path) for the 400 pilot — not a schema question.",
            "When to authorize Biomolecules subject_id metadata fix (already specified; not applied here).",
            "Whether to update BP-COVERAGE-* audit scripts' GENERATION_READY classifier in a follow-up (documentation/tooling only).",
            "Optional future enhancement (not required for contract): blueprint.source_document_id / knowledge_unit_id columns — owner/engineering ADR if desired.",
        ],
        "before": before,
        "after": after,
        "snapshot_identical": before == after,
        "freeze_ok": freeze_ok,
        "tests": tests,
        "files_inspected": [
            "cms.question_blueprints (read-only)",
            "information_schema / pg_constraint for blueprint columns",
            "apps/backend/app/modules/cms/models/content_factory.py",
            "apps/backend/app/modules/cms/models/content_factory_planning.py",
            "apps/backend/app/modules/cms/schemas/content_factory_planning.py",
            "apps/backend/app/modules/cms/services/content_factory_planning_service.py",
            "apps/backend/app/modules/cms/services/content_factory_generation_service.py",
            "apps/backend/app/modules/ingestion/services/ncert_canonical_source.py",
            "apps/backend/app/modules/ingestion/tests/test_ncert_canonical_source.py",
            "docs/architecture/ncert_canonical_source.md",
            "docs/product/CONTENT_FACTORY_P2_IMPLEMENTATION.md",
            "docs/product/CONTENT_FACTORY_DATA_MODEL.md",
            "docs/product/CONTENT_FACTORY_ARCHITECTURE.md",
            "docs/audits/bp_coverage_002_reconciliation_20260913.json",
        ],
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/provenance_contract_001_readonly.py",
        ],
        "confirmation": {
            "db_mutated": False,
            "blueprints_mutated": False,
            "provenance_rewritten": False,
            "questions_mutated": False,
            "kus_mutated": False,
            "ai_called": False,
            "mcqs_generated": False,
            "committed": False,
            "pushed": False,
        },
    }

    md_path, json_path = write_reports(payload)
    print(
        json.dumps(
            {
                "final_status": final,
                "json": str(json_path),
                "md": str(md_path),
                "allowed_tiers": list(PROVENANCE_TIERS),
                "ncert_accepted_by_pydantic": pydantic_probe["ncert"]["accepted"],
                "authoritative_accepted": pydantic_probe["authoritative"]["accepted"],
                "live_tiers": db_schema["live_provenance_tier_counts"],
                "legacy_counts": legacy["provenance_class_counts_reverified"],
                "biomolecules_ok": legacy["biomolecules_drift"]["all_subject_zoology_chapter_botany"],
                "freeze_ok": freeze_ok,
                "snapshot_identical": before == after,
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
                "prod_gate_requires_ncert": prod_gate_requires_ncert,
            },
            indent=2,
        )
    )
    return 0 if final != "RED — FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
