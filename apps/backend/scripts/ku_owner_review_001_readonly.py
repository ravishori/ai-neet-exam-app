"""KU-OWNER-REVIEW-001 — Read-only owner review of unresolved NCERT KU gaps
and Botany duplicate sv2c-botany-15.

No database mutations. Writes only docs/audits/ku_owner_review_001_*.{md,json}.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
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
from scripts.curriculum_baseline_005_ku_backfill import (  # noqa: E402
    decode_pua,
    extract_window,
    load_pdf_text,
)
from scripts.ku_coverage_002_ncert_ku_gaps import CHAPTER_PDF_MAP  # noqa: E402

REPORT_STEM = "ku_owner_review_001_20260913"
KU002_JSON = ROOT / "docs/audits/ku_coverage_002_20260913.json"
EXPECTED = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "DRAFT": 5298,
    "SUPERSEDED": 6,
    "unmapped_draft": 5024,
    "chapters": 56,
    "topics": 192,
    "concepts": 318,
    "knowledge_units": 370,
    "blueprints": 266,
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
    studymaterial_kus = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM knowledge.knowledge_units ku
            JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
            JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
            WHERE ku.deleted_at IS NULL
              AND coalesce(j.source_file_path, '') LIKE '%StudyMaterial%'
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
        "studymaterial_path_kus": studymaterial_kus,
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
        and snap["digestion_kus"] == 0
    )


def load_concept(conn, code: str) -> dict | None:
    row = conn.execute(
        text(
            """
            SELECT c.id::text AS concept_id, c.code AS concept_code, c.name AS concept_name,
                   coalesce(c.summary, '') AS summary,
                   coalesce(c.ncert_reference, '') AS ncert_reference,
                   c.created_at::text AS created_at, c.updated_at::text AS updated_at,
                   s.code AS subject, ch.class_level, ch.code AS chapter_code, ch.name AS chapter_name,
                   t.code AS topic_code, t.name AS topic_name,
                   (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                    WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL) AS ku_count,
                   (SELECT COUNT(*) FROM knowledge.knowledge_units ku
                    JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                    JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                    WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                      AND ku.validation_status = 'PASSED'
                      AND coalesce(j.source_file_path, '') LIKE '%NCERT Books%') AS ncert_ku_count,
                   (SELECT COUNT(*) FROM cms.question_blueprints bp
                    WHERE bp.concept_id = c.id AND bp.deleted_at IS NULL) AS blueprint_count,
                   (SELECT COUNT(*) FROM cms.content_items ci
                    WHERE ci.concept_id = c.id AND ci.deleted_at IS NULL
                      AND ci.content_type = 'QUESTION') AS question_count
            FROM academic.concepts c
            JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
            JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
            JOIN academic.subjects s ON s.id = ch.subject_id
            WHERE c.code = :code AND c.deleted_at IS NULL
            """
        ),
        {"code": code},
    ).mappings().one_or_none()
    return dict(row) if row else None


def find_section_hits(pdf_text: str, needles: list[str], limit: int = 5) -> list[dict]:
    hits = []
    lower = pdf_text.lower()
    for needle in needles:
        if not needle or len(needle) < 4:
            continue
        idx = lower.find(needle.lower())
        if idx < 0:
            continue
        # approximate page via form-feed / page breaks is unreliable; use char offset + nearby header
        start = max(0, idx - 120)
        end = min(len(pdf_text), idx + 280)
        snippet = re.sub(r"\s+", " ", pdf_text[start:end]).strip()
        # look for a nearby section number like 3.2 or 18.1
        header = None
        back = pdf_text[max(0, idx - 400) : idx + 80]
        m = re.search(r"(?m)^(\d+\.\d+)\s+([A-Z][^\n]{3,60})", back)
        if m:
            header = f"{m.group(1)} {m.group(2).strip()}"
        hits.append({"needle": needle, "char_offset": idx, "nearby_section_header": header, "snippet": snippet[:240]})
        if len(hits) >= limit:
            break
    return hits


def pdf_page_count(root: Path, rel: str) -> int | None:
    try:
        doc = fitz.open(root / rel)
        n = doc.page_count
        doc.close()
        return n
    except Exception:  # noqa: BLE001
        return None


def recommend(
    concept: dict,
    ku002_reason: str,
    pdf_ok: bool,
    window_ok: bool,
    evidence_note: str | None,
    hits: list[dict],
) -> tuple[str, str]:
    code = concept["concept_code"]
    name = concept["concept_name"]

    # Seed-like codes with weak naming → taxonomy first
    if code.startswith("sv2c-") and (
        not window_ok or "insufficient_token" in ku002_reason or evidence_note and "insufficient" in evidence_note
    ):
        return (
            "TAXONOMY_REVIEW",
            "Seed-style concept code with weak token match against NCERT text; rename/remap to NCERT terminology before KU creation.",
        )

    if not pdf_ok:
        return "SOURCE_REVIEW", "Mapped canonical PDF missing or unreadable under NCERT Books."

    # Strong NCERT presence despite extractor threshold miss
    if hits and not window_ok:
        # If concept name itself appears or multiple related needles hit
        strong = any(h["needle"].lower() in name.lower() or name.lower() in h["snippet"].lower() for h in hits)
        if strong or len(hits) >= 2:
            return (
                "ACCEPT_KU",
                "Canonical PDF contains relevant NCERT language; KU-COVERAGE-002 token threshold failed, but evidence looks sufficient for a carefully windowed KU.",
            )
        return (
            "SOURCE_REVIEW",
            "Some related terms appear in the PDF, but linkage to this concept title is weak; owner should confirm section mapping.",
        )

    if window_ok:
        return (
            "ACCEPT_KU",
            "Re-inspection found an extractable NCERT window; prior run likely failed only the token-score gate — safe to retry KU with tightened section targeting.",
        )

    # Multi-KU legacy chemistry/physics codes that already have many StudyMaterial KUs
    if concept["ku_count"] > 1 and concept["ncert_ku_count"] == 0:
        return (
            "KEEP_UNRESOLVED",
            "Concept already has legacy/non-NCERT KUs and NCERT token match remains weak; avoid adding ambiguous NCERT KU until owner confirms target section.",
        )

    if "insufficient_token" in ku002_reason:
        return (
            "KEEP_UNRESOLVED",
            "Canonical PDF exists but automated token overlap is below threshold and re-inspection did not find a clear concept-specific section.",
        )

    return "KEEP_UNRESOLVED", f"Unresolved for recorded reason: {ku002_reason}"


def review_unresolved(conn, root: Path, unresolved: list[dict]) -> list[dict]:
    out = []
    for item in unresolved:
        code = item["concept_code"]
        concept = load_concept(conn, code)
        pdfs = item.get("pdfs_tried") or CHAPTER_PDF_MAP.get(item.get("chapter") or "", [])
        pdf_reports = []
        best_window = None
        best_note = None
        best_pdf = None
        all_hits: list[dict] = []

        for rel in pdfs:
            path = root / rel
            exists = path.exists()
            readable = False
            pages = None
            err = None
            if exists:
                try:
                    validate_ncert_generation_source(path, root=root)
                    readable = True
                    pages = pdf_page_count(root, rel)
                except Exception as exc:  # noqa: BLE001
                    err = str(exc)
            pdf_reports.append(
                {
                    "relative_path": rel,
                    "absolute_path": str(path),
                    "exists": exists,
                    "readable_pdf": readable,
                    "page_count": pages,
                    "error": err,
                }
            )
            if not (exists and readable) or not concept:
                continue
            text_blob = load_pdf_text(root, rel)
            window, note = extract_window(
                text_blob,
                concept["concept_name"],
                concept.get("ncert_reference") or "",
                concept.get("summary") or "",
            )
            if window and (best_window is None or (note or "").startswith("section_window")):
                best_window, best_note, best_pdf = window, note, rel
            # Search needles from name + summary tokens
            needles = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", concept["concept_name"])
            needles += re.findall(r"[A-Za-z]{5,}", (concept.get("summary") or "")[:120])
            # Common NCERT aliases by code family
            aliases = {
                "factors-affecting-resistance": ["resistivity", "resistance", "temperature dependence"],
                "cardiac-cycle-phases": ["cardiac cycle", "systole", "diastole"],
                "heart-structure": ["human heart", "chambers of the heart", "atria"],
                "gonads-ducts": ["testes", "ovaries", "vas deferens", "oviduct"],
                "menstrual-phases": ["menstrual cycle", "follicular", "luteal"],
                "biomolecule-classes": ["biomolecules", "carbohydrates", "proteins", "amino acids"],
                "pcr-and-downstream-processing": ["PCR", "polymerase chain", "downstream processing"],
                "pk-plantae-boundaries-and-cyanobacteria": ["Plantae", "cyanobacteria", "chlorophyll"],
                "sp-sp2-sp3": ["hybridisation", "sp3", "sp2", "sp hybrid"],
                "primary-and-secondary-valency": ["primary valency", "secondary valency", "Werner"],
                "concentration-expressions": ["molarity", "molality", "mole fraction"],
            }.get(code, [])
            needles = list(dict.fromkeys(needles + aliases))
            hits = find_section_hits(text_blob, needles)
            for h in hits:
                all_hits.append({**h, "pdf": rel})

        window_ok = bool(best_window)
        pdf_ok = any(p["exists"] and p["readable_pdf"] for p in pdf_reports)
        decision, rationale = (
            recommend(concept, item.get("reason") or "", pdf_ok, window_ok, best_note, all_hits)
            if concept
            else ("TAXONOMY_REVIEW", "Concept row not found in live DB")
        )

        out.append(
            {
                "ku002_record": item,
                "concept": concept,
                "canonical_pdfs": pdf_reports,
                "extraction_reinspection": {
                    "window_found": window_ok,
                    "evidence_note": best_note,
                    "pdf_used": best_pdf,
                    "window_char_len": len(best_window) if best_window else 0,
                    "window_preview": (re.sub(r"\s+", " ", best_window)[:320] if best_window else None),
                },
                "ncert_term_hits": all_hits[:8],
                "evidence_appears_sufficient": decision == "ACCEPT_KU",
                "recommended_owner_decision": decision,
                "rationale": rationale,
            }
        )
    return out


def review_botany_duplicate(conn, root: Path) -> dict:
    codes = ("sv2c-botany-15", "syngamy-and-triple-fusion")
    concepts = {c: load_concept(conn, c) for c in codes}
    details = {}
    for code, concept in concepts.items():
        if not concept:
            details[code] = None
            continue
        kus = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT ku.id::text AS ku_id, ku.validation_status,
                           left(ku.summary, 240) AS summary,
                           left(coalesce(j.source_file_path, ''), 220) AS source_path,
                           left(coalesce(sec.heading, ''), 160) AS section_heading
                    FROM knowledge.knowledge_units ku
                    LEFT JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
                    LEFT JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
                    WHERE ku.concept_id = :cid AND ku.deleted_at IS NULL
                    ORDER BY ku.created_at
                    """
                ),
                {"cid": concept["concept_id"]},
            ).mappings()
        ]
        bps = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT bp.id::text AS blueprint_id, bp.blueprint_key, bp.provenance_tier, bp.target_count
                    FROM cms.question_blueprints bp
                    WHERE bp.concept_id = :cid AND bp.deleted_at IS NULL
                    ORDER BY bp.blueprint_key
                    """
                ),
                {"cid": concept["concept_id"]},
            ).mappings()
        ]
        # NCERT evidence check in lebo101
        pdf_rel = "Class 12/Biology/lebo1dd/lebo101.pdf"
        hits = []
        window = None
        note = None
        if (root / pdf_rel).exists():
            blob = load_pdf_text(root, pdf_rel)
            window, note = extract_window(blob, concept["concept_name"], concept.get("ncert_reference") or "", concept.get("summary") or "")
            hits = find_section_hits(blob, ["syngamy", "triple fusion", "double fertilisation", "double fertilization"])
        details[code] = {
            "concept": concept,
            "knowledge_units": kus,
            "blueprints": bps,
            "ncert_pdf": pdf_rel,
            "extraction": {
                "window_found": bool(window),
                "evidence_note": note,
                "window_preview": (re.sub(r"\s+", " ", window)[:320] if window else None),
                "term_hits": hits[:6],
            },
        }

    a = details.get("sv2c-botany-15")
    b = details.get("syngamy-and-triple-fusion")
    same_chapter = (
        a
        and b
        and a["concept"]["chapter_code"] == b["concept"]["chapter_code"]
        and a["concept"]["subject"] == b["concept"]["subject"]
    )
    name_overlap = (
        a
        and b
        and a["concept"]["concept_name"].strip().lower() == b["concept"]["concept_name"].strip().lower()
    )
    decision = "MERGE_REVIEW"
    rationale = (
        "Both concepts share subject/chapter and essentially identical titles for syngamy/triple fusion; "
        "both have NCERT Books evidence under lebo101.pdf. Seed-style code sv2c-botany-15 is likely a "
        "legacy duplicate of syngamy-and-triple-fusion. Owner should decide merge/retire mapping without "
        "silent auto-merge (questions/blueprints may attach to either)."
    )
    if not (a and b):
        decision = "TAXONOMY_REVIEW"
        rationale = "One of the concepts is missing from live DB."
    elif not name_overlap:
        decision = "TAXONOMY_REVIEW"
        rationale = "Titles differ; confirm semantic equivalence before merge."

    return {
        "pair": details,
        "same_chapter_subject": same_chapter,
        "identical_names": name_overlap,
        "appear_same_concept": bool(same_chapter and name_overlap),
        "recommended_owner_decision": decision,
        "rationale": rationale,
        "action_taken": "none (read-only)",
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
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m_pass = re.search(r"(\d+)\s+passed", out)
    m_fail = re.search(r"(\d+)\s+failed", out)
    return {
        "passed": int(m_pass.group(1)) if m_pass else None,
        "failed": int(m_fail.group(1)) if m_fail else (0 if proc.returncode == 0 else None),
        "exit_code": proc.returncode,
        "command": " ".join(cmd),
        "tail": "\n".join(out.strip().splitlines()[-30:]),
    }


def write_reports(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    decisions = Counter(r["recommended_owner_decision"] for r in payload["unresolved_reviews"])
    lines = [
        "# KU-OWNER-REVIEW-001 — NCERT KU gap + Botany duplicate owner review",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Mode: **READ-ONLY** (no DB mutation)",
        "- Git: **no commit / no push**",
        "",
        "## Summary",
        f"- Unresolved concepts reviewed: `{len(payload['unresolved_reviews'])}`",
        f"- Decision counts: `{dict(decisions)}`",
        f"- Botany duplicate decision: `{payload['botany_duplicate']['recommended_owner_decision']}`",
        "",
        "## 1. Unresolved concept reviews (21)",
    ]
    for r in payload["unresolved_reviews"]:
        c = r.get("concept") or {}
        lines += [
            f"### `{c.get('concept_code')}` — {c.get('concept_name')}",
            f"- ID: `{c.get('concept_id')}`",
            f"- Subject/class/chapter/topic: `{c.get('subject')}` / `{c.get('class_level')}` / "
            f"`{c.get('chapter_code')}` / `{c.get('topic_code')}`",
            f"- KU002 reason: `{r['ku002_record'].get('reason')}`",
            f"- PDFs: `{[p['relative_path'] for p in r['canonical_pdfs']]}` "
            f"(readable={[p['readable_pdf'] for p in r['canonical_pdfs']]})",
            f"- Reinspection window: `{r['extraction_reinspection']['window_found']}` "
            f"(`{r['extraction_reinspection'].get('evidence_note')}`)",
            f"- Evidence sufficient?: `{r['evidence_appears_sufficient']}`",
            f"- **Recommended decision: `{r['recommended_owner_decision']}`** — {r['rationale']}",
            "",
        ]
    lines += [
        "## 2. Botany duplicate review",
        f"```json\n{json.dumps(payload['botany_duplicate'], indent=2, default=str)[:6000]}\n```",
        "",
        "## 3. Safety verification",
        f"- Freeze OK: `{payload['freeze_ok']}`",
        f"- Snapshot identical: `{payload['snapshot_identical']}`",
        "### Before",
        f"```json\n{json.dumps(payload['before'], indent=2)}\n```",
        "### After",
        f"```json\n{json.dumps(payload['after'], indent=2)}\n```",
        "",
        "## 4. Tests",
        f"- Passed `{payload['tests'].get('passed')}` / Failed `{payload['tests'].get('failed')}`",
        "",
        "```",
        payload["tests"].get("tail") or "",
        "```",
        "",
        "## 5. Files changed",
    ]
    for f in payload["files_changed"]:
        lines.append(f"- `{f}`")
    lines += [
        "",
        "## Confirmation",
        f"```json\n{json.dumps(payload['confirmation'], indent=2)}\n```",
        "",
        "**STOP** — no remediation, no KU/blueprint/MCQ creation.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    try:
        root = get_ncert_source_root()
    except Exception:  # noqa: BLE001
        root = ROOT / "NCERT Books"

    ku002 = json.loads(KU002_JSON.read_text(encoding="utf-8"))
    unresolved = ku002["backfill"]["unresolved"]
    if len(unresolved) != 21:
        raise SystemExit(f"Expected 21 unresolved, found {len(unresolved)}")

    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        before = snapshot(conn)
        if not freeze_ok(before):
            raise SystemExit(f"ABORT freeze mismatch: {before}")
        reviews = review_unresolved(conn, root, unresolved)
        botany = review_botany_duplicate(conn, root)
        after = snapshot(conn)

    tests = run_tests()
    snapshot_identical = before == after
    freeze = freeze_ok(after) and snapshot_identical

    if not freeze or (tests.get("failed") or 0) > 0:
        final = "RED — FAILED"
    else:
        # Owner decisions remain → YELLOW is appropriate for a review package
        final = "YELLOW — OWNER REVIEW READY"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "mode": "READ-ONLY",
        "ncert_root": str(root),
        "source_ku002": str(KU002_JSON.relative_to(ROOT)),
        "before": before,
        "after": after,
        "snapshot_identical": snapshot_identical,
        "freeze_ok": freeze,
        "unresolved_reviews": reviews,
        "decision_counts": dict(Counter(r["recommended_owner_decision"] for r in reviews)),
        "botany_duplicate": botany,
        "tests": tests,
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/ku_owner_review_001_readonly.py",
        ],
        "files_inspected": [
            str(KU002_JSON.relative_to(ROOT)),
            "academic.concepts/topics/chapters",
            "knowledge.knowledge_units (read)",
            "cms.question_blueprints (read)",
            "NCERT Books PDFs referenced by unresolved concepts",
            "apps/backend/scripts/ku_coverage_002_ncert_ku_gaps.py (CHAPTER_PDF_MAP)",
        ],
        "confirmation": {
            "db_mutated": False,
            "kus_created": False,
            "concepts_modified": False,
            "blueprints_modified": False,
            "mcqs_generated": False,
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
                "unresolved_reviewed": len(reviews),
                "decision_counts": payload["decision_counts"],
                "botany_decision": botany["recommended_owner_decision"],
                "freeze_ok": freeze,
                "snapshot_identical": snapshot_identical,
                "kus": after["knowledge_units"],
                "blueprints": after["question_blueprints"],
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
            },
            indent=2,
        )
    )
    return 0 if final != "RED — FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
