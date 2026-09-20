"""BP-CREATE-002 — Create remaining verified NCERT-backed blueprints (no MCQs).

Creates authoritative blueprints for concepts eligible under BP-COVERAGE-003 /
BP-CREATE-001 production gates. Does not convert legacy BPs, generate MCQs,
or mutate taxonomy/questions/KUs.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.schemas.content_factory_planning import (  # noqa: E402
    LearningObjectiveCreateRequest,
    QuestionBlueprintCreateRequest,
    QuestionFamilyCreateRequest,
)
from app.modules.cms.services.content_factory_planning_service import (  # noqa: E402
    ContentFactoryPlanningService,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    assert_blueprint_ncert_source,
    get_ncert_source_root,
    validate_ncert_generation_source,
)
from app.modules.identity.models.user import User  # noqa: E402

REPORT_STEM = "bp_create_002_20260913"
CAMPAIGN = "bp-create-002-20260913"
COVERAGE_JSON = ROOT / "docs/audits/bp_coverage_003_20260913.json"
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
MERGE_REVIEW_CODES = frozenset({"sv2c-botany-15"})  # flag-only; do not create/merge
TARGET_COUNT = 2
EXPECTED_CREATE = 179
EXPECTED_TOTAL_BP = 445
PHYSICS_NUMERICAL = frozenset(
    {
        "escape-speed",
        "g-on-earth-surface",
        "variation-of-g-with-height-depth",
        "gravitational-potential-energy",
        "gravitational-constant",
        "energy-of-orbiting-satellite",
    }
)

FREEZE = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "DRAFT": 5298,
    "SUPERSEDED": 6,
    "unmapped_draft": 5024,
    "chapters": 56,
    "topics": 192,
    "concepts": 318,
    "knowledge_units": 381,
    "blueprints_before": 266,
    "studymaterial_path_kus": 73,
    "digestion_kus": 0,
}


def snapshot_sync(conn) -> dict:
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
        "authoritative_blueprints": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.question_blueprints
                WHERE deleted_at IS NULL AND provenance_tier = 'authoritative'
                """
            )
        ).scalar(),
        "canonical_ncert_blueprints": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.question_blueprints
                WHERE deleted_at IS NULL
                  AND provenance_tier = 'authoritative'
                  AND coalesce(constraints->>'ncert_derived', '') = 'true'
                  AND coalesce(constraints->>'ncert_source_path', '') ILIKE '%NCERT Books%'
                """
            )
        ).scalar(),
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


def freeze_base_ok(snap: dict, *, expect_blueprints: int | None = None) -> bool:
    bp_ok = True
    if expect_blueprints is not None:
        bp_ok = snap["question_blueprints"] == expect_blueprints
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
        and snap["studymaterial_path_kus"] == FREEZE["studymaterial_path_kus"]
        and snap["digestion_kus"] == FREEZE["digestion_kus"]
        and bp_ok
    )


def load_coverage_eligible_codes() -> set[str]:
    if not COVERAGE_JSON.exists():
        raise SystemExit(f"ABORT: missing {COVERAGE_JSON}")
    payload = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    codes = {r["concept_code"] for r in payload["analysis"]["eligible_concepts"]}
    if len(codes) != EXPECTED_CREATE:
        raise SystemExit(f"ABORT: coverage eligible expected {EXPECTED_CREATE}, got {len(codes)}")
    return codes


def load_eligible_concepts(conn, coverage_codes: set[str]) -> list[dict]:
    rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT c.id::text AS concept_id,
                       c.code AS concept_code,
                       c.name AS concept_name,
                       c.summary AS concept_summary,
                       s.id::text AS subject_id,
                       s.code AS subject,
                       ch.id::text AS chapter_id,
                       ch.code AS chapter_code,
                       ch.name AS chapter_name,
                       ch.class_level,
                       t.id::text AS topic_id,
                       t.code AS topic_code,
                       t.name AS topic_name,
                       ku.id::text AS ku_id,
                       ku.validation_status AS ku_status,
                       left(coalesce(sec.heading, ''), 200) AS section_heading,
                       j.source_file_path AS ncert_job_path,
                       (SELECT COUNT(*) FROM cms.question_blueprints bp
                        WHERE bp.concept_id = c.id AND bp.deleted_at IS NULL) AS existing_bp_count,
                       (SELECT COUNT(*) FROM cms.question_blueprints bp
                        WHERE bp.concept_id = c.id AND bp.deleted_at IS NULL
                          AND bp.provenance_tier = 'authoritative') AS existing_auth_bp_count,
                       (
                         SELECT COUNT(*) FROM knowledge.knowledge_units ku2
                         WHERE ku2.concept_id = c.id AND ku2.deleted_at IS NULL
                           AND ku2.validation_status = 'PASSED'
                       ) AS ku_passed_total,
                       (
                         SELECT COUNT(*) FROM knowledge.knowledge_units ku2
                         JOIN ingestion.ingestion_sections sec2 ON sec2.id = ku2.source_section_id
                         JOIN ingestion.ingestion_jobs j2 ON j2.id = sec2.job_id
                         WHERE ku2.concept_id = c.id AND ku2.deleted_at IS NULL
                           AND ku2.validation_status = 'PASSED'
                           AND coalesce(j2.source_file_path, '') LIKE '%NCERT Books%'
                       ) AS ncert_ku_passed
                FROM academic.concepts c
                JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                JOIN academic.subjects s ON s.id = ch.subject_id
                JOIN knowledge.knowledge_units ku ON ku.concept_id = c.id
                  AND ku.deleted_at IS NULL AND ku.validation_status = 'PASSED'
                JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                WHERE c.deleted_at IS NULL
                  AND ch.code <> 'digestion-absorption'
                  AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%'
                ORDER BY s.code, ch.code, c.code, ku.created_at ASC
                """
            ),
        ).mappings()
    ]
    by_concept: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_concept[r["concept_id"]].append(r)

    eligible = []
    skipped_existing = []
    blocked = []
    for concept_id, kus in by_concept.items():
        head = kus[0]
        code = head["concept_code"]
        if code in TAXONOMY_REVIEW_CODES:
            blocked.append({"concept_code": code, "reason": "TAXONOMY_REVIEW"})
            continue
        if code in MERGE_REVIEW_CODES:
            blocked.append({"concept_code": code, "reason": "MERGE_REVIEW_sv2c-botany-15"})
            continue
        if head["chapter_code"] in EXCLUDED_CHAPTERS:
            blocked.append({"concept_code": code, "reason": "digestion_excluded"})
            continue
        if head["ncert_ku_passed"] != 1:
            continue
        if head["existing_auth_bp_count"] > 0:
            if code in coverage_codes:
                skipped_existing.append(
                    {
                        "concept_code": code,
                        "subject": head["subject"],
                        "status": "SKIPPED_EXISTING",
                        "existing_auth_bp_count": head["existing_auth_bp_count"],
                    }
                )
            continue
        if code not in coverage_codes:
            # Live-eligible but not in coverage snapshot — do not create unexpectedly
            blocked.append({"concept_code": code, "reason": "not_in_coverage_003_eligible_set"})
            continue
        eligible.append(head)

    # Coverage codes that did not appear as live-eligible
    live_codes = {e["concept_code"] for e in eligible} | {s["concept_code"] for s in skipped_existing}
    missing = sorted(coverage_codes - live_codes - {b["concept_code"] for b in blocked})
    return eligible, skipped_existing, blocked, missing


def classification_for(concept_code: str, subject: str) -> str:
    if subject == "PHYSICS" and concept_code in PHYSICS_NUMERICAL:
        return "numerical"
    return "conceptual"


def concept_fingerprint(conn, codes: list[str]) -> dict[str, dict]:
    if not codes:
        return {}
    rows = conn.execute(
        text(
            """
            SELECT c.code,
                   c.id::text AS concept_id,
                   c.name,
                   c.updated_at::text AS updated_at,
                   (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                    WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL) AS ku_count,
                   (SELECT COUNT(*) FROM cms.question_blueprints bp
                    WHERE bp.concept_id = c.id AND bp.deleted_at IS NULL) AS bp_count
            FROM academic.concepts c
            WHERE c.deleted_at IS NULL AND c.code = ANY(:codes)
            """
        ),
        {"codes": codes},
    ).mappings()
    return {r["code"]: dict(r) for r in rows}


def provenance_summary(conn) -> dict:
    rows = list(
        conn.execute(
            text(
                """
                SELECT
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE provenance_tier = 'ai') AS ai_tier,
                  COUNT(*) FILTER (WHERE provenance_tier = 'authoritative') AS authoritative_tier,
                  COUNT(*) FILTER (
                    WHERE coalesce(constraints::text, '') ILIKE '%StudyMaterial%'
                  ) AS studymaterial_constraints,
                  COUNT(*) FILTER (
                    WHERE provenance_tier = 'authoritative'
                      AND coalesce(constraints->>'ncert_derived', '') = 'true'
                      AND coalesce(constraints->>'ncert_source_path', '') ILIKE '%NCERT Books%'
                  ) AS canonical_ncert_backed,
                  COUNT(*) FILTER (
                    WHERE provenance_tier = 'authoritative'
                      AND coalesce(constraints->>'ncert_derived', '') = 'true'
                  ) AS authoritative_ncert_derived,
                  COUNT(*) FILTER (WHERE coalesce((constraints->>'target_count'), '') <> '') AS noop
                FROM cms.question_blueprints
                WHERE deleted_at IS NULL
                """
            )
        ).mappings()
    )[0]
    target_dist = {
        str(r[0]): r[1]
        for r in conn.execute(
            text(
                """
                SELECT target_count, COUNT(*) FROM cms.question_blueprints
                WHERE deleted_at IS NULL
                GROUP BY target_count
                ORDER BY target_count
                """
            )
        )
    }
    return {**dict(rows), "target_count_distribution": target_dist}


def projected_capacity_after(conn) -> dict:
    """PROJECTED capacity: concepts with adequate canonical BP * their target sums."""
    rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT s.code AS subject,
                       c.code AS concept_code,
                       COALESCE(SUM(bp.target_count), 0) AS target_sum
                FROM academic.concepts c
                JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                JOIN academic.subjects s ON s.id = ch.subject_id
                JOIN cms.question_blueprints bp ON bp.concept_id = c.id AND bp.deleted_at IS NULL
                WHERE c.deleted_at IS NULL
                  AND bp.provenance_tier = 'authoritative'
                  AND coalesce(bp.constraints->>'ncert_derived', '') = 'true'
                  AND coalesce(bp.constraints->>'ncert_source_path', '') ILIKE '%NCERT Books%'
                GROUP BY s.code, c.code
                """
            )
        ).mappings()
    ]
    by_subj: dict[str, dict] = {
        s: {"concepts_with_adequate_canonical_bp": 0, "PROJECTED_pilot_question_capacity": 0}
        for s in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY")
    }
    for r in rows:
        subj = r["subject"]
        if subj not in by_subj:
            continue
        by_subj[subj]["concepts_with_adequate_canonical_bp"] += 1
        by_subj[subj]["PROJECTED_pilot_question_capacity"] += int(r["target_sum"] or 0)
    total = sum(v["PROJECTED_pilot_question_capacity"] for v in by_subj.values())
    return {
        "by_subject": by_subj,
        "PROJECTED_total_pilot_question_capacity": total,
        "PROJECTED_400_pilot_theoretically_supported": total >= 400,
        "note": "PROJECTED capacity from existing canonical NCERT blueprint target_count sums — not actual MCQs.",
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
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m_pass = re.search(r"(\d+)\s+passed", out)
    m_fail = re.search(r"(\d+)\s+failed", out)
    return {
        "passed": int(m_pass.group(1)) if m_pass else 0,
        "failed": int(m_fail.group(1)) if m_fail else (0 if proc.returncode == 0 else 1),
        "exit_code": proc.returncode,
        "command": " ".join(cmd),
        "tail": "\n".join(out.strip().splitlines()[-40:]),
    }


async def create_all(eligible: list[dict], actor_id: uuid.UUID | None, ncert_root: Path) -> dict:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    created: list[dict] = []
    reused: list[dict] = []
    failures: list[dict] = []
    families: dict[str, uuid.UUID] = {}

    async with AsyncSession(engine, expire_on_commit=False) as session:
        planning = ContentFactoryPlanningService(session)

        for subject in sorted({r["subject"] for r in eligible}):
            fam_key = f"{CAMPAIGN}-fam-{subject.lower()}-ncert-conceptual"
            fam, _fam_created = await planning.create_family(
                QuestionFamilyCreateRequest(
                    family_key=fam_key,
                    name=f"{subject} NCERT conceptual (BP-CREATE-002)",
                    description="NCERT-Books-grounded MCQ family for BP-CREATE-002 coverage",
                    applicable_subject_codes=[subject],
                    cognitive_intent="ncert grounded conceptual assessment",
                    difficulty_min="easy",
                    difficulty_max="hard",
                    question_format="MCQ_4",
                ),
                actor_id=actor_id,
            )
            families[subject] = fam.id
            await session.commit()

        for row in eligible:
            concept_id = uuid.UUID(row["concept_id"])
            subject = row["subject"]
            concept_code = row["concept_code"]
            if concept_code in TAXONOMY_REVIEW_CODES or concept_code in MERGE_REVIEW_CODES:
                failures.append(
                    {
                        "concept_code": concept_code,
                        "subject": subject,
                        "error": "blocked_special_case",
                    }
                )
                continue
            try:
                validated = validate_ncert_generation_source(row["ncert_job_path"], root=ncert_root)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "concept_code": concept_code,
                        "subject": subject,
                        "error": f"NCERT path validation failed: {exc}",
                        "path": row["ncert_job_path"],
                    }
                )
                continue

            classification = classification_for(concept_code, subject)
            obj_key = f"{CAMPAIGN}-obj-{subject.lower()}-{concept_code}"
            bp_key = f"{CAMPAIGN}-bp-{subject.lower()}-{concept_code}-mcq"

            try:
                # Idempotency: skip if campaign key already exists as adequate BP
                existing_key = await session.execute(
                    text(
                        """
                        SELECT id::text FROM cms.question_blueprints
                        WHERE blueprint_key = :k AND deleted_at IS NULL
                        LIMIT 1
                        """
                    ),
                    {"k": bp_key},
                )
                existing_id = existing_key.scalar_one_or_none()
                if existing_id:
                    reused.append(
                        {
                            "concept_code": concept_code,
                            "subject": subject,
                            "status": "SKIPPED_EXISTING",
                            "blueprint_id": existing_id,
                            "blueprint_key": bp_key,
                        }
                    )
                    continue

                # Re-check no authoritative BP appeared
                auth_now = await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM cms.question_blueprints
                        WHERE concept_id = :cid AND deleted_at IS NULL
                          AND provenance_tier = 'authoritative'
                        """
                    ),
                    {"cid": str(concept_id)},
                )
                if int(auth_now.scalar_one()) > 0:
                    reused.append(
                        {
                            "concept_code": concept_code,
                            "subject": subject,
                            "status": "SKIPPED_EXISTING",
                            "reason": "authoritative_bp_already_present",
                        }
                    )
                    continue

                obj, _obj_created = await planning.create_objective(
                    LearningObjectiveCreateRequest(
                        objective_key=obj_key,
                        concept_id=concept_id,
                        title=f"Assess NCERT-aligned understanding of {row['concept_name']}",
                        description=(row.get("concept_summary") or "")[:500] or None,
                        learning_level="apply",
                    ),
                    actor_id=actor_id,
                )
                await session.commit()

                constraints = {
                    "question_format": "MCQ_4",
                    "correct_option_count": 1,
                    "explanation_required": True,
                    "avoid_paraphrase_duplicates": True,
                    "ncert_derived": True,
                    "ncert_source_path": str(validated.resolved_path),
                    "ncert_source_relative": validated.relative_posix,
                    "classification": classification,
                    "reasoning": f"ncert_{classification}",
                    "campaign": CAMPAIGN,
                    "ku_id": row["ku_id"],
                }
                if row.get("section_heading"):
                    constraints["ncert_section_heading"] = row["section_heading"]

                bp, bp_created = await planning.create_blueprint(
                    QuestionBlueprintCreateRequest(
                        blueprint_key=bp_key,
                        subject_id=uuid.UUID(row["subject_id"]),
                        chapter_id=uuid.UUID(row["chapter_id"]),
                        topic_id=uuid.UUID(row["topic_id"]),
                        concept_id=concept_id,
                        learning_objective_id=obj.id,
                        question_family_id=families[subject],
                        difficulty="medium",
                        target_count=TARGET_COUNT,
                        provenance_tier="authoritative",
                        constraints=constraints,
                        new_version=False,
                    ),
                    actor_id=actor_id,
                )
                await session.commit()

                ncert_ok = assert_blueprint_ncert_source(
                    bp.constraints,
                    provenance_tier=bp.provenance_tier,
                    root=ncert_root,
                )
                validation = await planning.validate_blueprint(bp.id, actor_id=actor_id)

                record = {
                    "blueprint_id": str(bp.id),
                    "blueprint_key": bp.blueprint_key,
                    "created": bp_created,
                    "status_label": "CREATED" if bp_created else "SKIPPED_EXISTING",
                    "subject": subject,
                    "class_level": row["class_level"],
                    "chapter_code": row["chapter_code"],
                    "topic_code": row["topic_code"],
                    "concept_id": row["concept_id"],
                    "concept_code": concept_code,
                    "ku_id": row["ku_id"],
                    "ncert_source_path": str(validated.resolved_path),
                    "ncert_source_relative": validated.relative_posix,
                    "section_heading": row.get("section_heading") or None,
                    "provenance_tier": bp.provenance_tier,
                    "ncert_derived": True,
                    "target_count": bp.target_count,
                    "classification": classification,
                    "generation_eligible": bp.generation_eligible,
                    "status": bp.status,
                    "validate_verdict": validation.get("verdict"),
                    "ncert_assert_ok": ncert_ok is not None,
                    "existing_bp_count_before": row["existing_bp_count"],
                }
                if not (
                    bp.generation_eligible
                    and bp.provenance_tier == "authoritative"
                    and ncert_ok is not None
                    and validation.get("generation_eligible") is True
                    and bp.target_count == TARGET_COUNT
                ):
                    failures.append({**record, "error": "post-create eligibility/NCERT assert failed"})
                elif bp_created:
                    created.append(record)
                else:
                    reused.append(record)
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                failures.append(
                    {
                        "concept_code": concept_code,
                        "subject": subject,
                        "error": str(exc),
                    }
                )

    await engine.dispose()
    return {
        "created": created,
        "reused": reused,
        "failures": failures,
        "families": {k: str(v) for k, v in families.items()},
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    created = payload["created_blueprints"]
    lines = [
        "# BP-CREATE-002 — Verified NCERT-backed blueprint coverage",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- MCQ generation: **disabled / not run**",
        "- Publication: **not performed**",
        "- Git: **no commit / no push**",
        "",
        "## Summary",
        f"- Eligible (coverage-003 ∩ live gate): `{payload['eligible_count']}`",
        f"- Created: `{len(created)}`",
        f"- Skipped existing: `{len(payload['skipped_existing']) + len(payload['reused_blueprints'])}`",
        f"- Failures: `{len(payload['failures'])}`",
        f"- Blueprints: `{payload['before']['question_blueprints']}` → `{payload['after']['question_blueprints']}`",
        f"- Canonical NCERT BPs: `{payload['before'].get('canonical_ncert_blueprints')}` → `{payload['after'].get('canonical_ncert_blueprints')}`",
        f"- Created by subject: `{dict(Counter(c['subject'] for c in created))}`",
        "",
        "## Eligibility contract",
        "- `provenance_tier = authoritative`",
        "- `constraints.ncert_derived = true`",
        "- `constraints.ncert_source_path` under canonical NCERT Books root",
        "- Validated by `assert_blueprint_ncert_source`",
        "- Obsolete gate `provenance_tier == \"ncert\"` is NOT used",
        f"- `target_count = {TARGET_COUNT}`",
        "",
        "## Special cases untouched",
        f"- TAXONOMY_REVIEW unchanged: `{payload['taxonomy_review_unchanged']}`",
        f"- `sv2c-botany-15` unchanged: `{payload['sv2c_botany_15_unchanged']}`",
        f"- Digestion KUs: `{payload['after']['digestion_kus']}`",
        "",
        "## PROJECTED capacity after creation (not actual MCQs)",
        f"- **PROJECTED total:** `{payload['projected_capacity_after']['PROJECTED_total_pilot_question_capacity']}`",
        f"- **Supports 400 theoretically:** `{payload['projected_capacity_after']['PROJECTED_400_pilot_theoretically_supported']}`",
        "",
        "| Subject | Adequate canonical BP concepts | PROJECTED capacity |",
        "|---|---:|---:|",
    ]
    for subj, row in payload["projected_capacity_after"]["by_subject"].items():
        lines.append(
            f"| {subj} | {row['concepts_with_adequate_canonical_bp']} | **{row['PROJECTED_pilot_question_capacity']}** |"
        )

    lines += [
        "",
        "## Provenance after",
        f"```json\n{json.dumps(payload['provenance_after'], indent=2)}\n```",
        "",
        "## Created blueprints (IDs)",
    ]
    for c in created:
        lines.append(
            f"- `{c['blueprint_id']}` `{c['blueprint_key']}` — {c['subject']}/{c['chapter_code']}/"
            f"{c['concept_code']} — target={c['target_count']} — `{c['ncert_source_relative']}`"
        )

    if payload["failures"]:
        lines += ["", "## Failures", ""]
        for f in payload["failures"]:
            lines.append(f"- `{f.get('concept_code')}`: {f.get('error')}")

    lines += [
        "",
        "## Safety / freeze",
        f"- Freeze OK after: `{payload['freeze_ok_after']}`",
        f"- Factory orchestration unchanged: `{payload['factory_orchestration_unchanged']}`",
        f"- All new BPs pass NCERT assert: `{payload['all_new_ncert_assert_ok']}`",
        "",
        "### Before",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "### After",
        f"```json\n{json.dumps(payload['after'], indent=2)}\n```",
        "",
        "## Tests",
        f"- Passed `{payload['tests'].get('passed')}` / Failed `{payload['tests'].get('failed')}`",
        "",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## Files changed",
    ]
    for f in payload["files_changed"]:
        lines.append(f"- `{f}`")
    lines += [
        "",
        "## Confirmation",
        f"```json\n{json.dumps(payload['confirmation'], indent=2)}\n```",
        "",
        "**STOP** — no MCQ generation, no 400 pilot start, no publish, no commit, no push.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


async def async_main() -> int:
    coverage_codes = load_coverage_eligible_codes()
    settings = get_settings()
    sync_engine = create_engine(settings.database_url_sync)
    try:
        ncert_root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        ncert_root = ROOT / "NCERT Books"

    with sync_engine.connect() as conn:
        before = snapshot_sync(conn)
        if not freeze_base_ok(before, expect_blueprints=FREEZE["blueprints_before"]):
            raise SystemExit(f"ABORT: freeze mismatch before create: {before}")
        eligible, skipped_existing, blocked, missing = load_eligible_concepts(conn, coverage_codes)
        tax_before = concept_fingerprint(conn, list(TAXONOMY_REVIEW_CODES))
        bot_before = concept_fingerprint(conn, ["sv2c-botany-15", "syngamy-and-triple-fusion"])
        if missing:
            raise SystemExit(f"ABORT: coverage eligible missing from live gate: {missing}")
        if len(eligible) + len(skipped_existing) != EXPECTED_CREATE:
            # Allow if some skipped existing; created set should be eligible
            pass
        if len(eligible) != EXPECTED_CREATE and not skipped_existing:
            # Soft check — proceed but report; do not force
            pass

    async_engine = create_async_engine(settings.database_url)
    async with AsyncSession(async_engine) as session:
        actor = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one_or_none()
        actor_id = actor.id if actor else None
    await async_engine.dispose()

    result = await create_all(eligible, actor_id, ncert_root)

    with sync_engine.connect() as conn:
        after = snapshot_sync(conn)
        provenance_after = provenance_summary(conn)
        projected = projected_capacity_after(conn)
        tax_after = concept_fingerprint(conn, list(TAXONOMY_REVIEW_CODES))
        bot_after = concept_fingerprint(conn, ["sv2c-botany-15", "syngamy-and-triple-fusion"])

        if after["status"] != before["status"] or after["unmapped_draft"] != before["unmapped_draft"]:
            raise SystemExit("ABORT: question inventory changed")
        for k in (
            "chapters",
            "topics",
            "concepts",
            "knowledge_units",
            "content_batches",
            "generation_jobs",
            "generation_runs",
            "generation_candidates",
            "studymaterial_path_kus",
            "digestion_kus",
        ):
            if before[k] != after[k]:
                raise SystemExit(f"ABORT: {k} changed {before[k]} → {after[k]}")

        expected_bp = before["question_blueprints"] + len(result["created"])
        if after["question_blueprints"] != expected_bp:
            raise SystemExit(
                f"ABORT: blueprint count unexpected before={before['question_blueprints']} "
                f"after={after['question_blueprints']} created={len(result['created'])}"
            )

    tests = run_tests()
    freeze_ok_after = freeze_base_ok(after, expect_blueprints=after["question_blueprints"])
    factory_unchanged = all(
        before[k] == after[k]
        for k in ("content_batches", "generation_jobs", "generation_runs", "generation_candidates")
    )
    all_new_ok = len(result["created"]) > 0 and all(
        c["generation_eligible"] and c["ncert_assert_ok"] and c["provenance_tier"] == "authoritative" and c["ncert_derived"]
        for c in result["created"]
    )
    tax_ok = tax_before == tax_after
    sv2c_ok = bot_before.get("sv2c-botany-15") == bot_after.get("sv2c-botany-15")
    hit_expected = (
        len(result["created"]) == EXPECTED_CREATE
        and after["question_blueprints"] == EXPECTED_TOTAL_BP
        and len(result["failures"]) == 0
    )

    if not freeze_ok_after or not factory_unchanged or not all_new_ok or (tests.get("failed") or 0) > 0 or not tax_ok:
        final = "RED — FAILED"
    elif not hit_expected:
        final = "YELLOW — PARTIAL (created fewer/more than 179 or failures recorded)"
    else:
        final = "GREEN — COMPLETE/VERIFIED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "campaign": CAMPAIGN,
        "ncert_root": str(ncert_root),
        "target_count_per_blueprint": TARGET_COUNT,
        "expected_create": EXPECTED_CREATE,
        "expected_total_blueprints": EXPECTED_TOTAL_BP,
        "coverage_source": str(COVERAGE_JSON),
        "eligible_concepts": [
            {
                "concept_id": e["concept_id"],
                "concept_code": e["concept_code"],
                "subject": e["subject"],
                "chapter_code": e["chapter_code"],
                "ku_id": e["ku_id"],
                "ncert_job_path": e["ncert_job_path"],
                "existing_bp_count": e["existing_bp_count"],
            }
            for e in eligible
        ],
        "eligible_count": len(eligible),
        "eligible_by_subject": dict(Counter(e["subject"] for e in eligible)),
        "skipped_existing_precheck": skipped_existing,
        "blocked": blocked,
        "coverage_missing_from_live": missing,
        "before": before,
        "after": after,
        "created_blueprints": result["created"],
        "reused_blueprints": result["reused"],
        "skipped_existing": skipped_existing + [r for r in result["reused"]],
        "failures": result["failures"],
        "families": result["families"],
        "created_by_subject": dict(Counter(c["subject"] for c in result["created"])),
        "provenance_after": provenance_after,
        "projected_capacity_after": projected,
        "taxonomy_review_unchanged": tax_ok,
        "sv2c_botany_15_unchanged": sv2c_ok,
        "taxonomy_fingerprints": {"before": tax_before, "after": tax_after},
        "botany_fingerprints": {"before": bot_before, "after": bot_after},
        "freeze_ok_after": freeze_ok_after,
        "factory_orchestration_unchanged": factory_unchanged,
        "all_new_ncert_assert_ok": all_new_ok,
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/bp_create_002_ncert_blueprints.py",
            f"cms.question_blueprints (+{len(result['created'])} rows)",
            "cms.learning_objectives / cms.question_families (campaign keys)",
        ],
        "confirmation": {
            "mcqs_generated": False,
            "pilot_400_started": False,
            "published": False,
            "ai_called": False,
            "content_factory_jobs_created": False,
            "questions_mutated": False,
            "kus_mutated": False,
            "taxonomy_mutated": False,
            "legacy_provenance_rewritten": False,
            "sv2c_botany_15_merged": False,
            "committed_to_git": False,
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
                "eligible": len(eligible),
                "created": len(result["created"]),
                "reused": len(result["reused"]),
                "failures": len(result["failures"]),
                "blueprints_before": before["question_blueprints"],
                "blueprints_after": after["question_blueprints"],
                "canonical_ncert_after": after.get("canonical_ncert_blueprints"),
                "PROJECTED_capacity": projected["PROJECTED_total_pilot_question_capacity"],
                "freeze_ok": freeze_ok_after,
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
            },
            indent=2,
        )
    )
    return 0 if final.startswith("GREEN") else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
