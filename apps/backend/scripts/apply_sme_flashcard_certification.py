"""Validate and merge SME decisions; apply auditable status transitions."""
from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from app.core.database import AsyncSessionLocal

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
OUT = REPO / "docs" / "acquisition" / "flashcards" / "SEED-V1"
BATCH = "FLASHCARD-SEED-V1-SME-CERT"

ALLOWED_STATUS = {"VERIFIED", "REVIEW", "REJECTED"}
ALLOWED_EVIDENCE = {
    "DIRECT_NCERT_SUPPORT",
    "STRONG_NCERT_SUPPORT",
    "PROJECT_VERIFIED",
    "NTA_VERIFIED",
    "AUTHORITATIVE_EXTERNAL",
    "INSUFFICIENT_EVIDENCE",
    "CONTRADICTED",
    "MISSING_SOURCE",
}
PROMOTE_OK = {
    "DIRECT_NCERT_SUPPORT",
    "STRONG_NCERT_SUPPORT",
    "PROJECT_VERIFIED",
    "NTA_VERIFIED",
    "AUTHORITATIVE_EXTERNAL",
}


def load_decisions() -> list[dict]:
    merged: list[dict] = []
    for name in (
        "sme_decisions_biology.json",
        "sme_decisions_chemistry.json",
        "sme_decisions_physics.json",
    ):
        data = json.loads((OUT / name).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("decisions") or data.get("cards") or []
        for d in data:
            assert d["id"], name
            assert d["new_status"] in ALLOWED_STATUS, d
            assert d["evidence_class"] in ALLOWED_EVIDENCE, d
            # Gate: never promote without adequate evidence class
            if d["new_status"] == "VERIFIED" and d["evidence_class"] not in PROMOTE_OK:
                raise SystemExit(f"Illegal VERIFIED with {d['evidence_class']}: {d['id']}")
            if d["new_status"] == "REJECTED" and d["evidence_class"] not in {
                "CONTRADICTED",
                "INSUFFICIENT_EVIDENCE",
            }:
                # allow REJECTED with CONTRADICTED primarily
                pass
            merged.append(d)
    ids = [d["id"] for d in merged]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate decision IDs")
    return merged


async def load_review_baseline() -> dict[str, dict]:
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                text(
                    """
                    SELECT ci.id::text AS id, ci.slug, ci.tags, ci.status,
                           cv.id::text AS version_id, cv.body,
                           s.code AS subject_code,
                           ch.class_level::text AS class_level_taxonomy,
                           ch.name AS chapter, t.name AS topic, co.name AS concept,
                           co.code AS concept_code
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.current_version_id
                    JOIN academic.concepts co ON co.id = ci.concept_id
                    JOIN academic.topics t ON t.id = co.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ci.deleted_at IS NULL AND ci.content_type='FLASHCARD'
                      AND ci.status='PUBLISHED'
                      AND cv.body->>'certification_status' = 'REVIEW'
                    """
                )
            )
        ).mappings().all()
    out = {}
    for r in rows:
        b = r["body"] or {}
        out[r["id"]] = {
            "id": r["id"],
            "version_id": r["version_id"],
            "slug": r["slug"],
            "tags": list(r["tags"] or []),
            "subject_code": r["subject_code"],
            "chapter": r["chapter"],
            "topic": r["topic"],
            "concept": r["concept"],
            "concept_code": r["concept_code"],
            "class_level_taxonomy": r["class_level_taxonomy"],
            "front": b.get("front"),
            "back": b.get("back"),
            "explanation": b.get("explanation"),
            "difficulty": b.get("difficulty"),
            "source": b.get("source"),
            "source_reference": b.get("source_reference"),
            "class_level_body": b.get("class_level"),
            "prev_status": b.get("certification_status"),
            "prev_reason": b.get("certification_reason"),
            "prev_provenance": b.get("certification_provenance"),
            "body": b,
        }
    return out


def provenance_from_evidence(ev: str, source: str | None) -> str:
    if ev in {"DIRECT_NCERT_SUPPORT", "STRONG_NCERT_SUPPORT"}:
        return "NCERT_VERIFIED"
    if ev == "NTA_VERIFIED":
        return "NTA_VERIFIED"
    if ev == "PROJECT_VERIFIED":
        return "PROJECT_VERIFIED"
    if ev == "AUTHORITATIVE_EXTERNAL":
        return "AUTHORITATIVE_EXTERNAL"
    if ev == "MISSING_SOURCE":
        return "MISSING"
    if ev == "CONTRADICTED":
        return "UNSUPPORTED"
    # INSUFFICIENT_EVIDENCE
    src = (source or "").upper()
    if src == "NCERT":
        return "UNSUPPORTED"
    return "MISSING"


async def apply(transitions: list[dict], *, dry_run: bool) -> Counter:
    stats: Counter = Counter()
    if dry_run:
        for t in transitions:
            stats[t["new_status"]] += 1
            stats[f"from_{t['prev_status']}_to_{t['new_status']}"] += 1
        return stats

    async with AsyncSessionLocal() as s:
        for t in transitions:
            body = dict(t["body"])
            body["certification_status"] = t["new_status"]
            body["certification_reason"] = t["reason"]
            body["certification_provenance"] = t["provenance_class"]
            body["certification_flags"] = t.get("flags") or []
            body["certification_evidence_class"] = t["evidence_class"]
            body["certification_claim"] = t["claim"]
            body["certification_evidence"] = t["evidence"]
            body["certified_at"] = t["auditor_timestamp"]
            body["certification_batch"] = BATCH
            body["certification_prev_status"] = t["prev_status"]
            await s.execute(
                text(
                    """
                    UPDATE cms.content_versions
                    SET body = CAST(:body AS jsonb)
                    WHERE id = CAST(:vid AS uuid)
                    """
                ),
                {"body": json.dumps(body), "vid": t["version_id"]},
            )
            tags = [x for x in (t["tags"] or []) if not str(x).startswith("audit:")]
            tags.append(f"audit:{t['new_status']}")
            if t["new_status"] == "REJECTED":
                await s.execute(
                    text(
                        """
                        UPDATE cms.content_items
                        SET tags = CAST(:tags AS text[]), status='ARCHIVED', updated_at=NOW()
                        WHERE id = CAST(:id AS uuid)
                        """
                    ),
                    {"tags": tags, "id": t["id"]},
                )
                await s.execute(
                    text(
                        """
                        UPDATE cms.content_versions
                        SET workflow_state='ARCHIVED'
                        WHERE id = CAST(:vid AS uuid)
                        """
                    ),
                    {"vid": t["version_id"]},
                )
                stats["archived_rejected"] += 1
            else:
                await s.execute(
                    text(
                        """
                        UPDATE cms.content_items
                        SET tags = CAST(:tags AS text[]), updated_at=NOW()
                        WHERE id = CAST(:id AS uuid)
                        """
                    ),
                    {"tags": tags, "id": t["id"]},
                )
            stats[t["new_status"]] += 1
            stats[f"from_{t['prev_status']}_to_{t['new_status']}"] += 1
        await s.commit()
    return stats


async def final_corpus_snapshot() -> dict:
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                text(
                    """
                    SELECT ci.id::text AS id, ci.slug, ci.status, ci.tags, cv.body,
                           s.code AS subject_code,
                           ch.class_level::text AS class_level_taxonomy,
                           ch.name AS chapter, t.name AS topic, co.name AS concept,
                           co.code AS concept_code
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.current_version_id
                    JOIN academic.concepts co ON co.id = ci.concept_id
                    JOIN academic.topics t ON t.id = co.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ci.deleted_at IS NULL AND ci.content_type='FLASHCARD'
                      AND ci.status='PUBLISHED'
                    ORDER BY s.code, ch.name, ci.slug
                    """
                )
            )
        ).mappings().all()
    cards = []
    for r in rows:
        b = r["body"] or {}
        subj = "BIOLOGY" if r["subject_code"] in {"BOTANY", "ZOOLOGY"} else r["subject_code"]
        cl = b.get("class_level") or r["class_level_taxonomy"] or "UNSET"
        cards.append(
            {
                "id": r["id"],
                "slug": r["slug"],
                "subject_code": r["subject_code"],
                "subject_bucket": subj,
                "class_effective": str(cl),
                "chapter": r["chapter"],
                "topic": r["topic"],
                "concept": r["concept"],
                "concept_code": r["concept_code"],
                "front": b.get("front"),
                "back": b.get("back"),
                "explanation": b.get("explanation"),
                "difficulty": b.get("difficulty"),
                "source": b.get("source"),
                "source_reference": b.get("source_reference"),
                "publication_status": r["status"],
                "audit_status": b.get("certification_status"),
                "audit_reason": b.get("certification_reason"),
                "provenance_class": b.get("certification_provenance"),
                "evidence_class": b.get("certification_evidence_class"),
                "verified_at": b.get("certified_at"),
                "class_level_taxonomy": r["class_level_taxonomy"],
                "class_level_body": b.get("class_level"),
            }
        )
    return {"cards": cards}


def write_reports(
    *,
    transitions: list[dict],
    snapshot: dict,
    prev: dict,
    apply_stats: Counter,
    started: str,
) -> None:
    cards = snapshot["cards"]
    counts = Counter(c["audit_status"] for c in cards)
    subj = Counter(c["subject_bucket"] for c in cards)
    classes = Counter(c["class_effective"] for c in cards)
    prov = Counter(c["provenance_class"] or "MISSING" for c in cards)
    evid = Counter(c.get("evidence_class") or "n/a" for c in cards)

    newly_v = sum(1 for t in transitions if t["new_status"] == "VERIFIED")
    newly_r = sum(1 for t in transitions if t["new_status"] == "REVIEW")
    newly_x = sum(1 for t in transitions if t["new_status"] == "REJECTED")

    # transitions log
    (OUT / "sme_transitions.json").write_text(
        json.dumps(transitions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    fields = [
        "id",
        "subject_code",
        "subject_bucket",
        "class_effective",
        "chapter",
        "topic",
        "front",
        "back",
        "explanation",
        "difficulty",
        "source",
        "source_reference",
        "publication_status",
        "audit_status",
        "audit_reason",
        "provenance_class",
        "evidence_class",
        "verified_at",
    ]
    with (OUT / "card_audit.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(cards)

    (OUT / "card_audit.json").write_text(
        json.dumps(cards, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    review = [c for c in cards if c["audit_status"] == "REVIEW"]
    rejected = [c for c in cards if c["audit_status"] == "REJECTED"]
    verified = [c for c in cards if c["audit_status"] == "VERIFIED"]

    def md_cards(rows: list[dict], limit: int = 300) -> str:
        lines = []
        for r in rows[:limit]:
            lines.append(
                f"- `{r['id']}` [{r['subject_bucket']}/{r['chapter']}] "
                f"**{(r.get('front') or '')[:90]}** — {r.get('audit_reason') or ''} "
                f"({r.get('evidence_class') or r.get('provenance_class')})"
            )
        return "\n".join(lines) or "- None"

    (OUT / "review_cards.md").write_text(
        f"# Review flashcards (post-SME)\n\nCount: **{len(review)}**\n\n{md_cards(review)}\n",
        encoding="utf-8",
    )
    (OUT / "rejected_cards.md").write_text(
        f"# Rejected flashcards (post-SME)\n\nCount: **{len(rejected)}**\n\n{md_cards(rejected)}\n",
        encoding="utf-8",
    )

    cov: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for c in cards:
        cov[c["subject_bucket"]][c["class_effective"]][c["chapter"]] += 1
    cov_lines = ["# Coverage report (post-SME)", ""]
    for subj_name in sorted(cov):
        cov_lines.append(f"## {subj_name}")
        for cl in sorted(cov[subj_name]):
            cov_lines.append(f"### Class {cl}")
            for ch, n in sorted(cov[subj_name][cl].items(), key=lambda x: -x[1]):
                cov_lines.append(f"- {ch}: **{n}**")
        cov_lines.append("")
    (OUT / "coverage_report.md").write_text("\n".join(cov_lines) + "\n", encoding="utf-8")

    (OUT / "provenance_report.md").write_text(
        "\n".join(
            [
                "# Provenance report (post-SME)",
                "",
                f"- NCERT_VERIFIED: **{prov.get('NCERT_VERIFIED', 0)}**",
                f"- NTA_VERIFIED: **{prov.get('NTA_VERIFIED', 0)}**",
                f"- PROJECT_VERIFIED: **{prov.get('PROJECT_VERIFIED', 0)}**",
                f"- AUTHORITATIVE_EXTERNAL: **{prov.get('AUTHORITATIVE_EXTERNAL', 0)}**",
                f"- UNSUPPORTED: **{prov.get('UNSUPPORTED', 0)}**",
                f"- MISSING: **{prov.get('MISSING', 0)}**",
                "",
                "## Evidence classes (SME pass)",
                *[f"- {k}: **{v}**" for k, v in sorted(evid.items())],
                "",
            ]
        ),
        encoding="utf-8",
    )

    final_v = counts.get("VERIFIED", 0)
    final_r = counts.get("REVIEW", 0)
    final_x = counts.get("REJECTED", 0)
    total = len(cards)
    pct = round(100.0 * final_v / total, 2) if total else 0.0

    # Remaining REVIEW reasons
    why = Counter()
    for c in review:
        ev = c.get("evidence_class") or "UNSPECIFIED"
        why[ev] += 1

    verdict = "AMBER"
    rationale = [
        f"Previous VERIFIED={prev['VERIFIED']} REVIEW={prev['REVIEW']} REJECTED={prev['REJECTED']}",
        f"SME promotions to VERIFIED from REVIEW: {newly_v}",
        f"Remaining REVIEW: {final_r} ({dict(why)})",
        "Baseline VERIFIED cards preserved (not mass-reset).",
        "Fluids + Rotational remain MISSING_SOURCE (Class 11 PDFs absent from StudyMaterial (2).zip).",
        "Biomolecules chapter.class_level intentionally NULL (seed policy); content certified only when evidence supports.",
    ]
    if final_r == 0 and final_x == 0 and final_v == total:
        verdict = "GREEN"
        rationale.append("All published cards VERIFIED with claim-level evidence.")
    elif final_x > 0 and final_v < total * 0.5:
        verdict = "RED"

    summary_md = f"""# Verification summary — Flashcard Seed V1 SME Certification

**Verdict: {verdict}**

| Metric | Count |
|---|---:|
| Previous VERIFIED | {prev['VERIFIED']} |
| Previous REVIEW | {prev['REVIEW']} |
| Previous REJECTED | {prev['REJECTED']} |
| Newly VERIFIED (from REVIEW) | {newly_v} |
| Newly kept REVIEW | {newly_r} |
| Newly REJECTED | {newly_x} |
| Final VERIFIED | {final_v} |
| Final REVIEW | {final_r} |
| Final REJECTED | {final_x} |
| Verification % | {pct}% |
| TOTAL PUBLISHED | {total} |
| BIOLOGY | {subj.get('BIOLOGY', 0)} |
| CHEMISTRY | {subj.get('CHEMISTRY', 0)} |
| PHYSICS | {subj.get('PHYSICS', 0)} |
| CLASS 11 | {classes.get('11', 0)} |
| CLASS 12 | {classes.get('12', 0)} |
| CLASS UNSET | {classes.get('UNSET', 0)} |
| NCERT_VERIFIED provenance | {prov.get('NCERT_VERIFIED', 0)} |
| NTA_VERIFIED | {prov.get('NTA_VERIFIED', 0)} |
| PROJECT_VERIFIED | {prov.get('PROJECT_VERIFIED', 0)} |
| EXTERNAL | {prov.get('AUTHORITATIVE_EXTERNAL', 0)} |
| UNSUPPORTED | {prov.get('UNSUPPORTED', 0)} |
| MISSING | {prov.get('MISSING', 0)} |

## Why REVIEW remains
{chr(10).join(f'- {k}: **{v}**' for k, v in why.most_common()) or '- None'}

## Rationale
{chr(10).join('- ' + x for x in rationale)}

## Publication gate
- VERIFIED → Certified Study Mode (`certified_only=true`)
- REVIEW → practice with Needs review label (not Certified)
- REJECTED → archived / excluded
"""
    (OUT / "verification_summary.md").write_text(summary_md, encoding="utf-8")

    sme_report = summary_md + f"""
## SME batch
- batch_id: `{BATCH}`
- started_at: {started}
- finished_at: {datetime.now(UTC).isoformat()}
- apply_stats: `{dict(apply_stats)}`

## Transition audit
Every REVIEW card was dispositioned. See `sme_transitions.json` for prev→new, claim, evidence, evidence_class, timestamp.

## Taxonomy note — Biomolecules
`academic.chapters.class_level` for Biomolecules remains **NULL by design** (seed.py / RS-003-B-1). Cards keep body `class_level=11` aligned with NCERT Class 11 Ch 9 when content is certified; chapter taxonomy was not force-filled.

## Source discipline
No fabricated URLs. Page numbers in SME evidence, when present, are taken from PDF print labels / extractor context and must be treated as extractor-derived, not guaranteed exam-board citations.
"""
    (OUT / "sme_certification_report.md").write_text(sme_report, encoding="utf-8")
    (OUT / "audit_report.md").write_text(sme_report, encoding="utf-8")

    results = {
        "batch": BATCH,
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "previous": prev,
        "newly_verified": newly_v,
        "newly_review": newly_r,
        "newly_rejected": newly_x,
        "final_counts": dict(counts),
        "verification_pct": pct,
        "subject_counts": dict(subj),
        "class_counts": dict(classes),
        "provenance_counts": dict(prov),
        "evidence_counts": dict(evid),
        "review_why": dict(why),
        "apply_stats": dict(apply_stats),
        "verdict": verdict,
        "verdict_rationale": rationale,
        "total_published": total,
    }
    (OUT / "sme_results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


async def amain() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--authorize-apply", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.authorize_apply:
        print("Pass --dry-run or --authorize-apply")
        return 2

    started = datetime.now(UTC).isoformat()
    decisions = load_decisions()
    baseline = await load_review_baseline()
    if set(d["id"] for d in decisions) != set(baseline):
        missing = set(baseline) - {d["id"] for d in decisions}
        extra = {d["id"] for d in decisions} - set(baseline)
        raise SystemExit(f"Decision/queue mismatch missing={len(missing)} extra={len(extra)} {list(missing)[:3]} {list(extra)[:3]}")

    # Previous corpus counts
    async with AsyncSessionLocal() as s:
        prev_rows = (
            await s.execute(
                text(
                    """
                    SELECT cv.body->>'certification_status' AS st, count(*)
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id=ci.current_version_id
                    WHERE ci.deleted_at IS NULL AND ci.content_type='FLASHCARD' AND ci.status='PUBLISHED'
                    GROUP BY 1
                    """
                )
            )
        ).all()
    prev = {"VERIFIED": 0, "REVIEW": 0, "REJECTED": 0}
    for st, n in prev_rows:
        if st in prev:
            prev[st] = n

    transitions = []
    for d in decisions:
        base = baseline[d["id"]]
        transitions.append(
            {
                "id": d["id"],
                "version_id": base["version_id"],
                "tags": base["tags"],
                "body": base["body"],
                "prev_status": base["prev_status"],
                "new_status": d["new_status"],
                "reason": d.get("reason") or "",
                "claim": d.get("claim") or "",
                "evidence": d.get("evidence") or "",
                "evidence_class": d["evidence_class"],
                "provenance_class": provenance_from_evidence(d["evidence_class"], base.get("source")),
                "flags": [d["evidence_class"]],
                "auditor_timestamp": started,
                "subject_code": base["subject_code"],
                "chapter": base["chapter"],
                "front": base["front"],
            }
        )

    apply_stats = await apply(transitions, dry_run=args.dry_run)
    if args.dry_run:
        # synthesize post-state for reports without writing
        # rebuild snapshot mentally: start from all published, overlay transitions
        async with AsyncSessionLocal() as s:
            all_rows = (
                await s.execute(
                    text(
                        """
                        SELECT ci.id::text AS id, ci.slug, ci.status, cv.body,
                               s.code AS subject_code,
                               ch.class_level::text AS class_level_taxonomy,
                               ch.name AS chapter, t.name AS topic, co.name AS concept,
                               co.code AS concept_code
                        FROM cms.content_items ci
                        JOIN cms.content_versions cv ON cv.id = ci.current_version_id
                        JOIN academic.concepts co ON co.id = ci.concept_id
                        JOIN academic.topics t ON t.id = co.topic_id
                        JOIN academic.chapters ch ON ch.id = t.chapter_id
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE ci.deleted_at IS NULL AND ci.content_type='FLASHCARD' AND ci.status='PUBLISHED'
                        """
                    )
                )
            ).mappings().all()
        by_id = {t["id"]: t for t in transitions}
        cards = []
        for r in all_rows:
            b = dict(r["body"] or {})
            if r["id"] in by_id:
                t = by_id[r["id"]]
                b["certification_status"] = t["new_status"]
                b["certification_reason"] = t["reason"]
                b["certification_provenance"] = t["provenance_class"]
                b["certification_evidence_class"] = t["evidence_class"]
                b["certified_at"] = t["auditor_timestamp"]
            subj = "BIOLOGY" if r["subject_code"] in {"BOTANY", "ZOOLOGY"} else r["subject_code"]
            cl = b.get("class_level") or r["class_level_taxonomy"] or "UNSET"
            cards.append(
                {
                    "id": r["id"],
                    "slug": r["slug"],
                    "subject_code": r["subject_code"],
                    "subject_bucket": subj,
                    "class_effective": str(cl),
                    "chapter": r["chapter"],
                    "topic": r["topic"],
                    "concept": r["concept"],
                    "concept_code": r["concept_code"],
                    "front": b.get("front"),
                    "back": b.get("back"),
                    "explanation": b.get("explanation"),
                    "difficulty": b.get("difficulty"),
                    "source": b.get("source"),
                    "source_reference": b.get("source_reference"),
                    "publication_status": r["status"],
                    "audit_status": b.get("certification_status"),
                    "audit_reason": b.get("certification_reason"),
                    "provenance_class": b.get("certification_provenance"),
                    "evidence_class": b.get("certification_evidence_class"),
                    "verified_at": b.get("certified_at"),
                }
            )
        snapshot = {"cards": cards}
    else:
        snapshot = await final_corpus_snapshot()

    write_reports(
        transitions=transitions,
        snapshot=snapshot,
        prev=prev,
        apply_stats=apply_stats,
        started=started,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
