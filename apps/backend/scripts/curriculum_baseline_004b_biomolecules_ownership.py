"""CF-C4b — Apply owner-approved Biomolecules ownership migration.

APPROVED:
  Biology XI Biomolecules → project ownership BOTANY, class_level=11
  Source: NCERT Class XI Biology kebo109.pdf Ch 9
  Preserve published questions + blueprints (concept IDs unchanged).

Surgical only. No MCQs / AI / Factory / blueprints / KU creation.
No question row mutation. No commit.
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
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    get_ncert_source_root,
    validate_ncert_generation_source,
)

REPORT_STEM = "curriculum_baseline_004b_biomolecules_ownership_20260913"
UNMAPPED_FREEZE = 5024
STATUS_FREEZE = {
    "DRAFT": 5298,
    "PUBLISHED": 1479,
    "SUPERSEDED": 6,
    "IN_REVIEW": 111,
}
CHAPTER_CODE = "biomolecules"
SOURCE_PDF = "Class 11/Biology/kebo1dd/kebo109.pdf"


def snapshot(engine) -> dict:
    with engine.connect() as conn:
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


def chapter_state(engine) -> list[dict]:
    with engine.connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT s.code AS subject, ch.id::text AS chapter_id, ch.code, ch.name, ch.class_level,
                      (SELECT COUNT(*) FROM academic.topics t WHERE t.chapter_id=ch.id AND t.deleted_at IS NULL) topics,
                      (SELECT COUNT(*) FROM academic.concepts c
                       JOIN academic.topics t ON t.id=c.topic_id
                       WHERE t.chapter_id=ch.id AND c.deleted_at IS NULL AND t.deleted_at IS NULL) concepts
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ch.deleted_at IS NULL AND ch.code = :code
                    ORDER BY s.code
                    """
                ),
                {"code": CHAPTER_CODE},
            ).mappings()
        ]


def dependency_fingerprint(engine, chapter_id: str) -> dict:
    with engine.connect() as conn:
        concepts = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT c.id::text AS concept_id, c.code, c.name
                    FROM academic.concepts c
                    JOIN academic.topics t ON t.id = c.topic_id
                    WHERE t.chapter_id = :cid AND c.deleted_at IS NULL AND t.deleted_at IS NULL
                    ORDER BY c.code
                    """
                ),
                {"cid": chapter_id},
            ).mappings()
        ]
        questions = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT ci.id::text AS question_id, ci.status, ci.slug, ci.concept_id::text AS concept_id,
                           ci.version
                    FROM cms.content_items ci
                    JOIN academic.concepts c ON c.id = ci.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    WHERE t.chapter_id = :cid AND ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
                    ORDER BY ci.id
                    """
                ),
                {"cid": chapter_id},
            ).mappings()
        ]
        blueprints = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT bp.id::text AS blueprint_id, bp.concept_id::text AS concept_id, bp.version
                    FROM cms.question_blueprints bp
                    JOIN academic.concepts c ON c.id = bp.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    WHERE t.chapter_id = :cid AND bp.deleted_at IS NULL
                    ORDER BY bp.id
                    """
                ),
                {"cid": chapter_id},
            ).mappings()
        ]
        status_counts = {
            r[0]: r[1]
            for r in conn.execute(
                text(
                    """
                    SELECT ci.status, COUNT(*)
                    FROM cms.content_items ci
                    JOIN academic.concepts c ON c.id = ci.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    WHERE t.chapter_id = :cid AND ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
                    GROUP BY ci.status
                    """
                ),
                {"cid": chapter_id},
            )
        }
    return {
        "concepts": concepts,
        "concept_ids": [c["concept_id"] for c in concepts],
        "questions": questions,
        "question_ids": [q["question_id"] for q in questions],
        "blueprints": blueprints,
        "blueprint_ids": [b["blueprint_id"] for b in blueprints],
        "question_status_counts": status_counts,
    }


def apply_migration(engine) -> dict:
    with engine.begin() as conn:
        botany_id = conn.execute(
            text("SELECT id FROM academic.subjects WHERE code = 'BOTANY' AND deleted_at IS NULL")
        ).scalar_one()
        zoology_id = conn.execute(
            text("SELECT id FROM academic.subjects WHERE code = 'ZOOLOGY' AND deleted_at IS NULL")
        ).scalar_one()

        # Collision guard: BOTANY must not already own biomolecules
        existing_botany = conn.execute(
            text(
                """
                SELECT id::text FROM academic.chapters
                WHERE subject_id = :sid AND code = :code AND deleted_at IS NULL
                """
            ),
            {"sid": botany_id, "code": CHAPTER_CODE},
        ).scalar_one_or_none()
        if existing_botany:
            # Idempotent path if already migrated
            row = conn.execute(
                text(
                    """
                    SELECT id::text, class_level FROM academic.chapters
                    WHERE id = :id AND deleted_at IS NULL
                    """
                ),
                {"id": existing_botany},
            ).mappings().one()
            if row["class_level"] != "11":
                conn.execute(
                    text("UPDATE academic.chapters SET class_level = '11', updated_at = NOW() WHERE id = :id"),
                    {"id": existing_botany},
                )
            return {
                "action": "already_on_botany",
                "chapter_id": existing_botany,
                "class_level_set": "11",
            }

        zoo_ch = conn.execute(
            text(
                """
                SELECT id::text FROM academic.chapters
                WHERE subject_id = :sid AND code = :code AND deleted_at IS NULL
                """
            ),
            {"sid": zoology_id, "code": CHAPTER_CODE},
        ).scalar_one_or_none()
        if not zoo_ch:
            raise RuntimeError("Neither ZOOLOGY nor BOTANY biomolecules chapter found")

        updated = conn.execute(
            text(
                """
                UPDATE academic.chapters
                SET subject_id = :botany_id,
                    class_level = '11',
                    updated_at = NOW()
                WHERE id = :cid AND deleted_at IS NULL
                RETURNING id::text
                """
            ),
            {"botany_id": botany_id, "cid": zoo_ch},
        ).scalar_one()

        return {
            "action": "moved_zoology_to_botany",
            "chapter_id": updated,
            "from_subject": "ZOOLOGY",
            "to_subject": "BOTANY",
            "class_level_set": "11",
        }


def revalidate(engine, chapter_id: str, before_fp: dict, after_fp: dict) -> dict:
    with engine.connect() as conn:
        ownership = conn.execute(
            text(
                """
                SELECT s.code AS subject, ch.class_level, ch.code, ch.name
                FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.id = :cid
                """
            ),
            {"cid": chapter_id},
        ).mappings().one()

        # Every published question under chapter must derive class_level = 11
        pub_derivable = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items ci
                JOIN academic.concepts c ON c.id = ci.concept_id
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                WHERE t.chapter_id = :cid
                  AND ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
                  AND ci.status = 'PUBLISHED'
                  AND ch.class_level = '11'
                  AND ch.subject_id = (SELECT id FROM academic.subjects WHERE code = 'BOTANY')
                """
            ),
            {"cid": chapter_id},
        ).scalar()
        pub_total = before_fp["question_status_counts"].get("PUBLISHED", 0)

        # No ZOOLOGY biomolecules left
        zoo_left = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code = 'ZOOLOGY' AND ch.code = :code AND ch.deleted_at IS NULL
                """
            ),
            {"code": CHAPTER_CODE},
        ).scalar()

        chem_intact = conn.execute(
            text(
                """
                SELECT s.code, ch.class_level,
                  (SELECT COUNT(*) FROM academic.topics t WHERE t.chapter_id=ch.id AND t.deleted_at IS NULL)
                FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.code = 'biomolecules-chem' AND ch.deleted_at IS NULL
                """
            )
        ).one()

    concept_ids_ok = before_fp["concept_ids"] == after_fp["concept_ids"]
    questions_ok = before_fp["questions"] == after_fp["questions"]
    blueprints_ok = before_fp["blueprints"] == after_fp["blueprints"]
    ownership_ok = ownership["subject"] == "BOTANY" and ownership["class_level"] == "11"
    published_ok = pub_derivable == pub_total

    return {
        "ownership": dict(ownership),
        "zoo_biomolecules_remaining": zoo_left,
        "chemistry_biomolecules_chem": {
            "subject": chem_intact[0],
            "class_level": chem_intact[1],
            "topics": chem_intact[2],
        },
        "concept_ids_preserved": concept_ids_ok,
        "questions_preserved": questions_ok,
        "blueprints_preserved": blueprints_ok,
        "published_derive_class_11": published_ok,
        "published_count": pub_total,
        "published_derivable": pub_derivable,
        "ok": (
            ownership_ok
            and zoo_left == 0
            and concept_ids_ok
            and questions_ok
            and blueprints_ok
            and published_ok
            and chem_intact[0] == "CHEMISTRY"
            and chem_intact[1] == "12"
        ),
    }


def integrity(engine) -> dict:
    with engine.connect() as conn:
        dups = conn.execute(
            text(
                """
                SELECT s.code, ch.code, COUNT(*) FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.deleted_at IS NULL GROUP BY 1,2 HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        orphan_topics = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.topics t
                LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                WHERE t.deleted_at IS NULL AND ch.id IS NULL
                """
            )
        ).scalar()
        orphan_concepts = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.concepts c
                LEFT JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                WHERE c.deleted_at IS NULL AND t.id IS NULL
                """
            )
        ).scalar()
    return {
        "duplicate_chapters": [list(r) for r in dups],
        "orphan_topics": orphan_topics,
        "orphan_concepts": orphan_concepts,
        "ok": not dups and orphan_topics == 0 and orphan_concepts == 0,
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
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m_pass = re.search(r"(\d+)\s+passed", out)
    m_fail = re.search(r"(\d+)\s+failed", out)
    return {
        "passed": int(m_pass.group(1)) if m_pass else None,
        "failed": int(m_fail.group(1)) if m_fail else (0 if proc.returncode == 0 else None),
        "exit_code": proc.returncode,
        "command": " ".join(cmd),
        "tail": "\n".join(out.strip().splitlines()[-50:]),
    }


def write_report(payload: dict) -> tuple[Path, Path]:
    out = ROOT / "docs" / "audits"
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{REPORT_STEM}.json"
    mp = out / f"{REPORT_STEM}.md"
    jp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# CF-C4b — Biomolecules ownership migration (owner-approved)",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Decision applied: Biology XI Biomolecules → **BOTANY**, class_level=**11**",
        f"- Source PDF: `{SOURCE_PDF}` (project taxonomy decision; not an NCERT subject claim)",
        "- Git: **no commit / no push**",
        "",
        "## Migration",
        "```json",
        json.dumps(payload["migration"], indent=2),
        "```",
        "",
        "## Before / after chapter state",
        f"- Before: `{payload['chapters_before']}`",
        f"- After: `{payload['chapters_after']}`",
        "",
        "## Preservation / revalidation",
        "```json",
        json.dumps(payload["revalidation"], indent=2, default=str),
        "```",
        "",
        "## Safety",
        "### Before",
        "```json",
        json.dumps(payload["before"], indent=2),
        "```",
        "### After",
        "```json",
        json.dumps(payload["after"], indent=2),
        "```",
        f"- Freeze OK: `{payload['freeze_ok']}`",
        f"- Content safety unchanged: `{payload['content_safety_unchanged']}`",
        "",
        "## Integrity",
        "```json",
        json.dumps(payload["integrity"], indent=2),
        "```",
        "",
        "## Tests",
        f"- Passed: `{payload['tests']['passed']}` Failed: `{payload['tests']['failed']}` exit=`{payload['tests']['exit_code']}`",
        f"- `{payload['tests']['command']}`",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## Files changed",
    ]
    for f in payload.get("files_changed") or []:
        lines.append(f"- `{f}`")
    lines.append("")
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jp, mp


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    root = get_ncert_source_root()
    pdf = root / SOURCE_PDF
    validate_ncert_generation_source(pdf, root=root)

    before = snapshot(engine)
    chapters_before = chapter_state(engine)

    # Prefer ZOOLOGY chapter if present, else BOTANY (idempotent)
    target = next((c for c in chapters_before if c["subject"] == "ZOOLOGY"), None)
    if not target:
        target = next((c for c in chapters_before if c["subject"] == "BOTANY"), None)
    if not target:
        raise SystemExit("biomolecules chapter not found")

    before_fp = dependency_fingerprint(engine, target["chapter_id"])
    migration = apply_migration(engine)

    chapters_after = chapter_state(engine)
    after_chapter = next(c for c in chapters_after if c["subject"] == "BOTANY")
    after_fp = dependency_fingerprint(engine, after_chapter["chapter_id"])
    reval = revalidate(engine, after_chapter["chapter_id"], before_fp, after_fp)

    after = snapshot(engine)
    content_safety = before["status"] == after["status"] and before["unmapped_draft"] == after["unmapped_draft"]
    freeze_ok = after["unmapped_draft"] == UNMAPPED_FREEZE and after["status"] == STATUS_FREEZE
    integ = integrity(engine)
    tests = run_tests()

    if not content_safety or not freeze_ok or not reval["ok"] or not integ["ok"] or tests.get("exit_code") != 0:
        status = "RED — FAILED"
    elif after_chapter["subject"] == "BOTANY" and after_chapter["class_level"] == "11":
        status = "GREEN — COMPLETE/VERIFIED"
    else:
        status = "YELLOW — PARTIALLY VERIFIED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": status,
        "approved_decision": {
            "biology_subject_label": "BIOLOGY",
            "project_ownership": "BOTANY",
            "class_level": "11",
            "source_pdf": SOURCE_PDF,
            "ncert_chapter": "Class XI Biology Ch 9 Biomolecules",
        },
        "source_pdf_validated": True,
        "migration": migration,
        "chapters_before": chapters_before,
        "chapters_after": chapters_after,
        "before_fingerprint": {
            "concept_ids": before_fp["concept_ids"],
            "question_ids": before_fp["question_ids"],
            "blueprint_ids": before_fp["blueprint_ids"],
            "question_status_counts": before_fp["question_status_counts"],
        },
        "after_fingerprint": {
            "concept_ids": after_fp["concept_ids"],
            "question_ids": after_fp["question_ids"],
            "blueprint_ids": after_fp["blueprint_ids"],
            "question_status_counts": after_fp["question_status_counts"],
        },
        "revalidation": reval,
        "before": before,
        "after": after,
        "content_safety_unchanged": content_safety,
        "freeze_ok": freeze_ok,
        "integrity": integ,
        "tests": tests,
        "files_changed": [
            "apps/backend/scripts/curriculum_baseline_004b_biomolecules_ownership.py",
            "apps/backend/app/modules/academic/seed.py",
            "apps/backend/app/modules/academic/models/chapter.py",
            "apps/backend/app/modules/academic/tests/test_chapter_class_level.py",
            "apps/backend/app/modules/academic/tests/test_cf_c1_chemistry_class_12.py",
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
        ],
        "confirmation": {
            "questions_mutated": False,
            "concept_ids_changed": before_fp["concept_ids"] != after_fp["concept_ids"],
            "mcqs_generated": False,
            "ai_called": False,
            "blueprints_created": False,
        },
    }
    jp, mp = write_report(payload)
    print(
        json.dumps(
            {
                "final_status": status,
                "json": str(jp),
                "md": str(mp),
                "migration": migration,
                "revalidation_ok": reval["ok"],
                "freeze_ok": freeze_ok,
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
                "chapters_after": chapters_after,
            },
            indent=2,
            default=str,
        )
    )
    return 0 if status.startswith("GREEN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
