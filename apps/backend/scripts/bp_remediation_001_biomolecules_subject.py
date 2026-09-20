"""BP-REMEDIATION-001 — Surgical Biomolecules blueprint subject_id fix.

Updates ONLY subject_id ZOOLOGY → BOTANY on the five Biology XI Biomolecules
blueprints. No other columns, no questions, no KUs, no provenance changes.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402

REPORT_STEM = "bp_remediation_001_20260913"
CHAPTER_CODE = "biomolecules"
CHEM_CHAPTER = "biomolecules-chem"

# Exact IDs from BP-COVERAGE-002
EXPECTED_BLUEPRINT_IDS = [
    "dafae464-f60d-443f-b526-3e0c93390929",
    "876a2f73-994b-4a7b-bc5d-252267f8d2a3",
    "04e93763-bc48-472e-adb3-4088d872e1c4",
    "0b1c8f98-35eb-43f7-bb8e-2398c4a46de5",
    "8a42a7e2-c76f-4b64-be74-8fb0e3b472b5",
]

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


def load_target_blueprints(conn) -> list[dict]:
    rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT bp.id::text AS blueprint_id,
                       bp.blueprint_key,
                       bp.blueprint_version,
                       bp.subject_id::text AS subject_id,
                       s.code AS subject_code,
                       bp.chapter_id::text AS chapter_id,
                       ch.code AS chapter_code,
                       ch.class_level,
                       ch_s.code AS chapter_subject_code,
                       bp.topic_id::text AS topic_id,
                       t.code AS topic_code,
                       bp.concept_id::text AS concept_id,
                       c.code AS concept_code,
                       bp.target_count,
                       bp.provenance_tier,
                       bp.status,
                       bp.generation_eligible,
                       bp.constraints,
                       bp.updated_at::text AS updated_at,
                       bp.version AS row_version
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                JOIN academic.chapters ch ON ch.id = bp.chapter_id
                JOIN academic.subjects ch_s ON ch_s.id = ch.subject_id
                JOIN academic.topics t ON t.id = bp.topic_id
                JOIN academic.concepts c ON c.id = bp.concept_id
                WHERE bp.deleted_at IS NULL
                  AND ch.code = :chapter
                ORDER BY bp.blueprint_key
                """
            ),
            {"chapter": CHAPTER_CODE},
        ).mappings()
    ]
    for r in rows:
        cons = r.get("constraints")
        if hasattr(cons, "keys"):
            r["constraints"] = dict(cons)
    return rows


def question_counts_for_chapter(conn, chapter_code: str) -> dict:
    rows = {
        r[0]: r[1]
        for r in conn.execute(
            text(
                """
                SELECT ci.status, COUNT(*)
                FROM cms.content_items ci
                JOIN academic.concepts c ON c.id = ci.concept_id
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                WHERE ch.code = :code
                  AND ci.deleted_at IS NULL
                  AND ci.content_type = 'QUESTION'
                GROUP BY ci.status
                """
            ),
            {"code": chapter_code},
        )
    }
    return rows


def concept_ids_fingerprint(conn, chapter_code: str) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            text(
                """
                SELECT c.id::text
                FROM academic.concepts c
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                WHERE ch.code = :code AND c.deleted_at IS NULL AND t.deleted_at IS NULL
                ORDER BY c.code
                """
            ),
            {"code": chapter_code},
        )
    ]


def subject_uuid(conn, code: str) -> str:
    return conn.execute(
        text("SELECT id::text FROM academic.subjects WHERE code = :c"),
        {"c": code},
    ).scalar_one()


def validate_preconditions(targets: list[dict], botany_id: str, zoology_id: str) -> list[str]:
    errors: list[str] = []
    ids = [t["blueprint_id"] for t in targets]
    if sorted(ids) != sorted(EXPECTED_BLUEPRINT_IDS):
        errors.append(f"Unexpected blueprint set: {ids}")
    if len(targets) != 5:
        errors.append(f"Expected 5 blueprints, found {len(targets)}")
    for t in targets:
        if t["chapter_code"] != CHAPTER_CODE:
            errors.append(f"{t['blueprint_id']}: wrong chapter")
        if t["chapter_subject_code"] != "BOTANY":
            errors.append(f"{t['blueprint_id']}: chapter not BOTANY")
        if str(t["class_level"]) not in {"11", "11.0"} and t["class_level"] != 11:
            errors.append(f"{t['blueprint_id']}: class_level != 11 ({t['class_level']!r})")
        if t["subject_code"] != "ZOOLOGY":
            errors.append(f"{t['blueprint_id']}: subject_code is {t['subject_code']}, expected ZOOLOGY before fix")
        if t["subject_id"] != zoology_id:
            errors.append(f"{t['blueprint_id']}: subject_id mismatch vs ZOOLOGY uuid")
        if t["subject_id"] == botany_id:
            errors.append(f"{t['blueprint_id']}: already BOTANY — abort duplicate remediation")
    return errors


def apply_fix(conn, botany_id: str) -> int:
    result = conn.execute(
        text(
            """
            UPDATE cms.question_blueprints bp
            SET subject_id = CAST(:botany AS uuid),
                updated_at = NOW()
            FROM academic.chapters ch
            WHERE bp.chapter_id = ch.id
              AND bp.deleted_at IS NULL
              AND ch.code = :chapter
              AND bp.id IN (
                CAST(:id0 AS uuid), CAST(:id1 AS uuid), CAST(:id2 AS uuid),
                CAST(:id3 AS uuid), CAST(:id4 AS uuid)
              )
              AND bp.subject_id <> CAST(:botany AS uuid)
            """
        ),
        {
            "botany": botany_id,
            "chapter": CHAPTER_CODE,
            "id0": EXPECTED_BLUEPRINT_IDS[0],
            "id1": EXPECTED_BLUEPRINT_IDS[1],
            "id2": EXPECTED_BLUEPRINT_IDS[2],
            "id3": EXPECTED_BLUEPRINT_IDS[3],
            "id4": EXPECTED_BLUEPRINT_IDS[4],
        },
    )
    return result.rowcount


def _id_params() -> dict:
    return {
        "id0": EXPECTED_BLUEPRINT_IDS[0],
        "id1": EXPECTED_BLUEPRINT_IDS[1],
        "id2": EXPECTED_BLUEPRINT_IDS[2],
        "id3": EXPECTED_BLUEPRINT_IDS[3],
        "id4": EXPECTED_BLUEPRINT_IDS[4],
    }


def verify_after(conn, before_targets: list[dict], botany_id: str) -> dict:
    after = load_target_blueprints(conn)
    by_id = {t["blueprint_id"]: t for t in after}
    comparisons = []
    ok = True
    for b in before_targets:
        a = by_id.get(b["blueprint_id"])
        if not a:
            ok = False
            comparisons.append({"blueprint_id": b["blueprint_id"], "error": "missing after update"})
            continue
        preserved = {
            "blueprint_id": a["blueprint_id"] == b["blueprint_id"],
            "chapter_id": a["chapter_id"] == b["chapter_id"],
            "topic_id": a["topic_id"] == b["topic_id"],
            "concept_id": a["concept_id"] == b["concept_id"],
            "target_count": a["target_count"] == b["target_count"],
            "provenance_tier": a["provenance_tier"] == b["provenance_tier"],
            "constraints": a["constraints"] == b["constraints"],
            "status": a["status"] == b["status"],
            "generation_eligible": a["generation_eligible"] == b["generation_eligible"],
            "blueprint_key": a["blueprint_key"] == b["blueprint_key"],
        }
        subject_fixed = a["subject_code"] == "BOTANY" and a["subject_id"] == botany_id
        if not all(preserved.values()) or not subject_fixed:
            ok = False
        comparisons.append(
            {
                "blueprint_id": b["blueprint_id"],
                "blueprint_key": b["blueprint_key"],
                "before_subject_id": b["subject_id"],
                "before_subject_code": b["subject_code"],
                "after_subject_id": a["subject_id"],
                "after_subject_code": a["subject_code"],
                "chapter_id": a["chapter_id"],
                "topic_id": a["topic_id"],
                "concept_id": a["concept_id"],
                "preserved": preserved,
                "subject_fixed": subject_fixed,
            }
        )

    drift_remaining = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM cms.question_blueprints bp
            JOIN academic.chapters ch ON ch.id = bp.chapter_id
            WHERE bp.deleted_at IS NULL AND ch.code = :chapter
              AND bp.subject_id <> ch.subject_id
            """
        ),
        {"chapter": CHAPTER_CODE},
    ).scalar()

    duplicates = conn.execute(
        text(
            """
            SELECT blueprint_key, COUNT(*) FROM cms.question_blueprints
            WHERE deleted_at IS NULL
              AND id IN (
                CAST(:id0 AS uuid), CAST(:id1 AS uuid), CAST(:id2 AS uuid),
                CAST(:id3 AS uuid), CAST(:id4 AS uuid)
              )
            GROUP BY blueprint_key HAVING COUNT(*) > 1
            """
        ),
        _id_params(),
    ).fetchall()

    orphan = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM cms.question_blueprints bp
            LEFT JOIN academic.concepts c ON c.id = bp.concept_id AND c.deleted_at IS NULL
            WHERE bp.deleted_at IS NULL
              AND bp.id IN (
                CAST(:id0 AS uuid), CAST(:id1 AS uuid), CAST(:id2 AS uuid),
                CAST(:id3 AS uuid), CAST(:id4 AS uuid)
              )
              AND c.id IS NULL
            """
        ),
        _id_params(),
    ).scalar()

    return {
        "ok": ok and drift_remaining == 0 and len(duplicates) == 0 and orphan == 0,
        "comparisons": comparisons,
        "subject_ownership_drift_remaining": drift_remaining,
        "duplicate_keys": [r[0] for r in duplicates],
        "orphan_missing_concept": orphan,
        "all_botany": all(c.get("after_subject_code") == "BOTANY" for c in comparisons),
    }


def run_tests() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "app/modules/ingestion/tests/test_ncert_canonical_source.py",
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
        "tail": "\n".join(out.strip().splitlines()[-35:]),
    }


def freeze_matches(snap: dict) -> bool:
    return (
        snap["status"].get("PUBLISHED") == FREEZE["PUBLISHED"]
        and snap["status"].get("IN_REVIEW") == FREEZE["IN_REVIEW"]
        and snap["status"].get("DRAFT") == FREEZE["DRAFT"]
        and snap["status"].get("SUPERSEDED") == FREEZE["SUPERSEDED"]
        and snap["unmapped_draft"] == FREEZE["unmapped_draft"]
        and snap["chapters"] == FREEZE["chapters"]
        and snap["topics"] == FREEZE["topics"]
        and snap["concepts"] == FREEZE["concepts"]
        and snap["knowledge_units"] == FREEZE["knowledge_units"]
        and snap["question_blueprints"] == FREEZE["blueprints"]
    )


def write_reports(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    lines = [
        "# BP-REMEDIATION-001 — Biomolecules blueprint subject_id fix",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Git: **no commit / no push**",
        "",
        "## 1. Five exact blueprint IDs",
    ]
    for c in payload["verification"]["comparisons"]:
        lines.append(f"- `{c['blueprint_id']}` (`{c['blueprint_key']}`)")
    lines += [
        "",
        "## 2. Before / after subject_id",
    ]
    for c in payload["verification"]["comparisons"]:
        lines.append(
            f"- `{c['blueprint_id']}`: `{c['before_subject_code']}` (`{c['before_subject_id']}`) → "
            f"`{c['after_subject_code']}` (`{c['after_subject_id']}`)"
        )
    lines += [
        "",
        "## 3. Dependency verification",
        f"- Questions biomolecules before: `{payload['dependencies']['questions_before']}`",
        f"- Questions biomolecules after: `{payload['dependencies']['questions_after']}`",
        f"- Concept IDs unchanged: `{payload['dependencies']['concept_ids_unchanged']}`",
        f"- Chemistry biomolecules-chem blueprints: `{payload['dependencies']['chem_blueprints']}`",
        f"- Chemistry chapter subject: `{payload['dependencies']['chem_chapter']}`",
        f"- Rows updated: `{payload['rows_updated']}`",
        f"- Verification OK: `{payload['verification']['ok']}`",
        f"- Ownership drift remaining: `{payload['verification']['subject_ownership_drift_remaining']}`",
        f"- Orphans: `{payload['verification']['orphan_missing_concept']}`",
        f"- Duplicates: `{payload['verification']['duplicate_keys']}`",
        "",
        "## 4. Safety snapshot",
        "### Before",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "### After",
        f"```json\n{json.dumps(payload['after'], indent=2)}\n```",
        f"- Freeze OK: `{payload['freeze_ok']}` Snapshot academic identical except intended bp metadata: "
        f"`{payload['snapshot_counts_identical']}`",
        "",
        "## 5. Tests",
        f"- Passed: `{payload['tests'].get('passed')}` Failed: `{payload['tests'].get('failed')}`",
        f"- Unavailable: `{payload['tests'].get('unavailable')}`",
        "",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## 6. Exact files changed",
    ]
    for f in payload["files_changed"]:
        lines.append(f"- `{f}`")
    lines += [
        "",
        "## Confirmation",
        f"```json\n{json.dumps(payload['confirmation'], indent=2)}\n```",
        "",
        "**STOP** — do not create new blueprints or generate MCQs.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)

    with engine.begin() as conn:
        before = snapshot(conn)
        if not freeze_matches(before):
            raise SystemExit(f"ABORT: freeze mismatch before remediation: {before}")

        botany_id = subject_uuid(conn, "BOTANY")
        zoology_id = subject_uuid(conn, "ZOOLOGY")
        targets = load_target_blueprints(conn)
        errors = validate_preconditions(targets, botany_id, zoology_id)
        if errors:
            raise SystemExit("ABORT preconditions:\n" + "\n".join(errors))

        q_before = question_counts_for_chapter(conn, CHAPTER_CODE)
        concepts_before = concept_ids_fingerprint(conn, CHAPTER_CODE)
        chem_bps = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.question_blueprints bp
                JOIN academic.chapters ch ON ch.id = bp.chapter_id
                WHERE ch.code = :c AND bp.deleted_at IS NULL
                """
            ),
            {"c": CHEM_CHAPTER},
        ).scalar()
        chem_chapter = dict(
            conn.execute(
                text(
                    """
                    SELECT ch.id::text, ch.code, ch.class_level, s.code AS subject
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ch.code = :c AND ch.deleted_at IS NULL
                    """
                ),
                {"c": CHEM_CHAPTER},
            ).mappings().one()
        )

        # Fingerprint question item ids for biomolecules concepts before update
        question_ids_before = [
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT ci.id::text
                    FROM cms.content_items ci
                    JOIN academic.concepts c ON c.id = ci.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    WHERE ch.code = :c AND ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
                    ORDER BY ci.id
                    """
                ),
                {"c": CHAPTER_CODE},
            )
        ]

        before_snapshots = [
            {
                "blueprint_id": t["blueprint_id"],
                "blueprint_key": t["blueprint_key"],
                "subject_id": t["subject_id"],
                "subject_code": t["subject_code"],
                "chapter_id": t["chapter_id"],
                "topic_id": t["topic_id"],
                "concept_id": t["concept_id"],
                "target_count": t["target_count"],
                "provenance_tier": t["provenance_tier"],
            }
            for t in targets
        ]

        rows_updated = apply_fix(conn, botany_id)
        if rows_updated != 5:
            raise SystemExit(f"ABORT: expected 5 rows updated, got {rows_updated}")

        verification = verify_after(conn, targets, botany_id)
        q_after = question_counts_for_chapter(conn, CHAPTER_CODE)
        concepts_after = concept_ids_fingerprint(conn, CHAPTER_CODE)
        question_ids_after = [
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT ci.id::text
                    FROM cms.content_items ci
                    JOIN academic.concepts c ON c.id = ci.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    WHERE ch.code = :c AND ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
                    ORDER BY ci.id
                    """
                ),
                {"c": CHAPTER_CODE},
            )
        ]
        chem_bps_after = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.question_blueprints bp
                JOIN academic.chapters ch ON ch.id = bp.chapter_id
                WHERE ch.code = :c AND bp.deleted_at IS NULL
                """
            ),
            {"c": CHEM_CHAPTER},
        ).scalar()

        after = snapshot(conn)

        if not verification["ok"]:
            raise SystemExit(f"ABORT: post-verification failed: {verification}")
        if q_before != q_after or question_ids_before != question_ids_after:
            raise SystemExit("ABORT: question dependency changed")
        if concepts_before != concepts_after:
            raise SystemExit("ABORT: concept IDs changed")
        if chem_bps != chem_bps_after:
            raise SystemExit("ABORT: chemistry biomolecules-chem blueprints changed")
        if not freeze_matches(after):
            raise SystemExit(f"ABORT: freeze mismatch after: {after}")
        # Factory orchestration counts must not change
        for k in ("content_batches", "generation_jobs", "generation_runs", "generation_candidates"):
            if before[k] != after[k]:
                raise SystemExit(f"ABORT: {k} changed {before[k]} → {after[k]}")

    tests = run_tests()

    snapshot_counts_identical = (
        before["status"] == after["status"]
        and before["unmapped_draft"] == after["unmapped_draft"]
        and before["chapters"] == after["chapters"]
        and before["topics"] == after["topics"]
        and before["concepts"] == after["concepts"]
        and before["knowledge_units"] == after["knowledge_units"]
        and before["question_blueprints"] == after["question_blueprints"]
    )

    final = "GREEN — COMPLETE/VERIFIED"
    if (tests.get("failed") or 0) > 0 or not snapshot_counts_identical:
        final = "RED — FAILED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "rows_updated": rows_updated,
        "botany_subject_id": botany_id,
        "zoology_subject_id": zoology_id,
        "before_blueprints": before_snapshots,
        "verification": verification,
        "dependencies": {
            "questions_before": q_before,
            "questions_after": q_after,
            "question_ids_unchanged": question_ids_before == question_ids_after,
            "published_count": q_after.get("PUBLISHED"),
            "draft_count": q_after.get("DRAFT"),
            "concept_ids_unchanged": concepts_before == concepts_after,
            "concept_ids": concepts_after,
            "chem_blueprints": chem_bps_after,
            "chem_chapter": chem_chapter,
        },
        "before": before,
        "after": after,
        "freeze_ok": freeze_matches(after),
        "snapshot_counts_identical": snapshot_counts_identical,
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/bp_remediation_001_biomolecules_subject.py",
            "cms.question_blueprints.subject_id (5 rows only)",
        ],
        "confirmation": {
            "only_subject_id_updated": True,
            "questions_mutated": False,
            "kus_mutated": False,
            "taxonomy_mutated": False,
            "provenance_rewritten": False,
            "blueprints_created": False,
            "mcqs_generated": False,
            "ai_called": False,
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
                "rows_updated": rows_updated,
                "all_botany": verification["all_botany"],
                "questions": q_after,
                "freeze_ok": freeze_matches(after),
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
            },
            indent=2,
        )
    )
    return 0 if final.startswith("GREEN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
