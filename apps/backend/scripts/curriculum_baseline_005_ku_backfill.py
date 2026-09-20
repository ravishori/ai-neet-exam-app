"""CF-C5 — NCERT Knowledge Unit backfill (deterministic, no AI).

Creates Knowledge Units for GAP concepts ONLY when canonical NCERT Books
PDFs yield grounded sentence-facts. Uses minimal IngestionJob +
IngestionSection rows as required FK support (source_document_id NULL;
paths under NCERT Books only).

Does NOT: MCQs, Content Factory, AI, blueprints, question mutation, ECAEP.
Does NOT: create KUs for Digestion and Absorption.
Does NOT: delete/merge existing StudyMaterial-provenance KUs.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fitz
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

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

REPORT_STEM = "curriculum_baseline_005_ku_backfill_20260913"
UNMAPPED_FREEZE = 5024
STATUS_FREEZE = {
    "DRAFT": 5298,
    "PUBLISHED": 1479,
    "SUPERSEDED": 6,
    "IN_REVIEW": 111,
}
EXCLUDED_CHAPTERS = frozenset({"digestion-absorption"})

# Project chapter code → canonical NCERT Books relative path (verified CF-C1/C2/C3/C4).
CHAPTER_PDF_MAP: dict[str, str] = {
    # Physics XI
    "gravitation": "Class 11/Physics/keph1dd/keph1dd/keph107.pdf",
    # Chemistry XII
    "solutions": "Class 12/Chemistry 1/lech1dd/lech101.pdf",
    "electrochemistry": "Class 12/Chemistry 1/lech1dd/lech102.pdf",
    "chemical-kinetics": "Class 12/Chemistry 1/lech1dd/lech103.pdf",
    "d-and-f-block-elements": "Class 12/Chemistry 1/lech1dd/lech104.pdf",
    "coordination-compounds": "Class 12/Chemistry 1/lech1dd/lech105.pdf",
    "haloalkanes-and-haloarenes": "Class 12/Chemistry 2/lech2dd/lech201.pdf",
    "alcohols-phenols-and-ethers": "Class 12/Chemistry 2/lech2dd/lech202.pdf",
    "aldehydes-ketones-and-carboxylic-acids": "Class 12/Chemistry 2/lech2dd/lech203.pdf",
    "amines": "Class 12/Chemistry 2/lech2dd/lech204.pdf",
    "biomolecules-chem": "Class 12/Chemistry 2/lech2dd/lech205.pdf",
    # Biology XI
    "biomolecules": "Class 11/Biology/kebo1dd/kebo109.pdf",
    # Biology XII (project Botany/Zoology ownership)
    "sexual-reproduction-flowering-plants": "Class 12/Biology/lebo1dd/lebo101.pdf",
    "human-reproduction": "Class 12/Biology/lebo1dd/lebo102.pdf",
    "reproductive-health": "Class 12/Biology/lebo1dd/lebo103.pdf",
    "principles-of-inheritance-and-variation": "Class 12/Biology/lebo1dd/lebo104.pdf",
    "molecular-basis-of-inheritance": "Class 12/Biology/lebo1dd/lebo105.pdf",
    "evolution": "Class 12/Biology/lebo1dd/lebo106.pdf",
    "human-health-and-disease": "Class 12/Biology/lebo1dd/lebo107.pdf",
    "microbes-in-human-welfare": "Class 12/Biology/lebo1dd/lebo108.pdf",
    "biotechnology-principles-and-processes": "Class 12/Biology/lebo1dd/lebo109.pdf",
    "biotechnology-and-its-applications": "Class 12/Biology/lebo1dd/lebo110.pdf",
    "organisms-and-populations": "Class 12/Biology/lebo1dd/lebo111.pdf",
    "ecosystem": "Class 12/Biology/lebo1dd/lebo112.pdf",
    "biodiversity-and-conservation": "Class 12/Biology/lebo1dd/lebo113.pdf",
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


def inventory_kus(engine) -> dict:
    with engine.connect() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT ku.id::text AS ku_id, ku.validation_status, ku.extraction_confidence,
                           left(ku.summary, 160) AS summary,
                           c.id::text AS concept_id, c.code AS concept_code, c.name AS concept_name,
                           t.code AS topic_code, ch.code AS chapter_code, ch.name AS chapter_name,
                           ch.class_level, s.code AS subject,
                           sec.heading AS section_heading,
                           left(coalesce(j.source_file_path, ''), 160) AS job_source_path,
                           left(coalesce(d.relative_source_path, ''), 160) AS registry_relative_path
                    FROM knowledge.knowledge_units ku
                    JOIN academic.concepts c ON c.id = ku.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    LEFT JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                    LEFT JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                    LEFT JOIN ingestion.source_documents d ON d.id = j.source_document_id
                    WHERE ku.deleted_at IS NULL
                    ORDER BY s.code, ch.code, c.code, ku.created_at
                    """
                )
            ).mappings()
        ]
        multi = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT c.code AS concept_code, c.name AS concept_name, COUNT(*) AS ku_count
                    FROM knowledge.knowledge_units ku
                    JOIN academic.concepts c ON c.id = ku.concept_id
                    WHERE ku.deleted_at IS NULL AND c.deleted_at IS NULL
                    GROUP BY c.code, c.name
                    HAVING COUNT(*) > 1
                    ORDER BY ku_count DESC, c.code
                    """
                )
            ).mappings()
        ]
        orphan = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                LEFT JOIN academic.concepts c ON c.id = ku.concept_id AND c.deleted_at IS NULL
                WHERE ku.deleted_at IS NULL AND c.id IS NULL
                """
            )
        ).scalar()
        studymaterialish = sum(
            1
            for r in rows
            if "StudyMaterial" in (r.get("job_source_path") or "")
            or "ncert-books-class" in (r.get("registry_relative_path") or "").lower()
            or "Class 11-" in (r.get("registry_relative_path") or "")
            or "Class 12-" in (r.get("registry_relative_path") or "")
        )
        ncert_booksish = sum(1 for r in rows if "NCERT Books" in (r.get("job_source_path") or ""))
    return {
        "count": len(rows),
        "rows": rows,
        "multi_ku_concepts": multi,
        "orphan_kus": orphan,
        "provenance_hint": {
            "likely_studymaterial_registry_or_legacy": studymaterialish,
            "ncert_books_path": ncert_booksish,
            "other_or_null_path": len(rows) - studymaterialish - ncert_booksish,
        },
    }


def coverage_matrix(engine) -> dict:
    with engine.connect() as conn:
        concepts = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT c.id::text AS concept_id, c.code AS concept_code, c.name AS concept_name,
                           left(coalesce(c.summary, ''), 120) AS summary,
                           coalesce(c.ncert_reference, '') AS ncert_reference,
                           t.code AS topic_code, ch.code AS chapter_code, ch.class_level,
                           s.code AS subject,
                           (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                            WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL) AS ku_count,
                           (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                            WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                              AND ku.validation_status = 'PASSED') AS ku_passed
                    FROM academic.concepts c
                    JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                    JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE c.deleted_at IS NULL
                    ORDER BY s.code, ch.code, t.code, c.code
                    """
                )
            ).mappings()
        ]
    covered, gap, review = [], [], []
    for row in concepts:
        if row["chapter_code"] in EXCLUDED_CHAPTERS:
            gap.append({**row, "status": "EXCLUDED_CHAPTER"})
            continue
        if row["ku_count"] == 0:
            gap.append({**row, "status": "GAP"})
        elif row["ku_count"] > 1:
            review.append({**row, "status": "REVIEW"})
        else:
            covered.append({**row, "status": "COVERED"})
    by_chapter: dict[str, dict] = {}
    for row in concepts:
        key = f"{row['subject']}/{row['chapter_code']}"
        slot = by_chapter.setdefault(
            key,
            {"subject": row["subject"], "chapter": row["chapter_code"], "class_level": row["class_level"], "concepts": 0, "covered": 0, "gap": 0, "review": 0},
        )
        slot["concepts"] += 1
        if row["chapter_code"] in EXCLUDED_CHAPTERS or row["ku_count"] == 0:
            slot["gap"] += 1
        elif row["ku_count"] > 1:
            slot["review"] += 1
        else:
            slot["covered"] += 1
    return {
        "concept_total": len(concepts),
        "covered": covered,
        "gap": gap,
        "review": review,
        "counts": {"covered": len(covered), "gap": len(gap), "review": len(review)},
        "by_chapter": sorted(by_chapter.values(), key=lambda x: (-x["gap"], x["subject"], x["chapter"])),
    }


_pdf_cache: dict[str, str] = {}


def load_pdf_text(root: Path, rel: str) -> str:
    if rel in _pdf_cache:
        return _pdf_cache[rel]
    pdf = root / rel
    validate_ncert_generation_source(pdf, root=root)
    doc = fitz.open(pdf)
    parts = []
    for i in range(doc.page_count):
        parts.append(decode_pua(doc.load_page(i).get_text("text") or ""))
    doc.close()
    text_blob = "\n".join(parts)
    _pdf_cache[rel] = text_blob
    return text_blob


def _tokens(name: str) -> list[str]:
    words = re.findall(r"[A-Za-z]{4,}", name.lower())
    stop = {"that", "with", "from", "this", "into", "onto", "have", "been", "were", "their", "about", "which"}
    return [w for w in words if w not in stop]


def extract_window(pdf_text: str, concept_name: str, ncert_reference: str, summary: str) -> tuple[str | None, str]:
    """Return (window_text, evidence_note) or (None, reason)."""
    # Prefer section number from ncert_reference e.g. §7.2 or Ch 7 §7.3
    sec = None
    m = re.search(r"§\s*(\d+\.\d+)", ncert_reference or "")
    if m:
        sec = m.group(1)
    if not sec:
        m = re.search(r"(\d+\.\d+)", ncert_reference or "")
        if m:
            sec = m.group(1)

    if sec:
        # Find section header occurrences
        pat = re.compile(rf"(?m)^{re.escape(sec)}\s+.{{0,80}}$")
        hit = pat.search(pdf_text)
        if not hit:
            pat2 = re.compile(re.escape(sec) + r"\s+[A-Za-z]")
            hit = pat2.search(pdf_text)
        if hit:
            start = max(0, hit.start() - 200)
            end = min(len(pdf_text), hit.start() + 2800)
            return pdf_text[start:end], f"section_window:{sec}"

    # Token overlap search
    tokens = _tokens(concept_name) or _tokens(summary)
    if not tokens:
        return None, "no_search_tokens"
    best_i, best_score = -1, 0
    lower = pdf_text.lower()
    # sample windows every ~500 chars
    step = 500
    win = 2200
    for i in range(0, max(1, len(lower) - win), step):
        chunk = lower[i : i + win]
        score = sum(1 for t in tokens if t in chunk)
        if score > best_score:
            best_score, best_i = score, i
    need = max(1, min(3, len(tokens)))
    if best_score < need or best_i < 0:
        return None, f"insufficient_token_hits:{best_score}/{need}"
    return pdf_text[best_i : best_i + win], f"token_window:score={best_score}"


def special_safety(engine) -> dict:
    with engine.connect() as conn:
        chem = conn.execute(
            text(
                """
                SELECT s.code, ch.class_level,
                  (SELECT COUNT(*) FROM academic.topics t WHERE t.chapter_id=ch.id AND t.deleted_at IS NULL),
                  (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                   JOIN academic.concepts c ON c.id=ku.concept_id
                   JOIN academic.topics t ON t.id=c.topic_id
                   WHERE t.chapter_id=ch.id AND ku.deleted_at IS NULL)
                FROM academic.chapters ch JOIN academic.subjects s ON s.id=ch.subject_id
                WHERE ch.code='biomolecules-chem' AND ch.deleted_at IS NULL
                """
            )
        ).one()
        bio = conn.execute(
            text(
                """
                SELECT s.code, ch.class_level,
                  (SELECT COUNT(*) FROM cms.content_items ci
                   JOIN academic.concepts c ON c.id=ci.concept_id
                   JOIN academic.topics t ON t.id=c.topic_id
                   WHERE t.chapter_id=ch.id AND ci.deleted_at IS NULL AND ci.content_type='QUESTION' AND ci.status='PUBLISHED'),
                  (SELECT COUNT(*) FROM cms.question_blueprints bp
                   JOIN academic.concepts c ON c.id=bp.concept_id
                   JOIN academic.topics t ON t.id=c.topic_id
                   WHERE t.chapter_id=ch.id AND bp.deleted_at IS NULL)
                FROM academic.chapters ch JOIN academic.subjects s ON s.id=ch.subject_id
                WHERE ch.code='biomolecules' AND ch.deleted_at IS NULL
                """
            )
        ).one()
        grav = conn.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM academic.topics t JOIN academic.chapters ch ON ch.id=t.chapter_id
                   JOIN academic.subjects s ON s.id=ch.subject_id
                   WHERE s.code='PHYSICS' AND ch.code='gravitation' AND t.deleted_at IS NULL),
                  (SELECT COUNT(*) FROM academic.concepts c JOIN academic.topics t ON t.id=c.topic_id
                   JOIN academic.chapters ch ON ch.id=t.chapter_id
                   JOIN academic.subjects s ON s.id=ch.subject_id
                   WHERE s.code='PHYSICS' AND ch.code='gravitation' AND c.deleted_at IS NULL)
                """
            )
        ).one()
        dig_ku = conn.execute(
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
    return {
        "biomolecules_chem": {"subject": chem[0], "class_level": chem[1], "topics": chem[2], "kus": chem[3]},
        "biomolecules_botany": {
            "subject": bio[0],
            "class_level": bio[1],
            "published_questions": bio[2],
            "blueprints": bio[3],
        },
        "gravitation": {"topics": grav[0], "concepts": grav[1]},
        "digestion_absorption_kus": dig_ku,
        "ok": (
            chem[0] == "CHEMISTRY"
            and chem[1] == "12"
            and bio[0] == "BOTANY"
            and bio[1] == "11"
            and bio[2] == 5
            and bio[3] == 5
            and grav[0] > 0
            and grav[1] > 0
            and dig_ku == 0
        ),
    }


def backfill(session: Session, root: Path, gaps: list[dict]) -> dict:
    created = []
    skipped = []
    jobs_by_pdf: dict[str, uuid.UUID] = {}

    eligible = [
        g
        for g in gaps
        if g.get("status") == "GAP"
        and g["chapter_code"] not in EXCLUDED_CHAPTERS
        and g["chapter_code"] in CHAPTER_PDF_MAP
    ]

    for g in eligible:
        pdf_rel = CHAPTER_PDF_MAP[g["chapter_code"]]
        try:
            pdf_text = load_pdf_text(root, pdf_rel)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"concept": g["concept_code"], "reason": f"pdf_error:{exc}"})
            continue

        window, note = extract_window(
            pdf_text, g["concept_name"], g.get("ncert_reference") or "", g.get("summary") or ""
        )
        if not window:
            skipped.append({"concept": g["concept_code"], "reason": note, "pdf": pdf_rel})
            continue

        facts = extract_facts_from_section_text(window)
        if not facts:
            skipped.append({"concept": g["concept_code"], "reason": "no_facts", "pdf": pdf_rel})
            continue
        grounded, detail = check_grounding(facts, window)
        if not grounded:
            skipped.append(
                {"concept": g["concept_code"], "reason": f"ungrounded:{detail}", "pdf": pdf_rel, "evidence": note}
            )
            continue

        # Ensure job
        if pdf_rel not in jobs_by_pdf:
            pdf_path = root / pdf_rel
            checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            chapter_id = session.execute(
                text(
                    """
                    SELECT ch.id FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ch.code = :code AND s.code = :subj AND ch.deleted_at IS NULL
                    """
                ),
                {"code": g["chapter_code"], "subj": g["subject"]},
            ).scalar_one()
            subject_id = session.execute(
                text("SELECT id FROM academic.subjects WHERE code = :c AND deleted_at IS NULL"),
                {"c": g["subject"]},
            ).scalar_one()
            job = IngestionJob(
                source_file_path=str(pdf_path),
                original_filename=pdf_path.name,
                file_checksum=checksum,
                source_document_id=None,
                subject_id=subject_id,
                chapter_id=chapter_id,
                status="COMPLETED",
                stage_detail="CF-C5 NCERT Books KU backfill (deterministic; no AI)",
            )
            session.add(job)
            session.flush()
            jobs_by_pdf[pdf_rel] = job.id

        # Dedup: existing PASSED KU for concept
        existing = session.execute(
            text(
                """
                SELECT id::text FROM knowledge.knowledge_units
                WHERE concept_id = :cid AND deleted_at IS NULL AND validation_status = 'PASSED'
                LIMIT 1
                """
            ),
            {"cid": g["concept_id"]},
        ).scalar_one_or_none()
        if existing:
            skipped.append({"concept": g["concept_code"], "reason": "already_has_passed_ku"})
            continue

        summary = build_summary(facts, g["concept_name"])
        # Soft dedup on summary similarity within concept — skip exact hash collision
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
            skipped.append({"concept": g["concept_code"], "reason": "duplicate_content_hash"})
            continue

        section = IngestionSection(
            job_id=jobs_by_pdf[pdf_rel],
            heading=f"CF-C5 / {g['concept_name']}"[:300],
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
                "concept_code": g["concept_code"],
                "concept_name": g["concept_name"],
                "chapter": g["chapter_code"],
                "subject": g["subject"],
                "pdf": pdf_rel,
                "evidence": note,
                "facts": len(facts),
                "summary": summary[:160],
            }
        )

    session.commit()
    return {
        "eligible_gap_concepts": len(eligible),
        "created": created,
        "skipped": skipped,
        "jobs_created": len(jobs_by_pdf),
        "pdfs_used": sorted(jobs_by_pdf.keys()),
    }


def integrity(engine) -> dict:
    with engine.connect() as conn:
        orphan_ku = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                LEFT JOIN academic.concepts c ON c.id = ku.concept_id AND c.deleted_at IS NULL
                WHERE ku.deleted_at IS NULL AND c.id IS NULL
                """
            )
        ).scalar()
        orphan_sec = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                LEFT JOIN ingestion.ingestion_sections s ON s.id = ku.source_section_id AND s.deleted_at IS NULL
                WHERE ku.deleted_at IS NULL AND s.id IS NULL
                """
            )
        ).scalar()
        dig = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                JOIN academic.concepts c ON c.id = ku.concept_id
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                WHERE ch.code = 'digestion-absorption' AND ku.deleted_at IS NULL
                """
            )
        ).scalar()
    return {
        "orphan_kus_missing_concept": orphan_ku,
        "orphan_kus_missing_section": orphan_sec,
        "digestion_kus": dig,
        "ok": orphan_ku == 0 and orphan_sec == 0 and dig == 0,
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
        "app/modules/knowledge/tests/test_grounding_check.py",
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


def write_report(payload: dict) -> tuple[Path, Path]:
    out = ROOT / "docs" / "audits"
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"{REPORT_STEM}.json"
    mp = out / f"{REPORT_STEM}.md"
    # Trim huge inventories in markdown
    jp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    cov = payload["coverage_before"]["counts"]
    cov_a = payload["coverage_after"]["counts"]
    lines = [
        "# CF-C5 — NCERT Knowledge Unit backfill",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Git: **no commit / no push**",
        "- AI / Content Factory / MCQs / blueprints: **none**",
        "",
        "## 1. Existing KU count (before)",
        f"- `{payload['before']['knowledge_units']}`",
        f"- Provenance hint: `{payload['inventory']['provenance_hint']}`",
        f"- Multi-KU concepts (REVIEW): `{len(payload['inventory']['multi_ku_concepts'])}`",
        "",
        "## 2–3. Coverage before",
        f"- Concepts total: `{payload['coverage_before']['concept_total']}`",
        f"- COVERED: `{cov['covered']}`",
        f"- GAP: `{cov['gap']}`",
        f"- REVIEW (duplicate/overlapping KUs): `{cov['review']}`",
        "",
        "## 4. KUs added",
        f"- Created: `{len(payload['backfill']['created'])}`",
        f"- Skipped (insufficient NCERT evidence / ungrounded / etc.): `{len(payload['backfill']['skipped'])}`",
        f"- PDFs used: `{payload['backfill']['pdfs_used']}`",
        "",
        "## 5. Coverage after",
        f"- COVERED: `{cov_a['covered']}`",
        f"- GAP: `{cov_a['gap']}`",
        f"- REVIEW: `{cov_a['review']}`",
        f"- KU count after: `{payload['after']['knowledge_units']}`",
        "",
        "## 6. Remaining gaps (sample by chapter)",
    ]
    for ch in payload["coverage_after"]["by_chapter"][:25]:
        if ch["gap"]:
            lines.append(f"- `{ch['subject']}/{ch['chapter']}` gaps={ch['gap']} / concepts={ch['concepts']}")
    lines += [
        "",
        "## 7. KU-to-NCERT evidence (created)",
    ]
    for row in payload["backfill"]["created"][:40]:
        lines.append(
            f"- `{row['subject']}/{row['chapter']}/{row['concept_code']}` ← `{row['pdf']}` "
            f"evidence={row['evidence']} facts={row['facts']}"
        )
    if len(payload["backfill"]["created"]) > 40:
        lines.append(f"- … +{len(payload['backfill']['created']) - 40} more (see JSON)")
    lines += [
        "",
        "## 8. Duplicate analysis",
        f"- Multi-KU concepts before: `{[r['concept_code'] for r in payload['inventory']['multi_ku_concepts'][:20]]}`",
        "- Existing multi-KU concepts were **not** auto-merged/deleted.",
        "",
        "## 9. Safety counts",
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
        f"- Special safety: `{payload['special_safety']}`",
        "",
        "## 10. Tests / integrity",
        f"- Integrity: `{payload['integrity']}`",
        f"- Tests passed=`{payload['tests']['passed']}` failed=`{payload['tests']['failed']}` exit=`{payload['tests']['exit_code']}`",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## 11. Exact files changed",
    ]
    for f in payload.get("files_changed") or []:
        lines.append(f"- `{f}`")
    lines += [
        "",
        "## 12. Excluded chapters/items",
        f"- `{sorted(EXCLUDED_CHAPTERS)}` — absent from rationalised corpus; no KUs created.",
        "- Chapters without an entry in CHAPTER_PDF_MAP remain GAP (no invention).",
        "- Existing StudyMaterial-provenance KUs left untouched.",
        "",
    ]
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jp, mp


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    root = get_ncert_source_root()

    before = snapshot(engine)
    inventory = inventory_kus(engine)
    # Shrink inventory rows in payload file size — keep summary stats + multi list; full rows truncated
    inventory_out = {
        "count": inventory["count"],
        "multi_ku_concepts": inventory["multi_ku_concepts"],
        "orphan_kus": inventory["orphan_kus"],
        "provenance_hint": inventory["provenance_hint"],
        "sample_rows": inventory["rows"][:15],
    }
    coverage_before = coverage_matrix(engine)

    SessionLocal = Session(engine)
    try:
        backfill_result = backfill(SessionLocal, root, coverage_before["gap"])
    finally:
        SessionLocal.close()

    after = snapshot(engine)
    coverage_after = coverage_matrix(engine)
    special = special_safety(engine)
    integ = integrity(engine)
    tests = run_tests()

    content_safety = before["status"] == after["status"] and before["unmapped_draft"] == after["unmapped_draft"]
    freeze_ok = after["unmapped_draft"] == UNMAPPED_FREEZE and after["status"] == STATUS_FREEZE
    taxonomy_unchanged = (
        before["chapters"] == after["chapters"]
        and before["topics"] == after["topics"]
        and before["concepts"] == after["concepts"]
        and before["question_blueprints"] == after["question_blueprints"]
        and before["content_batches"] == after["content_batches"]
        and before["generation_jobs"] == after["generation_jobs"]
        and before["generation_runs"] == after["generation_runs"]
        and before["generation_candidates"] == after["generation_candidates"]
    )
    only_ku_grew = after["knowledge_units"] >= before["knowledge_units"]

    remaining_gaps = coverage_after["counts"]["gap"]
    if not content_safety or not freeze_ok or not integ["ok"] or not special["ok"] or not taxonomy_unchanged or tests.get("exit_code") != 0:
        status = "RED — FAILED"
    elif remaining_gaps > 0 or coverage_after["counts"]["review"] > 0:
        status = "YELLOW — PARTIALLY VERIFIED"
    else:
        status = "GREEN — COMPLETE/VERIFIED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": status,
        "before": before,
        "after": after,
        "content_safety_unchanged": content_safety,
        "freeze_ok": freeze_ok,
        "taxonomy_unchanged": taxonomy_unchanged,
        "inventory": inventory_out,
        "coverage_before": {
            "concept_total": coverage_before["concept_total"],
            "counts": coverage_before["counts"],
            "by_chapter": coverage_before["by_chapter"],
            "gap_sample": coverage_before["gap"][:30],
            "review_sample": coverage_before["review"][:30],
        },
        "coverage_after": {
            "concept_total": coverage_after["concept_total"],
            "counts": coverage_after["counts"],
            "by_chapter": coverage_after["by_chapter"],
            "gap_sample": coverage_after["gap"][:30],
            "review_sample": coverage_after["review"][:30],
        },
        "backfill": backfill_result,
        "chapter_pdf_map": CHAPTER_PDF_MAP,
        "excluded_chapters": sorted(EXCLUDED_CHAPTERS),
        "special_safety": special,
        "integrity": integ,
        "tests": tests,
        "files_changed": [
            "apps/backend/scripts/curriculum_baseline_005_ku_backfill.py",
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "knowledge.knowledge_units (+ supporting ingestion.ingestion_jobs/sections for NCERT Books paths)",
        ],
        "confirmation": {
            "mcqs_generated": False,
            "ai_called": False,
            "content_factory": False,
            "blueprints_created": False,
            "questions_mutated": False,
            "only_ku_and_min_ingestion_support": only_ku_grew and taxonomy_unchanged,
        },
    }
    jp, mp = write_report(payload)
    print(
        json.dumps(
            {
                "final_status": status,
                "json": str(jp),
                "md": str(mp),
                "ku_before": before["knowledge_units"],
                "ku_after": after["knowledge_units"],
                "created": len(backfill_result["created"]),
                "skipped": len(backfill_result["skipped"]),
                "covered_before": coverage_before["counts"]["covered"],
                "covered_after": coverage_after["counts"]["covered"],
                "gap_after": coverage_after["counts"]["gap"],
                "freeze_ok": freeze_ok,
                "special_ok": special["ok"],
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
            },
            indent=2,
        )
    )
    return 0 if not status.startswith("RED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
