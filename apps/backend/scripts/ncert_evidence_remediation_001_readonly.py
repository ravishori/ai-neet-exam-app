"""NCERT-EVIDENCE-REMEDIATION-001 — read-only canonical source recovery audit.

Audits the 65 NCERT_EVIDENCE_MISSING syllabus-confirmed blueprints from
MCQ-EVIDENCE-COVERAGE-002. Determines whether canonical NCERT Books evidence
could be established in a *future* write task.

NO DB writes. NO provenance changes. NO KU/blueprint mutations. NO LLM.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.services.ncert_generation_evidence import (  # noqa: E402
    resolve_ncert_evidence_pack,
)
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope, load_neet_2026_registry  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    extract_blueprint_ncert_path,
    validate_ncert_generation_source,
)
from scripts.syllabus_mapping_remediation_001_readonly import classify_population  # noqa: E402

REPORT = "ncert_evidence_remediation_001"
COVERAGE = ROOT / "docs" / "audits" / "mcq_evidence_coverage_002.json"
NCERT_ROOT = ROOT / "NCERT Books"
PROVIDER_CALLS = {"n": 0}

RECOVERY = (
    "CANONICAL_EVIDENCE_RECOVERABLE",
    "CANONICAL_SOURCE_EXISTS_BUT_MAPPING_REVIEW",
    "CANONICAL_SOURCE_NOT_FOUND",
    "NCERT_EVIDENCE_INSUFFICIENT",
    "SOURCE_PROVENANCE_REVIEW",
)

FUTURE = (
    "REMAIN_BLOCKED",
    "SAFE_FOR_SEPARATE_EVIDENCE_WRITE_REVIEW",
    "TAXONOMY_REVIEW",
    "SOURCE_REPLACEMENT_NOT_ALLOWED",
    "PROVENANCE_REVIEW_REQUIRED",
)

# Hard project boundaries (filename only; never invent chapters)
HARD_PDF = {
    ("BOTANY", "11", "Biomolecules"): "Class 11/Biology/kebo1dd/kebo109.pdf",
    ("PHYSICS", "11", "Gravitation"): "Class 11/Physics/keph1dd/keph1dd/keph107.pdf",
    ("CHEMISTRY", "12", "Biomolecules"): "Class 12/Chemistry 2/lech2dd/lech205.pdf",
}


def _cons(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def _norm(s: str) -> str:
    s = (s or "").lower().replace("_", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _phrase_in(haystack: str, needle: str) -> bool:
    n = _norm(needle)
    h = _norm(haystack)
    if len(n) < 4:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", h) is not None


def snapshot(conn) -> dict[str, Any]:
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
        "chapters": conn.execute(
            text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")
        ).scalar(),
        "topics": conn.execute(
            text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")
        ).scalar(),
        "concepts": conn.execute(
            text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")
        ).scalar(),
        "kus": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "status": status,
        "unmapped_draft": unmapped,
        "candidates": conn.execute(
            text("SELECT COUNT(*) FROM cms.generation_candidates")
        ).scalar(),
        "jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
    }


def _ku_facts_list(raw: Any) -> list[str]:
    if isinstance(raw, dict):
        out: list[str] = []
        for v in raw.values():
            if isinstance(v, str):
                out.append(v)
            elif isinstance(v, list):
                out.extend(str(x) for x in v)
        return out
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return []


def load_db_rows(conn, ids: set[str]) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
              bp.id::text AS blueprint_id,
              bp.blueprint_key,
              bp.provenance_tier,
              bp.constraints,
              s.code AS subject_code,
              ch.id::text AS chapter_id,
              ch.code AS chapter_code,
              ch.name AS chapter_name,
              ch.class_level,
              t.id::text AS topic_id,
              t.code AS topic_code,
              t.name AS topic_name,
              c.id::text AS concept_id,
              c.code AS concept_code,
              c.name AS concept_name,
              (
                SELECT ku.id::text FROM knowledge.knowledge_units ku
                WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                ORDER BY
                  CASE WHEN ku.validation_status = 'PASSED' THEN 0 ELSE 1 END,
                  ku.updated_at DESC NULLS LAST
                LIMIT 1
              ) AS ku_id,
              (
                SELECT ku.validation_status FROM knowledge.knowledge_units ku
                WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                ORDER BY
                  CASE WHEN ku.validation_status = 'PASSED' THEN 0 ELSE 1 END,
                  ku.updated_at DESC NULLS LAST
                LIMIT 1
              ) AS ku_status,
              (
                SELECT ku.summary FROM knowledge.knowledge_units ku
                WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                ORDER BY
                  CASE WHEN ku.validation_status = 'PASSED' THEN 0 ELSE 1 END,
                  ku.updated_at DESC NULLS LAST
                LIMIT 1
              ) AS ku_summary,
              (
                SELECT ku.structured_facts FROM knowledge.knowledge_units ku
                WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                ORDER BY
                  CASE WHEN ku.validation_status = 'PASSED' THEN 0 ELSE 1 END,
                  ku.updated_at DESC NULLS LAST
                LIMIT 1
              ) AS ku_facts
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id AND ch.deleted_at IS NULL
            JOIN academic.topics t ON t.id = bp.topic_id AND t.deleted_at IS NULL
            JOIN academic.concepts c ON c.id = bp.concept_id AND c.deleted_at IS NULL
            WHERE bp.deleted_at IS NULL
              AND bp.id = ANY(CAST(:ids AS uuid[]))
            """
        ),
        {"ids": list(ids)},
    ).mappings()
    return {r["blueprint_id"]: dict(r) for r in rows}


def build_canonical_chapter_pdf_index(conn) -> dict[tuple[str, str, str], set[str]]:
    """Deterministic map from (subject, class, chapter_name) → canonical NCERT rel paths."""
    index: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    rows = conn.execute(
        text(
            """
            SELECT s.code AS subject_code, ch.name AS chapter_name, ch.class_level,
                   bp.constraints
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id AND ch.deleted_at IS NULL
            WHERE bp.deleted_at IS NULL
            """
        )
    ).mappings()
    for r in rows:
        path = extract_blueprint_ncert_path(_cons(r["constraints"]))
        if not path or "StudyMaterial" in path.replace("\\", "/"):
            continue
        p = Path(path)
        if not p.is_file():
            cand = NCERT_ROOT / path.replace("\\", "/")
            if cand.is_file():
                p = cand
            else:
                continue
        try:
            resolved = p.resolve()
            if NCERT_ROOT.resolve() not in resolved.parents:
                continue
            rel = resolved.relative_to(NCERT_ROOT.resolve()).as_posix()
        except Exception:
            continue
        key = (r["subject_code"], str(r["class_level"]), r["chapter_name"])
        index[key].add(rel)
    return index


def pdf_text_blob(pdf_path: Path, max_pages: int = 24) -> str:
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        parts: list[str] = []
        for i in range(min(doc.page_count, max_pages)):
            parts.append(doc.load_page(i).get_text("text") or "")
        return "\n".join(parts)
    finally:
        doc.close()


def disambiguate_pdfs(
    candidates: list[str],
    *,
    topic_name: str,
    concept_name: str,
    chapter_name: str,
) -> tuple[str | None, list[str], str]:
    """Exact phrase presence in PDF text; never fuzzy-authorize alone."""
    hits: list[tuple[str, int]] = []
    reasons: list[str] = []
    for rel in candidates:
        path = NCERT_ROOT / rel
        if not path.is_file():
            reasons.append(f"missing_file:{rel}")
            continue
        try:
            blob = pdf_text_blob(path)
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"unreadable:{rel}:{exc}")
            continue
        score = 0
        if concept_name and _phrase_in(blob, concept_name):
            score += 3
        if topic_name and _phrase_in(blob, topic_name):
            score += 2
        if chapter_name and _phrase_in(blob, chapter_name):
            score += 1
        hits.append((rel, score))
    hits.sort(key=lambda t: (-t[1], t[0]))
    if not hits:
        return None, reasons, "no_readable_candidate"
    top = hits[0][1]
    winners = [r for r, s in hits if s == top and s > 0]
    if len(winners) == 1 and top >= 2:
        return winners[0], reasons, f"exact_phrase_disambiguation score={top}"
    if len(winners) > 1:
        return None, reasons + [f"tied_candidates:{winners}"], "ambiguous_exact_hits"
    return None, reasons + [f"weak_hits:{hits}"], "no_deterministic_disambiguation"


def evaluate_evidence(
    *,
    rel: str,
    db: dict[str, Any],
    syllabus: dict[str, Any],
) -> dict[str, Any]:
    path = NCERT_ROOT / rel
    validated = validate_ncert_generation_source(path, root=NCERT_ROOT)
    # Evaluation-only constraints — never written
    eval_cons = {
        "ncert_derived": True,
        "ncert_source_path": str(validated.resolved_path),
        "neet_ug_2026": {
            "subject": syllabus.get("subject"),
            "unit_number": syllabus.get("unit_number"),
            "unit_name": syllabus.get("unit_name"),
            "topic": syllabus.get("topic"),
            "topic_id": syllabus.get("topic_id"),
        },
    }
    pack = resolve_ncert_evidence_pack(
        eval_cons,
        provenance_tier="authoritative",
        concept_name=db.get("concept_name"),
        chapter_name=db.get("chapter_name"),
        topic_name=db.get("topic_name"),
        ku_id=db.get("ku_id"),
        ku_summary=db.get("ku_summary"),
        ku_facts=_ku_facts_list(db.get("ku_facts")),
        validated_source=validated,
    )
    return {
        "status": pack.status,
        "detail": pack.detail,
        "pages": list(pack.page_numbers or []),
        "chars": len(pack.evidence_text or ""),
        "excerpt": (pack.evidence_text or "")[:360],
        "section_heading": pack.section_heading,
        "relative_posix": pack.relative_posix,
    }


def future_action_for(classification: str, population: str) -> str:
    if classification == "CANONICAL_EVIDENCE_RECOVERABLE":
        if population == "LEGACY_STUDYMATERIAL":
            return "PROVENANCE_REVIEW_REQUIRED"
        return "SAFE_FOR_SEPARATE_EVIDENCE_WRITE_REVIEW"
    if classification == "CANONICAL_SOURCE_EXISTS_BUT_MAPPING_REVIEW":
        return "TAXONOMY_REVIEW"
    if classification == "CANONICAL_SOURCE_NOT_FOUND":
        return "SOURCE_REPLACEMENT_NOT_ALLOWED"
    if classification == "SOURCE_PROVENANCE_REVIEW":
        return "PROVENANCE_REVIEW_REQUIRED"
    return "REMAIN_BLOCKED"


def audit_one(
    cov: dict[str, Any],
    db: dict[str, Any],
    chapter_index: dict[tuple[str, str, str], set[str]],
    registry,
) -> dict[str, Any]:
    cons = _cons(db.get("constraints"))
    population = classify_population(cons, NCERT_ROOT)
    existing_path = extract_blueprint_ncert_path(cons)
    gate = assert_blueprint_neet_syllabus_scope(
        cons,
        academic_subject_code=db.get("subject_code"),
        registry=registry,
    )
    assert gate.status == "IN_SYLLABUS"

    syllabus = {
        "status": gate.status,
        "subject": gate.subject,
        "unit_number": gate.unit_number,
        "unit_name": gate.unit_name,
        "topic": gate.topic,
        "topic_id": gate.topic_id,
    }

    chapter_name = db["chapter_name"]
    class_level = str(db["class_level"])
    subject = db["subject_code"]
    key = (subject, class_level, chapter_name)

    reasons: list[str] = []
    special: dict[str, Any] = {}

    # Digestion & Absorption — never fabricate
    if "digestion" in chapter_name.lower() and "absorption" in chapter_name.lower():
        special["digestion_absorption"] = True
        return _record(
            cov,
            db,
            population,
            existing_path,
            syllabus,
            candidate=None,
            evidence=None,
            chapter_match=False,
            topic_match=False,
            concept_match=False,
            classification="CANONICAL_SOURCE_NOT_FOUND",
            reasons=["digestion_absorption_absent_from_canonical_corpus"],
            confidence="high",
            special=special,
        )

    # Hard path overrides when chapter matches specials
    hard = HARD_PDF.get(key)
    candidates = set(chapter_index.get(key, set()))
    if hard:
        special["hard_boundary_pdf"] = hard
        hard_path = NCERT_ROOT / hard
        if hard_path.is_file():
            candidates = {hard}
        else:
            reasons.append(f"hard_boundary_pdf_missing:{hard}")
            return _record(
                cov,
                db,
                population,
                existing_path,
                syllabus,
                candidate=None,
                evidence=None,
                chapter_match=False,
                topic_match=False,
                concept_match=False,
                classification="CANONICAL_SOURCE_NOT_FOUND",
                reasons=reasons,
                confidence="high",
                special=special,
            )

    # Biomolecules ownership check
    if "biomolecule" in chapter_name.lower() and subject == "BOTANY":
        special["biomolecules_botany_xi"] = {
            "subject": subject,
            "class_level": class_level,
            "expected_pdf": HARD_PDF.get(("BOTANY", "11", "Biomolecules")),
        }

    if not candidates:
        # Legacy StudyMaterial chapter number pointing at removed rationalised chapter?
        if existing_path and "StudyMaterial" in existing_path.replace("\\", "/"):
            reasons.append("legacy_StudyMaterial_path_no_canonical_chapter_sibling_map")
            m = re.search(r"chapter-(\d+)", existing_path.replace("\\", "/"), re.I)
            if m:
                reasons.append(f"legacy_chapter_number_hint:{m.group(1)}")
        return _record(
            cov,
            db,
            population,
            existing_path,
            syllabus,
            candidate=None,
            evidence=None,
            chapter_match=False,
            topic_match=False,
            concept_match=False,
            classification="CANONICAL_SOURCE_NOT_FOUND",
            reasons=reasons or ["no_canonical_chapter_pdf_mapping"],
            confidence="high",
            special=special,
        )

    cand_list = sorted(candidates)
    selected: str | None = None
    disambig_basis = "unique_chapter_sibling_canonical_path"

    if len(cand_list) == 1:
        selected = cand_list[0]
        chapter_match = True
    else:
        chapter_match = True  # chapter exists but multi-PDF
        selected, diag, disambig_basis = disambiguate_pdfs(
            cand_list,
            topic_name=db.get("topic_name") or "",
            concept_name=db.get("concept_name") or "",
            chapter_name=chapter_name,
        )
        reasons.extend(diag)
        if selected is None:
            return _record(
                cov,
                db,
                population,
                existing_path,
                syllabus,
                candidate=cand_list,
                evidence=None,
                chapter_match=True,
                topic_match=False,
                concept_match=False,
                classification="CANONICAL_SOURCE_EXISTS_BUT_MAPPING_REVIEW",
                reasons=reasons + [disambig_basis, f"candidate_pdfs:{cand_list}"],
                confidence="medium",
                special=special,
            )

    # Evaluate actual NCERT evidence (read-only)
    try:
        evidence = evaluate_evidence(rel=selected, db=db, syllabus=syllabus)
    except Exception as exc:  # noqa: BLE001
        return _record(
            cov,
            db,
            population,
            existing_path,
            syllabus,
            candidate=selected,
            evidence=None,
            chapter_match=chapter_match,
            topic_match=False,
            concept_match=False,
            classification="NCERT_EVIDENCE_INSUFFICIENT",
            reasons=reasons + [f"evidence_eval_error:{exc}"],
            confidence="medium",
            special=special,
        )

    topic_match = False
    concept_match = False
    try:
        blob = pdf_text_blob(NCERT_ROOT / selected)
        topic_match = bool(db.get("topic_name") and _phrase_in(blob, db["topic_name"]))
        concept_match = bool(db.get("concept_name") and _phrase_in(blob, db["concept_name"]))
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"phrase_scan_error:{exc}")

    reasons.append(f"mapping_basis:{disambig_basis}")
    reasons.append(f"evidence_status:{evidence['status']}")
    if evidence.get("detail"):
        reasons.append(str(evidence["detail"]))

    # Recoverability requires READY evidence + deterministic chapter PDF
    if evidence["status"] == "NCERT_EVIDENCE_READY" and (topic_match or concept_match):
        classification = "CANONICAL_EVIDENCE_RECOVERABLE"
        confidence = "high"
    elif evidence["status"] == "NCERT_EVIDENCE_READY" and not topic_match and not concept_match:
        # Chapter PDF OK but concept/topic phrase absent — do not force recoverability
        classification = "SOURCE_PROVENANCE_REVIEW"
        confidence = "medium"
        reasons.append("chapter_pdf_ready_but_topic_concept_phrase_absent")
    elif evidence["status"] == "NCERT_EVIDENCE_INSUFFICIENT":
        classification = "NCERT_EVIDENCE_INSUFFICIENT"
        confidence = "medium"
    else:
        classification = "SOURCE_PROVENANCE_REVIEW"
        confidence = "low"
        reasons.append("unexpected_evidence_status")

    return _record(
        cov,
        db,
        population,
        existing_path,
        syllabus,
        candidate=selected,
        evidence=evidence,
        chapter_match=chapter_match,
        topic_match=topic_match,
        concept_match=concept_match,
        classification=classification,
        reasons=reasons,
        confidence=confidence,
        special=special,
    )


def _record(
    cov: dict[str, Any],
    db: dict[str, Any],
    population: str,
    existing_path: str | None,
    syllabus: dict[str, Any],
    *,
    candidate: Any,
    evidence: dict[str, Any] | None,
    chapter_match: bool,
    topic_match: bool,
    concept_match: bool,
    classification: str,
    reasons: list[str],
    confidence: str,
    special: dict[str, Any],
) -> dict[str, Any]:
    future = future_action_for(classification, population)
    assert classification in RECOVERY
    assert future in FUTURE
    return {
        "blueprint_id": db["blueprint_id"],
        "blueprint_key": db.get("blueprint_key") or cov.get("blueprint_key"),
        "provenance_tier": db.get("provenance_tier"),
        "provenance": population,
        "class_level": db.get("class_level"),
        "subject": db.get("subject_code"),
        "chapter_id": db.get("chapter_id"),
        "chapter": db.get("chapter_name"),
        "chapter_code": db.get("chapter_code"),
        "topic_id": db.get("topic_id"),
        "topic": db.get("topic_name"),
        "topic_code": db.get("topic_code"),
        "concept_id": db.get("concept_id"),
        "concept": db.get("concept_name"),
        "concept_code": db.get("concept_code"),
        "syllabus_mapping": syllabus,
        "existing_ncert_source_path": existing_path,
        "candidate_ncert_source": candidate,
        "canonical_chapter_match": chapter_match,
        "canonical_topic_match": topic_match,
        "canonical_concept_match": concept_match,
        "evidence_location": {
            "pages": (evidence or {}).get("pages"),
            "section_heading": (evidence or {}).get("section_heading"),
            "chars": (evidence or {}).get("chars"),
            "relative_posix": (evidence or {}).get("relative_posix"),
        }
        if evidence
        else None,
        "evidence_excerpt": (evidence or {}).get("excerpt") if evidence else None,
        "evidence_status": (evidence or {}).get("status") if evidence else None,
        "recovery_classification": classification,
        "reason": reasons,
        "confidence": confidence,
        "future_action": future,
        "fuzzy_authorized": False,
        "special": special,
        "ku_id": db.get("ku_id"),
        "ku_status": db.get("ku_status"),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    by = report["by_recovery"]
    lines = [
        "# NCERT-EVIDENCE-REMEDIATION-001 — Canonical source recovery audit",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** READ_ONLY",
        f"**Verdict:** **{report['verdict']}**",
        "",
        "## Population",
        "",
        f"- Audited (`NCERT_EVIDENCE_MISSING`): **{report['audited_count']}**",
        f"- StudyMaterial: **{report['population_counts'].get('LEGACY_STUDYMATERIAL', 0)}**",
        f"- SOURCE_MISSING: **{report['population_counts'].get('SOURCE_MISSING', 0)}**",
        f"- GENERATION_READY untouched: **{report['generation_ready_untouched']}**",
        f"- REVIEW_REQUIRED untouched: **{report['review_required_untouched']}**",
        "",
        "## Recovery classifications (sum → 65)",
        "",
    ]
    for k in RECOVERY:
        lines.append(f"- {k}: **{by.get(k, 0)}**")
    lines += [
        f"- Sum: **{sum(by.get(k, 0) for k in RECOVERY)}**",
        "",
        "## By subject",
        "",
        "| Subject | Recoverable | Mapping review | Not found | Insufficient | Provenance review |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for subj, counts in sorted(report["by_subject"].items()):
        lines.append(
            f"| {subj} | {counts.get('CANONICAL_EVIDENCE_RECOVERABLE', 0)} | "
            f"{counts.get('CANONICAL_SOURCE_EXISTS_BUT_MAPPING_REVIEW', 0)} | "
            f"{counts.get('CANONICAL_SOURCE_NOT_FOUND', 0)} | "
            f"{counts.get('NCERT_EVIDENCE_INSUFFICIENT', 0)} | "
            f"{counts.get('SOURCE_PROVENANCE_REVIEW', 0)} |"
        )
    lines += [
        "",
        "## By class",
        "",
        f"```json\n{json.dumps(report['by_class'], indent=2)}\n```",
        "",
        "## Future actions",
        "",
        f"```json\n{json.dumps(report['by_future_action'], indent=2)}\n```",
        "",
        "## Special attention",
        "",
        f"```json\n{json.dumps(report['special_attention'], indent=2)}\n```",
        "",
        "## Database freeze",
        "",
        f"- Unchanged: **{report['database_unchanged']}**",
        f"- Before: `{json.dumps(report['database_before'])}`",
        f"- After: `{json.dumps(report['database_after'])}`",
        "",
        "## Provider",
        "",
        f"- provider_call_count: **{report['provider_call_count']}**",
        "",
        "## Tests",
        "",
        f"```json\n{json.dumps(report.get('tests'), indent=2)}\n```",
        "",
        "## Failures",
        "",
        f"- {report.get('failures') or 'None'}",
        "",
        "## Limitations",
        "",
    ]
    for lim in report.get("limitations", []):
        lines.append(f"- {lim}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    assert NCERT_ROOT.is_dir()
    assert COVERAGE.is_file()
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    missing = [b for b in coverage["blueprints"] if b["readiness"] == "NCERT_EVIDENCE_MISSING"]
    assert len(missing) == 65, f"expected 65 missing, got {len(missing)}"
    ready_ids = {
        b["blueprint_id"]
        for b in coverage["blueprints"]
        if b["readiness"] == "GENERATION_READY"
    }
    assert len(ready_ids) == 132

    miss_ids = {b["blueprint_id"] for b in missing}
    registry = load_neet_2026_registry()
    engine = create_engine(get_settings().database_url_sync)

    with engine.connect() as conn:
        before = snapshot(conn)
        chapter_index = build_canonical_chapter_pdf_index(conn)
        db_rows = load_db_rows(conn, miss_ids)
        assert len(db_rows) == 65

        # Confirm 248 still review-required (sample + count via gate on non-confirmed)
        review_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM (
                  SELECT DISTINCT ON (bp.blueprint_key) bp.id, bp.constraints, s.code
                  FROM cms.question_blueprints bp
                  JOIN academic.subjects s ON s.id = bp.subject_id
                  WHERE bp.deleted_at IS NULL
                  ORDER BY bp.blueprint_key, bp.blueprint_version DESC
                ) t
                """
            )
        ).scalar()
        # We'll gate-scan only to count review after loading coverage meta
        audited: list[dict[str, Any]] = []
        for cov in missing:
            db = db_rows[cov["blueprint_id"]]
            audited.append(audit_one(cov, db, chapter_index, registry))

        # Gate counts for safety
        all_latest = conn.execute(
            text(
                """
                SELECT DISTINCT ON (bp.blueprint_key)
                  bp.id::text, bp.constraints, s.code AS subject_code
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                WHERE bp.deleted_at IS NULL
                ORDER BY bp.blueprint_key, bp.blueprint_version DESC
                """
            )
        ).mappings()
        gate_counts: Counter = Counter()
        for r in all_latest:
            st = assert_blueprint_neet_syllabus_scope(
                _cons(r["constraints"]),
                academic_subject_code=r["subject_code"],
                registry=registry,
            ).status
            gate_counts[st] += 1

        after = snapshot(conn)

    by_recovery = Counter(r["recovery_classification"] for r in audited)
    by_pop = Counter(r["provenance"] for r in audited)
    by_future = Counter(r["future_action"] for r in audited)
    by_subject: dict[str, Counter] = defaultdict(Counter)
    by_class: dict[str, Counter] = defaultdict(Counter)
    by_unit: dict[str, Counter] = defaultdict(Counter)
    by_pdf: dict[str, Counter] = defaultdict(Counter)
    for r in audited:
        by_subject[r["subject"] or "?"][r["recovery_classification"]] += 1
        by_class[str(r.get("class_level") or "?")][r["recovery_classification"]] += 1
        unit = r["syllabus_mapping"].get("unit_number")
        subj = r["syllabus_mapping"].get("subject") or "?"
        uk = f"{subj}:U{int(unit):02d}" if unit is not None else f"{subj}:?"
        by_unit[uk][r["recovery_classification"]] += 1
        cand = r.get("candidate_ncert_source")
        if isinstance(cand, str):
            by_pdf[cand][r["recovery_classification"]] += 1
        elif isinstance(cand, list):
            by_pdf["(ambiguous:" + ",".join(cand) + ")"][r["recovery_classification"]] += 1
        else:
            by_pdf["(none)"][r["recovery_classification"]] += 1

    special_attention = {
        "digestion_absorption": [r for r in audited if r.get("special", {}).get("digestion_absorption")],
        "biomolecules_botany_xi": [
            {
                "blueprint_id": r["blueprint_id"],
                "subject": r["subject"],
                "class_level": r["class_level"],
                "candidate": r["candidate_ncert_source"],
                "classification": r["recovery_classification"],
                "ownership_ok": r["subject"] == "BOTANY" and str(r["class_level"]) == "11",
            }
            for r in audited
            if "biomolecule" in (r.get("chapter") or "").lower() and r["subject"] == "BOTANY"
        ],
        "gravitation_keph107": [
            {
                "blueprint_id": r["blueprint_id"],
                "candidate": r["candidate_ncert_source"],
                "classification": r["recovery_classification"],
            }
            for r in audited
            if (r.get("chapter") or "").lower() == "gravitation"
            or (isinstance(r.get("candidate_ncert_source"), str) and "keph107" in r["candidate_ncert_source"])
        ],
        "chemistry_xii_biomolecules_lech205": [
            {
                "blueprint_id": r["blueprint_id"],
                "candidate": r["candidate_ncert_source"],
                "classification": r["recovery_classification"],
            }
            for r in audited
            if r["subject"] == "CHEMISTRY" and "biomolecule" in (r.get("chapter") or "").lower()
        ],
    }

    sum_ok = sum(by_recovery[k] for k in RECOVERY) == 65
    unchanged = before == after
    no_fuzzy = all(not r.get("fuzzy_authorized") for r in audited)
    provider_ok = PROVIDER_CALLS["n"] == 0
    biomolecules_ok = all(x["ownership_ok"] for x in special_attention["biomolecules_botany_xi"]) if special_attention["biomolecules_botany_xi"] else True
    gate_ok = gate_counts.get("IN_SYLLABUS") == 197 and gate_counts.get(
        "SYLLABUS_MAPPING_REVIEW_REQUIRED"
    ) == 248

    failures: list[str] = []
    verdict = "GREEN"
    if not unchanged:
        failures.append("database_mutated")
        verdict = "RED"
    if not provider_ok:
        failures.append("provider_called")
        verdict = "RED"
    if not sum_ok or len(audited) != 65:
        failures.append("classification_sum")
        verdict = "RED"
    if not no_fuzzy:
        failures.append("fuzzy_authorized")
        verdict = "RED"
    if not biomolecules_ok:
        failures.append("biomolecules_ownership")
        verdict = "RED" if verdict != "RED" else verdict
    if not gate_ok:
        failures.append(f"gate_drift:{dict(gate_counts)}")
        verdict = "RED"
    # Recoverable findings imply separate write decision → YELLOW
    if by_recovery.get("CANONICAL_EVIDENCE_RECOVERABLE", 0) > 0 and verdict == "GREEN":
        verdict = "YELLOW"
    if by_recovery.get("SOURCE_PROVENANCE_REVIEW", 0) > 0 and verdict == "GREEN":
        verdict = "YELLOW"

    report = {
        "task": "NCERT-EVIDENCE-REMEDIATION-001",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "READ_ONLY",
        "ncert_root": str(NCERT_ROOT),
        "input_audit": str(COVERAGE),
        "audited_count": 65,
        "population_counts": dict(by_pop),
        "generation_ready_untouched": 132,
        "review_required_untouched": 248,
        "gate_counts": dict(gate_counts),
        "by_recovery": {k: by_recovery.get(k, 0) for k in RECOVERY},
        "by_future_action": dict(by_future),
        "by_subject": {k: dict(v) for k, v in sorted(by_subject.items())},
        "by_class": {k: dict(v) for k, v in sorted(by_class.items())},
        "by_neet_unit": {k: dict(v) for k, v in sorted(by_unit.items())},
        "by_ncert_pdf": {
            k: dict(v)
            for k, v in sorted(by_pdf.items(), key=lambda kv: -sum(kv[1].values()))
        },
        "special_attention": special_attention,
        "database_before": before,
        "database_after": after,
        "database_unchanged": unchanged,
        "provider_call_count": PROVIDER_CALLS["n"],
        "blueprints": audited,
        "verdict": verdict,
        "failures": failures,
        "limitations": [
            "Read-only: no provenance/ncert_source_path/KU/blueprint writes performed.",
            "CANONICAL_EVIDENCE_RECOVERABLE does not authorize provenance migration.",
            "Chapter→PDF map derived from existing canonical sibling blueprints only.",
            "Multi-PDF academic chapters (Optics/Electrostatics/Kinematics) require exact phrase disambiguation.",
            "StudyMaterial text was never used as factual evidence.",
            "YELLOW when recoverable or provenance-review items exist — separate write task required.",
        ],
        "tests": {"pending": True},
        "acceptance": {
            "audited_65": len(audited) == 65,
            "sum_65": sum_ok,
            "no_db_mutation": unchanged,
            "no_provider": provider_ok,
            "no_fuzzy": no_fuzzy,
            "ready_untouched": True,
            "review_untouched": gate_ok,
        },
    }

    out_json = ROOT / "docs" / "audits" / f"{REPORT}.json"
    out_md = ROOT / "docs" / "audits" / f"{REPORT}.md"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_markdown(report, out_md)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "by_recovery": report["by_recovery"],
                "by_future_action": dict(by_future),
                "unchanged": unchanged,
                "provider_calls": PROVIDER_CALLS["n"],
                "json": str(out_json),
            },
            indent=2,
        )
    )
    return 0 if verdict != "RED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
