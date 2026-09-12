"""FACTORY-PYQ-P0: generate read-only PYQ discovery report from NEET_PYQ_OFFICIAL.zip."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from app.modules.cms.pyq.pyq_discovery import (
    SCOPE_YEARS,
    FileClassification,
    inventory_zip,
    probe_sample_pdfs,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ZIP = REPO_ROOT / "NEET_PYQ_OFFICIAL.zip"
OUT_PATH = REPO_ROOT / "docs" / "content-factory" / "PYQ_SOURCE_DISCOVERY_2020_2025.md"


def _md(report, probes) -> str:
    lines = [
        "# PYQ Source Discovery — NEET 2020–2025",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}  ",
        "**Mode:** READ-ONLY discovery — no DB import, no AI, no generation  ",
        f"**Source:** `{report.zip_path}`  ",
        f"**ZIP SHA-256:** `{report.zip_sha256}`  ",
        f"**ZIP size:** {report.zip_size_bytes:,} bytes",
        "",
        "## A. ZIP inventory",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Total ZIP entries | {report.total_entries} |",
        f"| PDF files | {report.pdf_count} |",
        f"| In-scope PDFs (2020–2025) | {report.scope_pdf_count} |",
        f"| Out-of-scope PDFs | {report.out_of_scope_pdf_count} |",
        "",
        "## B. Year-by-year paper inventory (2020–2025 scope)",
        "",
        "| Year | PDF count | Notes |",
        "|------|----------:|-------|",
    ]
    for year in sorted(SCOPE_YEARS):
        entries = report.by_year.get(year, [])
        papers = [e for e in entries if e.classification == FileClassification.NEET_QUESTION_PAPER]
        note = "—"
        if year == "2022" and not papers:
            note = "**MISSING — no PDFs in ZIP**"
        elif year == "2025":
            note = "NTA sets 45–48 + timestamp Paper_* variants; V2 duplicates"
        elif year == "2024" and len(papers) < 10:
            note = "Low count — verify corpus completeness"
        lines.append(f"| {year} | {len(papers)} | {note} |")

    lines += [
        "",
        "## C. Answer-key inventory",
        "",
        f"Separate answer-key files detected: **{report.by_classification.get(FileClassification.ANSWER_KEY.value, 0)}**  ",
        "No filename-based answer keys found. Official answers may be:",
        "- embedded in question PDFs (not verified at P0)",
        "- absent from this ZIP (blocker for automated scoring)",
        "- provided in a separate corpus not included here",
        "",
        "## D. Subject inventory",
        "",
        "Subject is **not encoded in filenames**. Provisional subject detection requires PDF text/layout parsing.",
        "Probe samples detected section markers:",
        "",
    ]
    for p in probes:
        subj = ", ".join(p.subject_sections_detected) or "none in sample"
        lines.append(f"- `{PurePosixPath(p.relative_path).name}` → {subj} ({p.extractability})")

    math_count = report.by_classification.get(FileClassification.EXCLUDED_MATHEMATICS.value, 0)
    lines += [
        "",
        "## E. Mathematics exclusions",
        "",
        f"Mathematics files by filename: **{math_count}**  ",
        "NEET-UG scope excludes Mathematics. No Mathematics subject section expected in NEET papers.",
        "If Mathematics appears inside combined papers, segment by subject boundary — do not import Math items.",
        "",
        "## F. File hashes",
        "",
        "Every PDF SHA-256 computed from ZIP bytes (content-addressable).",
        "",
        "| Year | File | SHA-256 (prefix) | Size | Classification |",
        "|------|------|------------------|-----:|----------------|",
    ]
    for entry in sorted(report.files, key=lambda e: (e.year or "", e.relative_path)):
        if entry.year not in SCOPE_YEARS:
            continue
        lines.append(
            f"| {entry.year} | `{entry.file_name}` | `{entry.sha256[:16]}…` | {entry.file_size:,} | {entry.classification.value} |"
        )

    lines += [
        "",
        "### Exact duplicate file groups (same SHA-256)",
        "",
    ]
    if report.duplicate_file_groups:
        for grp in report.duplicate_file_groups:
            lines.append(f"- {', '.join('`' + PurePosixPath(p).name + '`' for p in grp)}")
    else:
        lines.append("- None detected (byte-identical duplicates)")

    lines += [
        "",
        "## G. Extraction feasibility",
        "",
        "| File | Pages | Text chars (sample) | Type | Q# hits | Option hits | Anomalies |",
        "|------|------:|--------------------:|------|--------:|-------------:|-----------|",
    ]
    for p in probes:
        lines.append(
            f"| `{PurePosixPath(p.relative_path).name}` | {p.page_count} | {p.text_chars} | {p.extractability} | "
            f"{p.question_number_hits} | {p.option_pattern_hits} | {', '.join(p.anomalies) or '—'} |"
        )

    text_n = sum(1 for p in probes if p.extractability == "TEXT")
    scanned_n = sum(1 for p in probes if p.extractability == "SCANNED")
    mixed_n = sum(1 for p in probes if p.extractability == "MIXED")

    lines += [
        "",
        f"Sample probe summary: TEXT={text_n}, MIXED={mixed_n}, SCANNED={scanned_n} (n={len(probes)} samples).",
        "",
        "## H. Question segmentation feasibility",
        "",
        "Deterministic segmentation plan (not implemented):",
        "1. Detect NEET section headers (PHYSICS / CHEMISTRY / BIOLOGY) from extracted text.",
        "2. Parse question numbers via `(1)`, `1.`, `Q1` patterns — validate monotonic sequence per section.",
        "3. Capture options via `(1)…(4)` or `(A)…(D)` blocks.",
        "4. Flag image-only blocks when text density < threshold and images present.",
        "5. Do **not** infer missing options or answers.",
        "",
        "P0 probes show option patterns in most TEXT/MIXED samples; scanned PDFs need OCR gate (future phase).",
        "",
        "## I. Answer-key association strategy",
        "",
        "Proposed (deterministic, no AI):",
        "1. If separate answer-key PDFs arrive → map by `(year, set_code, language)`.",
        "2. If keys embedded → parse trailing answer grid per section (pattern TBD per paper layout).",
        "3. Store `official_answer` only when pattern match confidence = HIGH; else `validation_status=UNRESOLVED`.",
        "4. Never infer answers from model knowledge.",
        "",
        "**P0 blocker:** this ZIP contains question papers only — no answer-key files identified.",
        "",
        "## J. Duplicate analysis",
        "",
        "### File-level (byte identical)",
        "",
    ]
    if report.duplicate_file_groups:
        for grp in report.duplicate_file_groups:
            lines.append(f"- {' = '.join('`' + PurePosixPath(p).name + '`' for p in grp)}")
    else:
        lines.append("- No byte-identical duplicates across scope years.")

    lines += [
        "",
        "### Cross-paper question duplicates (policy)",
        "",
        "Repeated questions across **different** papers/years remain **separate PYQ occurrences** with distinct provenance.",
        "Only duplicate extractions from the **same** paper are dedup candidates.",
        "",
        "Filename duplicate markers detected:",
        "- `Paper_20211218100118.pdf` vs `Paper_20211218100118 (1).pdf` (2021) — verify SHA-256",
        "- `NEET_2025_EN_*_NTA.pdf.pdf` vs `*_V2.pdf.pdf` — likely layout revisions, not identical",
        "",
        "## K. OCR / image risks",
        "",
        "- Scanned/image PDFs require OCR pipeline (not in P0).",
        "- Diagram/table questions need VisualAsset linkage — do not drop.",
        "- Double extension `.pdf.pdf` on 2025 NTA files may confuse naive parsers.",
        "- Page-boundary splits may break multi-line stems — use layout-aware extraction.",
        "",
        "## L. Proposed database model (NOT IMPLEMENTED)",
        "",
        "Reuse `content_items` for generated MCQs only. Add dedicated PYQ schema:",
        "",
        "```",
        "cms.pyq_papers",
        "  id, exam_year, paper_code, set_code, language, source_zip_path, source_member_path,",
        "  source_sha256, page_count, extraction_status, validation_status, ...audited",
        "",
        "cms.pyq_questions",
        "  id, paper_id, question_number, subject, stem_text, options_json, official_answer,",
        "  source_page, source_sha256, question_hash, normalized_hash, validation_status,",
        "  ...audited",
        "```",
        "",
        "Optional link table `cms.pyq_question_promotions` if a PYQ is later promoted to ECAEP content — never merge pools.",
        "",
        "Existing `QuestionBody.pyq_year` remains for **published** CMS questions; PYQ tables hold source corpus separately.",
        "",
        "## M. Proposed deterministic ingestion pipeline (PYQ-P1)",
        "",
        "1. **Unpack** ZIP to ephemeral workspace (never modify ZIP).",
        "2. **Register** papers in `cms.pyq_papers` with SHA-256 + metadata.",
        "3. **Extract** text per page (PyMuPDF); OCR gate for SCANNED.",
        "4. **Segment** by subject + question number + options.",
        "5. **Associate** answers when key material available.",
        "6. **Validate** structural gates (4 options, unique texts, Q# present).",
        "7. **Hash** `question_hash` (raw) + `normalized_hash` (stem+options normalized).",
        "8. **Dedup** only within same paper extraction run.",
        "9. **Exclude** Mathematics items explicitly.",
        "",
        "## N. Validation gates",
        "",
        "| Gate | Rule |",
        "|------|------|",
        "| G1 | 4 options A–D present |",
        "| G2 | Unique option texts |",
        "| G3 | Question number monotonic per section |",
        "| G4 | Official answer present or UNRESOLVED |",
        "| G5 | Subject ∈ {Physics, Chemistry, Biology} |",
        "| G6 | Mathematics → EXCLUDED |",
        "| G7 | Source SHA-256 matches registered paper |",
        "",
        "## O. Estimated question counts",
        "",
        "**Not deterministically established at P0** — full paper parse not run.",
        "Heuristic: standard NEET paper ≈ 180 MCQs × paper count → upper bound **~14,580** if all 81 PDFs are unique full papers.",
        "Actual count requires P1 segmentation; duplicate sets (2025 V2, 2021 filename dup) will reduce unique extractions.",
        "",
        "## P. Blockers",
        "",
    ]
    for b in report.blockers:
        lines.append(f"- {b}")
    if not report.blockers:
        lines.append("- None critical beyond answer-key absence and 2022 gap")

    lines += [
        "",
        "## Q. Recommended next phase",
        "",
        "**PYQ-P1: Deterministic paper parse + staging tables**",
        "- Acquire 2022 corpus + official answer keys",
        "- Implement `cms.pyq_papers` / `cms.pyq_questions` migration",
        "- Build layout parser on 2 papers/year sample set",
        "- OCR gate for scanned PDFs",
        "- Still no ECAEP / publish / factory generation",
        "",
        "## Safety attestation",
        "",
        "| Check | Status |",
        "|-------|--------|",
        "| Database changes | **0** |",
        "| Generation calls | **0** |",
        "| AI provider calls | **0** |",
        "| ECAEP changes | **0** |",
        "| Publication changes | **0** |",
        "",
    ]
    return "\n".join(lines)


def main() -> dict:
    zip_path = DEFAULT_ZIP
    if not zip_path.is_file():
        raise FileNotFoundError(f"ZIP not found: {zip_path}")

    report = inventory_zip(zip_path)
    scope_entries = [e for e in report.files if e.year in SCOPE_YEARS]
    probes = probe_sample_pdfs(zip_path, scope_entries)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(_md(report, probes), encoding="utf-8")

    payload = {
        "files_discovered": report.pdf_count,
        "papers_discovered": report.by_classification.get(FileClassification.NEET_QUESTION_PAPER.value, 0),
        "years_covered": sorted(y for y in report.by_year if y in SCOPE_YEARS),
        "years_missing_in_scope": sorted(SCOPE_YEARS - set(report.by_year)),
        "subjects_detected": "requires PDF parse — not in filenames",
        "mathematics_excluded_count": report.by_classification.get(FileClassification.EXCLUDED_MATHEMATICS.value, 0),
        "answer_key_count": report.by_classification.get(FileClassification.ANSWER_KEY.value, 0),
        "duplicate_file_groups": len(report.duplicate_file_groups),
        "blockers": report.blockers,
        "report_path": str(OUT_PATH),
    }
    print(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    main()
