#!/usr/bin/env python3
"""Phase 3.2 — DB-derived content readiness + inventory truth (SELECT-only).

Never mutates the database. Never publishes.

Usage (from apps/backend):
  python scripts/content_readiness_inventory.py
  python scripts/content_readiness_inventory.py --subject Chemistry
  python scripts/content_readiness_inventory.py --json-only

Writes:
  docs/audits/content_readiness_inventory_YYYYMMDD.json
  docs/audits/content_readiness_inventory_YYYYMMDD.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "docs" / "audits"
TODAY = date.today().strftime("%Y%m%d")

# Import disposition helpers without requiring app package if path differs
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.modules.cms.services.draft_disposition import (  # noqa: E402
    classify_draft_disposition,
    readiness_label_for_question,
)


def _sync_url() -> tuple[str, dict[str, str]]:
    from app.core.config import get_settings

    s = get_settings()
    async_url = s.database_url
    live = async_url.replace("+asyncpg", "+psycopg")
    meta = {
        "audit_target": live.split("@")[-1] if "@" in live else live,
        "note": "Uses DATABASE_URL (live app). SELECT-only.",
    }
    return live, meta


def q(conn, sql: str, params: dict | None = None):
    return conn.execute(text(sql), params or {})


def mappings(conn, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    return [dict(r) for r in q(conn, sql, params).mappings().all()]


def _ncert_verified(tags: list | None, body: dict | None) -> bool:
    tags = tags or []
    for t in tags:
        if isinstance(t, str) and (
            t.startswith("ncert_level:SOURCE_TEXT_VERIFIED")
            or t.startswith("ncert:SOURCE_TEXT_VERIFIED")
            or "SOURCE_TEXT_VERIFIED" in t
            or "SECTION_VERIFIED" in t
        ):
            return True
    if isinstance(body, dict):
        ncert = body.get("ncert_evidence") or body.get("ncert")
        if isinstance(ncert, dict):
            level = (ncert.get("verification_level") or "").upper()
            if level and level not in ("NOT_VERIFIED", "", "NONE", "0"):
                return True
    return False


def _has_lineage(model_used: str | None, ku_id: Any) -> bool:
    return bool(model_used or ku_id)


def _body_structure_ok(body: dict | None) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not isinstance(body, dict):
        return False, ["missing_body"]
    stem = (body.get("stem") or "").strip() if isinstance(body.get("stem"), str) else ""
    if not stem:
        issues.append("missing_stem")
    opts = body.get("options")
    if not isinstance(opts, list) or len(opts) != 4:
        issues.append("options_not_4")
    else:
        texts = []
        for o in opts:
            if isinstance(o, dict):
                texts.append((o.get("text") or "").strip())
            else:
                texts.append(str(o).strip())
        if len(set(texts)) < 4:
            issues.append("duplicate_options")
    if body.get("correct_option") not in ("A", "B", "C", "D"):
        issues.append("bad_correct_option")
    expl = body.get("explanation")
    if not (isinstance(expl, str) and expl.strip()):
        issues.append("missing_explanation")
    if (body.get("difficulty") or "").lower() not in ("easy", "medium", "hard"):
        issues.append("missing_difficulty")
    return len(issues) == 0, issues


def _structural_ok(body: dict | None, concept_id: Any) -> tuple[bool, list[str]]:
    ok, issues = _body_structure_ok(body)
    if not concept_id:
        issues = [*issues, "missing_concept"]
        ok = False
    return ok, issues


def inventory_overview(conn) -> dict[str, Any]:
    by_type_status = mappings(
        conn,
        """
        SELECT content_type, status, COUNT(*)::int AS count
        FROM cms.content_items
        WHERE deleted_at IS NULL
        GROUP BY content_type, status
        ORDER BY content_type, status
        """,
    )
    questions_by_subject = mappings(
        conn,
        """
        SELECT COALESCE(s.name, 'UNMAPPED') AS subject, ci.status, COUNT(*)::int AS count
        FROM cms.content_items ci
        LEFT JOIN academic.concepts c ON c.id = ci.concept_id
        LEFT JOIN academic.topics t ON t.id = c.topic_id
        LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id
        LEFT JOIN academic.subjects s ON s.id = ch.subject_id
        WHERE ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
    )
    return {"by_type_status": by_type_status, "questions_by_subject_status": questions_by_subject}


def subject_readiness(conn, subject_name: str) -> dict[str, Any]:
    rows = mappings(
        conn,
        """
        SELECT
          ci.id::text AS id,
          ci.status,
          ci.concept_id,
          ci.tags,
          ci.title,
          ch.name AS chapter_name,
          t.name AS topic_name,
          c.name AS concept_name,
          cv.body,
          cv.model_used,
          cv.knowledge_unit_id
        FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        LEFT JOIN academic.concepts c ON c.id = ci.concept_id
        LEFT JOIN academic.topics t ON t.id = c.topic_id
        LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id
        LEFT JOIN academic.subjects s ON s.id = ch.subject_id
        WHERE ci.deleted_at IS NULL
          AND ci.content_type = 'QUESTION'
          AND s.name = :subject
        """,
        {"subject": subject_name},
    )

    status_counts: Counter[str] = Counter()
    readiness_counts: Counter[str] = Counter()
    chapter_pub: Counter[str] = Counter()
    chapter_total: Counter[str] = Counter()
    topic_pub: Counter[str] = Counter()
    concept_pub: Counter[str] = Counter()
    mapped = 0
    unmapped = 0
    with_provenance = 0
    ncert_verified = 0
    structural_ok_n = 0
    stem_hashes: dict[str, list[str]] = defaultdict(list)

    for r in rows:
        status_counts[r["status"]] += 1
        body = r["body"] if isinstance(r["body"], dict) else {}
        ok, _issues = _structural_ok(body, r["concept_id"])
        lineage = _has_lineage(r["model_used"], r["knowledge_unit_id"])
        ncert = _ncert_verified(r["tags"], body if isinstance(body, dict) else None)
        if r["concept_id"]:
            mapped += 1
        else:
            unmapped += 1
        if lineage:
            with_provenance += 1
        if ncert:
            ncert_verified += 1
        if ok:
            structural_ok_n += 1
        stem = (body.get("stem") or "").strip().lower() if isinstance(body, dict) else ""
        if stem:
            stem_hashes[stem].append(r["id"])
        ch = r["chapter_name"] or "(unknown)"
        chapter_total[ch] += 1
        if r["status"] == "PUBLISHED":
            chapter_pub[ch] += 1
            if r["topic_name"]:
                topic_pub[r["topic_name"]] += 1
            if r["concept_name"]:
                concept_pub[r["concept_name"]] += 1

    # Second pass for duplicate flags + readiness labels
    dup_stems = {s for s, ids in stem_hashes.items() if len(ids) > 1}
    for r in rows:
        body = r["body"] if isinstance(r["body"], dict) else {}
        ok, _ = _structural_ok(body, r["concept_id"])
        lineage = _has_lineage(r["model_used"], r["knowledge_unit_id"])
        ncert = _ncert_verified(r["tags"], body if isinstance(body, dict) else None)
        stem = (body.get("stem") or "").strip().lower() if isinstance(body, dict) else ""
        label = readiness_label_for_question(
            status=r["status"],
            concept_id=r["concept_id"],
            structural_valid=ok,
            has_provenance_lineage=lineage,
            ncert_verified=ncert,
            suspected_duplicate=stem in dup_stems,
        )
        readiness_counts[label] += 1

    # Chapters/topics/concepts with zero published — from academic tree for subject
    all_chapters = mappings(
        conn,
        """
        SELECT ch.name AS chapter_name
        FROM academic.chapters ch
        JOIN academic.subjects s ON s.id = ch.subject_id
        WHERE s.name = :subject AND ch.deleted_at IS NULL
        ORDER BY ch.display_order
        """,
        {"subject": subject_name},
    )
    zero_pub_chapters = [c["chapter_name"] for c in all_chapters if chapter_pub[c["chapter_name"]] == 0]

    all_topics = mappings(
        conn,
        """
        SELECT t.name AS topic_name
        FROM academic.topics t
        JOIN academic.chapters ch ON ch.id = t.chapter_id
        JOIN academic.subjects s ON s.id = ch.subject_id
        WHERE s.name = :subject AND t.deleted_at IS NULL
        """,
        {"subject": subject_name},
    )
    zero_pub_topics = [t["topic_name"] for t in all_topics if topic_pub[t["topic_name"]] == 0]

    all_concepts = mappings(
        conn,
        """
        SELECT c.name AS concept_name
        FROM academic.concepts c
        JOIN academic.topics t ON t.id = c.topic_id
        JOIN academic.chapters ch ON ch.id = t.chapter_id
        JOIN academic.subjects s ON s.id = ch.subject_id
        WHERE s.name = :subject AND c.deleted_at IS NULL
        """,
        {"subject": subject_name},
    )
    zero_pub_concepts = [c["concept_name"] for c in all_concepts if concept_pub[c["concept_name"]] == 0]

    return {
        "subject": subject_name,
        "total_questions": len(rows),
        "status_counts": dict(status_counts),
        "mapped": mapped,
        "unmapped": unmapped,
        "structurally_complete": structural_ok_n,
        "with_provenance_lineage": with_provenance,
        "ncert_verified_count": ncert_verified,
        "ncert_note": "Provenance ≠ NCERT certification. Count uses tags/body ncert evidence only.",
        "possible_duplicate_stem_groups": len(dup_stems),
        "readiness_counts": dict(readiness_counts),
        "chapter_distribution_published": dict(chapter_pub),
        "chapter_distribution_all": dict(chapter_total),
        "chapters_zero_published": zero_pub_chapters,
        "topics_zero_published_count": len(zero_pub_topics),
        "concepts_zero_published_count": len(zero_pub_concepts),
        "operational_note": (
            "Do not publish to reach quotas. Every promotion requires ECAEP gates + human action."
        ),
    }


def unmapped_disposition(conn, *, sample_limit: int = 10000) -> dict[str, Any]:
    total_unmapped_draft = int(
        q(
            conn,
            """
            SELECT COUNT(*) FROM cms.content_items ci
            WHERE ci.deleted_at IS NULL
              AND ci.content_type = 'QUESTION'
              AND ci.concept_id IS NULL
              AND ci.status = 'DRAFT'
            """,
        ).scalar()
        or 0
    )
    rows = mappings(
        conn,
        """
        SELECT
          ci.id::text AS id,
          ci.status,
          ci.concept_id,
          ci.tags,
          cv.body,
          cv.model_used,
          cv.knowledge_unit_id
        FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.deleted_at IS NULL
          AND ci.content_type = 'QUESTION'
          AND ci.concept_id IS NULL
          AND ci.status = 'DRAFT'
        LIMIT :lim
        """,
        {"lim": sample_limit},
    )
    stem_map: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        body = r["body"] if isinstance(r["body"], dict) else {}
        stem = (body.get("stem") or "").strip().lower() if isinstance(body, dict) else ""
        if stem:
            stem_map[stem].append(r["id"])
    dup = {s for s, ids in stem_map.items() if len(ids) > 1}

    counts: Counter[str] = Counter()
    for r in rows:
        body = r["body"] if isinstance(r["body"], dict) else {}
        body_ok, _ = _body_structure_ok(body)
        stem_ok = bool((body.get("stem") or "").strip()) if isinstance(body, dict) else False
        lineage = _has_lineage(r["model_used"], r["knowledge_unit_id"])
        stem = (body.get("stem") or "").strip().lower() if isinstance(body, dict) else ""
        code = classify_draft_disposition(
            status=r["status"],
            concept_id=r["concept_id"],
            structural_valid=body_ok,
            has_provenance_lineage=lineage,
            suspected_duplicate=stem in dup,
            has_stem=stem_ok,
        )
        # concept_id IS NULL → never READY_FOR_ECAEP; stay UNMAPPED unless INVALID/DUP
        if code in ("READY_FOR_ECAEP", "NEEDS_SOURCE", "MAPPABLE") and not r["concept_id"]:
            code = "UNMAPPED"
        counts[code] += 1

    return {
        "unmapped_draft_total": total_unmapped_draft,
        "unmapped_draft_scanned": len(rows),
        "disposition_counts": dict(counts),
        "rules": {
            "never_auto_publish": True,
            "classification_is_heuristic": True,
            "does_not_certify_validity": True,
            "tag_prefix": "disposition:",
            "apply_tags": "Use explicit operator tooling only — this script never writes tags.",
        },
    }


def integrity_checks(conn) -> dict[str, Any]:
    orphan_concepts = q(
        conn,
        """
        SELECT COUNT(*) FROM academic.concepts c
        WHERE c.deleted_at IS NULL
          AND NOT EXISTS (
            SELECT 1 FROM academic.topics t WHERE t.id = c.topic_id AND t.deleted_at IS NULL
          )
        """,
    ).scalar()
    questions_bad_subject = q(
        conn,
        """
        SELECT COUNT(*) FROM cms.content_items ci
        JOIN academic.concepts c ON c.id = ci.concept_id
        WHERE ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
          AND c.deleted_at IS NOT NULL
        """,
    ).scalar()
    published_missing_options = q(
        conn,
        """
        SELECT COUNT(*) FROM cms.content_items ci
        JOIN cms.content_versions cv ON cv.id = ci.current_version_id
        WHERE ci.deleted_at IS NULL AND ci.content_type = 'QUESTION' AND ci.status = 'PUBLISHED'
          AND (
            NOT (cv.body ? 'options')
            OR jsonb_typeof(cv.body->'options') <> 'array'
            OR jsonb_array_length(cv.body->'options') <> 4
          )
        """,
    ).scalar()
    return {
        "orphan_concepts": int(orphan_concepts or 0),
        "questions_pointing_soft_deleted_concepts": int(questions_bad_subject or 0),
        "published_missing_four_options": int(published_missing_options or 0),
    }


def build_report(conn, meta: dict[str, str]) -> dict[str, Any]:
    overview = inventory_overview(conn)
    chem = subject_readiness(conn, "Chemistry")
    zoo = subject_readiness(conn, "Zoology")
    unmapped = unmapped_disposition(conn)
    integrity = integrity_checks(conn)

    # NEET mock gate hint
    pub_by_subj = {
        r["subject"]: r["count"]
        for r in overview["questions_by_subject_status"]
        if r["status"] == "PUBLISHED"
    }
    zoo_pub = int(pub_by_subj.get("Zoology", 0))
    chem_pub = int(pub_by_subj.get("Chemistry", 0))
    mock_blocked = zoo_pub < 45  # NEET biology half needs zoology share; keep honest

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "3.2",
        "database": meta,
        "safety": {
            "select_only": True,
            "no_auto_publish": True,
            "student_visible_status": "PUBLISHED",
            "do_not_mass_publish_unmapped_drafts": True,
        },
        "overview": overview,
        "chemistry": chem,
        "zoology": zoo,
        "unmapped_draft_disposition": unmapped,
        "integrity": integrity,
        "neet_mock": {
            "full_180_blocked": mock_blocked,
            "reason": (
                f"Zoology published={zoo_pub} (<45 minimum for balanced Biology allocation). "
                f"Chemistry published={chem_pub}. Revalidate before claiming mock readiness."
            ),
            "do_not_publish_to_quota": True,
        },
        "verification_procedure": (
            "Re-run: cd apps/backend && python scripts/content_readiness_inventory.py. "
            "Do not hard-code these counts into product docs as permanent truth."
        ),
    }


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Content readiness inventory ({report['generated_at'][:10]})",
        "",
        "**Phase 3.2** · SELECT-only · DB-derived · never publish",
        "",
        f"Target: `{report['database'].get('audit_target')}`",
        "",
        "## Safety",
        "",
        "- Student-visible status: **PUBLISHED** only",
        "- No auto-publish; do not mass-publish unmapped drafts",
        "- Provenance ≠ NCERT certification",
        "",
        "## Chemistry",
        "",
        "```json",
        json.dumps(report["chemistry"]["status_counts"], indent=2),
        "```",
        "",
        f"Readiness: `{json.dumps(report['chemistry']['readiness_counts'])}`",
        f"Chapters with zero published: **{len(report['chemistry']['chapters_zero_published'])}**",
        f"NCERT-verified (evidence-based count): **{report['chemistry']['ncert_verified_count']}**",
        "",
        "## Zoology",
        "",
        "```json",
        json.dumps(report["zoology"]["status_counts"], indent=2),
        "```",
        "",
        f"Readiness: `{json.dumps(report['zoology']['readiness_counts'])}`",
        f"Chapters with zero published: **{len(report['zoology']['chapters_zero_published'])}**",
        "",
        "## Unmapped DRAFT disposition (heuristic)",
        "",
        "```json",
        json.dumps(report["unmapped_draft_disposition"]["disposition_counts"], indent=2),
        "```",
        "",
        "## NEET mock",
        "",
        report["neet_mock"]["reason"],
        "",
        "## Revalidation",
        "",
        report["verification_procedure"],
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3.2 content readiness inventory (SELECT-only)")
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--subject", choices=["Chemistry", "Zoology"], default=None)
    args = parser.parse_args()

    url, meta = _sync_url()
    engine = create_engine(url)
    with engine.connect() as conn:
        if args.subject:
            report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "subject_focus": subject_readiness(conn, args.subject),
                "database": meta,
            }
        else:
            report = build_report(conn, meta)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"content_readiness_inventory_{TODAY}.json"
    md_path = OUT_DIR / f"content_readiness_inventory_{TODAY}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if not args.subject:
        md_path.write_text(to_markdown(report), encoding="utf-8")

    if args.json_only:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"Wrote {json_path}")
        if not args.subject:
            print(f"Wrote {md_path}")
        chem = report.get("chemistry") or report.get("subject_focus")
        if chem:
            print(f"{chem.get('subject')}: status={chem.get('status_counts')} readiness={chem.get('readiness_counts')}")
        if report.get("zoology"):
            z = report["zoology"]
            print(f"Zoology: status={z['status_counts']} readiness={z['readiness_counts']}")
        if report.get("unmapped_draft_disposition"):
            print(f"Unmapped disposition: {report['unmapped_draft_disposition']['disposition_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
