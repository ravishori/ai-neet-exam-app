"""BP-COVERAGE-003 — Fresh NCERT blueprint coverage audit (read-only).

Post KU-OWNER-REMEDIATION-001 (+11 NCERT KUs). Uses production eligibility:
- NCERT KU via ingestion job path under NCERT Books
- BP-CREATE-001 gate: exactly 1 NCERT PASSED KU + no authoritative BP
- Canonical NCERT BP contract via assert_blueprint_ncert_source
  (authoritative + ncert_derived + path under NCERT Books)

No database mutations. Writes only docs/audits/bp_coverage_003_*.{md,json}.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    NcertSourceError,
    assert_blueprint_ncert_source,
    blueprint_declares_ncert_source,
    extract_blueprint_ncert_path,
    get_ncert_source_root,
)

REPORT_STEM = "bp_coverage_003_20260913"
EXPECTED = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "DRAFT": 5298,
    "SUPERSEDED": 6,
    "unmapped_draft": 5024,
    "chapters": 56,
    "topics": 192,
    "concepts": 318,
    "knowledge_units": 381,
    "blueprints": 266,
    "studymaterial_path_kus": 73,
    "digestion_kus": 0,
}
EXCLUDED_CHAPTERS = frozenset({"digestion-absorption"})
SUBJECTS = ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY")
TARGET_COUNT_PROJECTED = 2
SUBJECT_PILOT_TARGET = 100
PILOT_TOTAL_TARGET = 400

TAXONOMY_REVIEW_CODES = frozenset(
    {
        "sv2c-zoology-12",
        "sv2c-zoology-15",
        "sv2c-zoology-08",
        "sv2c-zoology-05",
        "sv2c-botany-14",
        "sv2c-botany-02",
        "sv2c-chemistry-04",
        "sv2c-chemistry-14",
        "sv2c-chemistry-34",
        "sv2c-chemistry-19",
    }
)
BOTANY_DUP_PAIR = ("sv2c-botany-15", "syngamy-and-triple-fusion")


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
        "studymaterial_path_kus": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                WHERE ku.deleted_at IS NULL
                  AND coalesce(j.source_file_path, '') LIKE '%StudyMaterial%'
                """
            )
        ).scalar(),
        "digestion_kus": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                JOIN academic.concepts c ON c.id = ku.concept_id
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                WHERE ch.code = 'digestion-absorption' AND ku.deleted_at IS NULL
                """
            )
        ).scalar(),
        "concepts_with_ncert_ku": conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT ku.concept_id) FROM knowledge.knowledge_units ku
                JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                WHERE ku.deleted_at IS NULL AND ku.validation_status = 'PASSED'
                  AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%'
                """
            )
        ).scalar(),
        "authoritative_blueprints": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.question_blueprints
                WHERE deleted_at IS NULL AND provenance_tier = 'authoritative'
                """
            )
        ).scalar(),
    }


def freeze_ok(snap: dict) -> bool:
    return (
        snap["status"].get("PUBLISHED") == EXPECTED["PUBLISHED"]
        and snap["status"].get("IN_REVIEW") == EXPECTED["IN_REVIEW"]
        and snap["status"].get("DRAFT") == EXPECTED["DRAFT"]
        and snap["status"].get("SUPERSEDED") == EXPECTED["SUPERSEDED"]
        and snap["unmapped_draft"] == EXPECTED["unmapped_draft"]
        and snap["chapters"] == EXPECTED["chapters"]
        and snap["topics"] == EXPECTED["topics"]
        and snap["concepts"] == EXPECTED["concepts"]
        and snap["knowledge_units"] == EXPECTED["knowledge_units"]
        and snap["question_blueprints"] == EXPECTED["blueprints"]
        and snap["studymaterial_path_kus"] == EXPECTED["studymaterial_path_kus"]
        and snap["digestion_kus"] == EXPECTED["digestion_kus"]
    )


def load_concepts(conn) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT c.id::text AS concept_id,
                       c.code AS concept_code,
                       c.name AS concept_name,
                       s.code AS subject,
                       ch.code AS chapter_code,
                       ch.name AS chapter_name,
                       ch.class_level,
                       t.code AS topic_code,
                       t.name AS topic_name,
                       (
                         SELECT COUNT(*) FROM knowledge.knowledge_units ku
                         WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                           AND ku.validation_status = 'PASSED'
                       ) AS passed_ku_count,
                       (
                         SELECT COUNT(*) FROM knowledge.knowledge_units ku
                         JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                         JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                         WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                           AND ku.validation_status = 'PASSED'
                           AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%'
                       ) AS ncert_ku_count,
                       (
                         SELECT j.source_file_path
                         FROM knowledge.knowledge_units ku
                         JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                         JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                         WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                           AND ku.validation_status = 'PASSED'
                           AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%'
                         ORDER BY ku.created_at ASC
                         LIMIT 1
                       ) AS ncert_ku_path,
                       (
                         SELECT ku.id::text
                         FROM knowledge.knowledge_units ku
                         JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                         JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                         WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                           AND ku.validation_status = 'PASSED'
                           AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%'
                         ORDER BY ku.created_at ASC
                         LIMIT 1
                       ) AS ncert_ku_id,
                       (SELECT COUNT(*) FROM cms.question_blueprints bp
                        WHERE bp.concept_id = c.id AND bp.deleted_at IS NULL) AS bp_count,
                       (SELECT COUNT(*) FROM cms.question_blueprints bp
                        WHERE bp.concept_id = c.id AND bp.deleted_at IS NULL
                          AND bp.provenance_tier = 'authoritative') AS auth_bp_count
                FROM academic.concepts c
                JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE c.deleted_at IS NULL
                ORDER BY s.code, ch.code, c.code
                """
            )
        ).mappings()
    ]


def load_blueprints(conn) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT bp.id::text AS blueprint_id,
                       bp.blueprint_key,
                       bp.status,
                       bp.generation_eligible,
                       bp.is_active,
                       bp.difficulty,
                       bp.target_count,
                       bp.provenance_tier,
                       bp.constraints,
                       bp.concept_id::text AS concept_id,
                       c.code AS concept_code,
                       c.name AS concept_name,
                       s.code AS subject,
                       ch.code AS chapter_code,
                       t.code AS topic_code
                FROM cms.question_blueprints bp
                LEFT JOIN academic.concepts c ON c.id = bp.concept_id
                LEFT JOIN academic.topics t ON t.id = bp.topic_id
                LEFT JOIN academic.chapters ch ON ch.id = bp.chapter_id
                LEFT JOIN academic.subjects s ON s.id = bp.subject_id
                WHERE bp.deleted_at IS NULL
                ORDER BY s.code, c.code, bp.blueprint_key
                """
            )
        ).mappings()
    ]


def classify_bp_provenance(bp: dict, ncert_root: Path) -> dict:
    cons = bp.get("constraints") if isinstance(bp.get("constraints"), dict) else {}
    if isinstance(bp.get("constraints"), str):
        try:
            cons = json.loads(bp["constraints"])
        except json.JSONDecodeError:
            cons = {}
    tier = (bp.get("provenance_tier") or "").strip().lower()
    path = extract_blueprint_ncert_path(cons)
    declares = blueprint_declares_ncert_source(cons, tier)
    blob = json.dumps(cons, ensure_ascii=False)

    out = {
        "blueprint_id": bp["blueprint_id"],
        "blueprint_key": bp["blueprint_key"],
        "concept_code": bp.get("concept_code"),
        "subject": bp.get("subject"),
        "chapter_code": bp.get("chapter_code"),
        "provenance_tier": tier,
        "target_count": bp.get("target_count"),
        "ncert_derived": cons.get("ncert_derived") is True,
        "extracted_path": path,
        "has_studymaterial": "StudyMaterial" in blob,
        "has_ncert_books": "NCERT Books" in blob or (path and "NCERT Books" in path),
        "assert_ok": False,
        "assert_error": None,
        "classification": "OTHER",
    }

    if out["has_studymaterial"]:
        out["classification"] = "LEGACY_STUDYMATERIAL"
        return out

    if tier == "authoritative" and cons.get("ncert_derived") is True and path:
        try:
            validated = assert_blueprint_ncert_source(cons, provenance_tier=tier, root=ncert_root)
            out["assert_ok"] = True
            out["classification"] = "CANONICAL_NCERT_BACKED"
            out["validated_relative"] = validated.relative_posix if validated else None
            return out
        except NcertSourceError as exc:
            out["assert_error"] = f"{exc.code}:{exc}"
            out["classification"] = "SOURCE_REQUIRES_REVIEW"
            return out

    if declares and not path:
        out["classification"] = "SOURCE_MISSING"
        return out

    if path and "NCERT Books" not in (path or "") and not out["has_ncert_books"]:
        out["classification"] = "LEGACY_OTHER"
        return out

    if tier == "ai":
        out["classification"] = "LEGACY_AI"
        return out

    if tier == "authoritative":
        out["classification"] = "AUTHORITATIVE_NON_NCERT_CONTRACT"
        return out

    out["classification"] = "OTHER"
    return out


def analyze(concepts: list[dict], blueprints: list[dict], ncert_root: Path) -> dict:
    bp_classes = [classify_bp_provenance(bp, ncert_root) for bp in blueprints]
    by_class = Counter(b["classification"] for b in bp_classes)
    by_subject_bps = Counter(b.get("subject") or "UNKNOWN" for b in blueprints)
    by_subject_tier = defaultdict(Counter)
    for b in blueprints:
        by_subject_tier[b.get("subject") or "UNKNOWN"][(b.get("provenance_tier") or "").lower()] += 1

    # Concept → canonical NCERT BPs
    canon_bps_by_concept: dict[str, list[dict]] = defaultdict(list)
    for bc in bp_classes:
        if bc["classification"] == "CANONICAL_NCERT_BACKED" and bc.get("concept_code"):
            canon_bps_by_concept[bc["concept_code"]].append(bc)

    auth_bps_by_concept: dict[str, list[dict]] = defaultdict(list)
    for bp in blueprints:
        if (bp.get("provenance_tier") or "").lower() == "authoritative" and bp.get("concept_code"):
            auth_bps_by_concept[bp["concept_code"]].append(bp)

    all_bps_by_concept: dict[str, list[dict]] = defaultdict(list)
    for bp in blueprints:
        if bp.get("concept_code"):
            all_bps_by_concept[bp["concept_code"]].append(bp)

    # Duplicate / conflicting coverage
    duplicate_flags = []
    for code, bps in all_bps_by_concept.items():
        if len(bps) > 1:
            classes = {
                next(bc["classification"] for bc in bp_classes if bc["blueprint_id"] == b["blueprint_id"])
                for b in bps
            }
            duplicate_flags.append(
                {
                    "concept_code": code,
                    "bp_count": len(bps),
                    "keys": [b["blueprint_key"] for b in bps],
                    "tiers": [b.get("provenance_tier") for b in bps],
                    "classifications": sorted(classes),
                    "conflict": len(classes) > 1,
                }
            )

    # Botany duplicate relationship (taxonomy, not BP merge)
    botany_dup = {
        "pair": list(BOTANY_DUP_PAIR),
        "disposition": "MERGE_REVIEW (unchanged; flag only)",
        "concepts": {},
    }

    taxonomy_rows = []
    eligible = []
    adequate = []
    ku_no_bp = []
    with_ncert_ku = []
    without_ncert_ku = []
    source_review = []
    digestion = []

    for c in concepts:
        code = c["concept_code"]
        if c["chapter_code"] == "digestion-absorption":
            digestion.append(
                {
                    "concept_code": code,
                    "subject": c["subject"],
                    "ncert_ku_count": c["ncert_ku_count"],
                    "bp_count": c["bp_count"],
                    "note": "excluded — no canonical NCERT PDF",
                }
            )

        has_ncert = c["ncert_ku_count"] > 0
        if has_ncert:
            with_ncert_ku.append(code)
        else:
            without_ncert_ku.append(code)

        has_adequate = code in canon_bps_by_concept
        adequate_target_sum = sum(int(b.get("target_count") or 0) for b in canon_bps_by_concept.get(code, []))

        # BP-CREATE-001 eligibility (production)
        is_eligible = (
            c["chapter_code"] not in EXCLUDED_CHAPTERS
            and c["ncert_ku_count"] == 1
            and c["auth_bp_count"] == 0
        )

        row = {
            "concept_id": c["concept_id"],
            "concept_code": code,
            "concept_name": c["concept_name"],
            "subject": c["subject"],
            "class_level": c["class_level"],
            "chapter_code": c["chapter_code"],
            "topic_code": c["topic_code"],
            "ncert_ku_count": c["ncert_ku_count"],
            "passed_ku_count": c["passed_ku_count"],
            "bp_count": c["bp_count"],
            "auth_bp_count": c["auth_bp_count"],
            "has_adequate_canonical_bp": has_adequate,
            "adequate_target_sum": adequate_target_sum,
            "eligible_for_ncert_bp_create": is_eligible,
            "taxonomy_review": code in TAXONOMY_REVIEW_CODES,
            "ncert_ku_path": c.get("ncert_ku_path"),
        }

        if code in TAXONOMY_REVIEW_CODES:
            taxonomy_rows.append(
                {
                    **row,
                    "safely_remediated": False,
                    "independently_eligible": is_eligible,
                    "note": "TAXONOMY_REVIEW — unchanged; not counted as safely remediated",
                }
            )

        if code in BOTANY_DUP_PAIR:
            botany_dup["concepts"][code] = {
                "concept_id": c["concept_id"],
                "ncert_ku_count": c["ncert_ku_count"],
                "bp_count": c["bp_count"],
                "auth_bp_count": c["auth_bp_count"],
                "has_adequate_canonical_bp": has_adequate,
            }

        if has_adequate:
            adequate.append(row)

        if is_eligible:
            # Do not treat taxonomy-review as "safely remediated" even if somehow eligible
            eligible.append({**row, "projected_target_count": TARGET_COUNT_PROJECTED})

        if has_ncert and c["bp_count"] == 0:
            ku_no_bp.append(row)

        # Source/evidence review: has NCERT KU but path missing/invalid, or auth BP fails assert
        if has_ncert and not c.get("ncert_ku_path"):
            source_review.append({**row, "reason": "ncert_ku_without_path"})
        for bc in canon_bps_by_concept.get(code, []):
            pass  # already assert_ok
        for bp in auth_bps_by_concept.get(code, []):
            bc = next(x for x in bp_classes if x["blueprint_id"] == bp["blueprint_id"])
            if bc["classification"] == "SOURCE_REQUIRES_REVIEW":
                source_review.append({**row, "reason": "authoritative_bp_assert_failed", "bp": bc["blueprint_key"]})

    # Subject rolls
    subject_stats = {}
    for subj in SUBJECTS:
        sc = [c for c in concepts if c["subject"] == subj]
        s_with_ku = [c for c in sc if c["ncert_ku_count"] > 0]
        s_adequate = [r for r in adequate if r["subject"] == subj]
        s_eligible = [r for r in eligible if r["subject"] == subj]
        s_ku_no_bp = [r for r in ku_no_bp if r["subject"] == subj]
        s_tax = [r for r in taxonomy_rows if r["subject"] == subj]

        existing_adequate_projected = sum(r["adequate_target_sum"] for r in s_adequate)
        # Prefer actual target_count on canonical BPs; if 0 fall back to TARGET_COUNT_PROJECTED per concept
        existing_capacity = 0
        for r in s_adequate:
            existing_capacity += r["adequate_target_sum"] if r["adequate_target_sum"] > 0 else TARGET_COUNT_PROJECTED

        newly_projected = len(s_eligible) * TARGET_COUNT_PROJECTED
        # Avoid double-counting: eligible have no auth BP, so not in adequate
        total_projected = existing_capacity + newly_projected
        gap_100 = max(0, SUBJECT_PILOT_TARGET - total_projected)

        subject_stats[subj] = {
            "total_concepts": len(sc),
            "concepts_with_verified_ncert_ku": len(s_with_ku),
            "concepts_without_verified_ncert_ku": len(sc) - len(s_with_ku),
            "existing_blueprints": by_subject_bps.get(subj, 0),
            "blueprint_tiers": dict(by_subject_tier.get(subj, {})),
            "concepts_with_adequate_canonical_bp": len(s_adequate),
            "concepts_eligible_for_bp_create": len(s_eligible),
            "concepts_with_ku_but_no_bp": len(s_ku_no_bp),
            "taxonomy_review_concepts": len(s_tax),
            "missing_canonical_bps": len(s_eligible),  # create opportunities under production gate
            "PROJECTED_bp_capacity_if_create_at_target_2": newly_projected,
            "PROJECTED_existing_canonical_target_capacity": existing_capacity,
            "PROJECTED_pilot_question_capacity": total_projected,
            "gap_versus_100_question_subject_target": gap_100,
            "bottleneck": (
                "taxonomy_review_and_ku_gaps"
                if gap_100 > 0 and len(s_eligible) * TARGET_COUNT_PROJECTED < gap_100
                else ("eligible_bp_create_backlog" if len(s_eligible) > 0 and gap_100 > 0 else ("meets_or_exceeds_100_projected" if gap_100 == 0 else "other"))
            ),
            "eligible_concept_codes_sample": [r["concept_code"] for r in s_eligible[:25]],
            "ku_no_bp_codes_sample": [r["concept_code"] for r in s_ku_no_bp[:25]],
        }

    total_projected = sum(s["PROJECTED_pilot_question_capacity"] for s in subject_stats.values())
    total_eligible = sum(s["concepts_eligible_for_bp_create"] for s in subject_stats.values())
    total_adequate = sum(s["concepts_with_adequate_canonical_bp"] for s in subject_stats.values())

    bottlenecks = sorted(
        (
            {
                "subject": subj,
                "gap_versus_100": subject_stats[subj]["gap_versus_100_question_subject_target"],
                "PROJECTED_capacity": subject_stats[subj]["PROJECTED_pilot_question_capacity"],
                "eligible": subject_stats[subj]["concepts_eligible_for_bp_create"],
                "with_ncert_ku": subject_stats[subj]["concepts_with_verified_ncert_ku"],
                "bottleneck": subject_stats[subj]["bottleneck"],
            }
            for subj in SUBJECTS
        ),
        key=lambda x: -x["gap_versus_100"],
    )

    return {
        "totals": {
            "concepts": len(concepts),
            "concepts_with_verified_ncert_ku": len(with_ncert_ku),
            "concepts_without_verified_ncert_ku": len(without_ncert_ku),
            "blueprints": len(blueprints),
            "concepts_with_adequate_canonical_bp": total_adequate,
            "concepts_eligible_for_ncert_bp_create": total_eligible,
            "concepts_with_ku_but_no_bp": len(ku_no_bp),
            "taxonomy_review_concepts": len(taxonomy_rows),
            "source_review_flags": len(source_review),
            "duplicate_or_multi_bp_concepts": len(duplicate_flags),
            "conflicting_provenance_multi_bp": sum(1 for d in duplicate_flags if d["conflict"]),
        },
        "blueprint_provenance_counts": dict(by_class),
        "blueprints_by_subject": dict(by_subject_bps),
        "subject_stats": subject_stats,
        "PROJECTED_total_pilot_question_capacity": total_projected,
        "PROJECTED_400_pilot_theoretically_supported": total_projected >= PILOT_TOTAL_TARGET,
        "PROJECTED_gap_versus_400": max(0, PILOT_TOTAL_TARGET - total_projected),
        "bottlenecks": bottlenecks,
        "eligible_concepts": eligible,
        "adequate_concepts": [
            {"concept_code": r["concept_code"], "subject": r["subject"], "adequate_target_sum": r["adequate_target_sum"]}
            for r in adequate
        ],
        "ku_but_no_bp": ku_no_bp,
        "taxonomy_review": taxonomy_rows,
        "source_review": source_review[:50],
        "duplicate_bp_coverage": duplicate_flags[:80],
        "digestion_exclusion": {
            "chapter": "digestion-absorption",
            "excluded": True,
            "concepts": digestion,
            "kus": 0,
        },
        "sv2c_botany_15_duplicate_flag": botany_dup,
        "eligibility_contract": {
            "ncert_ku": "PASSED KU whose ingestion job path contains 'NCERT Books'",
            "bp_create_gate": "exactly 1 NCERT PASSED KU AND auth_bp_count == 0 AND chapter not digestion-absorption",
            "adequate_canonical_bp": (
                "provenance_tier=authoritative AND constraints.ncert_derived=true "
                "AND assert_blueprint_ncert_source passes (path under NCERT Books)"
            ),
            "obsolete_gate_rejected": 'provenance_tier == "ncert"',
            "projected_target_count": TARGET_COUNT_PROJECTED,
        },
    }


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
    proc = subprocess.run(cmd, cwd=str(BACKEND), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    passed = failed = 0
    m = re.search(r"(\d+) passed", out)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", out)
    if m:
        failed = int(m.group(1))
    return {
        "passed": passed,
        "failed": failed,
        "exit_code": proc.returncode,
        "command": " ".join(cmd),
        "tail": "\n".join(out.strip().splitlines()[-40:]),
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    a = payload["analysis"]
    lines = [
        "# BP-COVERAGE-003 — Fresh NCERT blueprint coverage audit",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Mode: **READ-ONLY** (no DB mutation)",
        "- Git: **no commit / no push**",
        "",
        "## Executive verdict",
        payload["executive_verdict"],
        "",
        "## Eligibility contract (production)",
        f"- NCERT KU: `{a['eligibility_contract']['ncert_ku']}`",
        f"- BP create gate: `{a['eligibility_contract']['bp_create_gate']}`",
        f"- Adequate canonical BP: `{a['eligibility_contract']['adequate_canonical_bp']}`",
        f"- Rejected obsolete gate: `{a['eligibility_contract']['obsolete_gate_rejected']}`",
        f"- PROJECTED new BP `target_count`: `{a['eligibility_contract']['projected_target_count']}`",
        "",
        "## Integrity (before = after)",
        f"- Freeze OK: `{payload['freeze_ok']}`",
        f"- Snapshot identical: `{payload['snapshot_identical']}`",
        f"- Mutation occurred: `{payload['confirmation']['db_mutated']}`",
        "",
        "### Before",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "### After",
        f"```json\n{json.dumps(payload['after'], indent=2)}\n```",
        "",
        "## Totals",
        f"- Concepts: `{a['totals']['concepts']}`",
        f"- With verified NCERT KU: `{a['totals']['concepts_with_verified_ncert_ku']}`",
        f"- Without verified NCERT KU: `{a['totals']['concepts_without_verified_ncert_ku']}`",
        f"- Blueprints: `{a['totals']['blueprints']}`",
        f"- Concepts with adequate canonical NCERT BP: `{a['totals']['concepts_with_adequate_canonical_bp']}`",
        f"- Concepts eligible for NCERT BP create: `{a['totals']['concepts_eligible_for_ncert_bp_create']}`",
        f"- Concepts with KU but no BP: `{a['totals']['concepts_with_ku_but_no_bp']}`",
        f"- TAXONOMY_REVIEW concepts: `{a['totals']['taxonomy_review_concepts']}`",
        f"- Multi-BP concepts: `{a['totals']['duplicate_or_multi_bp_concepts']}` (conflicting provenance: `{a['totals']['conflicting_provenance_multi_bp']}`)",
        "",
        "## Blueprint provenance (legacy vs canonical)",
        f"```json\n{json.dumps(a['blueprint_provenance_counts'], indent=2)}\n```",
        f"- Blueprints by subject: `{a['blueprints_by_subject']}`",
        "",
        "## PROJECTED pilot capacity (not actual MCQs)",
        f"- **PROJECTED total pilot question capacity:** `{a['PROJECTED_total_pilot_question_capacity']}`",
        f"- **PROJECTED 400-question pilot theoretically supported:** `{a['PROJECTED_400_pilot_theoretically_supported']}`",
        f"- **PROJECTED gap versus 400:** `{a['PROJECTED_gap_versus_400']}`",
        "",
        "### Subject-by-subject",
        "",
        "| Subject | Concepts | NCERT KU | Adequate BP concepts | Eligible create | KU no BP | Existing BPs | PROJECTED capacity | Gap vs 100 | Bottleneck |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for subj in SUBJECTS:
        s = a["subject_stats"][subj]
        lines.append(
            f"| {subj} | {s['total_concepts']} | {s['concepts_with_verified_ncert_ku']} | "
            f"{s['concepts_with_adequate_canonical_bp']} | {s['concepts_eligible_for_bp_create']} | "
            f"{s['concepts_with_ku_but_no_bp']} | {s['existing_blueprints']} | "
            f"**{s['PROJECTED_pilot_question_capacity']}** | {s['gap_versus_100_question_subject_target']} | "
            f"{s['bottleneck']} |"
        )

    lines += [
        "",
        "### Bottlenecks (largest gap first)",
        f"```json\n{json.dumps(a['bottlenecks'], indent=2)}\n```",
        "",
        "## Concepts with KU but missing BP (sample in JSON; full list in JSON)",
        f"- Count: `{len(a['ku_but_no_bp'])}`",
        "",
        "## TAXONOMY_REVIEW exclusions (unchanged)",
        f"- Count: `{len(a['taxonomy_review'])}`",
        "- Not counted as safely remediated.",
        "",
        "| Code | Subject | NCERT KU | Eligible independently? |",
        "|---|---|---:|---|",
    ]
    for r in a["taxonomy_review"]:
        lines.append(
            f"| `{r['concept_code']}` | {r['subject']} | {r['ncert_ku_count']} | `{r['independently_eligible']}` |"
        )

    lines += [
        "",
        "## Digestion & Absorption exclusion",
        f"```json\n{json.dumps(a['digestion_exclusion'], indent=2)}\n```",
        "",
        "## sv2c-botany-15 duplicate flag (no merge)",
        f"```json\n{json.dumps(a['sv2c_botany_15_duplicate_flag'], indent=2)}\n```",
        "",
        "## Eligible for BP create (count)",
        f"- `{len(a['eligible_concepts'])}` concepts — full list in JSON (`eligible_concepts`).",
        "",
        "## Tests",
        f"- Passed `{payload['tests'].get('passed')}` / Failed `{payload['tests'].get('failed')}`",
        "",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## Files written",
    ]
    for f in payload["files_changed"]:
        lines.append(f"- `{f}`")
    lines += [
        "",
        "## Confirmation",
        f"```json\n{json.dumps(payload['confirmation'], indent=2)}\n```",
        "",
        "**STOP** — no blueprint creation, no MCQs, no commit, no push.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    try:
        ncert_root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        ncert_root = ROOT / "NCERT Books"

    with engine.connect() as conn:
        before = snapshot(conn)
        if not freeze_ok(before):
            raise SystemExit(f"ABORT freeze mismatch: {before}")
        concepts = load_concepts(conn)
        blueprints = load_blueprints(conn)
        analysis = analyze(concepts, blueprints, ncert_root)
        after = snapshot(conn)

    identical = before == after
    if not identical or not freeze_ok(after):
        raise SystemExit("ABORT: snapshot drifted during read-only audit")

    tests = run_tests()

    total_proj = analysis["PROJECTED_total_pilot_question_capacity"]
    supported = analysis["PROJECTED_400_pilot_theoretically_supported"]
    eligible_n = analysis["totals"]["concepts_eligible_for_ncert_bp_create"]
    adequate_n = analysis["totals"]["concepts_with_adequate_canonical_bp"]

    if tests["failed"] or tests["exit_code"] != 0:
        final = "YELLOW — AUDIT COMPLETE; TESTS WARN"
    else:
        final = "GREEN — READ-ONLY AUDIT COMPLETE"

    verdict = (
        f"After KU-OWNER-REMEDIATION-001, {before['concepts_with_ncert_ku']} concepts have verified NCERT KUs "
        f"and {before['question_blueprints']} blueprints remain unchanged. "
        f"{adequate_n} concepts already have adequate canonical NCERT BPs; "
        f"{eligible_n} concepts are newly/still eligible for BP-CREATE under production gates. "
        f"PROJECTED pilot capacity at target_count={TARGET_COUNT_PROJECTED} is {total_proj} "
        f"({'supports' if supported else 'does not yet support'} the 400-question theoretical pilot). "
        "No blueprints or MCQs were created in this audit."
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READ-ONLY",
        "final_status": final,
        "executive_verdict": verdict,
        "ncert_root": str(ncert_root),
        "before": before,
        "after": after,
        "snapshot_identical": identical,
        "freeze_ok": True,
        "analysis": analysis,
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/bp_coverage_003_readonly.py",
        ],
        "confirmation": {
            "db_mutated": False,
            "blueprints_created": False,
            "blueprints_modified": False,
            "mcqs_generated": False,
            "kus_modified": False,
            "taxonomy_modified": False,
            "questions_modified": False,
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
                "concepts_with_ncert_ku": before["concepts_with_ncert_ku"],
                "eligible": eligible_n,
                "adequate": adequate_n,
                "PROJECTED_capacity": total_proj,
                "PROJECTED_supports_400": supported,
                "kus": before["knowledge_units"],
                "blueprints": before["question_blueprints"],
                "freeze_ok": True,
                "tests_passed": tests["passed"],
                "tests_failed": tests["failed"],
            },
            indent=2,
        )
    )
    return 0 if final.startswith("GREEN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
