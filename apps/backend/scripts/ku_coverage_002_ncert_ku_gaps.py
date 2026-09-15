"""KU-COVERAGE-002 — Close verified NCERT Knowledge Unit gaps.

Extends CF-C5 deterministic NCERT Books extraction to chapters missing from
the CF-C5 CHAPTER_PDF_MAP. Creates PASSED KUs only when grounded evidence
is found under the canonical NCERT Books root.

Does NOT: MCQs, blueprints, question mutation, taxonomy changes,
rewrite StudyMaterial KUs, Digestion & Absorption coverage.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.ingestion.models import IngestionJob, IngestionSection  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    get_ncert_source_root,
    validate_ncert_generation_source,
)
from app.modules.knowledge.models import KnowledgeUnit  # noqa: E402
from app.modules.knowledge.services.deterministic_structuring_service import (  # noqa: E402
    _content_hash,
    build_summary,
    extract_facts_from_section_text,
)
from app.modules.knowledge.services.grounding_check import check_grounding  # noqa: E402

# Reuse CF-C5 PDF helpers
from scripts.curriculum_baseline_005_ku_backfill import (  # noqa: E402
    decode_pua,
    extract_window,
    load_pdf_text,
)

REPORT_STEM = "ku_coverage_002_20260913"
EXCLUDED_CHAPTERS = frozenset({"digestion-absorption"})
PRIORITY = ("PHYSICS", "ZOOLOGY", "BOTANY", "CHEMISTRY")

# Extended map: chapter_code -> one or more relative NCERT Books paths
CHAPTER_PDF_MAP: dict[str, list[str]] = {
    # Physics XI
    "units-and-measurement": ["Class 11/Physics/keph1dd/keph1dd/keph101.pdf"],
    "kinematics": [
        "Class 11/Physics/keph1dd/keph1dd/keph102.pdf",
        "Class 11/Physics/keph1dd/keph1dd/keph103.pdf",
    ],
    "laws-of-motion": ["Class 11/Physics/keph1dd/keph1dd/keph104.pdf"],
    "work-energy-power": ["Class 11/Physics/keph1dd/keph1dd/keph105.pdf"],
    "systems-of-particles-rotational-motion": ["Class 11/Physics/keph1dd/keph1dd/keph106.pdf"],
    "gravitation": ["Class 11/Physics/keph1dd/keph1dd/keph107.pdf"],
    "mechanical-properties-of-solids": ["Class 11/Physics/keph2dd/keph2dd/keph201.pdf"],
    "mechanical-properties-of-fluids": ["Class 11/Physics/keph2dd/keph2dd/keph202.pdf"],
    "thermodynamics-physics": ["Class 11/Physics/keph2dd/keph2dd/keph204.pdf"],
    "kinetic-theory": ["Class 11/Physics/keph2dd/keph2dd/keph205.pdf"],
    # Physics XII
    "electrostatics": [
        "Class 12/Physics/leph1dd/leph101.pdf",
        "Class 12/Physics/leph1dd/leph102.pdf",
    ],
    "current-electricity": ["Class 12/Physics/leph1dd/leph103.pdf"],
    "optics": [
        "Class 12/Physics/leph2dd/leph201.pdf",
        "Class 12/Physics/leph2dd/leph202.pdf",
    ],
    # Chemistry XI
    "basic-concepts-chemistry": ["Class 11/Chemistry/kech1dd/kech1dd/kech101.pdf"],
    "structure-of-atom": ["Class 11/Chemistry/kech1dd/kech1dd/kech102.pdf"],
    "chemical-bonding": ["Class 11/Chemistry/kech1dd/kech1dd/kech104.pdf"],
    "thermodynamics-chemistry": ["Class 11/Chemistry/kech1dd/kech1dd/kech105.pdf"],
    "equilibrium": ["Class 11/Chemistry/kech1dd/kech1dd/kech106.pdf"],
    "redox-reactions": ["Class 11/Chemistry/kech2dd/kech201.pdf"],
    "organic-chemistry-basics": ["Class 11/Chemistry/kech2dd/kech202.pdf"],
    # Chemistry XII (already in CF-C5; keep for completeness)
    "solutions": ["Class 12/Chemistry 1/lech1dd/lech101.pdf"],
    "electrochemistry": ["Class 12/Chemistry 1/lech1dd/lech102.pdf"],
    "chemical-kinetics": ["Class 12/Chemistry 1/lech1dd/lech103.pdf"],
    "d-and-f-block-elements": ["Class 12/Chemistry 1/lech1dd/lech104.pdf"],
    "coordination-compounds": ["Class 12/Chemistry 1/lech1dd/lech105.pdf"],
    "haloalkanes-and-haloarenes": ["Class 12/Chemistry 2/lech2dd/lech201.pdf"],
    "alcohols-phenols-and-ethers": ["Class 12/Chemistry 2/lech2dd/lech202.pdf"],
    "aldehydes-ketones-and-carboxylic-acids": ["Class 12/Chemistry 2/lech2dd/lech203.pdf"],
    "amines": ["Class 12/Chemistry 2/lech2dd/lech204.pdf"],
    "biomolecules-chem": ["Class 12/Chemistry 2/lech2dd/lech205.pdf"],
    # Botany XI
    "the-living-world": ["Class 11/Biology/kebo1dd/kebo101.pdf"],
    "biological-classification": ["Class 11/Biology/kebo1dd/kebo102.pdf"],
    "plant-kingdom": ["Class 11/Biology/kebo1dd/kebo103.pdf"],
    "morphology-flowering-plants": ["Class 11/Biology/kebo1dd/kebo105.pdf"],
    "cell-unit-of-life": ["Class 11/Biology/kebo1dd/kebo108.pdf"],
    "biomolecules": ["Class 11/Biology/kebo1dd/kebo109.pdf"],
    "photosynthesis": ["Class 11/Biology/kebo1dd/kebo111.pdf"],
    "plant-growth-development": ["Class 11/Biology/kebo1dd/kebo113.pdf"],
    # Botany XII (CF-C5)
    "sexual-reproduction-flowering-plants": ["Class 12/Biology/lebo1dd/lebo101.pdf"],
    "principles-of-inheritance-and-variation": ["Class 12/Biology/lebo1dd/lebo104.pdf"],
    "molecular-basis-of-inheritance": ["Class 12/Biology/lebo1dd/lebo105.pdf"],
    "microbes-in-human-welfare": ["Class 12/Biology/lebo1dd/lebo108.pdf"],
    "biotechnology-principles-and-processes": ["Class 12/Biology/lebo1dd/lebo109.pdf"],
    "biotechnology-and-its-applications": ["Class 12/Biology/lebo1dd/lebo110.pdf"],
    "organisms-and-populations": ["Class 12/Biology/lebo1dd/lebo111.pdf"],
    "ecosystem": ["Class 12/Biology/lebo1dd/lebo112.pdf"],
    "biodiversity-and-conservation": ["Class 12/Biology/lebo1dd/lebo113.pdf"],
    # Zoology XI
    "animal-kingdom": ["Class 11/Biology/kebo1dd/kebo104.pdf"],
    "structural-organisation-animals": ["Class 11/Biology/kebo1dd/kebo107.pdf"],
    "breathing-exchange-of-gases": ["Class 11/Biology/kebo1dd/kebo114.pdf"],
    "body-fluids-circulation": ["Class 11/Biology/kebo1dd/kebo115.pdf"],
    # Zoology XII
    "human-reproduction": ["Class 12/Biology/lebo1dd/lebo102.pdf"],
    "reproductive-health": ["Class 12/Biology/lebo1dd/lebo103.pdf"],
    "evolution": ["Class 12/Biology/lebo1dd/lebo106.pdf"],
    "human-health-and-disease": ["Class 12/Biology/lebo1dd/lebo107.pdf"],
}

FREEZE_Q = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "DRAFT": 5298,
    "SUPERSEDED": 6,
    "unmapped_draft": 5024,
}
FREEZE_ACADEMIC = {"chapters": 56, "topics": 192, "concepts": 318, "blueprints": 266}


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
        "ingestion_jobs": conn.execute(text("SELECT COUNT(*) FROM ingestion.ingestion_jobs")).scalar(),
        "ncert_books_passed_kus": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                WHERE ku.deleted_at IS NULL AND ku.validation_status = 'PASSED'
                  AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%'
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
        snap["status"].get("PUBLISHED") == FREEZE_Q["PUBLISHED"]
        and snap["status"].get("IN_REVIEW") == FREEZE_Q["IN_REVIEW"]
        and snap["status"].get("DRAFT") == FREEZE_Q["DRAFT"]
        and snap["status"].get("SUPERSEDED") == FREEZE_Q["SUPERSEDED"]
        and snap["unmapped_draft"] == FREEZE_Q["unmapped_draft"]
        and snap["chapters"] == FREEZE_ACADEMIC["chapters"]
        and snap["topics"] == FREEZE_ACADEMIC["topics"]
        and snap["concepts"] == FREEZE_ACADEMIC["concepts"]
        and snap["question_blueprints"] == FREEZE_ACADEMIC["blueprints"]
    )


def load_candidates(conn) -> list[dict]:
    rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT c.id::text AS concept_id, c.code AS concept_code, c.name AS concept_name,
                       coalesce(c.summary, '') AS summary,
                       coalesce(c.ncert_reference, '') AS ncert_reference,
                       s.code AS subject, s.id::text AS subject_id,
                       ch.code AS chapter_code, ch.id::text AS chapter_id, ch.class_level,
                       t.code AS topic_code,
                       (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                        WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                          AND ku.validation_status = 'PASSED') AS passed_ku_count,
                       (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                        JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                        JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                        WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                          AND ku.validation_status = 'PASSED'
                          AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%') AS ncert_ku_count,
                       (SELECT COUNT(*) FROM cms.question_blueprints bp
                        WHERE bp.concept_id = c.id AND bp.deleted_at IS NULL
                          AND bp.provenance_tier = 'authoritative') AS auth_bp_count
                FROM academic.concepts c
                JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE c.deleted_at IS NULL
                  AND ch.code <> 'digestion-absorption'
                ORDER BY s.code, ch.code, c.code
                """
            )
        ).mappings()
    ]
    out = []
    for r in rows:
        if r["chapter_code"] not in CHAPTER_PDF_MAP:
            r["skip_reason"] = "chapter_not_in_pdf_map"
            continue
        if r["ncert_ku_count"] > 0:
            continue  # already has NCERT KU
        out.append(r)
    # Priority sort
    rank = {s: i for i, s in enumerate(PRIORITY)}
    out.sort(key=lambda x: (rank.get(x["subject"], 99), x["chapter_code"], x["concept_code"]))
    return out


def find_window_across_pdfs(
    root: Path, pdf_rels: list[str], concept_name: str, ncert_reference: str, summary: str
) -> tuple[str | None, str, str | None]:
    """Return (window, evidence_note, pdf_rel_used)."""
    best: tuple[str, str, str] | None = None
    best_score = -1
    last_reason = "no_pdf"
    for rel in pdf_rels:
        try:
            pdf_text = load_pdf_text(root, rel)
        except Exception as exc:  # noqa: BLE001
            last_reason = f"pdf_error:{exc}"
            continue
        window, note = extract_window(pdf_text, concept_name, ncert_reference, summary)
        if not window:
            last_reason = note
            continue
        # Prefer section_window hits
        score = 100 if note.startswith("section_window") else 10
        m = re.search(r"score=(\d+)", note)
        if m:
            score = int(m.group(1))
        if score > best_score:
            best_score = score
            best = (window, f"{note}|pdf={rel}", rel)
    if best:
        return best[0], best[1], best[2]
    return None, last_reason, None


def backfill(session: Session, root: Path, candidates: list[dict]) -> dict:
    created = []
    unresolved = []
    jobs_by_pdf: dict[str, uuid.UUID] = {}

    for g in candidates:
        pdf_rels = CHAPTER_PDF_MAP[g["chapter_code"]]
        # Validate all mapped PDFs exist under root
        missing = [p for p in pdf_rels if not (root / p).exists()]
        if missing:
            unresolved.append(
                {
                    "concept_code": g["concept_code"],
                    "subject": g["subject"],
                    "chapter": g["chapter_code"],
                    "reason": f"mapped_pdf_missing:{missing}",
                }
            )
            continue

        window, note, pdf_rel = find_window_across_pdfs(
            root, pdf_rels, g["concept_name"], g.get("ncert_reference") or "", g.get("summary") or ""
        )
        if not window or not pdf_rel:
            unresolved.append(
                {
                    "concept_code": g["concept_code"],
                    "subject": g["subject"],
                    "chapter": g["chapter_code"],
                    "reason": note or "insufficient_evidence",
                    "pdfs_tried": pdf_rels,
                }
            )
            continue

        facts = extract_facts_from_section_text(window)
        if not facts:
            unresolved.append(
                {
                    "concept_code": g["concept_code"],
                    "subject": g["subject"],
                    "chapter": g["chapter_code"],
                    "reason": "no_facts",
                    "pdf": pdf_rel,
                    "evidence": note,
                }
            )
            continue
        grounded, detail = check_grounding(facts, window)
        if not grounded:
            unresolved.append(
                {
                    "concept_code": g["concept_code"],
                    "subject": g["subject"],
                    "chapter": g["chapter_code"],
                    "reason": f"ungrounded:{detail}",
                    "pdf": pdf_rel,
                    "evidence": note,
                }
            )
            continue

        # Re-check no NCERT KU appeared
        existing_ncert = session.execute(
            text(
                """
                SELECT ku.id::text FROM knowledge.knowledge_units ku
                JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                WHERE ku.concept_id = :cid AND ku.deleted_at IS NULL
                  AND ku.validation_status = 'PASSED'
                  AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%'
                LIMIT 1
                """
            ),
            {"cid": g["concept_id"]},
        ).scalar_one_or_none()
        if existing_ncert:
            unresolved.append(
                {
                    "concept_code": g["concept_code"],
                    "subject": g["subject"],
                    "reason": "already_has_ncert_ku",
                }
            )
            continue

        if pdf_rel not in jobs_by_pdf:
            pdf_path = root / pdf_rel
            validate_ncert_generation_source(pdf_path, root=root)
            checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            job = IngestionJob(
                source_file_path=str(pdf_path.resolve()),
                original_filename=pdf_path.name,
                file_checksum=checksum,
                source_document_id=None,
                subject_id=uuid.UUID(g["subject_id"]),
                chapter_id=uuid.UUID(g["chapter_id"]),
                status="COMPLETED",
                stage_detail="KU-COVERAGE-002 NCERT Books KU backfill (deterministic; no AI)",
            )
            session.add(job)
            session.flush()
            jobs_by_pdf[pdf_rel] = job.id

        summary = build_summary(facts, g["concept_name"])
        chash = _content_hash(facts)
        dup_hash = session.execute(
            text(
                """
                SELECT id::text FROM knowledge.knowledge_units
                WHERE concept_id = :cid AND content_hash = :h AND deleted_at IS NULL
                LIMIT 1
                """
            ),
            {"cid": g["concept_id"], "h": chash},
        ).scalar_one_or_none()
        if dup_hash:
            unresolved.append(
                {
                    "concept_code": g["concept_code"],
                    "subject": g["subject"],
                    "reason": "duplicate_content_hash",
                    "pdf": pdf_rel,
                }
            )
            continue

        section = IngestionSection(
            job_id=jobs_by_pdf[pdf_rel],
            heading=f"KU-COVERAGE-002 / {g['concept_name']}"[:300],
            source_page=1,
            raw_text=window,
            matched_concept_id=uuid.UUID(g["concept_id"]),
            questions_generated=0,
            language_code="en",
            language_name="English",
            language_confidence=1.0,
        )
        session.add(section)
        session.flush()

        unit = KnowledgeUnit(
            version=1,
            content_hash=chash,
            structured_facts=facts,
            summary=summary,
            source_section_id=section.id,
            concept_id=uuid.UUID(g["concept_id"]),
            extraction_confidence=0.85,
            validation_status="PASSED",
            validation_detail=None,
        )
        session.add(unit)
        session.flush()
        created.append(
            {
                "ku_id": str(unit.id),
                "concept_id": g["concept_id"],
                "concept_code": g["concept_code"],
                "concept_name": g["concept_name"],
                "subject": g["subject"],
                "class_level": g["class_level"],
                "chapter": g["chapter_code"],
                "topic": g["topic_code"],
                "pdf": pdf_rel,
                "evidence": note,
                "facts": len(facts),
                "summary": summary[:200],
                "had_legacy_passed_ku": g["passed_ku_count"] > 0,
                "auth_bp_count": g["auth_bp_count"],
            }
        )

    session.commit()
    return {
        "candidates": len(candidates),
        "created": created,
        "unresolved": unresolved,
        "jobs_created": len(jobs_by_pdf),
        "pdfs_used": sorted(jobs_by_pdf.keys()),
    }


def pilot_capacity_impact(conn) -> dict:
    """Estimate BP-CREATE-style eligibility after KU backfill (no blueprint creation)."""
    rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT s.code AS subject, c.id::text AS concept_id, c.code AS concept_code, ch.code AS chapter_code,
                  (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                   JOIN ingestion.ingestion_sections sec ON sec.id=ku.source_section_id
                   JOIN ingestion.ingestion_jobs j ON j.id=sec.job_id
                   WHERE ku.concept_id=c.id AND ku.deleted_at IS NULL
                     AND ku.validation_status='PASSED'
                     AND coalesce(j.source_file_path,'') LIKE '%NCERT Books%') AS ncert_ku,
                  (SELECT COUNT(*) FROM cms.question_blueprints bp
                   WHERE bp.concept_id=c.id AND bp.deleted_at IS NULL
                     AND bp.provenance_tier='authoritative') AS auth_bp
                FROM academic.concepts c
                JOIN academic.topics t ON t.id=c.topic_id AND t.deleted_at IS NULL
                JOIN academic.chapters ch ON ch.id=t.chapter_id AND ch.deleted_at IS NULL
                JOIN academic.subjects s ON s.id=ch.subject_id
                WHERE c.deleted_at IS NULL AND ch.code <> 'digestion-absorption'
                """
            )
        ).mappings()
    ]
    out = {}
    for subj in PRIORITY:
        xs = [r for r in rows if r["subject"] == subj]
        eligible = [r for r in xs if r["ncert_ku"] == 1]
        need_bp = [r for r in eligible if r["auth_bp"] == 0]
        with_auth = [r for r in eligible if r["auth_bp"] > 0]
        # Conservative target_count=2 as BP-CREATE-001
        capacity_if_bp = len(need_bp) * 2 + len(with_auth) * 2
        # Existing BP-CREATE capacity on with_auth only (already have BPs)
        existing_bp_capacity = len(with_auth) * 2
        out[subj] = {
            "concepts_total": len(xs),
            "concepts_with_exactly_1_ncert_ku": len(eligible),
            "already_have_authoritative_bp": len(with_auth),
            "newly_eligible_for_blueprint": len(need_bp),
            "estimated_target_capacity_if_bps_created_at_2": capacity_if_bp,
            "current_authoritative_bp_target_capacity_approx": existing_bp_capacity,
            "pilot_target": 100,
            "shortfall_vs_100_if_only_existing_bps": max(0, 100 - existing_bp_capacity),
            "shortfall_vs_100_if_new_bps_also_created": max(0, 100 - capacity_if_bp),
            "note": (
                "Capacity estimates assume target_count=2 per concept and do NOT create blueprints. "
                "BP-CREATE-001 already created authoritative BPs for prior eligible set."
            ),
        }
    return out


def investigate_physics_gap(conn) -> dict:
    return {
        "root_cause": (
            "CF-C5 CHAPTER_PDF_MAP only included Physics chapter 'gravitation'. "
            "Other Physics chapters had zero mapped canonical NCERT Books PDFs, so no NCERT KUs "
            "were created even though PDFs exist under NCERT Books."
        ),
        "cfc5_physics_chapters_mapped": ["gravitation"],
        "ku_coverage_002_physics_chapters_mapped": sorted(
            [k for k, v in CHAPTER_PDF_MAP.items() if "Physics" in str(v)]
        ),
    }


def investigate_sv2c(conn) -> dict:
    row = conn.execute(
        text(
            """
            SELECT c.id::text, c.code, c.name, left(coalesce(c.summary,''),240) AS summary,
                   ch.code AS chapter, s.code AS subject,
                   (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                    WHERE ku.concept_id=c.id AND ku.deleted_at IS NULL) kus,
                   (SELECT left(ku.summary,200) FROM knowledge.knowledge_units ku
                    WHERE ku.concept_id=c.id AND ku.deleted_at IS NULL
                    ORDER BY ku.created_at LIMIT 1) ku_summary,
                   (SELECT left(coalesce(j.source_file_path,''),200)
                    FROM knowledge.knowledge_units ku
                    JOIN ingestion.ingestion_sections sec ON sec.id=ku.source_section_id
                    JOIN ingestion.ingestion_jobs j ON j.id=sec.job_id
                    WHERE ku.concept_id=c.id AND ku.deleted_at IS NULL
                    ORDER BY ku.created_at LIMIT 1) path
            FROM academic.concepts c
            JOIN academic.topics t ON t.id=c.topic_id
            JOIN academic.chapters ch ON ch.id=t.chapter_id
            JOIN academic.subjects s ON s.id=ch.subject_id
            WHERE c.code = 'sv2c-botany-15' AND c.deleted_at IS NULL
            """
        )
    ).mappings().one_or_none()
    twins = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT c.code, c.name, ch.code AS chapter
                FROM academic.concepts c
                JOIN academic.topics t ON t.id=c.topic_id
                JOIN academic.chapters ch ON ch.id=t.chapter_id
                WHERE c.deleted_at IS NULL
                  AND (
                    c.code ILIKE '%syngamy%'
                    OR c.name ILIKE '%syngamy%'
                    OR c.name ILIKE '%triple fusion%'
                  )
                ORDER BY c.code
                """
            )
        ).mappings()
    ]
    finding = {
        "concept": dict(row) if row else None,
        "possible_duplicates": twins,
        "assessment": (
            "Code `sv2c-botany-15` is seed-like, but the concept name is 'Syngamy and triple fusion' "
            "and its existing KU summary/path resolve under NCERT Books Class 12 Biology lebo101.pdf "
            "(Sexual Reproduction in Flowering Plants). Evidence appears genuinely NCERT-grounded. "
            "A parallel well-named concept may also exist — taxonomy reconciliation is OWNER REVIEW "
            "(not modified in this task)."
        ),
        "action_taken": "none (reported only; concept/KU/blueprint untouched)",
    }
    return finding


def run_tests() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "app/modules/ingestion/tests/test_ncert_canonical_source.py",
        "app/modules/knowledge/tests/test_grounding_check.py",
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
        "app/modules/academic/tests/test_cf_c2_biology.py",
        "app/modules/academic/tests/test_cf_c3_gravitation.py",
        "app/modules/academic/tests/test_cf_c4_biomolecules.py",
        "app/modules/academic/tests/test_cf_c5_ku_backfill.py",
        "app/modules/cms/tests/test_question_blueprints.py",
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


def write_reports(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    created = payload["backfill"]["created"]
    by_subj = Counter(c["subject"] for c in created)
    lines = [
        "# KU-COVERAGE-002 — Close verified NCERT Knowledge Unit gaps",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Blueprints/MCQs: **not created**",
        "- Git: **no commit / no push**",
        "",
        "## Before / after KU counts",
        f"- KUs before: `{payload['before']['knowledge_units']}` → after: `{payload['after']['knowledge_units']}`",
        f"- Concepts with NCERT KU before: `{payload['before']['concepts_with_ncert_ku']}` → after: `{payload['after']['concepts_with_ncert_ku']}`",
        f"- NCERT Books PASSED KUs before: `{payload['before']['ncert_books_passed_kus']}` → after: `{payload['after']['ncert_books_passed_kus']}`",
        f"- Created this run: `{len(created)}`",
        f"- Unresolved: `{len(payload['backfill']['unresolved'])}`",
        "",
        "## New KUs by subject",
        f"`{dict(by_subj)}`",
        "",
        "## Physics gap investigation",
        f"```json\n{json.dumps(payload['physics_gap'], indent=2)}\n```",
        "",
        "## sv2c-botany-15 finding",
        f"```json\n{json.dumps(payload['sv2c_botany_15'], indent=2)}\n```",
        "",
        "## Newly covered concepts (sample)",
    ]
    for c in created[:40]:
        lines.append(
            f"- `{c['subject']}/{c['chapter']}/{c['concept_code']}` → KU `{c['ku_id']}` ← `{c['pdf']}` ({c['evidence']})"
        )
    if len(created) > 40:
        lines.append(f"- … +{len(created) - 40} more (see JSON)")
    lines += [
        "",
        "## Remaining unresolved (by reason)",
        f"`{dict(Counter(u.get('reason','?').split(':')[0] for u in payload['backfill']['unresolved']))}`",
        "",
        "## Pilot capacity impact (no blueprints created)",
        "",
        "| Subject | Concepts w/ exactly 1 NCERT KU | Already have auth BP | Newly eligible for BP | Est. capacity if BP@2 | Shortfall if new BPs too |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for subj, row in payload["pilot_capacity_impact"].items():
        lines.append(
            f"| {subj} | {row['concepts_with_exactly_1_ncert_ku']} | {row['already_have_authoritative_bp']} | "
            f"{row['newly_eligible_for_blueprint']} | {row['estimated_target_capacity_if_bps_created_at_2']} | "
            f"{row['shortfall_vs_100_if_new_bps_also_created']} |"
        )
    lines += [
        "",
        "## Safety / freeze",
        f"- Question freeze OK: `{payload['question_freeze_ok']}`",
        f"- Academic freeze OK: `{payload['academic_freeze_ok']}`",
        f"- CF generation jobs/runs/candidates unchanged: `{payload['factory_orchestration_unchanged']}`",
        f"- Digestion KUs: `{payload['digestion_kus']}`",
        f"- Blueprints unchanged: `{payload['before']['question_blueprints']} → {payload['after']['question_blueprints']}`",
        "",
        "### Before",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "### After",
        f"```json\n{json.dumps(payload['after'], indent=2)}\n```",
        "",
        "## Tests",
        f"- Passed `{payload['tests'].get('passed')}` / Failed `{payload['tests'].get('failed')}`",
        f"- Unavailable: `{payload['tests'].get('unavailable')}`",
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
        "**STOP** — do not create blueprints or generate MCQs; wait for owner review.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        root = ROOT / "NCERT Books"

    with engine.connect() as conn:
        before = snapshot(conn)
        if not freeze_ok(before):
            raise SystemExit(f"ABORT freeze before: {before}")
        candidates = load_candidates(conn)
        physics_gap = investigate_physics_gap(conn)
        sv2c = investigate_sv2c(conn)
        dig_before = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                JOIN academic.concepts c ON c.id=ku.concept_id
                JOIN academic.topics t ON t.id=c.topic_id
                JOIN academic.chapters ch ON ch.id=t.chapter_id
                WHERE ch.code='digestion-absorption' AND ku.deleted_at IS NULL
                """
            )
        ).scalar()

    session = SessionLocal()
    try:
        backfill_result = backfill(session, root, candidates)
    finally:
        session.close()

    with engine.connect() as conn:
        after = snapshot(conn)
        dig_after = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                JOIN academic.concepts c ON c.id=ku.concept_id
                JOIN academic.topics t ON t.id=c.topic_id
                JOIN academic.chapters ch ON ch.id=t.chapter_id
                WHERE ch.code='digestion-absorption' AND ku.deleted_at IS NULL
                """
            )
        ).scalar()
        capacity = pilot_capacity_impact(conn)

    tests = run_tests()

    question_freeze_ok = (
        after["status"] == before["status"] and after["unmapped_draft"] == before["unmapped_draft"]
    )
    academic_freeze_ok = all(
        before[k] == after[k] for k in ("chapters", "topics", "concepts", "question_blueprints")
    )
    factory_unchanged = all(
        before[k] == after[k]
        for k in ("content_batches", "generation_jobs", "generation_runs", "generation_candidates")
    )
    ku_increased = after["knowledge_units"] == before["knowledge_units"] + len(backfill_result["created"])

    if (
        not question_freeze_ok
        or not academic_freeze_ok
        or not factory_unchanged
        or dig_after != 0
        or dig_before != 0
        or not ku_increased
        or (tests.get("failed") or 0) > 0
    ):
        final = "RED — FAILED"
    elif backfill_result["unresolved"] or any(
        capacity[s]["shortfall_vs_100_if_new_bps_also_created"] > 0 for s in PRIORITY
    ):
        final = "YELLOW — PARTIALLY VERIFIED"
    else:
        final = "GREEN — COMPLETE/VERIFIED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "ncert_root": str(root),
        "before": before,
        "after": after,
        "candidates_count": len(candidates),
        "candidates_by_subject": dict(Counter(c["subject"] for c in candidates)),
        "backfill": backfill_result,
        "physics_gap": physics_gap,
        "sv2c_botany_15": sv2c,
        "pilot_capacity_impact": capacity,
        "digestion_kus": dig_after,
        "question_freeze_ok": question_freeze_ok,
        "academic_freeze_ok": academic_freeze_ok,
        "factory_orchestration_unchanged": factory_unchanged,
        "chapter_pdf_map": CHAPTER_PDF_MAP,
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/ku_coverage_002_ncert_ku_gaps.py",
            f"knowledge.knowledge_units (+{len(backfill_result['created'])})",
            "ingestion.ingestion_jobs / ingestion.ingestion_sections (minimal FK support)",
        ],
        "confirmation": {
            "mcqs_generated": False,
            "blueprints_created": False,
            "questions_mutated": False,
            "taxonomy_mutated": False,
            "legacy_studymaterial_kus_rewritten": False,
            "digestion_excluded": True,
            "ai_called": False,
            "committed": False,
            "pushed": False,
        },
    }
    md_path, json_path = write_reports(payload)

    # cleanup probes
    for p in (
        BACKEND / "scripts/_probe_ku_coverage_gaps.py",
        BACKEND / "scripts/_probe_ku_types.py",
    ):
        if p.exists():
            p.unlink()

    print(
        json.dumps(
            {
                "final_status": final,
                "json": str(json_path),
                "md": str(md_path),
                "kus_before": before["knowledge_units"],
                "kus_after": after["knowledge_units"],
                "created": len(backfill_result["created"]),
                "unresolved": len(backfill_result["unresolved"]),
                "created_by_subject": dict(Counter(c["subject"] for c in backfill_result["created"])),
                "concepts_with_ncert_ku": {
                    "before": before["concepts_with_ncert_ku"],
                    "after": after["concepts_with_ncert_ku"],
                },
                "pilot_capacity_impact": {
                    s: {
                        "newly_eligible_for_blueprint": capacity[s]["newly_eligible_for_blueprint"],
                        "est_capacity_if_bp": capacity[s]["estimated_target_capacity_if_bps_created_at_2"],
                        "shortfall_if_new_bps": capacity[s]["shortfall_vs_100_if_new_bps_also_created"],
                    }
                    for s in PRIORITY
                },
                "question_freeze_ok": question_freeze_ok,
                "factory_unchanged": factory_unchanged,
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
            },
            indent=2,
        )
    )
    return 0 if final != "RED — FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
