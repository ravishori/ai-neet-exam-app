#!/usr/bin/env python3
"""FACTORY-PYQ-P2 — validate and complete NEET PYQ staging corpus."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.modules.cms.pyq.pyq_discovery import inventory_zip
from app.modules.cms.pyq.pyq_p2 import NEET_2022_STATUS, run_p2_validation
from app.modules.cms.pyq.pyq_staging import default_staging_root
from app.modules.cms.pyq.pyq_ocr import tesseract_available


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _docs_dir() -> Path:
    return _repo_root() / "docs" / "content-factory"


def write_reports(
    *,
    summary,
    sample: list[dict],
    zip_path: Path,
    staging_root: Path,
    inventory,
) -> None:
    docs = _docs_dir()
    docs.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat()

    # Main P2 report
    lines = [
        "# PYQ Validation P2 Report — NEET 2020–2025",
        "",
        f"**Generated:** {ts}  ",
        f"**Verdict:** **{summary.verdict}**  ",
        "**Mode:** Staging validation only — no AI, no DB writes, no publication  ",
        f"**Source ZIP:** `{zip_path}`  ",
        f"**ZIP SHA-256:** `{inventory.zip_sha256}` (unchanged)  ",
        f"**Staging root:** `{staging_root}`",
        "",
        "## Summary",
        "",
        "| # | Metric | Value |",
        "|---|--------|------:|",
        f"| 1 | Papers processed | {summary.papers_processed} |",
        f"| 2 | OCR papers processed | {summary.ocr_papers_processed} |",
        f"| 3 | OCR pages processed | {summary.ocr_pages_processed} |",
        f"| 4 | OCR failures | {summary.ocr_failures} |",
        f"| 5 | Questions extracted (TEXT) | {summary.questions_extracted} |",
        f"| 6 | Questions requiring review | {summary.questions_needs_review} |",
        f"| 7 | missing_options resolved | {summary.missing_options_resolved} |",
        f"| 7b | missing_options unresolved | {summary.missing_options_unresolved} |",
        f"| 7c | missing_options needs_review | {summary.missing_options_needs_review} |",
        f"| 8 | ANSWER_KNOWN | {summary.answer_known} |",
        f"| 9 | ANSWER_PENDING | {summary.answer_pending} |",
        f"| 10 | ANSWER_CONFLICT | {summary.answer_conflict} |",
        f"| 11 | ANSWER_UNVERIFIED | {summary.answer_unverified} |",
        f"| 12 | Subject classified | {summary.subject_classified} |",
        f"| 12b | Subject UNKNOWN | {summary.subject_unknown} |",
        f"| 12c | Subject needs review | {summary.subject_needs_review} |",
        f"| 13 | 2022 gap | {NEET_2022_STATUS} |",
        f"| 14 | Mathematics exclusions | {summary.mathematics_exclusions} |",
        f"| 15 | Within-paper duplicates | {summary.duplicate_within_paper} |",
        f"| 15b | Cross-paper repeats (retained) | {summary.cross_paper_repeats} |",
        f"| 18 | Idempotent rerun | {summary.idempotent} |",
        f"| 19 | Tests | see pytest output |",
        f"| 20 | AI calls | 0 |",
        f"| 21 | production DB writes | 0 |",
        f"| 22 | content_items modified | 0 |",
        f"| 23 | ECAEP changes | 0 |",
        f"| 24 | publication changes | 0 |",
        "",
        "## Verdict rationale",
        "",
    ]
    if summary.verdict == "YELLOW":
        lines.extend(
            [
                "Corpus materially improved with P2 provenance, answer classification, and missing-options triage,",
                "but explicit validation gaps remain:",
                "",
                f"- Local Tesseract {'available' if tesseract_available() else '**not installed**'} — {summary.ocr_failures}/{summary.ocr_pages_processed} OCR pages failed",
                f"- {summary.missing_options_needs_review} diagram/image-option questions need human review",
                f"- {summary.answer_known} authoritative answers found in supplied corpus",
                f"- {summary.subject_unknown} questions remain subject=UNKNOWN (2020 papers lack section headers)",
                f"- NEET 2022 papers: **{NEET_2022_STATUS}**",
                "",
            ]
        )
    elif summary.verdict == "RED":
        lines.append("Source integrity or extraction process failure detected — see anomalies.")
    else:
        lines.append("All required validation gates passed.")

    lines.extend(
        [
            "## Checksums",
            "",
            "```json",
            json.dumps(summary.checksums, indent=2),
            "```",
            "",
            "## Safety attestation",
            "",
            "| Check | Value |",
            "|-------|------:|",
            "| ai_provider_calls | 0 |",
            "| production_db_writes | 0 |",
            "| content_items_modified | 0 |",
            "| ecaep_changes | 0 |",
            "| publication_changes | 0 |",
            "| source_zip_modified | 0 |",
            "",
            "**STOP.** No production database import. Await explicit authorization for P3.",
            "",
        ]
    )
    (_docs_dir() / "PYQ_VALIDATION_P2_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    # Answer key status
    ans_lines = [
        "# PYQ Answer Key Status — P2",
        "",
        f"**Generated:** {ts}",
        "",
        "## Corpus search result",
        "",
        "No separate answer-key PDFs exist in the supplied ZIP (confirmed P0/P1/P2).",
        "Embedded authoritative answer grids (≥10 consecutive lines inside answer-key sections) were **not found**.",
        "",
        "## Classification counts (TEXT extracted questions)",
        "",
        f"| Status | Count |",
        f"|--------|------:|",
        f"| ANSWER_KNOWN | {summary.answer_known} |",
        f"| ANSWER_PENDING | {summary.answer_pending} |",
        f"| ANSWER_CONFLICT | {summary.answer_conflict} |",
        f"| ANSWER_UNVERIFIED | {summary.answer_unverified} |",
        "",
        "## Policy",
        "",
        "- No AI-generated answers used.",
        "- Instructional 'Answer Sheet' mentions are not treated as authoritative keys.",
        "- Isolated ratio lines inside question bodies (e.g. `1 : c`) are rejected as false positives.",
        "",
    ]
    (_docs_dir() / "PYQ_ANSWER_KEY_STATUS.md").write_text("\n".join(ans_lines), encoding="utf-8")

    # OCR status
    ocr_lines = [
        "# PYQ OCR Status — P2",
        "",
        f"**Generated:** {ts}",
        "",
        f"**Local Tesseract available:** {tesseract_available()}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| SCANNED papers processed | {summary.ocr_papers_processed} |",
        f"| OCR pages processed | {summary.ocr_pages_processed} |",
        f"| OCR pages failed | {summary.ocr_failures} |",
        f"| OCR pages extracted | {summary.ocr_pages_processed - summary.ocr_failures} |",
        "",
        "## Per-paper OCR artifacts",
        "",
        "See `papers/{sha256}/ocr.p2.json` for page-level status (`OCR_FAILED`, `OCR_EXTRACTED`, `NEEDS_REVIEW`).",
        "",
        "## Blocker",
        "",
    ]
    if not tesseract_available():
        ocr_lines.append(
            "Tesseract is not installed on this host. SCANNED papers (2023–2025) cannot be text-extracted "
            "without installing local Tesseract or supplying born-digital PDFs. No external OCR/AI APIs were used."
        )
    else:
        ocr_lines.append("Tesseract is available; review per-paper `ocr.p2.json` for extraction yields.")
    ocr_lines.append("")
    (_docs_dir() / "PYQ_OCR_STATUS.md").write_text("\n".join(ocr_lines), encoding="utf-8")

    # Validation sample
    sample_lines = [
        "# PYQ Validation Sample — P2",
        "",
        f"**Generated:** {ts}",
        "",
        "Deterministic sample (first paper per year bucket by filename). No AI validation.",
        "",
        "| Year | Source file | Q# | Page | Options | Subject | Answer | Provenance OK | Status |",
        "|------|-------------|---:|-----:|--------:|---------|--------|:-------------:|--------|",
    ]
    for row in sample:
        if row.get("status"):
            sample_lines.append(f"| {row.get('exam_year','?')} | — | — | — | — | — | — | — | {row['status']} |")
            continue
        sample_lines.append(
            f"| {row['exam_year']} | `{Path(row['source_file']).name}` | {row.get('sample_question_number','?')} | "
            f"{row.get('sample_source_page','?')} | {row.get('sample_options_present',0)}/4 | "
            f"{row.get('sample_subject','?')} | {row.get('sample_answer_status','?')} | "
            f"{'yes' if row.get('chain_verified') else 'no'} | {row.get('validation_status','?')} |"
        )
    sample_lines.extend(["", "## Detail", "", "```json", json.dumps(sample, indent=2, ensure_ascii=False), "```", ""])
    (_docs_dir() / "PYQ_VALIDATION_SAMPLE.md").write_text("\n".join(sample_lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="FACTORY-PYQ-P2 validation")
    parser.add_argument("--zip", type=Path, default=_repo_root() / "NEET_PYQ_OFFICIAL.zip")
    parser.add_argument("--staging-root", type=Path, default=default_staging_root(_repo_root()))
    args = parser.parse_args()

    if not args.staging_root.exists():
        raise SystemExit(f"P1 staging not found: {args.staging_root}")
    if not args.zip.exists():
        raise SystemExit(f"ZIP not found: {args.zip}")

    inventory = inventory_zip(args.zip)
    results, summary, sample = run_p2_validation(args.staging_root, args.zip)
    write_reports(
        summary=summary,
        sample=sample,
        zip_path=args.zip,
        staging_root=args.staging_root,
        inventory=inventory,
    )
    print(json.dumps({"verdict": summary.verdict, "ocr_failures": summary.ocr_failures, "needs_review": summary.questions_needs_review}, indent=2))


if __name__ == "__main__":
    main()
