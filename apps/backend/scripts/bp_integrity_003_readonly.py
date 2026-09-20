"""BP-INTEGRITY-003 — Final NCERT blueprint integrity audit (read-only).

Independent gate before MCQ pilot authorization. Audits all canonical
NCERT blueprints against production assert_blueprint_ncert_source contract.
No database mutations.
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
    extract_blueprint_ncert_path,
    get_ncert_source_root,
)

REPORT_STEM = "bp_integrity_003_20260913"
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
    "blueprints": 445,
    "canonical_ncert": 308,
    "legacy_total": 137,
    "legacy_studymaterial": 100,
    "legacy_ai": 37,
    "studymaterial_path_kus": 73,
    "digestion_kus": 0,
    "concepts_with_ncert_ku": 308,
}
SUBJECT_EXPECTED = {
    "PHYSICS": {"concepts": 67, "capacity": 134},
    "CHEMISTRY": {"concepts": 92, "capacity": 184},
    "BOTANY": {"concepts": 95, "capacity": 190},
    "ZOOLOGY": {"concepts": 54, "capacity": 108},
}
TOTAL_PROJECTED = 616
EXCLUDED_CHAPTERS = frozenset({"digestion-absorption"})
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
MERGE_REVIEW_CODES = frozenset({"sv2c-botany-15"})


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
        and snap["concepts_with_ncert_ku"] == EXPECTED["concepts_with_ncert_ku"]
    )


def parse_constraints(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


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
                       bp.topic_id::text AS topic_id,
                       bp.chapter_id::text AS chapter_id,
                       bp.subject_id::text AS subject_id,
                       c.code AS concept_code,
                       c.name AS concept_name,
                       c.deleted_at AS concept_deleted_at,
                       t.code AS topic_code,
                       t.deleted_at AS topic_deleted_at,
                       t.chapter_id::text AS topic_chapter_id,
                       ch.code AS chapter_code,
                       ch.deleted_at AS chapter_deleted_at,
                       ch.subject_id::text AS chapter_subject_id,
                       s.code AS subject,
                       s.id::text AS subject_row_id,
                       (
                         SELECT COUNT(*) FROM knowledge.knowledge_units ku
                         JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                         JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                         WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                           AND ku.validation_status = 'PASSED'
                           AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%'
                       ) AS ncert_ku_count
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


def is_canonical_candidate(cons: dict, tier: str) -> bool:
    return (
        (tier or "").lower() == "authoritative"
        and cons.get("ncert_derived") is True
        and bool(extract_blueprint_ncert_path(cons))
        and "NCERT Books" in (extract_blueprint_ncert_path(cons) or "")
        and "StudyMaterial" not in json.dumps(cons)
    )


def classify_legacy(cons: dict, tier: str) -> str:
    blob = json.dumps(cons, ensure_ascii=False)
    if "StudyMaterial" in blob:
        return "LEGACY_STUDYMATERIAL"
    if (tier or "").lower() == "ai":
        return "LEGACY_AI"
    path = extract_blueprint_ncert_path(cons) or ""
    if (tier or "").lower() == "authoritative" and cons.get("ncert_derived") is True and "NCERT Books" in path:
        return "CANONICAL_NCERT_BACKED"
    if (tier or "").lower() == "authoritative" and not path:
        return "SOURCE_MISSING"
    if path and "NCERT Books" not in path:
        return "INVALID_OR_OUTSIDE_PATH"
    return "OTHER"


def audit_canonical_bp(bp: dict, cons: dict, ncert_root: Path) -> dict:
    failures: list[str] = []
    path = extract_blueprint_ncert_path(cons)
    tier = (bp.get("provenance_tier") or "").strip().lower()
    blob = json.dumps(cons, ensure_ascii=False)

    # 1–3 taxonomy
    if not bp.get("concept_id") or bp.get("concept_deleted_at") is not None or not bp.get("concept_code"):
        failures.append("invalid_or_missing_concept")
    if not bp.get("topic_code") or bp.get("topic_deleted_at") is not None:
        failures.append("invalid_or_missing_topic")
    if not bp.get("chapter_code") or bp.get("chapter_deleted_at") is not None:
        failures.append("invalid_or_missing_chapter")
    if bp.get("topic_chapter_id") and bp.get("chapter_id") and bp["topic_chapter_id"] != bp["chapter_id"]:
        failures.append("topic_chapter_mismatch")
    if bp.get("chapter_subject_id") and bp.get("subject_id") and bp["chapter_subject_id"] != bp["subject_id"]:
        failures.append("chapter_subject_mismatch")

    # 4 NCERT KU
    if int(bp.get("ncert_ku_count") or 0) < 1:
        failures.append("missing_verified_ncert_ku")

    # 5–7 provenance contract
    if tier != "authoritative":
        failures.append(f"provenance_tier={tier}")
    if cons.get("ncert_derived") is not True:
        failures.append("ncert_derived_not_true")
    if not path:
        failures.append("missing_ncert_source_path")

    # 8–10 path / assert / readable
    assert_ok = False
    assert_error = None
    pdf_readable = False
    try:
        validated = assert_blueprint_ncert_source(cons, provenance_tier=tier, root=ncert_root)
        assert_ok = validated is not None
        if validated:
            pdf_path = validated.resolved_path
            try:
                pdf_path.relative_to(ncert_root.resolve())
            except ValueError:
                failures.append("path_outside_ncert_root")
            if pdf_path.exists() and pdf_path.is_file() and pdf_path.suffix.lower() == ".pdf":
                with pdf_path.open("rb") as fh:
                    pdf_readable = fh.read(5) == b"%PDF-"
            if not pdf_readable:
                failures.append("pdf_unreadable")
        else:
            failures.append("assert_returned_none")
    except NcertSourceError as exc:
        assert_error = f"{exc.code}:{exc}"
        failures.append(f"assert_failed:{exc.code}")

    # 11 target_count
    if int(bp.get("target_count") or 0) != 2:
        failures.append(f"target_count={bp.get('target_count')}")

    # 13–14 StudyMaterial / outside
    if "StudyMaterial" in blob or (path and "StudyMaterial" in path):
        failures.append("points_to_studymaterial")
    if path and "NCERT Books" not in path:
        failures.append("path_not_under_ncert_books_string")

    # 15–18 exclusions
    if bp.get("chapter_code") in EXCLUDED_CHAPTERS:
        failures.append("digestion_excluded_chapter")
    if bp.get("concept_code") in TAXONOMY_REVIEW_CODES:
        failures.append("taxonomy_review_concept")
    # sv2c-botany-15 may have a pre-existing canonical BP from earlier campaigns;
    # integrity audit flags it for owner awareness but does not treat pre-CREATE
    # coverage as a CREATE-002 remediation merge. Record as note if present.
    merge_flag = bp.get("concept_code") in MERGE_REVIEW_CODES

    return {
        "blueprint_id": bp["blueprint_id"],
        "blueprint_key": bp["blueprint_key"],
        "concept_code": bp.get("concept_code"),
        "subject": bp.get("subject"),
        "chapter_code": bp.get("chapter_code"),
        "topic_code": bp.get("topic_code"),
        "target_count": bp.get("target_count"),
        "ncert_ku_count": bp.get("ncert_ku_count"),
        "ncert_source_path": path,
        "assert_ok": assert_ok,
        "assert_error": assert_error,
        "pdf_readable": pdf_readable,
        "merge_review_concept": merge_flag,
        "failures": failures,
        "passed": len(failures) == 0,
    }


def run_audit(blueprints: list[dict], ncert_root: Path) -> dict:
    canonical_rows = []
    legacy_rows = []
    provenance_counts: Counter = Counter()
    failing = []
    assert_failures = []
    incorrect_provenance = []
    invalid_paths = []
    source_missing = []

    for bp in blueprints:
        cons = parse_constraints(bp.get("constraints"))
        tier = (bp.get("provenance_tier") or "").strip().lower()
        klass = classify_legacy(cons, tier)
        provenance_counts[klass] += 1

        if klass == "CANONICAL_NCERT_BACKED" or is_canonical_candidate(cons, tier):
            # Prefer assert-based canonical membership
            row = audit_canonical_bp(bp, cons, ncert_root)
            # Only count as canonical if contract shape matches expected
            if is_canonical_candidate(cons, tier):
                canonical_rows.append({**row, "classification": "CANONICAL_NCERT_BACKED"})
                if not row["passed"]:
                    failing.append(row)
                if not row["assert_ok"]:
                    assert_failures.append(row)
                if row["failures"]:
                    if any("provenance" in f or "ncert_derived" in f for f in row["failures"]):
                        incorrect_provenance.append(row)
                    if any("path" in f or "pdf" in f or "assert" in f for f in row["failures"]):
                        invalid_paths.append(row)
            else:
                legacy_rows.append({"blueprint_id": bp["blueprint_id"], "classification": klass, "concept_code": bp.get("concept_code")})
        else:
            legacy_rows.append(
                {
                    "blueprint_id": bp["blueprint_id"],
                    "blueprint_key": bp["blueprint_key"],
                    "classification": klass,
                    "concept_code": bp.get("concept_code"),
                    "subject": bp.get("subject"),
                    "provenance_tier": tier,
                }
            )
            if klass == "SOURCE_MISSING":
                source_missing.append(bp["blueprint_key"])
            if klass == "INVALID_OR_OUTSIDE_PATH":
                invalid_paths.append({"blueprint_key": bp["blueprint_key"], "note": "legacy_invalid_path"})

    # Deduplicate canonical list if both branches fired — rebuild cleanly
    canon_by_id = {}
    for bp in blueprints:
        cons = parse_constraints(bp.get("constraints"))
        tier = (bp.get("provenance_tier") or "").strip().lower()
        if is_canonical_candidate(cons, tier):
            row = audit_canonical_bp(bp, cons, ncert_root)
            canon_by_id[bp["blueprint_id"]] = {**row, "classification": "CANONICAL_NCERT_BACKED"}
    canonical_rows = list(canon_by_id.values())
    failing = [r for r in canonical_rows if not r["passed"]]
    assert_failures = [r for r in canonical_rows if not r["assert_ok"]]

    # Legacy recount from non-canonical
    legacy_sm = 0
    legacy_ai = 0
    other_legacy = 0
    for bp in blueprints:
        cons = parse_constraints(bp.get("constraints"))
        tier = (bp.get("provenance_tier") or "").strip().lower()
        if is_canonical_candidate(cons, tier):
            continue
        klass = classify_legacy(cons, tier)
        if klass == "LEGACY_STUDYMATERIAL":
            legacy_sm += 1
        elif klass == "LEGACY_AI":
            legacy_ai += 1
        else:
            other_legacy += 1
            if klass == "SOURCE_MISSING":
                source_missing.append(bp.get("blueprint_key"))

    # Duplicates: multiple canonical BPs per concept
    by_concept: dict[str, list[dict]] = defaultdict(list)
    for r in canonical_rows:
        if r.get("concept_code"):
            by_concept[r["concept_code"]].append(r)
    duplicates = [
        {
            "concept_code": code,
            "bp_count": len(rows),
            "keys": [r["blueprint_key"] for r in rows],
            "target_counts": [r["target_count"] for r in rows],
        }
        for code, rows in by_concept.items()
        if len(rows) > 1
    ]
    # same concept + same target_count combination
    dup_target = [d for d in duplicates if len(set(d["target_counts"])) == 1]

    # Subject rolls
    subject_stats = {}
    for subj, exp in SUBJECT_EXPECTED.items():
        rows = [r for r in canonical_rows if r.get("subject") == subj]
        concepts = {r["concept_code"] for r in rows if r.get("concept_code")}
        target_dist = Counter(int(r.get("target_count") or 0) for r in rows)
        bps_per_concept = Counter(len(v) for k, v in by_concept.items() if any(x.get("subject") == subj for x in v))
        capacity = sum(int(r.get("target_count") or 0) for r in rows)
        subject_stats[subj] = {
            "canonical_ncert_bps": len(rows),
            "canonical_ncert_concepts_covered": len(concepts),
            "expected_concepts": exp["concepts"],
            "concepts_match_expected": len(concepts) == exp["concepts"],
            "bps_per_concept_distribution": dict(bps_per_concept),
            "target_count_distribution": dict(target_dist),
            "PROJECTED_capacity": capacity,
            "expected_PROJECTED_capacity": exp["capacity"],
            "capacity_match_expected": capacity == exp["capacity"],
            "failing_bps": sum(1 for r in rows if not r["passed"]),
        }

    total_capacity = sum(s["PROJECTED_capacity"] for s in subject_stats.values())
    taxonomy_on_canon = [r for r in canonical_rows if r.get("concept_code") in TAXONOMY_REVIEW_CODES]
    digestion_on_canon = [r for r in canonical_rows if r.get("chapter_code") in EXCLUDED_CHAPTERS]
    merge_on_canon = [r for r in canonical_rows if r.get("merge_review_concept")]

    # Legacy fingerprints (keys only — prove not deleted)
    legacy_keys_sm = []
    legacy_keys_ai = []
    for bp in blueprints:
        cons = parse_constraints(bp.get("constraints"))
        tier = (bp.get("provenance_tier") or "").strip().lower()
        if is_canonical_candidate(cons, tier):
            continue
        klass = classify_legacy(cons, tier)
        if klass == "LEGACY_STUDYMATERIAL":
            legacy_keys_sm.append(bp["blueprint_key"])
        elif klass == "LEGACY_AI":
            legacy_keys_ai.append(bp["blueprint_key"])

    anomalies = []
    if len(canonical_rows) != EXPECTED["canonical_ncert"]:
        anomalies.append(f"canonical_count={len(canonical_rows)} expected={EXPECTED['canonical_ncert']}")
    if legacy_sm != EXPECTED["legacy_studymaterial"]:
        anomalies.append(f"legacy_studymaterial={legacy_sm} expected={EXPECTED['legacy_studymaterial']}")
    if legacy_ai != EXPECTED["legacy_ai"]:
        anomalies.append(f"legacy_ai={legacy_ai} expected={EXPECTED['legacy_ai']}")
    if total_capacity != TOTAL_PROJECTED:
        anomalies.append(f"PROJECTED_capacity={total_capacity} expected={TOTAL_PROJECTED}")
    for subj, s in subject_stats.items():
        if not s["concepts_match_expected"]:
            anomalies.append(
                f"{subj}_concepts={s['canonical_ncert_concepts_covered']} expected={s['expected_concepts']}"
            )
        if not s["capacity_match_expected"]:
            anomalies.append(
                f"{subj}_capacity={s['PROJECTED_capacity']} expected={s['expected_PROJECTED_capacity']}"
            )
    if failing:
        anomalies.append(f"canonical_failures={len(failing)}")
    if taxonomy_on_canon:
        anomalies.append(f"taxonomy_review_on_canonical={len(taxonomy_on_canon)}")
    if digestion_on_canon:
        anomalies.append(f"digestion_on_canonical={len(digestion_on_canon)}")
    if dup_target:
        anomalies.append(f"duplicate_concept_target_combos={len(dup_target)}")

    all_pass = (
        len(failing) == 0
        and len(canonical_rows) == EXPECTED["canonical_ncert"]
        and legacy_sm == EXPECTED["legacy_studymaterial"]
        and legacy_ai == EXPECTED["legacy_ai"]
        and total_capacity == TOTAL_PROJECTED
        and all(s["concepts_match_expected"] and s["capacity_match_expected"] for s in subject_stats.values())
        and not taxonomy_on_canon
        and not digestion_on_canon
        and not dup_target
    )

    return {
        "canonical_count": len(canonical_rows),
        "canonical_passed": sum(1 for r in canonical_rows if r["passed"]),
        "canonical_failed": len(failing),
        "failing_canonical": failing,
        "assert_failures": [
            {"blueprint_key": r["blueprint_key"], "assert_error": r["assert_error"]} for r in assert_failures
        ],
        "incorrect_provenance": [
            {"blueprint_key": r["blueprint_key"], "failures": r["failures"]} for r in incorrect_provenance
        ],
        "invalid_or_unreadable_paths": [
            {"blueprint_key": r.get("blueprint_key"), "failures": r.get("failures")}
            for r in invalid_paths
            if isinstance(r, dict) and r.get("blueprint_key")
        ][:50],
        "source_missing_keys": source_missing[:50],
        "source_missing_count": len(source_missing),
        "provenance_counts": {
            "CANONICAL_NCERT_BACKED": len(canonical_rows),
            "LEGACY_STUDYMATERIAL": legacy_sm,
            "LEGACY_AI": legacy_ai,
            "SOURCE_MISSING": len(source_missing),
            "OTHER_LEGACY": other_legacy,
            "TOTAL": len(blueprints),
            "LEGACY_TOTAL": legacy_sm + legacy_ai + other_legacy,
        },
        "legacy_protection": {
            "studymaterial_count": legacy_sm,
            "ai_count": legacy_ai,
            "expected_studymaterial": EXPECTED["legacy_studymaterial"],
            "expected_ai": EXPECTED["legacy_ai"],
            "studymaterial_ok": legacy_sm == EXPECTED["legacy_studymaterial"],
            "ai_ok": legacy_ai == EXPECTED["legacy_ai"],
            "studymaterial_keys_sample": legacy_keys_sm[:10],
            "ai_keys_sample": legacy_keys_ai[:10],
            "note": "Legacy BPs counted in-place; not converted/rewritten/deleted by this audit.",
        },
        "duplicates": {
            "multi_canonical_bp_concepts": duplicates,
            "same_concept_same_target": dup_target,
        },
        "subject_stats": subject_stats,
        "PROJECTED_total_capacity": total_capacity,
        "PROJECTED_total_expected": TOTAL_PROJECTED,
        "PROJECTED_match": total_capacity == TOTAL_PROJECTED,
        "exclusions": {
            "taxonomy_review_on_canonical": [
                {"blueprint_key": r["blueprint_key"], "concept_code": r["concept_code"]} for r in taxonomy_on_canon
            ],
            "digestion_on_canonical": [
                {"blueprint_key": r["blueprint_key"], "concept_code": r["concept_code"]} for r in digestion_on_canon
            ],
            "sv2c_botany_15_canonical_bps": [
                {
                    "blueprint_key": r["blueprint_key"],
                    "concept_code": r["concept_code"],
                    "note": "pre-existing MERGE_REVIEW pair member; not merged; flagged only",
                }
                for r in merge_on_canon
            ],
        },
        "anomalies": anomalies,
        "all_canonical_pass": all_pass,
        # Compact pass list omitted from MD; full failure detail retained
        "canonical_sample_passed": [
            {
                "blueprint_key": r["blueprint_key"],
                "concept_code": r["concept_code"],
                "subject": r["subject"],
                "target_count": r["target_count"],
            }
            for r in canonical_rows[:5]
            if r["passed"]
        ],
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
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    a = payload["audit"]
    lines = [
        "# BP-INTEGRITY-003 — Final NCERT blueprint integrity audit",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Mode: **READ-ONLY**",
        "- Git: **no commit / no push**",
        "- MCQ generation: **not started**",
        "",
        "## Executive verdict",
        payload["executive_verdict"],
        "",
        "## Integrity freeze (before = after)",
        f"- Freeze OK: `{payload['freeze_ok']}`",
        f"- Snapshot identical: `{payload['snapshot_identical']}`",
        f"- Mutation: `{payload['confirmation']['db_mutated']}`",
        "",
        "### Snapshot",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "",
        "## Canonical NCERT blueprints",
        f"- Count: `{a['canonical_count']}` (expected `{EXPECTED['canonical_ncert']}`)",
        f"- Passed all checks: `{a['canonical_passed']}`",
        f"- Failed: `{a['canonical_failed']}`",
        f"- All canonical pass: `{a['all_canonical_pass']}`",
        "",
        "## Provenance counts",
        f"```json\n{json.dumps(a['provenance_counts'], indent=2)}\n```",
        "",
        "## Legacy protection",
        f"```json\n{json.dumps(a['legacy_protection'], indent=2)}\n```",
        "",
        "## Subject audit (PROJECTED capacity ≠ actual MCQs)",
        "",
        "| Subject | Concepts | Expected | BPs | PROJECTED capacity | Expected capacity | Match | Failures |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for subj in SUBJECT_EXPECTED:
        s = a["subject_stats"][subj]
        match = s["concepts_match_expected"] and s["capacity_match_expected"]
        lines.append(
            f"| {subj} | {s['canonical_ncert_concepts_covered']} | {s['expected_concepts']} | "
            f"{s['canonical_ncert_bps']} | **{s['PROJECTED_capacity']}** | {s['expected_PROJECTED_capacity']} | "
            f"`{match}` | {s['failing_bps']} |"
        )
    lines += [
        "",
        f"- **PROJECTED total:** `{a['PROJECTED_total_capacity']}` (expected `{a['PROJECTED_total_expected']}`, match `{a['PROJECTED_match']}`)",
        "",
        "## Duplicates",
        f"- Multi-canonical-BP concepts: `{len(a['duplicates']['multi_canonical_bp_concepts'])}`",
        f"- Same concept + same target_count: `{len(a['duplicates']['same_concept_same_target'])}`",
        "",
        "## Exclusions",
        f"```json\n{json.dumps(a['exclusions'], indent=2)}\n```",
        "",
        "## Failures / anomalies requiring owner review",
    ]
    if a["failing_canonical"]:
        lines.append(f"- Canonical failures: `{len(a['failing_canonical'])}`")
        for r in a["failing_canonical"][:30]:
            lines.append(f"  - `{r['blueprint_key']}` / `{r['concept_code']}`: {r['failures']}")
    else:
        lines.append("- No canonical blueprint failures.")
    if a["anomalies"]:
        lines.append(f"- Anomalies: `{a['anomalies']}`")
    else:
        lines.append("- No count/capacity anomalies.")

    lines += [
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
        "**STOP** — no MCQ generation, no 400 pilot, no commit, no push.",
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
        blueprints = load_blueprints(conn)
        audit = run_audit(blueprints, ncert_root)
        after = snapshot(conn)

    identical = before == after
    if not identical:
        raise SystemExit("ABORT: snapshot drifted during read-only audit")

    tests = run_tests()

    material_ok = (
        audit["all_canonical_pass"]
        and freeze_ok(after)
        and identical
        and (tests.get("failed") or 0) == 0
        and tests.get("exit_code") == 0
    )

    # MERGE_REVIEW flag on sv2c-botany-15 is informational if a pre-existing
    # canonical BP exists; it does not alone block if all checks passed and
    # no merge was performed. Only block if it's in failing_canonical.
    if material_ok:
        final = "GREEN — MCQ PILOT AUTHORIZATION READY"
        verdict = (
            f"All {audit['canonical_count']} canonical NCERT blueprints passed integrity checks. "
            f"Legacy StudyMaterial={audit['legacy_protection']['studymaterial_count']}, "
            f"AI={audit['legacy_protection']['ai_count']} preserved. "
            f"PROJECTED capacity={audit['PROJECTED_total_capacity']}. "
            "Question/factory freeze intact. Ready for owner-authorized MCQ pilot — not started."
        )
    else:
        final = "YELLOW — MCQ PILOT BLOCKED"
        verdict = (
            f"Integrity gate blocked. canonical_failed={audit['canonical_failed']}, "
            f"anomalies={audit['anomalies']}. Do not start MCQ generation."
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
        "audit": audit,
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/bp_integrity_003_readonly.py",
        ],
        "confirmation": {
            "db_mutated": False,
            "blueprints_created": False,
            "blueprints_modified": False,
            "kus_modified": False,
            "mcqs_generated": False,
            "pilot_400_started": False,
            "published": False,
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
                "canonical": audit["canonical_count"],
                "canonical_passed": audit["canonical_passed"],
                "canonical_failed": audit["canonical_failed"],
                "legacy_sm": audit["legacy_protection"]["studymaterial_count"],
                "legacy_ai": audit["legacy_protection"]["ai_count"],
                "PROJECTED_capacity": audit["PROJECTED_total_capacity"],
                "anomalies": audit["anomalies"],
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
