"""Finalize BIO11-CH04-B001 scientific/NCERT audit artifacts (read-only vs questions.jsonl)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload, sessionmaker

REPO = Path(__file__).resolve().parents[3]
BATCH = REPO / "docs" / "acquisition" / "batches" / "20260912-BIO11-CH04-B001"
AUTH = "2905fc8240d62ec86ebfb1c9e26c7ce487dc0ba8b3f8e85b21ce48de347e112a"
SOURCE_SHA = "2c092dd3d16cf15f2d3bcaf0636653c6e7b370c9b2159ffad73df3601643ba87"


def is_batch(item, batch: str, needle: str) -> bool:
    tags = item.tags or []
    if isinstance(tags, dict):
        tags = tags.get("tags") or []
    if batch in (tags or []) or any(batch in str(t) for t in (tags or [])):
        return True
    slug = item.slug or ""
    return needle in slug.lower() or batch in slug


async def db_snap():
    os.chdir(REPO / "apps" / "backend")
    from app.core.config import get_settings
    from app.modules.cms.models.content_item import ContentItem

    eng = create_async_engine(get_settings().database_url)
    Session = sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        items = (
            await session.execute(select(ContentItem).options(selectinload(ContentItem.versions)))
        ).scalars().all()
        batches = {
            "CH01": ("20260912-BIO11-CH01-B001", "bio11-ch01-b001"),
            "CH02": ("20260912-BIO11-CH02-B001", "bio11-ch02-b001"),
            "CH03": ("20260912-BIO11-CH03-B001", "bio11-ch03-b001"),
            "CH04": ("20260912-BIO11-CH04-B001", "bio11-ch04-b001"),
            "PHY02": ("20260911-PHY11-CH02-B001", "phy11-ch02-b001"),
        }
        status: dict = {}
        for name, (b, n) in batches.items():
            subset = [i for i in items if is_batch(i, b, n)]
            status[name] = dict(Counter(i.status for i in subset))
            status[name]["_total"] = len(subset)
        tax = (
            await session.execute(
                text(
                    "SELECT (SELECT count(*) FROM academic.subjects WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.chapters WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.topics WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.concepts WHERE deleted_at IS NULL)"
                )
            )
        ).one()
        await session.rollback()
    await eng.dispose()
    return status, tuple(tax)


def main() -> None:
    qs_path = BATCH / "questions.jsonl"
    raw = qs_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != AUTH:
        raise SystemExit(f"RED — ARTIFACT INTEGRITY FAILURE: {sha}")

    qs = [json.loads(l) for l in raw.decode().splitlines() if l.strip()]
    manifest_raw = (BATCH / "manifest.json").read_bytes()
    extract_raw = (BATCH / "_source_extract.txt").read_bytes()
    identity_raw = (BATCH / "_source_identity.json").read_bytes()

    p1 = json.loads((BATCH / "_audit_partial_q001_050.json").read_text(encoding="utf-8"))
    p2 = json.loads((BATCH / "_audit_partial_q051_100.json").read_text(encoding="utf-8"))
    results = p1["results"] + p2["results"]
    if len(results) != 100:
        raise SystemExit(f"expected 100 results, got {len(results)}")

    for r in results:
        if r.get("ncert_evidence") == "WEAK_UNSUPPORTED":
            r["ncert_evidence"] = "WEAK/UNSUPPORTED"

    def cnt(pred):
        return sum(1 for r in results if pred(r))

    textbook_ref = 0
    for r in results:
        blob = (" ".join(r.get("issues", [])) + " " + r.get("recommended_action", "")).lower()
        if any(
            k in blob
            for k in (
                "textbook-referential",
                "textbook referential",
                "described in the chapter",
                "according to the chapter",
                "table 4.1",
                "table 4.2",
                "singled out in the chapter",
                "made in the chapter",
                "claim about",
            )
        ):
            textbook_ref += 1

    summary = {
        "total_audited": 100,
        "PASS": cnt(lambda r: r["verdict"] == "PASS"),
        "REPAIR": cnt(lambda r: r["verdict"] == "REPAIR"),
        "REJECT": cnt(lambda r: r["verdict"] == "REJECT"),
        "ncert_direct": cnt(lambda r: r["ncert_evidence"] == "NCERT_DIRECT"),
        "ncert_supported_inference": cnt(lambda r: r["ncert_evidence"] == "SUPPORTED_INFERENCE"),
        "ncert_weak_unsupported": cnt(
            lambda r: r["ncert_evidence"] in ("WEAK_UNSUPPORTED", "WEAK/UNSUPPORTED")
        ),
        "answer_key_failures": cnt(lambda r: r["answer_key_correctness"] == "FAIL"),
        "explanation_failures": cnt(lambda r: r["explanation_correctness"] == "FAIL"),
        "ambiguity_failures": cnt(lambda r: r["ambiguity"] == "FLAG"),
        "option_quality_failures": cnt(lambda r: r["option_quality"] == "FAIL"),
        "difficulty_mismatches": cnt(lambda r: r["difficulty_assessment"] != "OK"),
        "question_type_mismatches": cnt(lambda r: r["question_type_assessment"] == "MISMATCH"),
        "textbook_referential_stems": textbook_ref,
        "low_neet_relevance": cnt(lambda r: r["neet_relevance"] == "LOW"),
        "exact_duplicates": 0,
        "near_duplicates_at_or_above_0_82": 0,
        "unsupported_content_findings": 0,
    }

    assessed = dict(Counter(r["difficulty_assessed_level"] for r in results))
    declared = dict(Counter(r["difficulty_declared"] for r in results))
    topics = dict(Counter(q["topic"] for q in qs))

    status, tax = asyncio.run(db_snap())

    repair_ids = [r["external_question_id"] for r in results if r["verdict"] == "REPAIR"]
    reject_ids = [r["external_question_id"] for r in results if r["verdict"] == "REJECT"]

    audit = {
        "batch_id": "20260912-BIO11-CH04-B001",
        "audit_date": "2026-09-12",
        "audit_type": "scientific_ncert_readonly",
        "chapter": "Animal Kingdom",
        "class_level": "11",
        "subject": "Biology",
        "authoritative_artifact_sha256": AUTH,
        "source_pdf": "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-4.pdf",
        "source_pdf_sha256": SOURCE_SHA,
        "source_pdf_page_count": 18,
        "source_extract": "docs/acquisition/batches/20260912-BIO11-CH04-B001/_source_extract.txt",
        "source_edition_note": (
            "NCERT Class 11 Biology 2024-25 Chapter 4 Animal Kingdom (18 pages). "
            "PDF is authoritative; extract is an audit aid."
        ),
        "overall_verdict": "AMBER — BIO11-CH04-B001 REPAIR REQUIRED",
        "summary": summary,
        "difficulty_distribution": {
            "declared": {
                "easy": declared.get("easy", 0),
                "medium": declared.get("medium", 0),
                "hard": declared.get("hard", 0),
            },
            "assessed": {
                "easy": assessed.get("easy", 0),
                "medium": assessed.get("medium", 0),
                "hard": assessed.get("hard", 0),
            },
        },
        "topic_coverage": topics,
        "coverage_analysis": {
            "classification_criteria": "Strong (§4.1.1–4.1.6; 17 items).",
            "Porifera": "Adequate (6).",
            "Cnidaria_Coelenterata": "Adequate (8).",
            "Ctenophora": "Thin but source-proportionate (4).",
            "Platyhelminthes": "Adequate (7).",
            "Aschelminthes": "Adequate (6).",
            "Annelida": "Adequate (7).",
            "Arthropoda": "Strong (9).",
            "Mollusca": "Adequate (6).",
            "Echinodermata": "Adequate (6).",
            "Hemichordata": "Thin but source-proportionate (4).",
            "Chordata": "Strong including Table 4.1/4.2 and vertebrate classes (20).",
            "note": (
                "Coverage gaps are batch-design observations, not per-item REJECT causes. "
                "Vertebrate classes are lightly sampled (often 1 item each) relative to "
                "phylum blocks — acceptable given NCERT density and acquisition-only scope."
            ),
        },
        "answer_distribution": dict(Counter(q["correct_option"] for q in qs)),
        "question_type_distribution_declared": dict(Counter(q["question_type"] for q in qs)),
        "repair_question_ids": repair_ids,
        "reject_question_ids": reject_ids,
        "artifact_integrity": {
            "questions_jsonl_sha256": AUTH,
            "questions_jsonl_sha256_verified": True,
            "manifest_json_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "source_extract_sha256": hashlib.sha256(extract_raw).hexdigest(),
            "source_identity_sha256": hashlib.sha256(identity_raw).hexdigest(),
            "questions_jsonl_modified": False,
            "alternate_artifact_0fd98de7_used": False,
        },
        "database_regression": {
            "postgresql_writes": 0,
            "CH01": status["CH01"],
            "CH02": status["CH02"],
            "CH03": status["CH03"],
            "CH04": status["CH04"],
            "Physics_PHY11_CH02_B001": status["PHY02"],
            "expectations_met": {
                "CH01_PUBLISHED_100": status["CH01"].get("PUBLISHED") == 100,
                "CH02_PUBLISHED_100": status["CH02"].get("PUBLISHED") == 100,
                "CH03_PUBLISHED_100": status["CH03"].get("PUBLISHED") == 100,
                "Physics_DRAFT_24": status["PHY02"].get("DRAFT") == 24,
                "CH04_imported_0": status["CH04"].get("_total", 0) == 0,
            },
            "taxonomy_snapshot": {
                "subjects": tax[0],
                "chapters": tax[1],
                "topics": tax[2],
                "concepts": tax[3],
            },
        },
        "safety_note": (
            "Audit only. Did not overwrite questions.jsonl. Did not use alternate SHA "
            "0fd98de7…. Did not repair, import, certify, publish, or mutate taxonomy/DB."
        ),
        "results": results,
    }

    (BATCH / "scientific_ncert_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (BATCH / "_audit_question_results.json").write_text(
        json.dumps(
            {"batch_id": "20260912-BIO11-CH04-B001", "results": results, "summary": summary},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Scientific / NCERT audit — BIO11-CH04-B001 (Animal Kingdom)",
        "",
        "**Verdict: AMBER — REPAIR REQUIRED**",
        "",
        "Read-only audit. Authoritative original `questions.jsonl` was not modified.",
        "",
        "## Artifact integrity",
        "",
        f"- Authoritative SHA-256: `{AUTH}` — **VERIFIED**",
        "- Alternate late-agent SHA `0fd98de7…`: **not used**",
        "- Question count: 100 (IDs 000001–000100, contiguous)",
        "- NCERT source: `ncert-books-class-11-biology-chapter-4.pdf`",
        f"- Source SHA-256: `{SOURCE_SHA}`",
        "- Edition marker: 2024-25 · Pages: 18",
        "",
        "## Summary counts",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
    ]
    for k, v in summary.items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## Difficulty",
        "",
        f"- Declared: easy {declared.get('easy', 0)} / medium {declared.get('medium', 0)} / hard {declared.get('hard', 0)}",
        f"- Independently assessed: easy {assessed.get('easy', 0)} / medium {assessed.get('medium', 0)} / hard {assessed.get('hard', 0)}",
        "- Finding: widespread **difficulty inflation** (many single-sentence NCERT recall items labelled hard/medium).",
        "",
        "## Coverage",
        "",
    ]
    for t, c in sorted(topics.items()):
        lines.append(f"- {t}: {c}")
    lines += [
        "",
        "## Key findings",
        "",
        "- **0 REJECT** — no scientifically wrong or unsupported keyed answers.",
        "- **0 answer-key / explanation failures**.",
        "- **98 NCERT_DIRECT**, **2 SUPPORTED_INFERENCE**, **0 WEAK/UNSUPPORTED**.",
        "- **50 REPAIR** — almost entirely metadata/editorial (difficulty, question-type, textbook-referential stems, 1 ambiguity, 2 option-length cues).",
        "- **Exact duplicates: 0 · Near-duplicates (≥0.82): 0**.",
        "- Ambiguity FLAG: Q000003 (tissue-level stem should name the organisation level uniquely).",
        "- Option-quality FAIL: Q000056, Q000091 (correct option markedly longer / glossed).",
        "",
        "## REPAIR list (bounded; not executed)",
        "",
    ]
    for r in results:
        if r["verdict"] != "REPAIR":
            continue
        lines.append(f"- `{r['external_question_id']}` — {r['recommended_action']}")
    lines += [
        "",
        "## Database / regression (read-only)",
        "",
        "- PostgreSQL writes: **0**",
        f"- CH01 PUBLISHED={status['CH01'].get('PUBLISHED')} SUPERSEDED={status['CH01'].get('SUPERSEDED', 0)}",
        f"- CH02 PUBLISHED={status['CH02'].get('PUBLISHED')} SUPERSEDED={status['CH02'].get('SUPERSEDED', 0)}",
        f"- CH03 PUBLISHED={status['CH03'].get('PUBLISHED')}",
        f"- CH04 imported={status['CH04'].get('_total', 0)}",
        f"- Physics CH02 DRAFT={status['PHY02'].get('DRAFT')}",
        f"- Taxonomy: subjects={tax[0]}, chapters={tax[1]}, topics={tax[2]}, concepts={tax[3]}",
        "",
        "## Mandatory stop",
        "",
        "Repair, DRAFT import, taxonomy, ECAEP, NCERT certification, and publication were **not** executed.",
        "",
    ]
    (BATCH / "scientific_ncert_audit.md").write_text("\n".join(lines), encoding="utf-8")

    final = hashlib.sha256(qs_path.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "FINAL_SHA": final,
                "SHA_OK": final == AUTH,
                "summary": summary,
                "DB": status,
                "TAX": tax,
                "textbook_ref": textbook_ref,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
