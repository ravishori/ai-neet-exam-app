"""BP-CREATE-001 — Create NCERT-backed question blueprints (no MCQ generation).

Creates new authoritative blueprints for concepts with exactly one PASSED KU
whose ingestion job path is under NCERT Books. Does not convert legacy BPs,
does not generate MCQs, does not create Content Factory jobs.
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

REPORT_STEM = "bp_create_001_20260913"
CAMPAIGN = "bp-create-001-20260913"
EXCLUDED_CHAPTERS = frozenset({"digestion-absorption"})
TARGET_COUNT = 2  # conservative pilot quota per concept
NUMERICAL_CONCEPTS = frozenset(
    {
        "escape-speed",
        "g-on-earth-surface",
        "variation-of-g-with-height-depth",
        "gravitational-potential-energy",
        "gravitational-constant",
        "energy-of-orbiting-satellite",
        "classification-of-alcohols",  # keep mostly conceptual; leave empty extras
    }
)
# Prefer explicit numerical set for Physics Gravitation only
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
    "knowledge_units": 202,
    "blueprints_before": 137,
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
    }


def freeze_ok(snap: dict, *, expect_blueprints: int | None = None) -> bool:
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
        and bp_ok
    )


def load_eligible_concepts(conn) -> list[dict]:
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
    # Keep concepts with exactly one NCERT PASSED KU and no authoritative BP yet
    by_concept: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_concept[r["concept_id"]].append(r)

    eligible = []
    for concept_id, kus in by_concept.items():
        head = kus[0]
        if head["ncert_ku_passed"] != 1:
            continue
        if head["existing_auth_bp_count"] > 0:
            continue
        # Use the single NCERT KU row (first)
        eligible.append(head)
    return eligible


def classification_for(concept_code: str, subject: str) -> str:
    if subject == "PHYSICS" and concept_code in PHYSICS_NUMERICAL:
        return "numerical"
    return "conceptual"


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
        "tail": "\n".join(out.strip().splitlines()[-35:]),
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

        # One family per subject for this campaign
        for subject in sorted({r["subject"] for r in eligible}):
            fam_key = f"{CAMPAIGN}-fam-{subject.lower()}-ncert-conceptual"
            fam, fam_created = await planning.create_family(
                QuestionFamilyCreateRequest(
                    family_key=fam_key,
                    name=f"{subject} NCERT conceptual (BP-CREATE-001)",
                    description="NCERT-Books-grounded MCQ family for BP-CREATE-001 pilot coverage",
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
            try:
                validated = validate_ncert_generation_source(row["ncert_job_path"], root=ncert_root)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "concept_code": concept_code,
                        "error": f"NCERT path validation failed: {exc}",
                        "path": row["ncert_job_path"],
                    }
                )
                continue

            classification = classification_for(concept_code, subject)
            obj_key = f"{CAMPAIGN}-obj-{subject.lower()}-{concept_code}"
            bp_key = f"{CAMPAIGN}-bp-{subject.lower()}-{concept_code}-mcq"

            try:
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
                # Only attach section heading when present in KU ingestion (never fabricate pages)
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

                # Production NCERT generation gate (not the incorrect 'ncert' tier audit gate)
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
    return {"created": created, "reused": reused, "failures": failures, "families": {k: str(v) for k, v in families.items()}}


def legacy_treatment_summary(conn) -> dict:
    rows = list(
        conn.execute(
            text(
                """
                SELECT
                  COUNT(*) FILTER (WHERE provenance_tier = 'ai') AS ai_tier,
                  COUNT(*) FILTER (WHERE provenance_tier = 'authoritative') AS authoritative_tier,
                  COUNT(*) FILTER (
                    WHERE coalesce(constraints::text, '') ILIKE '%StudyMaterial%'
                  ) AS studymaterial_constraints,
                  COUNT(*) FILTER (
                    WHERE provenance_tier = 'ai'
                      AND coalesce(constraints->>'ncert_source_path', '') = ''
                  ) AS source_missingish_ai
                FROM cms.question_blueprints
                WHERE deleted_at IS NULL
                """
            )
        ).mappings()
    )[0]
    return {
        **dict(rows),
        "note": (
            "Legacy StudyMaterial / SOURCE_MISSING blueprints were not rewritten. "
            "New authoritative NCERT blueprints were added alongside where eligible."
        ),
    }


def pilot_capacity(created: list[dict], eligible: list[dict]) -> dict:
    out = {}
    for subj in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY"):
        elig = [e for e in eligible if e["subject"] == subj]
        bps = [c for c in created if c["subject"] == subj]
        capacity = sum(int(c["target_count"]) for c in bps)
        out[subj] = {
            "eligible_concepts": len(elig),
            "generation_ready_bps_created": len(bps),
            "total_target_capacity": capacity,
            "pilot_target": 100,
            "pilot_capacity_claim": min(capacity, 100),
            "shortfall_vs_100": max(0, 100 - capacity),
            "note": (
                "Capacity is sum of blueprint target_count for newly created NCERT-backed BPs only; "
                "not a claim of realized MCQ yield."
            ),
        }
    return out


def write_reports(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    created = payload["created_blueprints"]
    lines = [
        "# BP-CREATE-001 — NCERT-backed blueprint coverage",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- MCQ generation: **disabled / not run**",
        "- Git: **no commit / no push**",
        "",
        "## 1. Blueprints before",
        f"- Total: `{payload['before']['question_blueprints']}`",
        f"- Authoritative: `{payload['before']['authoritative_blueprints']}`",
        "",
        "## 2–4. Blueprints created",
        f"- Created: `{len(created)}`",
        f"- Reused (idempotent): `{len(payload['reused_blueprints'])}`",
        f"- Failures: `{len(payload['failures'])}`",
        f"- After total: `{payload['after']['question_blueprints']}`",
        f"- After authoritative: `{payload['after']['authoritative_blueprints']}`",
        "",
        "### Exact blueprint IDs created",
    ]
    for c in created:
        lines.append(
            f"- `{c['blueprint_id']}` `{c['blueprint_key']}` — {c['subject']}/{c['chapter_code']}/"
            f"{c['concept_code']} — target={c['target_count']} — `{c['ncert_source_relative']}`"
        )
    lines += [
        "",
        "## 5–8. Concept/KU/provenance/targets",
        f"- Campaign: `{CAMPAIGN}`",
        f"- Provenance: `authoritative` + `ncert_derived=true` + canonical `ncert_source_path`",
        f"- Target count per new BP: `{TARGET_COUNT}`",
        f"- By subject created: `{dict(Counter(c['subject'] for c in created))}`",
        "",
        "## 9–10. Subject-wise pilot capacity",
        "",
        "| Subject | Eligible concepts | Generation-ready BPs | Total target capacity | Pilot capacity (≤100) | Shortfall vs 100 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for subj, row in payload["pilot_capacity"].items():
        lines.append(
            f"| {subj} | {row['eligible_concepts']} | {row['generation_ready_bps_created']} | "
            f"{row['total_target_capacity']} | {row['pilot_capacity_claim']} | {row['shortfall_vs_100']} |"
        )
    lines += [
        "",
        "## 11. Legacy blueprint treatment",
        f"```json\n{json.dumps(payload['legacy_treatment'], indent=2)}\n```",
        "",
        "## 12. SOURCE_MISSING treatment",
        "- Left unresolved; not rewritten; not used as NCERT evidence for new BPs.",
        "",
        "## 13. Excluded content",
        "- `digestion-absorption`: no blueprints created.",
        "",
        "## 14. Safety counts",
        "### Before",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "### After",
        f"```json\n{json.dumps(payload['after'], indent=2)}\n```",
        f"- Question freeze OK: `{payload['question_freeze_ok']}`",
        f"- Factory jobs/runs/candidates unchanged: `{payload['factory_orchestration_unchanged']}`",
        "",
        "## 15. Tests",
        f"- Passed `{payload['tests'].get('passed')}` / Failed `{payload['tests'].get('failed')}`",
        f"- Unavailable: `{payload['tests'].get('unavailable')}`",
        "",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## 16. Exact files changed",
    ]
    for f in payload["files_changed"]:
        lines.append(f"- `{f}`")
    lines += [
        "",
        "## Confirmation",
        f"```json\n{json.dumps(payload['confirmation'], indent=2)}\n```",
        "",
        "**STOP** — do not generate MCQs; wait for owner review.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


async def async_main() -> int:
    settings = get_settings()
    sync_engine = create_engine(settings.database_url_sync)
    try:
        ncert_root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        ncert_root = ROOT / "NCERT Books"

    with sync_engine.connect() as conn:
        before = snapshot_sync(conn)
        if not freeze_ok(before, expect_blueprints=FREEZE["blueprints_before"]):
            raise SystemExit(f"ABORT: freeze mismatch before create: {before}")
        eligible = load_eligible_concepts(conn)
        if not eligible:
            raise SystemExit("ABORT: no eligible concepts")

    # Actor
    async_engine = create_async_engine(settings.database_url)
    async with AsyncSession(async_engine) as session:
        actor = (
            await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))
        ).scalar_one_or_none()
        actor_id = actor.id if actor else None
    await async_engine.dispose()

    result = await create_all(eligible, actor_id, ncert_root)

    with sync_engine.connect() as conn:
        after = snapshot_sync(conn)
        legacy = legacy_treatment_summary(conn)
        # Verify no question mutation
        if after["status"] != before["status"] or after["unmapped_draft"] != before["unmapped_draft"]:
            raise SystemExit("ABORT: question inventory changed")
        for k in ("chapters", "topics", "concepts", "knowledge_units", "content_batches", "generation_jobs", "generation_runs", "generation_candidates"):
            if before[k] != after[k]:
                raise SystemExit(f"ABORT: {k} changed {before[k]} → {after[k]}")

        expected_bp = before["question_blueprints"] + len(result["created"])
        # reused don't increase count
        if after["question_blueprints"] != expected_bp and not result["reused"]:
            # If some failures, expected = before + created only
            pass
        if after["question_blueprints"] != before["question_blueprints"] + len(result["created"]):
            raise SystemExit(
                f"ABORT: blueprint count unexpected before={before['question_blueprints']} "
                f"after={after['question_blueprints']} created={len(result['created'])}"
            )

    tests = run_tests()
    capacity = pilot_capacity(result["created"], eligible)

    question_freeze_ok = freeze_ok(after, expect_blueprints=after["question_blueprints"]) and (
        after["status"] == before["status"] and after["unmapped_draft"] == before["unmapped_draft"]
    )
    factory_unchanged = all(
        before[k] == after[k]
        for k in ("content_batches", "generation_jobs", "generation_runs", "generation_candidates")
    )
    all_created_ok = (
        len(result["failures"]) == 0
        and len(result["created"]) > 0
        and all(c["generation_eligible"] and c["ncert_assert_ok"] for c in result["created"])
    )

    # YELLOW if subject shortfalls remain (expected for Physics/Zoology given KU coverage)
    shortfalls = {s: v["shortfall_vs_100"] for s, v in capacity.items() if v["shortfall_vs_100"] > 0}
    if not question_freeze_ok or not factory_unchanged or (tests.get("failed") or 0) > 0 or not all_created_ok:
        final = "RED — FAILED"
    elif shortfalls:
        final = "YELLOW — PARTIALLY VERIFIED"
    else:
        final = "GREEN — COMPLETE/VERIFIED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "campaign": CAMPAIGN,
        "ncert_root": str(ncert_root),
        "target_count_per_blueprint": TARGET_COUNT,
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
        "before": before,
        "after": after,
        "created_blueprints": result["created"],
        "reused_blueprints": result["reused"],
        "failures": result["failures"],
        "families": result["families"],
        "pilot_capacity": capacity,
        "shortfalls_vs_pilot_100": shortfalls,
        "legacy_treatment": legacy,
        "source_missing_treatment": "Unresolved legacy AI blueprints without NCERT Books path were not modified.",
        "excluded_content": {
            "digestion-absorption": "No blueprints created (absent from rationalised corpus).",
        },
        "question_freeze_ok": question_freeze_ok,
        "factory_orchestration_unchanged": factory_unchanged,
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/bp_create_001_ncert_blueprints.py",
            f"cms.question_blueprints (+{len(result['created'])} rows)",
            "cms.learning_objectives / cms.question_families (campaign keys)",
        ],
        "confirmation": {
            "mcqs_generated": False,
            "ai_called": False,
            "content_factory_jobs_created": False,
            "questions_mutated": False,
            "kus_mutated": False,
            "taxonomy_mutated": False,
            "legacy_provenance_rewritten": False,
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
                "pilot_capacity": capacity,
                "question_freeze_ok": question_freeze_ok,
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
            },
            indent=2,
        )
    )
    return 0 if final != "RED — FAILED" else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
