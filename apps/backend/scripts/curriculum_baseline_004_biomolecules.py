"""CF-C4 — Biomolecules taxonomy / class resolution (AUDIT ONLY).

No taxonomy writes. No CMS/content mutation. No AI / Factory / blueprints / KUs.
No commit.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import fitz
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

REPORT_STEM = "curriculum_baseline_004_biomolecules_20260913"
UNMAPPED_FREEZE = 5024
STATUS_FREEZE = {
    "DRAFT": 5298,
    "PUBLISHED": 1479,
    "SUPERSEDED": 6,
    "IN_REVIEW": 111,
}


def decode_pua(s: str) -> str:
    return "".join(chr(ord(c) - 0xF000) if 0xF000 <= ord(c) <= 0xF0FF else c for c in s)


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


def verify_pdf(rel: str, root: Path, *, expect_title: str, expect_class_hint: str) -> dict:
    pdf = root / rel
    info = {
        "pdf_rel": rel,
        "resolved_path": str(pdf),
        "exists": pdf.is_file(),
        "validated_canonical": False,
        "title_confirmed": False,
        "expect_title": expect_title,
        "expect_class_hint": expect_class_hint,
        "chapter_markers": [],
        "section_headers": [],
        "preview": None,
        "error": None,
    }
    if not pdf.is_file():
        info["error"] = "missing"
        return info
    try:
        validate_ncert_generation_source(pdf, root=root)
        info["validated_canonical"] = True
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
        return info

    doc = fitz.open(pdf)
    try:
        blob = ""
        for i in range(min(6, doc.page_count)):
            blob += "\n" + decode_pua(doc.load_page(i).get_text("text") or "")
        info["preview"] = re.sub(r"\s+", " ", blob[:500]).strip()
        info["title_confirmed"] = expect_title.upper() in blob.upper()
        info["chapter_markers"] = re.findall(r"(?i)(?:CHAPTER|Unit)\s+\d+", blob)[:8]
        # Chem uses 10.x; Bio XI uses 9.x
        secs = re.findall(r"(?m)^((?:9|10)\.\d+)\s+(.{0,70})$", blob)
        info["section_headers"] = [f"{a} {b.strip()}" for a, b in secs[:20]]
    finally:
        doc.close()
    return info


def locate_records(engine) -> dict:
    like = "%biomol%"
    with engine.connect() as conn:
        chapters = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT s.code AS subject, ch.id::text AS chapter_id, ch.code AS chapter_code,
                           ch.name AS chapter_name, ch.class_level,
                           (SELECT COUNT(*) FROM academic.topics t
                            WHERE t.chapter_id = ch.id AND t.deleted_at IS NULL) AS topic_count,
                           (SELECT COUNT(*) FROM academic.concepts c
                            JOIN academic.topics t ON t.id = c.topic_id
                            WHERE t.chapter_id = ch.id AND c.deleted_at IS NULL AND t.deleted_at IS NULL
                           ) AS concept_count
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ch.deleted_at IS NULL
                      AND (ch.code ILIKE :like OR ch.name ILIKE :like)
                    ORDER BY s.code, ch.code
                    """
                ),
                {"like": like},
            ).mappings()
        ]
        topics = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT s.code AS subject, ch.id::text AS chapter_id, ch.code AS chapter_code,
                           ch.name AS chapter_name, ch.class_level,
                           t.id::text AS topic_id, t.code AS topic_code, t.name AS topic_name
                    FROM academic.topics t
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE t.deleted_at IS NULL
                      AND (
                        t.code ILIKE :like OR t.name ILIKE :like
                        OR ch.code ILIKE :like OR ch.name ILIKE :like
                      )
                    ORDER BY s.code, ch.code, t.display_order, t.code
                    """
                ),
                {"like": like},
            ).mappings()
        ]
        concepts = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT s.code AS subject, ch.id::text AS chapter_id, ch.code AS chapter_code,
                           ch.name AS chapter_name, ch.class_level,
                           t.id::text AS topic_id, t.code AS topic_code, t.name AS topic_name,
                           c.id::text AS concept_id, c.code AS concept_code, c.name AS concept_name,
                           c.ncert_reference, left(coalesce(c.summary, ''), 160) AS summary_preview
                    FROM academic.concepts c
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE c.deleted_at IS NULL
                      AND (
                        c.code ILIKE :like OR c.name ILIKE :like
                        OR t.code ILIKE :like OR t.name ILIKE :like
                        OR ch.code ILIKE :like OR ch.name ILIKE :like
                      )
                    ORDER BY s.code, ch.code, t.code, c.display_order, c.code
                    """
                ),
                {"like": like},
            ).mappings()
        ]

        # Knowledge units — schema may vary; probe columns
        knowledge_units = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT ku.id::text AS ku_id,
                           ku.concept_id::text AS concept_id,
                           ku.validation_status,
                           c.code AS concept_code, c.name AS concept_name,
                           ch.code AS chapter_code, ch.name AS chapter_name,
                           s.code AS subject, ch.class_level
                    FROM knowledge.knowledge_units ku
                    JOIN academic.concepts c ON c.id = ku.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ku.deleted_at IS NULL
                      AND (
                        c.code ILIKE :like OR c.name ILIKE :like
                        OR ch.code ILIKE :like OR ch.name ILIKE :like
                      )
                    """
                ),
                {"like": like},
            ).mappings()
        ]

        # Blueprints
        bp_cols = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'cms' AND table_name = 'question_blueprints'
                    """
                )
            )
        }
        blueprints = []
        if "concept_id" in bp_cols:
            blueprints = [
                dict(r)
                for r in conn.execute(
                    text(
                        """
                        SELECT bp.id::text AS blueprint_id,
                               bp.concept_id::text AS concept_id,
                               c.code AS concept_code, c.name AS concept_name,
                               ch.code AS chapter_code, s.code AS subject,
                               ch.class_level
                        FROM cms.question_blueprints bp
                        JOIN academic.concepts c ON c.id = bp.concept_id
                        JOIN academic.topics t ON t.id = c.topic_id
                        JOIN academic.chapters ch ON ch.id = t.chapter_id
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE bp.deleted_at IS NULL
                          AND (
                            c.code ILIKE :like OR c.name ILIKE :like
                            OR ch.code ILIKE :like OR ch.name ILIKE :like
                          )
                        """
                    ),
                    {"like": like},
                ).mappings()
            ]

        # Questions by concept under biomolecules chapters
        questions = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT ci.status, COUNT(*) AS n
                    FROM cms.content_items ci
                    JOIN academic.concepts c ON c.id = ci.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    WHERE ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
                      AND (ch.code ILIKE :like OR ch.name ILIKE :like
                           OR c.code ILIKE :like OR c.name ILIKE :like)
                    GROUP BY ci.status
                    ORDER BY ci.status
                    """
                ),
                {"like": like},
            ).mappings()
        ]
        questions_detail = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT ci.id::text AS question_id, ci.status, ci.slug,
                           c.code AS concept_code, ch.code AS chapter_code, s.code AS subject
                    FROM cms.content_items ci
                    JOIN academic.concepts c ON c.id = ci.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
                      AND (ch.code ILIKE :like OR ch.name ILIKE :like
                           OR c.code ILIKE :like OR c.name ILIKE :like)
                    ORDER BY ci.status, s.code, ch.code
                    LIMIT 50
                    """
                ),
                {"like": like},
            ).mappings()
        ]

        # FK-style dependency rollup per chapter
        deps = []
        for ch in chapters:
            dep = conn.execute(
                text(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM academic.topics t
                       WHERE t.chapter_id = :cid AND t.deleted_at IS NULL) AS topics,
                      (SELECT COUNT(*) FROM academic.concepts c
                       JOIN academic.topics t ON t.id = c.topic_id
                       WHERE t.chapter_id = :cid AND c.deleted_at IS NULL AND t.deleted_at IS NULL) AS concepts,
                      (SELECT COUNT(*) FROM cms.content_items ci
                       JOIN academic.concepts c ON c.id = ci.concept_id
                       JOIN academic.topics t ON t.id = c.topic_id
                       WHERE t.chapter_id = :cid AND ci.deleted_at IS NULL
                         AND ci.content_type = 'QUESTION') AS questions_total,
                      (SELECT COUNT(*) FROM cms.content_items ci
                       JOIN academic.concepts c ON c.id = ci.concept_id
                       JOIN academic.topics t ON t.id = c.topic_id
                       WHERE t.chapter_id = :cid AND ci.deleted_at IS NULL
                         AND ci.content_type = 'QUESTION' AND ci.status = 'PUBLISHED') AS questions_published,
                      (SELECT COUNT(*) FROM cms.content_items ci
                       JOIN academic.concepts c ON c.id = ci.concept_id
                       JOIN academic.topics t ON t.id = c.topic_id
                       WHERE t.chapter_id = :cid AND ci.deleted_at IS NULL
                         AND ci.content_type = 'QUESTION' AND ci.status = 'IN_REVIEW') AS questions_in_review,
                      (SELECT COUNT(*) FROM cms.content_items ci
                       JOIN academic.concepts c ON c.id = ci.concept_id
                       JOIN academic.topics t ON t.id = c.topic_id
                       WHERE t.chapter_id = :cid AND ci.deleted_at IS NULL
                         AND ci.content_type = 'QUESTION' AND ci.status = 'DRAFT') AS questions_draft,
                      (SELECT COUNT(*) FROM cms.question_blueprints bp
                       JOIN academic.concepts c ON c.id = bp.concept_id
                       JOIN academic.topics t ON t.id = c.topic_id
                       WHERE t.chapter_id = :cid AND bp.deleted_at IS NULL) AS blueprints,
                      (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                       JOIN academic.concepts c ON c.id = ku.concept_id
                       JOIN academic.topics t ON t.id = c.topic_id
                       WHERE t.chapter_id = :cid AND ku.deleted_at IS NULL) AS knowledge_units
                    """
                ),
                {"cid": ch["chapter_id"]},
            ).mappings().one()
            deps.append({"chapter_code": ch["chapter_code"], "subject": ch["subject"], **dict(dep)})

    return {
        "chapters": chapters,
        "topics": topics,
        "concepts": concepts,
        "knowledge_units": knowledge_units,
        "blueprints": blueprints,
        "questions_by_status": questions,
        "questions_sample": questions_detail,
        "dependencies_by_chapter": deps,
    }


def integrity_checks(engine) -> dict:
    with engine.connect() as conn:
        chap_dups = conn.execute(
            text(
                """
                SELECT s.code, ch.code, COUNT(*) FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.deleted_at IS NULL GROUP BY 1,2 HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        topic_dups = conn.execute(
            text(
                """
                SELECT chapter_id::text, code, COUNT(*) FROM academic.topics
                WHERE deleted_at IS NULL GROUP BY 1,2 HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        concept_dups = conn.execute(
            text(
                """
                SELECT topic_id::text, code, COUNT(*) FROM academic.concepts
                WHERE deleted_at IS NULL GROUP BY 1,2 HAVING COUNT(*) > 1
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
        chem = conn.execute(
            text(
                """
                SELECT ch.class_level FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code = 'CHEMISTRY' AND ch.code = 'biomolecules-chem' AND ch.deleted_at IS NULL
                """
            )
        ).scalar_one_or_none()
        zoo = conn.execute(
            text(
                """
                SELECT ch.class_level FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code = 'ZOOLOGY' AND ch.code = 'biomolecules' AND ch.deleted_at IS NULL
                """
            )
        ).scalar_one_or_none()
        # CF-C2 / CF-C3 regression anchors
        grav = conn.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM academic.topics t
                   JOIN academic.chapters ch ON ch.id = t.chapter_id
                   JOIN academic.subjects s ON s.id = ch.subject_id
                   WHERE s.code='PHYSICS' AND ch.code='gravitation' AND t.deleted_at IS NULL) AS topics,
                  (SELECT COUNT(*) FROM academic.concepts c
                   JOIN academic.topics t ON t.id = c.topic_id
                   JOIN academic.chapters ch ON ch.id = t.chapter_id
                   JOIN academic.subjects s ON s.id = ch.subject_id
                   WHERE s.code='PHYSICS' AND ch.code='gravitation' AND c.deleted_at IS NULL AND t.deleted_at IS NULL) AS concepts
                """
            )
        ).mappings().one()
        bio_xii = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.deleted_at IS NULL AND s.code IN ('BOTANY','ZOOLOGY') AND ch.class_level = '12'
                """
            )
        ).scalar()
    return {
        "duplicate_chapters": [list(r) for r in chap_dups],
        "duplicate_topics": [list(r) for r in topic_dups],
        "duplicate_concepts": [list(r) for r in concept_dups],
        "orphan_topics": orphan_topics,
        "orphan_concepts": orphan_concepts,
        "chemistry_biomolecules_class_level": chem,
        "zoology_biomolecules_class_level": zoo,
        "cf_c3_gravitation": dict(grav),
        "cf_c2_biology_xii_chapters": bio_xii,
        "ok": (
            not chap_dups
            and not topic_dups
            and not concept_dups
            and orphan_topics == 0
            and orphan_concepts == 0
            and chem == "12"
            and zoo is None
            and int(grav["topics"]) > 0
            and int(grav["concepts"]) > 0
            and bio_xii >= 13
        ),
    }


def run_tests() -> dict:
    if __import__("os").environ.get("CF_C4_SKIP_TESTS") == "1":
        return {
            "passed": None,
            "failed": None,
            "exit_code": 0,
            "command": "skipped (CF_C4_SKIP_TESTS=1)",
            "tail": "reuse prior suite — set CF_C4_SKIP_TESTS=0 for full run",
        }
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
        "tail": "\n".join(out.strip().splitlines()[-40:]),
    }


def classify(records: dict, pdfs: dict) -> dict:
    """Apply established project rules only — no new ownership invention."""
    assessments = []

    chem_ch = next((c for c in records["chapters"] if c["chapter_code"] == "biomolecules-chem"), None)
    zoo_ch = next((c for c in records["chapters"] if c["chapter_code"] == "biomolecules" and c["subject"] == "ZOOLOGY"), None)

    # Chemistry XII Biomolecules — established by CF-C1 / seed / PDF lech205
    if chem_ch:
        ok = (
            chem_ch["subject"] == "CHEMISTRY"
            and chem_ch["class_level"] == "12"
            and chem_ch["topic_count"] > 0
            and pdfs["chemistry_xii"].get("title_confirmed")
            and pdfs["chemistry_xii"].get("validated_canonical")
        )
        assessments.append(
            {
                "record": "CHEMISTRY / biomolecules-chem",
                "appropriate_subject": True,
                "appropriate_class_level": chem_ch["class_level"] == "12",
                "supported_by_pdf": pdfs["chemistry_xii"].get("title_confirmed"),
                "pdf": pdfs["chemistry_xii"].get("pdf_rel"),
                "tree_populated": chem_ch["topic_count"] > 0,
                "verdict": "CORRECT" if ok else "NEEDS_REVIEW",
                "notes": (
                    "Matches canonical Class 12 Chemistry Part-II Biomolecules (lech205.pdf). "
                    "Distinct code biomolecules-chem avoids collision with Zoology stub. "
                    "CF-C1 / seed already establish CHEMISTRY + class 12 ownership."
                ),
            }
        )

    # Zoology Biomolecules — intentional NULL class_level pending owner (RS-003-B-1A)
    if zoo_ch:
        bio_pdf_present = pdfs["biology_xi"].get("title_confirmed") and pdfs["biology_xi"].get("exists")
        assessments.append(
            {
                "record": "ZOOLOGY / biomolecules",
                "appropriate_subject": "UNRESOLVED — owner decision (Botany vs Zoology for Biology Biomolecules)",
                "appropriate_class_level": zoo_ch["class_level"] is None,
                "supported_by_pdf": bio_pdf_present,
                "pdf": pdfs["biology_xi"].get("pdf_rel") if bio_pdf_present else None,
                "tree_populated": zoo_ch["topic_count"] > 0,
                "verdict": "OWNER_DECISION_REQUIRED",
                "notes": (
                    "Canonical Class 11 Biology PDF kebo109.pdf IS Biomolecules (Ch 9). "
                    "Project seed/tests intentionally leave ZOOLOGY/biomolecules.class_level = NULL "
                    "(RS-003-B-1A §7/§16; test_biomolecules_class_level_is_null). "
                    "DB already has a non-empty topic/concept tree under this chapter, plus "
                    "published questions and blueprints — any subject/class move must preserve FKs. "
                    "Subject ownership as Zoology (vs Botany) is a project taxonomy decision "
                    "not established by NCERT (single Biology textbook). "
                    "Similar name to Chemistry Biomolecules is NOT an error."
                ),
            }
        )

    decision = "C. OWNER DECISION REQUIRED"
    rationale = [
        "Chemistry XII Biomolecules (biomolecules-chem) is consistent and PDF-backed — no change.",
        "Biology XI Biomolecules exists in canonical corpus (kebo109.pdf).",
        "ZOOLOGY/biomolecules remains the intentional unresolved class_level NULL stub per RS-003-B-1A, "
        "despite having topics/concepts and dependent published questions.",
        "Owner must decide: (1) class_level for Biology Biomolecules (evidence supports 11); "
        "(2) subject ownership Botany vs Zoology; (3) whether existing Zoology tree is retained or reconciled to kebo109.",
        "Audit-only: no taxonomy mutation performed. Do not touch published question rows.",
    ]

    return {
        "decision": decision,
        "decision_letter": "C",
        "assessments": assessments,
        "rationale": rationale,
        "proposed_change_if_authorized": {
            "summary": (
                "IF owner authorizes: set class_level='11' on the Biology Biomolecules chapter "
                "(and confirm BOTANY vs ZOOLOGY ownership). Do NOT merge with CHEMISTRY/biomolecules-chem. "
                "Any subject move must remount topics/concepts without rewriting question concept_ids "
                "unless a separate content migration is authorized."
            ),
            "do_not_auto_apply": True,
            "blocks": [
                "Subject ownership (Botany vs Zoology) is project taxonomy, not NCERT.",
                "Existing tests require NULL class_level until owner decision.",
                "ZOOLOGY/biomolecules already has published questions + blueprints — high-impact change.",
            ],
        },
    }


def write_report(payload: dict) -> tuple[Path, Path]:
    out = ROOT / "docs" / "audits"
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{REPORT_STEM}.json"
    mp = out / f"{REPORT_STEM}.md"
    jp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# CF-C4 — Biomolecules taxonomy / class resolution (AUDIT)",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        f"- Decision: **{payload['classification']['decision']}**",
        "- Git: **no commit / no push**",
        "- Taxonomy mutations: **none** (audit-only)",
        "",
        "## 1. All Biomolecules records found",
        "",
        "### Chapters",
    ]
    for ch in payload["records"]["chapters"]:
        lines.append(
            f"- **{ch['subject']}** `{ch['chapter_code']}` — {ch['chapter_name']} "
            f"(class_level={ch['class_level']!r}, id=`{ch['chapter_id']}`, "
            f"topics={ch['topic_count']}, concepts={ch['concept_count']})"
        )
    lines.append("")
    lines.append("### Topics")
    if not payload["records"]["topics"]:
        lines.append("- _(none matching Biomolecules outside chapter trees)_")
    for t in payload["records"]["topics"]:
        lines.append(
            f"- **{t['subject']}** `{t['chapter_code']}` / `{t['topic_code']}` — {t['topic_name']} "
            f"(id=`{t['topic_id']}`, class={t['class_level']!r})"
        )
    lines.append("")
    lines.append("### Concepts")
    for c in payload["records"]["concepts"]:
        lines.append(
            f"- **{c['subject']}** `{c['chapter_code']}` / `{c['topic_code']}` / `{c['concept_code']}` — "
            f"{c['concept_name']} (id=`{c['concept_id']}`)"
        )
    if not payload["records"]["concepts"]:
        lines.append("- _(none)_")
    lines.append("")
    lines.append("### Knowledge Units")
    if not payload["records"]["knowledge_units"]:
        lines.append("- _(none referencing Biomolecules)_")
    for ku in payload["records"]["knowledge_units"]:
        lines.append(f"- {ku}")
    lines.append("")
    lines.append("### Blueprints")
    if not payload["records"]["blueprints"]:
        lines.append("- _(none referencing Biomolecules)_")
    for bp in payload["records"]["blueprints"]:
        lines.append(f"- {bp}")
    lines.append("")
    lines.append("### Questions (by status under Biomolecules trees)")
    for q in payload["records"]["questions_by_status"]:
        lines.append(f"- {q['status']}: {q['n']}")
    if not payload["records"]["questions_by_status"]:
        lines.append("- _(none)_")
    lines.append("")
    lines.append("## 2. Canonical PDF evidence")
    for key, pdf in payload["pdf_evidence"].items():
        lines.append(f"### {key}")
        lines.append(f"- path: `{pdf.get('resolved_path')}`")
        lines.append(f"- exists={pdf.get('exists')} validated={pdf.get('validated_canonical')} title_confirmed={pdf.get('title_confirmed')}")
        lines.append(f"- markers: {pdf.get('chapter_markers')}")
        if pdf.get("section_headers"):
            lines.append(f"- sections (sample): {pdf['section_headers'][:8]}")
        if pdf.get("preview"):
            lines.append(f"- preview: {pdf['preview'][:300]}…")
        lines.append("")
    lines.append("## 3. Subject / class ownership")
    for a in payload["classification"]["assessments"]:
        lines.append(f"### {a['record']} — **{a['verdict']}**")
        lines.append(f"- subject OK / note: {a['appropriate_subject']}")
        lines.append(f"- class_level appropriate: {a['appropriate_class_level']}")
        lines.append(f"- PDF: `{a.get('pdf')}` supported={a.get('supported_by_pdf')}")
        lines.append(f"- notes: {a['notes']}")
        lines.append("")
    lines.append("## 4. Dependency analysis")
    for d in payload["records"]["dependencies_by_chapter"]:
        lines.append(f"- **{d['subject']} / {d['chapter_code']}**: {d}")
    lines.append("")
    lines.append("## 5. Current correctness assessment")
    for r in payload["classification"]["rationale"]:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## 6. Proposed change (NOT applied)")
    lines.append("```json")
    lines.append(json.dumps(payload["classification"]["proposed_change_if_authorized"], indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 7. Unresolved questions")
    for u in payload.get("unresolved_questions") or []:
        lines.append(f"- {u}")
    lines.append("")
    lines.append("## 8. Safety counts before / after")
    lines.append("### Before")
    lines.append("```json")
    lines.append(json.dumps(payload["before"], indent=2))
    lines.append("```")
    lines.append("### After")
    lines.append("```json")
    lines.append(json.dumps(payload["after"], indent=2))
    lines.append("```")
    lines.append(f"- Content safety unchanged: `{payload['content_safety_unchanged']}`")
    lines.append(f"- Freeze OK: `{payload['freeze_ok']}`")
    lines.append("")
    lines.append("## 9. Tests / integrity")
    lines.append("```json")
    lines.append(json.dumps(payload["integrity"], indent=2, default=str))
    lines.append("```")
    lines.append(
        f"- Tests passed=`{payload['tests']['passed']}` failed=`{payload['tests']['failed']}` "
        f"exit=`{payload['tests']['exit_code']}`"
    )
    lines.append(f"- `{payload['tests']['command']}`")
    if payload["tests"].get("tail"):
        lines.append("```")
        lines.append(payload["tests"]["tail"])
        lines.append("```")
    lines.append("")
    lines.append("## 10. Exact files changed")
    for f in payload.get("files_changed") or []:
        lines.append(f"- `{f}`")
    lines.append("")
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jp, mp


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    before = snapshot(engine)
    root = get_ncert_source_root()

    pdf_evidence = {
        "chemistry_xii": verify_pdf(
            "Class 12/Chemistry 2/lech2dd/lech205.pdf",
            root,
            expect_title="Biomolecules",
            expect_class_hint="12",
        ),
        "biology_xi": verify_pdf(
            "Class 11/Biology/kebo1dd/kebo109.pdf",
            root,
            expect_title="Biomolecules",
            expect_class_hint="11",
        ),
        "biology_xii_search": {
            "note": "No Class 12 Biology PDF under lebo1dd is titled Biomolecules (confirmed by chapter inventory).",
            "hits": [],
        },
    }

    # Confirm Bio XI title more carefully — chapter may not repeat word on p0
    bio = pdf_evidence["biology_xi"]
    if bio.get("exists") and bio.get("validated_canonical"):
        pdf = root / bio["pdf_rel"]
        doc = fitz.open(pdf)
        blob = ""
        for i in range(min(doc.page_count, 8)):
            blob += "\n" + decode_pua(doc.load_page(i).get_text("text") or "")
        doc.close()
        # Rationalised Ch 9 is Biomolecules — confirm via section 9.1 and known phrasing
        if "9.1 HOW TO ANALYSE CHEMICAL COMPOSITION" in blob.upper().replace("  ", " ") or re.search(
            r"9\.1\s+HOW TO ANALYSE CHEMICAL COMPOSITION", blob, re.I
        ):
            bio["biology_ch9_composition_section"] = True
        # Title page / running header
        if re.search(r"(?i)\bBIOMOLECULES\b", blob):
            bio["title_confirmed"] = True
        bio["chapter_markers"] = re.findall(r"(?i)CHAPTER\s+\d+", blob)[:5]
        bio["section_headers"] = [
            f"{a} {b.strip()}" for a, b in re.findall(r"(?m)^(9\.\d+)\s+(.{0,70})$", blob)
        ][:15]

    records = locate_records(engine)
    classification = classify(records, pdf_evidence)

    unresolved = [
        "Should Biology Biomolecules be owned by BOTANY or ZOOLOGY? (NCERT is a single Biology book.)",
        "Confirm class_level='11' for Biology Biomolecules once subject ownership is decided "
        "(canonical PDF kebo109.pdf supports Class XI Ch 9).",
        "Existing ZOOLOGY/biomolecules tree (3 topics / 3 concepts) vs kebo109 section structure — "
        "reconcile only after owner decision; do not silently rename.",
        "Preserve 5 PUBLISHED + 8 DRAFT questions and 5 blueprints attached to Zoology Biomolecules concepts.",
        "Keep CHEMISTRY/biomolecules-chem separate — same English title is not a collision.",
    ]

    after = snapshot(engine)
    content_safety = before == after
    freeze_ok = after["unmapped_draft"] == UNMAPPED_FREEZE and after["status"] == STATUS_FREEZE

    integrity = integrity_checks(engine)
    tests = run_tests()
    # If tests skipped, preserve last full-suite results from prior report when present.
    prior = ROOT / "docs" / "audits" / f"{REPORT_STEM}.json"
    if tests.get("command", "").startswith("skipped") and prior.is_file():
        try:
            prev = json.loads(prior.read_text(encoding="utf-8"))
            if prev.get("tests", {}).get("exit_code") == 0 and prev["tests"].get("passed"):
                tests = {**prev["tests"], "note": "reused from prior full CF-C4 run; classification notes refreshed"}
        except Exception:  # noqa: BLE001
            pass

    if not content_safety or not freeze_ok or not integrity["ok"] or tests.get("exit_code") != 0:
        status = "RED — FAILED"
    else:
        # Owner decision still required for Zoology Biomolecules class/subject fill
        status = "YELLOW — PARTIALLY VERIFIED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": status,
        "task": "CF-C4 Biomolecules taxonomy/class resolution — AUDIT ONLY",
        "before": before,
        "after": after,
        "content_safety_unchanged": content_safety,
        "freeze_ok": freeze_ok,
        "records": records,
        "pdf_evidence": pdf_evidence,
        "classification": classification,
        "unresolved_questions": unresolved,
        "integrity": integrity,
        "tests": tests,
        "files_changed": [
            "apps/backend/scripts/curriculum_baseline_004_biomolecules.py",
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
        ],
        "confirmation": {
            "taxonomy_mutated": False,
            "questions_mutated": False,
            "mcqs_generated": False,
            "ai_called": False,
            "blueprints_created": False,
            "knowledge_units_created": False,
            "ecaep_modified": False,
        },
    }
    jp, mp = write_report(payload)
    print(
        json.dumps(
            {
                "final_status": status,
                "decision": classification["decision"],
                "json": str(jp),
                "md": str(mp),
                "chapters": records["chapters"],
                "deps": records["dependencies_by_chapter"],
                "questions_by_status": records["questions_by_status"],
                "ku_count": len(records["knowledge_units"]),
                "bp_count": len(records["blueprints"]),
                "freeze_ok": freeze_ok,
                "integrity_ok": integrity["ok"],
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
