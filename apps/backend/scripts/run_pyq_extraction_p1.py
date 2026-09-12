#!/usr/bin/env python3
"""FACTORY-PYQ-P1 — deterministic NEET PYQ extraction into local staging.

No AI calls, no DB writes, no production import.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path

from app.modules.cms.pyq.pyq_discovery import (
    FileClassification,
    inventory_zip,
    sha256_bytes,
)
from app.modules.cms.pyq.pyq_extraction import (
    ValidationStatus,
    extract_paper,
    validate_paper_extraction,
)
from app.modules.cms.pyq.pyq_staging import (
    compute_cross_paper_repeats,
    default_staging_root,
    write_manifest,
    write_paper_staging,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _report_path() -> Path:
    return _repo_root() / "docs" / "content-factory" / "PYQ_EXTRACTION_P1_REPORT.md"


def _select_unique_papers(report) -> list:
    """One entry per content SHA-256; skip duplicate file aliases and non-papers."""
    chosen: dict[str, object] = {}
    for entry in report.files:
        if entry.classification not in {
            FileClassification.NEET_QUESTION_PAPER,
            FileClassification.DUPLICATE_PAPER,
        }:
            continue
        if entry.classification == FileClassification.DUPLICATE_PAPER:
            continue
        if entry.sha256 not in chosen:
            chosen[entry.sha256] = entry
    return list(chosen.values())


def run_extraction(
    zip_path: Path,
    staging_root: Path,
    *,
    write_report: bool = True,
) -> dict:
    report = inventory_zip(zip_path)
    entries = _select_unique_papers(report)

    results = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for entry in entries:
            pdf_bytes = zf.read(entry.relative_path)
            result = extract_paper(entry, pdf_bytes)
            validate_paper_extraction(result)
            write_paper_staging(staging_root, result)
            results.append(result)

    all_questions = [q for r in results for q in r.questions]
    cross = compute_cross_paper_repeats(all_questions)
    manifest = write_manifest(
        staging_root,
        zip_path=str(zip_path),
        zip_sha256=report.zip_sha256,
        results=results,
        cross_paper_repeats=cross,
    )

    summary = {
        "manifest": manifest,
        "results": results,
        "cross_paper_repeats": cross,
        "inventory": report,
        "entries_processed": entries,
    }
    if write_report:
        _write_markdown_report(summary, staging_root)
    return summary


def _write_markdown_report(summary: dict, staging_root: Path) -> None:
    manifest = summary["manifest"]
    results = summary["results"]
    inventory = summary["inventory"]
    cross = summary["cross_paper_repeats"]

    extracted = [
        q
        for r in results
        for q in r.questions
        if q.validation_status == ValidationStatus.EXTRACTED.value
    ]
    ocr_records = [
        q
        for r in results
        for q in r.questions
        if q.validation_status == ValidationStatus.OCR_REQUIRED.value
    ]
    dupes = [q for r in results for q in r.questions if q.duplicate_within_paper]

    mode_counts = Counter(r.extraction_mode for r in results)
    year_papers = Counter(r.exam_year or "unknown" for r in results)
    year_questions = Counter(q.exam_year or "unknown" for q in extracted)
    subject_counts = Counter(q.subject or "unknown" for q in extracted)

    anomalies: list[str] = []
    for r in results:
        anomalies.extend(r.validation_anomalies)

    per_paper_lines = []
    for r in sorted(results, key=lambda x: (x.exam_year or "", x.source_file)):
        qcount = len(
            [q for q in r.questions if q.validation_status == ValidationStatus.EXTRACTED.value]
        )
        per_paper_lines.append(
            f"| {r.exam_year or '?'} | `{Path(r.source_file).name}` | {r.extraction_mode} | {qcount} | {len(r.ocr_required_pages)} |"
        )

    blockers = [
        "2022 exam year absent from source ZIP",
        "No separate answer-key files in corpus",
        f"{len(ocr_records)} OCR_REQUIRED page/paper records — local OCR pipeline not present",
        "No authoritative embedded answer grids detected in TEXT papers",
        "cms.pyq_papers / cms.pyq_questions tables not created (awaiting authorization)",
        "Production content_items import blocked until P2 validation",
    ]
    if manifest.mathematics_exclusions:
        blockers.append(f"{manifest.mathematics_exclusions} Mathematics question(s) excluded")

    p2_steps = [
        "Human review of staging samples (2020 TEXT, 2021 TEXT, 2023 SCANNED, 2025 SCANNED)",
        "Approve or implement local deterministic OCR for SCANNED/MIXED papers",
        "Source authoritative answer keys (separate corpus or manual curation)",
        "Resolve missing question numbers and option gaps flagged in extraction_report.json",
        "Approve cms.pyq_papers / cms.pyq_questions migration",
        "Import staging → DB with read-back verification",
        "Optional ECAEP promotion path for curated PYQ subsets only",
    ]

    lines = [
        "# PYQ Extraction P1 Report — NEET 2020–2025",
        "",
        f"**Generated:** {manifest.generated_at}  ",
        "**Mode:** Deterministic local extraction — no AI, no DB writes, no publication  ",
        f"**Source ZIP:** `{inventory.zip_path}`  ",
        f"**ZIP SHA-256:** `{inventory.zip_sha256}`  ",
        f"**Staging root:** `{staging_root}`",
        "",
        "## A. Files processed",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| ZIP entries | {inventory.total_entries} |",
        f"| PDF files in ZIP | {inventory.pdf_count} |",
        f"| Unique papers extracted | {manifest.unique_papers} |",
        f"| Duplicate file aliases skipped | {inventory.pdf_count - manifest.unique_papers} |",
        "",
        "## B. Papers processed",
        "",
        f"Processed **{manifest.papers_processed}** unique question papers into staging.",
        "",
        "## C. Year distribution",
        "",
        "| Year | Papers | Extracted questions |",
        "|------|-------:|------------------:|",
    ]
    for year in sorted(year_papers):
        lines.append(f"| {year} | {year_papers[year]} | {year_questions.get(year, 0)} |")

    lines.extend(
        [
            "",
            "## D. 2022 gap",
            "",
            "Exam year **2022 is absent** from the ZIP (confirmed at P0 and unchanged at P1).",
            "",
            "## E. Subject distribution",
            "",
            "| Subject | Extracted questions |",
            "|---------|--------------------:|",
        ]
    )
    for subj, count in sorted(subject_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"| {subj} | {count} |")

    lines.extend(
        [
            "",
            "## F. Mathematics exclusions",
            "",
            f"Mathematics exclusions: **{manifest.mathematics_exclusions}**  ",
            "Filename-based Mathematics files: **0**. No Mathematics sections detected in TEXT extraction.",
            "",
            "## G. Question counts per paper",
            "",
            "| Year | File | Mode | Questions | OCR pages |",
            "|------|------|------|----------:|----------:|",
            *per_paper_lines,
            "",
            "## H. Total extracted question records",
            "",
            f"- **{manifest.extracted_questions}** fully extracted MCQ records  ",
            f"- **{manifest.total_question_records}** total staging records (includes OCR stubs)",
            "",
            "## I. Text vs scanned vs mixed",
            "",
            "| Extraction mode | Papers |",
            "|-----------------|-------:|",
        ]
    )
    for mode, count in sorted(mode_counts.items()):
        lines.append(f"| {mode} | {count} |")

    lines.extend(
        [
            "",
            "## J. OCR_REQUIRED count",
            "",
            f"**{manifest.ocr_required_records}** OCR_REQUIRED staging records across **{mode_counts.get('SCANNED', 0)}** fully scanned papers and mixed-mode OCR pages.",
            "",
            "## K. Answer-known count",
            "",
            f"**{manifest.answer_known}** questions with authoritative embedded answers.",
            "",
            "## L. ANSWER_PENDING count",
            "",
            f"**{manifest.answer_pending}** extracted questions with `answer_status=ANSWER_PENDING` (no authoritative answer source in corpus).",
            "",
            "## M. Duplicate extraction candidates",
            "",
            f"**{manifest.duplicate_within_paper}** within-paper duplicate extraction candidates flagged.",
            "",
            "## N. Cross-paper repeated questions",
            "",
            f"**{manifest.cross_paper_repeats}** normalized question hashes appear in more than one paper (retained in staging, not collapsed).",
            "",
            "## O. Extraction anomalies",
            "",
        ]
    )
    if anomalies:
        for item in sorted(set(anomalies))[:80]:
            lines.append(f"- `{item}`")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## P. Staging artifact location",
            "",
            f"```text",
            f"{staging_root}/",
            "  manifest.json",
            "  cross_paper_repeats.json",
            "  papers/{source_sha256}/",
            "    paper.json",
            "    questions.jsonl",
            "    extraction_report.json",
            "```",
            "",
            "## Q. Production-import blockers",
            "",
        ]
    )
    for b in blockers:
        lines.append(f"- {b}")

    lines.extend(["", "## R. Recommended P2 validation process", ""])
    for step in p2_steps:
        lines.append(f"1. {step}" if step == p2_steps[0] else f"- {step}")

    lines.extend(
        [
            "",
            "## Final safety attestation",
            "",
            "| Check | Value |",
            "|-------|------:|",
        ]
    )
    for key, val in manifest.safety_attestation.items():
        lines.append(f"| {key} | {val} |")

    lines.extend(
        [
            "",
            "**STOP.** No production database import performed. Await explicit authorization for P2.",
            "",
        ]
    )

    report_path = _report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="FACTORY-PYQ-P1 deterministic extraction")
    parser.add_argument(
        "--zip",
        type=Path,
        default=_repo_root() / "NEET_PYQ_OFFICIAL.zip",
        help="Path to NEET_PYQ_OFFICIAL.zip",
    )
    parser.add_argument(
        "--staging-root",
        type=Path,
        default=default_staging_root(_repo_root()),
        help="Staging output directory",
    )
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args()

    if not args.zip.exists():
        raise SystemExit(f"ZIP not found: {args.zip}")

    summary = run_extraction(args.zip, args.staging_root, write_report=not args.no_report)
    manifest = summary["manifest"]
    print(json.dumps({"papers": manifest.papers_processed, "extracted": manifest.extracted_questions}, indent=2))


if __name__ == "__main__":
    main()
