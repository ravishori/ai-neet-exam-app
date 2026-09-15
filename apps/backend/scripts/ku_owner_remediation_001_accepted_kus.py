"""KU-OWNER-REMEDIATION-001 — Create NCERT KUs ONLY for ACCEPT_KU concepts.

Reads owner decisions from docs/audits/ku_owner_review_001_20260913.json.
Creates at most one NCERT-grounded PASSED KU per ACCEPT_KU concept.

Does NOT: taxonomy changes, merges, blueprints, MCQs, StudyMaterial rewrite,
Digestion coverage, TAXONOMY_REVIEW concepts, sv2c-botany-15.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import uuid
from collections import Counter
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
from scripts.curriculum_baseline_005_ku_backfill import (  # noqa: E402
    extract_window,
    load_pdf_text,
)
from scripts.ku_coverage_002_ncert_ku_gaps import CHAPTER_PDF_MAP  # noqa: E402

REPORT_STEM = "ku_owner_remediation_001_20260913"
OWNER_REVIEW_JSON = ROOT / "docs/audits/ku_owner_review_001_20260913.json"

FREEZE_Q = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "DRAFT": 5298,
    "SUPERSEDED": 6,
    "unmapped_draft": 5024,
}
FREEZE_ACADEMIC = {"chapters": 56, "topics": 192, "concepts": 318, "blueprints": 266}
KU_BEFORE = 370

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
BOTANY_PAIR = frozenset({"sv2c-botany-15", "syngamy-and-triple-fusion"})

# Literal NCERT phrases used only when CF-C5/KU-002 token window fails.
# Phrases were verified against canonical NCERT Books PDFs (no web/StudyMaterial).
OWNER_NEEDLES: dict[str, dict] = {
    "factors-affecting-resistance": {
        "min_hits": 2,
        "needles": [
            "resistivity",
            "depends on the material",
            "resistance of a conductor",
            "length and the area",
        ],
    },
    "cardiac-cycle-phases": {
        "min_hits": 2,
        "needles": ["cardiac cycle", "systole", "diastole", "joint diastole"],
    },
    "heart-structure": {
        "min_hits": 2,
        "needles": ["human heart", "pericardium", "four chambers", "atria", "ventricles"],
    },
    "gonads-ducts": {
        "min_hits": 2,
        "needles": [
            "pair of testes",
            "male reproductive system",
            "female reproductive system",
            "fallopian",
            "vas deferens",
            "ovaries",
        ],
    },
    "menstrual-phases": {
        "min_hits": 2,
        "needles": [
            "menstrual cycle",
            "menstrual phase",
            "follicular phase",
            "luteal phase",
        ],
    },
    "biomolecule-classes": {
        "min_hits": 2,
        "needles": [
            "biomolecules",
            "carbohydrates",
            "proteins",
            "lipids",
            "nucleic acids",
        ],
    },
    "pcr-and-downstream-processing": {
        "min_hits": 2,
        "needles": [
            "polymerase chain reaction",
            "PCR",
            "downstream processing",
            "amplification",
        ],
    },
    "pk-plantae-boundaries-and-cyanobacteria": {
        "min_hits": 2,
        "needles": [
            "cyanobacteria",
            "excluded from Plantae",
            "Plantae",
            "Whittaker",
        ],
    },
    "sp-sp2-sp3": {
        "min_hits": 2,
        "needles": ["hybridisation", "sp hybrid", "sp2", "sp3"],
    },
    "primary-and-secondary-valency": {
        "min_hits": 2,
        "needles": [
            "primary valence",
            "secondary valence",
            "Werner",
            "coordination compounds",
        ],
    },
    "concentration-expressions": {
        "min_hits": 2,
        "needles": [
            "molality",
            "molarity",
            "mole fraction",
            "mass percentage",
            "parts per million",
        ],
    },
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


def freeze_base_ok(snap: dict) -> bool:
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
        and snap["studymaterial_path_kus"] == 73
        and snap["digestion_kus"] == 0
    )


def load_accept_codes() -> list[str]:
    payload = json.loads(OWNER_REVIEW_JSON.read_text(encoding="utf-8"))
    codes = []
    for row in payload["unresolved_reviews"]:
        if row.get("recommended_owner_decision") != "ACCEPT_KU":
            continue
        code = row["concept"]["concept_code"]
        if code in TAXONOMY_REVIEW_CODES or code in BOTANY_PAIR:
            raise SystemExit(f"ABORT: ACCEPT_KU list contains forbidden code {code}")
        codes.append(code)
    if len(codes) != 11:
        raise SystemExit(f"ABORT: expected 11 ACCEPT_KU concepts, got {len(codes)}: {codes}")
    return codes


def load_targets(conn, codes: list[str]) -> list[dict]:
    rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT c.id::text AS concept_id, c.code AS concept_code, c.name AS concept_name,
                       coalesce(c.summary, '') AS summary,
                       coalesce(c.ncert_reference, '') AS ncert_reference,
                       c.updated_at::text AS concept_updated_at,
                       s.code AS subject, s.id::text AS subject_id,
                       ch.code AS chapter_code, ch.id::text AS chapter_id, ch.class_level,
                       t.code AS topic_code, t.name AS topic_name,
                       (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                        WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                          AND ku.validation_status = 'PASSED') AS passed_ku_count,
                       (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                        JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                        JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                        WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                          AND ku.validation_status = 'PASSED'
                          AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%') AS ncert_ku_count
                FROM academic.concepts c
                JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE c.deleted_at IS NULL AND c.code = ANY(:codes)
                ORDER BY s.code, ch.code, c.code
                """
            ),
            {"codes": codes},
        ).mappings()
    ]
    found = {r["concept_code"] for r in rows}
    missing = [c for c in codes if c not in found]
    if missing:
        raise SystemExit(f"ABORT: concepts not found: {missing}")
    return rows


def concept_fingerprint(conn, codes: list[str]) -> dict[str, dict]:
    rows = conn.execute(
        text(
            """
            SELECT c.code,
                   c.id::text AS concept_id,
                   c.name,
                   c.updated_at::text AS updated_at,
                   (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                    WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL) AS ku_count
            FROM academic.concepts c
            WHERE c.deleted_at IS NULL AND c.code = ANY(:codes)
            """
        ),
        {"codes": codes},
    ).mappings()
    return {r["code"]: dict(r) for r in rows}


def extract_owner_window(
    pdf_text: str, concept_name: str, ncert_reference: str, summary: str, concept_code: str
) -> tuple[str | None, str]:
    """Prefer CF-C5/KU-002 extract_window; fall back to owner-verified NCERT phrases."""
    window, note = extract_window(pdf_text, concept_name, ncert_reference, summary)
    if window:
        return window, f"cfc5_window:{note}"

    cfg = OWNER_NEEDLES.get(concept_code)
    if not cfg:
        return None, f"no_owner_needles:{note}"

    needles = cfg["needles"]
    min_hits = int(cfg["min_hits"])
    lower = pdf_text.lower()
    win = 2400
    step = 350
    best_i, best_score, best_hits = -1, 0, []
    for i in range(0, max(1, len(lower) - win), step):
        chunk = lower[i : i + win]
        hits = [n for n in needles if n.lower() in chunk]
        score = len(hits)
        # Prefer earlier windows on ties (closer to section openings).
        if score > best_score or (score == best_score and score > 0 and (best_i < 0 or i < best_i)):
            best_score, best_i, best_hits = score, i, hits

    if best_score < min_hits or best_i < 0:
        return None, f"owner_needles_insufficient:{best_score}/{min_hits}|prior={note}"

    return (
        pdf_text[best_i : best_i + win],
        f"owner_needle_window:score={best_score}|hits={best_hits}|prior={note}",
    )


def find_window_across_pdfs(
    root: Path,
    pdf_rels: list[str],
    concept_name: str,
    ncert_reference: str,
    summary: str,
    concept_code: str,
) -> tuple[str | None, str, str | None]:
    best: tuple[str, str, str] | None = None
    best_score = -1
    last_reason = "no_pdf"
    for rel in pdf_rels:
        try:
            pdf_text = load_pdf_text(root, rel)
        except Exception as exc:  # noqa: BLE001
            last_reason = f"pdf_error:{exc}"
            continue
        window, note = extract_owner_window(
            pdf_text, concept_name, ncert_reference, summary, concept_code
        )
        if not window:
            last_reason = note
            continue
        score = 100 if "section_window" in note else 10
        m = re.search(r"score=(\d+)", note)
        if m:
            score = int(m.group(1))
        if score > best_score:
            best_score = score
            best = (window, f"{note}|pdf={rel}", rel)
    if best:
        return best[0], best[1], best[2]
    return None, last_reason, None


def existing_ncert_ku(session: Session, concept_id: str) -> str | None:
    return session.execute(
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
        {"cid": concept_id},
    ).scalar_one_or_none()


def remediate(session: Session, root: Path, targets: list[dict]) -> dict:
    created: list[dict] = []
    skipped: list[dict] = []
    failed: list[dict] = []
    jobs_by_pdf: dict[str, uuid.UUID] = {}

    for g in targets:
        code = g["concept_code"]
        if code in TAXONOMY_REVIEW_CODES or code in BOTANY_PAIR:
            failed.append({"concept_code": code, "status": "BLOCKED_FORBIDDEN", "reason": "not ACCEPT_KU scope"})
            continue

        existing = existing_ncert_ku(session, g["concept_id"])
        if existing:
            skipped.append(
                {
                    "concept_code": code,
                    "concept_name": g["concept_name"],
                    "subject": g["subject"],
                    "status": "SKIPPED_EXISTING",
                    "existing_ku_id": existing,
                }
            )
            continue

        pdf_rels = CHAPTER_PDF_MAP.get(g["chapter_code"])
        if not pdf_rels:
            failed.append(
                {
                    "concept_code": code,
                    "status": "FAILED",
                    "reason": "chapter_not_in_pdf_map",
                    "chapter": g["chapter_code"],
                }
            )
            continue
        missing = [p for p in pdf_rels if not (root / p).exists()]
        if missing:
            failed.append(
                {
                    "concept_code": code,
                    "status": "FAILED",
                    "reason": f"mapped_pdf_missing:{missing}",
                }
            )
            continue

        window, note, pdf_rel = find_window_across_pdfs(
            root,
            pdf_rels,
            g["concept_name"],
            g.get("ncert_reference") or "",
            g.get("summary") or "",
            code,
        )
        if not window or not pdf_rel:
            failed.append(
                {
                    "concept_code": code,
                    "status": "FAILED",
                    "reason": note or "insufficient_evidence",
                    "pdfs_tried": pdf_rels,
                }
            )
            continue

        facts = extract_facts_from_section_text(window)
        if not facts:
            failed.append(
                {"concept_code": code, "status": "FAILED", "reason": "no_facts", "pdf": pdf_rel, "evidence": note}
            )
            continue
        grounded, detail = check_grounding(facts, window)
        if not grounded:
            failed.append(
                {
                    "concept_code": code,
                    "status": "FAILED",
                    "reason": f"ungrounded:{detail}",
                    "pdf": pdf_rel,
                    "evidence": note,
                }
            )
            continue

        # Re-check race / idempotency
        existing = existing_ncert_ku(session, g["concept_id"])
        if existing:
            skipped.append(
                {
                    "concept_code": code,
                    "concept_name": g["concept_name"],
                    "subject": g["subject"],
                    "status": "SKIPPED_EXISTING",
                    "existing_ku_id": existing,
                }
            )
            continue

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
            skipped.append(
                {
                    "concept_code": code,
                    "concept_name": g["concept_name"],
                    "subject": g["subject"],
                    "status": "SKIPPED_EXISTING",
                    "existing_ku_id": dup_hash,
                    "reason": "duplicate_content_hash",
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
                stage_detail="KU-OWNER-REMEDIATION-001 NCERT Books KU (owner ACCEPT_KU only)",
            )
            session.add(job)
            session.flush()
            jobs_by_pdf[pdf_rel] = job.id

        summary = build_summary(facts, g["concept_name"])
        section = IngestionSection(
            job_id=jobs_by_pdf[pdf_rel],
            heading=f"KU-OWNER-REMEDIATION-001 / {g['concept_name']}"[:300],
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
                "status": "CREATED",
                "ku_id": str(unit.id),
                "concept_id": g["concept_id"],
                "concept_code": code,
                "concept_name": g["concept_name"],
                "subject": g["subject"],
                "class_level": g["class_level"],
                "chapter": g["chapter_code"],
                "topic": g["topic_code"],
                "pdf": pdf_rel,
                "evidence": note,
                "facts": len(facts),
                "summary": summary[:240],
                "window_preview": " ".join(window.split())[:280],
            }
        )

    session.commit()
    return {
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "jobs_created": len(jobs_by_pdf),
        "pdfs_used": sorted(jobs_by_pdf.keys()),
        "subject_additions": dict(Counter(r["subject"] for r in created)),
    }


def run_tests() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "app/modules/ingestion/tests/test_ncert_canonical_source.py",
        "app/modules/knowledge/tests/test_grounding_check.py",
        "app/modules/academic/tests/test_cf_c1_chemistry_class_12.py",
        "app/modules/academic/tests/test_chapter_class_level.py",
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

    lines = [
        "# KU-OWNER-REMEDIATION-001 — Owner-accepted NCERT KU creation",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Mode: **MUTATING (ACCEPT_KU KUs only)**",
        "- Git: **no commit / no push**",
        "",
        "## Summary",
        f"- ACCEPT_KU concepts processed: `{payload['accept_ku_count']}`",
        f"- Created: `{len(payload['created'])}`",
        f"- Skipped existing: `{len(payload['skipped'])}`",
        f"- Failed: `{len(payload['failed'])}`",
        f"- KU count: `{payload['before']['knowledge_units']}` → `{payload['after']['knowledge_units']}`",
        f"- Subject-wise additions: `{payload['subject_additions']}`",
        f"- Concepts with NCERT KU: `{payload['before'].get('concepts_with_ncert_ku')}` → `{payload['after'].get('concepts_with_ncert_ku')}`",
        "",
        "## 1. Exact 11 concepts processed",
        "",
        "| Code | Name | Subject | Class | Chapter | Topic | Status | PDF |",
        "|---|---|---|---|---|---|---|---|",
    ]
    by_code = {r["concept_code"]: r for r in payload["created"] + payload["skipped"] + payload["failed"]}
    for code in payload["accept_codes"]:
        row = by_code.get(code, {})
        meta = payload["targets_meta"].get(code, {})
        lines.append(
            f"| `{code}` | {meta.get('concept_name','')} | {meta.get('subject','')} | "
            f"{meta.get('class_level','')} | `{meta.get('chapter_code','')}` | `{meta.get('topic_code','')}` | "
            f"**{row.get('status','MISSING')}** | `{row.get('pdf') or row.get('existing_ku_id') or ''}` |"
        )

    lines += ["", "## 2. Created KUs (detail)", ""]
    for r in payload["created"]:
        lines += [
            f"### `{r['concept_code']}` — {r['concept_name']}",
            f"- KU ID: `{r['ku_id']}`",
            f"- Subject/class/chapter/topic: `{r['subject']}` / `{r['class_level']}` / `{r['chapter']}` / `{r['topic']}`",
            f"- Canonical PDF: `{r['pdf']}`",
            f"- Evidence: `{r['evidence']}`",
            f"- Facts: `{r['facts']}`",
            f"- Summary: {r['summary']}",
            f"- Window preview: {r['window_preview']}",
            "",
        ]

    if payload["skipped"]:
        lines += ["## 3. Skipped existing", ""]
        for r in payload["skipped"]:
            lines.append(f"- `{r['concept_code']}` → `{r['status']}` (`{r.get('existing_ku_id')}`)")
        lines.append("")

    if payload["failed"]:
        lines += ["## 4. Failures", ""]
        for r in payload["failed"]:
            lines.append(f"- `{r['concept_code']}` → `{r.get('reason')}`")
        lines.append("")

    lines += [
        "## 5. Untouched confirmations",
        f"- TAXONOMY_REVIEW concepts unchanged: `{payload['taxonomy_review_unchanged']}`",
        f"- `sv2c-botany-15` unchanged: `{payload['sv2c_botany_15_unchanged']}`",
        f"- `syngamy-and-triple-fusion` unchanged: `{payload['syngamy_unchanged']}`",
        f"- Blueprints created: `{payload['confirmation']['blueprints_created']}`",
        f"- MCQs generated: `{payload['confirmation']['mcqs_generated']}`",
        "",
        "### TAXONOMY_REVIEW fingerprints (before/after)",
        f"```json\n{json.dumps(payload['taxonomy_fingerprints'], indent=2)}\n```",
        "",
        "### Botany pair fingerprints (before/after)",
        f"```json\n{json.dumps(payload['botany_fingerprints'], indent=2)}\n```",
        "",
        "## 6. Safety / freeze",
        f"- Base freeze OK (before): `{payload['freeze_ok_before']}`",
        f"- Base freeze OK (after): `{payload['freeze_ok_after']}`",
        f"- KU delta matches created: `{payload['ku_delta_matches_created']}`",
        f"- Factory orchestration unchanged: `{payload['factory_orchestration_unchanged']}`",
        f"- StudyMaterial KUs: `{payload['before']['studymaterial_path_kus']}` → `{payload['after']['studymaterial_path_kus']}`",
        f"- Digestion KUs: `{payload['before']['digestion_kus']}` → `{payload['after']['digestion_kus']}`",
        "",
        "### Before",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "### After",
        f"```json\n{json.dumps(payload['after'], indent=2)}\n```",
        "",
        "## 7. Tests",
        f"- Passed `{payload['tests'].get('passed')}` / Failed `{payload['tests'].get('failed')}`",
        "",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## 8. Files changed",
    ]
    for f in payload["files_changed"]:
        lines.append(f"- `{f}`")
    lines += [
        "",
        "## Confirmation",
        f"```json\n{json.dumps(payload['confirmation'], indent=2)}\n```",
        "",
        "**STOP** — no BP-CREATE, no MCQs, no commit, no push.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    if not OWNER_REVIEW_JSON.exists():
        raise SystemExit(f"ABORT: missing owner review {OWNER_REVIEW_JSON}")

    accept_codes = load_accept_codes()
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        root = ROOT / "NCERT Books"

    with engine.connect() as conn:
        before = snapshot(conn)
        if before["knowledge_units"] != KU_BEFORE:
            raise SystemExit(f"ABORT: expected KU count {KU_BEFORE}, got {before['knowledge_units']}")
        if not freeze_base_ok(before):
            raise SystemExit(f"ABORT freeze before: {before}")
        targets = load_targets(conn, accept_codes)
        tax_before = concept_fingerprint(conn, list(TAXONOMY_REVIEW_CODES))
        bot_before = concept_fingerprint(conn, list(BOTANY_PAIR))

    session = SessionLocal()
    try:
        result = remediate(session, root, targets)
    finally:
        session.close()

    with engine.connect() as conn:
        after = snapshot(conn)
        tax_after = concept_fingerprint(conn, list(TAXONOMY_REVIEW_CODES))
        bot_after = concept_fingerprint(conn, list(BOTANY_PAIR))

    created_n = len(result["created"])
    expected_kus = KU_BEFORE + created_n
    ku_delta_ok = after["knowledge_units"] == expected_kus
    freeze_after = freeze_base_ok(after)
    factory_ok = (
        before["generation_jobs"] == after["generation_jobs"]
        and before["generation_runs"] == after["generation_runs"]
        and before["generation_candidates"] == after["generation_candidates"]
        and before["content_batches"] == after["content_batches"]
        and before["question_blueprints"] == after["question_blueprints"]
    )
    taxonomy_ok = tax_before == tax_after
    sv2c_ok = bot_before.get("sv2c-botany-15") == bot_after.get("sv2c-botany-15")
    syngamy_ok = bot_before.get("syngamy-and-triple-fusion") == bot_after.get("syngamy-and-triple-fusion")

    tests = run_tests()

    if result["failed"] or not ku_delta_ok or not freeze_after or not factory_ok or not taxonomy_ok:
        final = "RED — REMEDIATION INCOMPLETE"
    elif tests["failed"] or tests["exit_code"] != 0:
        final = "YELLOW — KUs CREATED; TESTS WARN"
    else:
        final = "GREEN — OWNER-ACCEPTED KUs CREATED"

    targets_meta = {
        t["concept_code"]: {
            "concept_name": t["concept_name"],
            "subject": t["subject"],
            "class_level": t["class_level"],
            "chapter_code": t["chapter_code"],
            "topic_code": t["topic_code"],
        }
        for t in targets
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "mutating_accept_ku_only",
        "final_status": final,
        "ncert_root": str(root),
        "source_owner_review": str(OWNER_REVIEW_JSON),
        "accept_codes": accept_codes,
        "accept_ku_count": len(accept_codes),
        "targets_meta": targets_meta,
        "created": result["created"],
        "skipped": result["skipped"],
        "failed": result["failed"],
        "subject_additions": result["subject_additions"],
        "jobs_created": result["jobs_created"],
        "pdfs_used": result["pdfs_used"],
        "before": before,
        "after": after,
        "freeze_ok_before": freeze_base_ok(before),
        "freeze_ok_after": freeze_after,
        "ku_delta_matches_created": ku_delta_ok,
        "factory_orchestration_unchanged": factory_ok,
        "taxonomy_review_unchanged": taxonomy_ok,
        "sv2c_botany_15_unchanged": sv2c_ok,
        "syngamy_unchanged": syngamy_ok,
        "taxonomy_fingerprints": {"before": tax_before, "after": tax_after},
        "botany_fingerprints": {"before": bot_before, "after": bot_after},
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/ku_owner_remediation_001_accepted_kus.py",
        ],
        "confirmation": {
            "only_accept_ku_processed": True,
            "taxonomy_review_untouched": taxonomy_ok,
            "sv2c_botany_15_untouched": sv2c_ok,
            "syngamy_and_triple_fusion_untouched": syngamy_ok,
            "blueprints_created": False,
            "mcqs_generated": False,
            "concepts_modified": False,
            "topics_modified": False,
            "chapters_modified": False,
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
                "created": created_n,
                "skipped": len(result["skipped"]),
                "failed": len(result["failed"]),
                "kus": after["knowledge_units"],
                "blueprints": after["question_blueprints"],
                "tests_passed": tests["passed"],
                "tests_failed": tests["failed"],
            },
            indent=2,
        )
    )
    return 0 if final.startswith("GREEN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
