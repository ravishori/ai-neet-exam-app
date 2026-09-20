#!/usr/bin/env python3
"""Phase 3.3 — SELECT-only Zoology IN_REVIEW ECAEP campaign preparation.

Never mutates content. Never approves/publishes/certifies.

Usage (from apps/backend):
  python scripts/zoology_in_review_campaign_prep.py
  python scripts/zoology_in_review_campaign_prep.py --json-only

Writes:
  docs/audits/zoology_in_review_campaign_prep_YYYYMMDD.json
  docs/audits/zoology_in_review_campaign_prep_YYYYMMDD.md
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

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.modules.cms.services.draft_disposition import ncert_state_from_evidence  # noqa: E402
from app.modules.cms.services.editorial_review_service import _structural_assessment  # noqa: E402


def _sync_url() -> tuple[str, dict[str, str]]:
    from app.core.config import get_settings

    s = get_settings()
    async_url = s.database_url
    live = async_url.replace("+asyncpg", "+psycopg")
    meta = {
        "audit_target": live.split("@")[-1] if "@" in live else live,
        "note": "Uses DATABASE_URL (live app). SELECT-only. No content mutation.",
    }
    return live, meta


def q(conn, sql: str, params: dict | None = None):
    return conn.execute(text(sql), params or {})


def mappings(conn, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    return [dict(r) for r in q(conn, sql, params).mappings().all()]


CAMPAIGN_SQL = """
SELECT
  ci.id::text AS id,
  ci.title,
  ci.status,
  ci.tags,
  ci.slug,
  ci.concept_id::text AS concept_id,
  cv.body,
  cv.model_used,
  cv.knowledge_unit_id::text AS knowledge_unit_id,
  sub.name AS subject,
  ch.name AS chapter,
  ch.class_level AS class_level,
  t.name AS topic,
  c.name AS concept
FROM cms.content_items ci
JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
JOIN academic.concepts c ON c.id = ci.concept_id
JOIN academic.topics t ON t.id = c.topic_id
JOIN academic.chapters ch ON ch.id = t.chapter_id
JOIN academic.subjects sub ON sub.id = ch.subject_id
WHERE ci.deleted_at IS NULL
  AND ci.content_type = 'QUESTION'
  AND ci.status = 'IN_REVIEW'
  AND sub.name = 'Zoology'
ORDER BY ch.name, t.name, ci.title
"""


def build_report(conn) -> dict[str, Any]:
    rows = mappings(conn, CAMPAIGN_SQL)
    chapters: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    classes: Counter[str] = Counter()
    ncert_levels: Counter[str] = Counter()
    warning_counts: Counter[str] = Counter()
    stem_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    items: list[dict[str, Any]] = []

    for r in rows:
        body = r["body"] if isinstance(r["body"], dict) else {}
        chapters[r["chapter"] or "UNKNOWN"] += 1
        topics[r["topic"] or "UNKNOWN"] += 1
        classes[str(r["class_level"] if r["class_level"] is not None else "unavailable")] += 1

        ncert = ncert_state_from_evidence(tags=r["tags"], body=body)
        ncert_levels[str(ncert.get("verification_level") or "NONE")] += 1

        struct = _structural_assessment("QUESTION", body, True)
        warnings: list[str] = []
        if not ncert.get("is_verified"):
            warnings.append("MISSING_NCERT_EVIDENCE")
        if not struct.get("valid"):
            warnings.append("OPTION_DEFECT" if any("option" in str(i).lower() for i in struct.get("issues") or []) else "STRUCTURAL_ISSUE")
            for issue in struct.get("issues") or []:
                warnings.append(f"STRUCTURAL:{issue}")
        has_lineage = bool(r.get("model_used") or r.get("knowledge_unit_id"))
        if not has_lineage:
            warnings.append("PROVENANCE_GAP")
        expl = body.get("explanation")
        if not expl or (isinstance(expl, str) and not expl.strip()):
            warnings.append("EXPLANATION_CONCERN")
        opts = body.get("options") or []
        if not isinstance(opts, list) or len(opts) != 4:
            warnings.append("OPTION_DEFECT")
        if body.get("correct_option") is None:
            warnings.append("WRONG_ANSWER_POSSIBLE")

        for w in warnings:
            warning_counts[w] += 1

        stem = body.get("stem") if isinstance(body.get("stem"), str) else ""
        stem_norm = stem.strip().lower()
        if stem_norm:
            stem_groups[stem_norm].append({"id": r["id"], "title": r["title"] or ""})

        # Class from chapter.class_level; also note tag class: if present
        class_from_tag = None
        for t in r["tags"] or []:
            if isinstance(t, str) and t.startswith("class:"):
                class_from_tag = t.split(":", 1)[1] or None
                break

        items.append(
            {
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "subject": r["subject"],
                "class_level": r["class_level"],
                "class_level_source": "academic.chapters.class_level" if r["class_level"] is not None else "unavailable",
                "class_tag": class_from_tag,
                "chapter": r["chapter"],
                "topic": r["topic"],
                "concept": r["concept"],
                "concept_id": r["concept_id"],
                "difficulty": body.get("difficulty"),
                "correct_option": body.get("correct_option"),
                "option_count": len(opts) if isinstance(opts, list) else 0,
                "has_explanation": bool(expl and str(expl).strip()),
                "provenance": {
                    "model_used": r.get("model_used"),
                    "knowledge_unit_id": r.get("knowledge_unit_id"),
                    "has_lineage": has_lineage,
                },
                "ncert": {
                    "verification_level": ncert.get("verification_level"),
                    "is_verified": ncert.get("is_verified"),
                    "has_structured_evidence": ncert.get("has_structured_evidence"),
                    "disclaimer": ncert.get("disclaimer"),
                },
                "structural_valid": bool(struct.get("valid")),
                "structural_issues": list(struct.get("issues") or []),
                "publication_eligible_now": False,
                "publication_note": "IN_REVIEW cannot publish; requires APPROVED + explicit publish + gates.",
                "prep_warnings": warnings,
                "admin_queue_url": f"/admin/ai-review?subject_name=Zoology&status=IN_REVIEW",
                "review_packet_path": f"/api/v1/cms/content-items/{r['id']}/review-packet",
                "admin_content_url": f"/admin/content/{r['id']}",
            }
        )

    exact_dups = [v for v in stem_groups.values() if len(v) > 1]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "campaign": {
            "name": "Zoology IN_REVIEW controlled ECAEP review",
            "scope": {"subject_name": "Zoology", "status": "IN_REVIEW", "content_type": "QUESTION"},
            "excludes": ["Chemistry", "Physics", "Botany", "DRAFT", "PUBLISHED", "SUPERSEDED", "unmapped_DRAFT"],
            "read_only": True,
            "no_auto_approve": True,
            "no_auto_publish": True,
            "no_quota_publishing": True,
            "provenance_is_not_ncert_certification": True,
        },
        "totals": {
            "matching_population": len(rows),
            "authoritative": True,
            "all_mapped": all(bool(i["concept_id"]) for i in items),
            "all_zoology": all(i["subject"] == "Zoology" for i in items),
            "all_in_review": all(i["status"] == "IN_REVIEW" for i in items),
        },
        "distributions": {
            "by_chapter": dict(chapters),
            "by_topic": dict(topics.most_common(30)),
            "by_class_level": dict(classes),
            "ncert_verification_level": dict(ncert_levels),
        },
        "prep_warning_counts": dict(warning_counts),
        "duplicate_risk": {
            "method": "exact_normalized_stem_within_campaign",
            "near_duplicate_semantic_search": "unavailable_in_this_script",
            "packet_method": "editorial_review_service.find_suspected_duplicates (exact stem; sample scan)",
            "exact_stem_duplicate_groups": len(exact_dups),
            "exact_stem_duplicate_items": sum(len(g) for g in exact_dups),
            "groups": exact_dups[:20],
        },
        "review_packet_fields": [
            "item_id",
            "academic.subject/chapter/topic/concept",
            "academic.class_level",
            "question.stem/options/correct_option/explanation/difficulty",
            "provenance",
            "ncert",
            "structural",
            "publication_eligibility",
            "suspected_duplicates",
            "checklist",
            "blocking_reasons (via eligibility + structural)",
        ],
        "ecaep_human_checklist": [
            "A Scientific correctness",
            "B Exactly one defensible answer",
            "C Four meaningful options",
            "D No duplicate/near-duplicate",
            "E Clear wording",
            "F No ambiguity",
            "G Correct chapter/topic/concept",
            "H NCERT alignment/evidence",
            "I Appropriate NEET relevance",
            "J Appropriate difficulty",
            "K Explanation correctness",
            "L Provenance completeness",
            "M Publication blockers",
        ],
        "operator_urls": {
            "admin_queue": "/admin/ai-review?subject_name=Zoology&status=IN_REVIEW",
            "api_queue": "/api/v1/cms/editorial-review-queue?subject_name=Zoology&status=IN_REVIEW",
        },
        "items": items,
        "db_meta": {},
    }


def to_markdown(report: dict[str, Any]) -> str:
    t = report["totals"]
    d = report["distributions"]
    lines = [
        "# Zoology IN_REVIEW — ECAEP campaign preparation (read-only)",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Scope",
        "",
        "- Subject: **Zoology**",
        "- Status: **IN_REVIEW**",
        f"- Authoritative matching population: **{t['matching_population']}**",
        "- Read-only preparation — no approve / publish / reject / certify / map",
        "- Provenance ≠ NCERT certification",
        "- Do **not** publish to hit mock quotas",
        "",
        "## Distributions",
        "",
        f"- Class levels: `{d['by_class_level']}`",
        f"- Chapters: `{d['by_chapter']}`",
        f"- NCERT verification levels (as stored): `{d['ncert_verification_level']}`",
        "",
        "## Prep warning rollup (heuristic — not SME decisions)",
        "",
    ]
    for k, v in sorted(report["prep_warning_counts"].items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{k}`: {v}")
    if not report["prep_warning_counts"]:
        lines.append("- (none)")
    dup = report["duplicate_risk"]
    lines += [
        "",
        "## Duplicate risk",
        "",
        f"- Exact stem duplicate groups in campaign: **{dup['exact_stem_duplicate_groups']}**",
        f"- Method: {dup['method']}",
        f"- Semantic near-dup: {dup['near_duplicate_semantic_search']}",
        "",
        "## Human review entry points",
        "",
        f"- Admin queue: `{report['operator_urls']['admin_queue']}`",
        f"- API queue: `{report['operator_urls']['api_queue']}`",
        "- Open each item's Admin content page / review packet; complete checklist before any decision",
        "",
        "## Item index (IDs only — open packet for full stem/options)",
        "",
    ]
    for i, item in enumerate(report["items"], 1):
        warns = ",".join(item["prep_warnings"]) if item["prep_warnings"] else "none"
        lines.append(
            f"{i}. `{item['id']}` · {item['chapter']} / {item['topic']} · class={item['class_level'] or 'unavailable'} · warnings={warns}"
        )
    lines += [
        "",
        "## Safety",
        "",
        "- Unmapped DRAFT backlog must remain frozen",
        "- This script never writes to `cms.content_items`",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="SELECT-only Zoology IN_REVIEW campaign prep")
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    url, meta = _sync_url()
    engine = create_engine(url)
    with engine.connect() as conn:
        report = build_report(conn)
    report["db_meta"] = meta

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"zoology_in_review_campaign_prep_{TODAY}.json"
    md_path = OUT_DIR / f"zoology_in_review_campaign_prep_{TODAY}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if not args.json_only:
        md_path.write_text(to_markdown(report), encoding="utf-8")

    print(f"matching_population={report['totals']['matching_population']}")
    print(f"wrote {json_path}")
    if not args.json_only:
        print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
