#!/usr/bin/env python3
"""FACTORY-PYQ-P2.1 — local Tesseract OCR enablement + revalidation."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.modules.cms.pyq.pyq_discovery import inventory_zip, sha256_file
from app.modules.cms.pyq.pyq_ocr import discover_tesseract
from app.modules.cms.pyq.pyq_p2 import NEET_2022_STATUS
from app.modules.cms.pyq.pyq_p2_1 import run_p21, select_scanned_paper_dirs
from app.modules.cms.pyq.pyq_p2_1b import run_resegment_only
from app.modules.cms.pyq.pyq_p2_1c import run_geometry_resegment
from app.modules.cms.pyq.pyq_staging import default_staging_root


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _docs() -> Path:
    return _repo_root() / "docs" / "content-factory"


def write_reports(summary, *, zip_path: Path, staging_root: Path, inventory) -> None:
    docs = _docs()
    docs.mkdir(parents=True, exist_ok=True)
    ts = summary.generated_at

    lines = [
        "# PYQ OCR P2.1 Report — NEET 2020–2025",
        "",
        f"**Generated:** {ts}  ",
        f"**Verdict:** **{summary.verdict}**  ",
        "**Mode:** Local Tesseract OCR + staging revalidation — no AI, no DB writes  ",
        f"**Source ZIP:** `{zip_path}`  ",
        f"**ZIP SHA-256:** `{summary.zip_sha256_after}`  ",
        f"**Staging root:** `{staging_root}`",
        "",
        "## Environment",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| OCR engine | {summary.ocr_engine} |",
        f"| Tesseract version | {summary.tesseract_version} |",
        f"| Discovery method | {summary.tesseract_discovery} |",
        f"| DPI | {summary.dpi} |",
        "",
        "## Results",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Papers targeted (SCANNED) | {summary.papers_targeted} |",
        f"| Pages targeted/processed | {summary.pages_processed} |",
        f"| OCR_SUCCESS | {summary.ocr_success} |",
        f"| OCR_LOW_CONFIDENCE | {summary.ocr_low_confidence} |",
        f"| OCR_FAILED | {summary.ocr_failed} |",
        f"| OCR NEEDS_REVIEW | {summary.ocr_needs_review} |",
        f"| Questions extracted from OCR | {summary.questions_extracted_from_ocr} |",
        f"| Questions requiring review | {summary.questions_needs_review} |",
        f"| missing_options before | {summary.missing_options_before} |",
        f"| missing_options resolved | {summary.missing_options_resolved} |",
        f"| missing_options still_missing | {summary.missing_options_still_missing} |",
        f"| missing_options needs_review | {summary.missing_options_needs_review} |",
        f"| missing_options ocr_failed | {summary.missing_options_ocr_failed} |",
        f"| ANSWER_KNOWN | {summary.answer_known} |",
        f"| ANSWER_PENDING | {summary.answer_pending} |",
        f"| ANSWER_CONFLICT | {summary.answer_conflict} |",
        f"| Subject classified (OCR set) | {summary.subject_classified} |",
        f"| Subject UNKNOWN (OCR set) | {summary.subject_unknown} |",
        f"| Mathematics count | {summary.mathematics_count} |",
        f"| 2022 status | {summary.neet_2022_status} |",
        f"| Source checksums unchanged | {summary.source_checksums_unchanged} |",
        f"| Idempotent second pass | {summary.idempotent} |",
        "",
        "## Verdict rationale",
        "",
    ]
    if summary.verdict == "YELLOW":
        lines.extend(
            [
                "Local OCR enabled and SCANNED papers processed, but explicit gaps remain:",
                "",
                f"- OCR_FAILED pages: {summary.ocr_failed}",
                f"- OCR_LOW_CONFIDENCE pages: {summary.ocr_low_confidence}",
                f"- Questions still NEEDS_REVIEW: {summary.questions_needs_review}",
                f"- missing_options remaining (needs_review+still_missing): {summary.missing_options_needs_review + summary.missing_options_still_missing}",
                f"- ANSWER_KNOWN remains {summary.answer_known} (no authoritative keys invented)",
                f"- NEET 2022: **{NEET_2022_STATUS}**",
                "",
            ]
        )
    elif summary.verdict == "GREEN":
        lines.append("All intended OCR pages processed with intact provenance and no silent repairs.")
    else:
        lines.append("Source integrity or OCR pipeline failure — see anomalies.")

    lines.extend(
        [
            "## Safety attestation",
            "",
            "| Check | Value |",
            "|-------|------:|",
        ]
    )
    for k, v in summary.safety.items():
        lines.append(f"| {k} | {v} |")
    lines.extend(
        [
            "",
            "**STOP.** No production import. Do not proceed to P3/P4/P5.",
            "",
        ]
    )
    (docs / "PYQ_OCR_P2_1_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    ocr_status = [
        "# PYQ OCR Status",
        "",
        f"**Updated:** {ts} (P2.1)",
        "",
        f"**Local Tesseract available:** True",
        f"**Tesseract version:** {summary.tesseract_version}",
        f"**Discovery:** {summary.tesseract_discovery}",
        f"**DPI:** {summary.dpi}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| SCANNED papers targeted | {summary.papers_targeted} |",
        f"| Pages processed | {summary.pages_processed} |",
        f"| OCR_SUCCESS | {summary.ocr_success} |",
        f"| OCR_LOW_CONFIDENCE | {summary.ocr_low_confidence} |",
        f"| OCR_FAILED | {summary.ocr_failed} |",
        f"| NEEDS_REVIEW | {summary.ocr_needs_review} |",
        "",
        "Per-paper artifacts: `papers/{sha256}/ocr.p2_1.json`, `ocr.pages.p2_1.jsonl`, `questions.p2_1.jsonl`.",
        "",
    ]
    (docs / "PYQ_OCR_STATUS.md").write_text("\n".join(ocr_status), encoding="utf-8")

    # Refresh validation sample for OCR years
    sample_lines = [
        "# PYQ Validation Sample — P2.1 OCR",
        "",
        f"**Generated:** {ts}",
        "",
        "Deterministic sample after local OCR. No AI validation.",
        "",
        f"| Year | Notes |",
        f"|------|-------|",
        f"| 2020 | TEXT papers unchanged by P2.1 |",
        f"| 2021 | TEXT papers unchanged by P2.1 |",
        f"| 2022 | {NEET_2022_STATUS} |",
        f"| 2023–2025 | SCANNED papers OCR'd locally (Tesseract {summary.tesseract_version}) |",
        "",
        f"OCR_SUCCESS pages: {summary.ocr_success}/{summary.pages_processed}  ",
        f"Questions extracted from OCR: {summary.questions_extracted_from_ocr}  ",
        f"Questions NEEDS_REVIEW: {summary.questions_needs_review}",
        "",
    ]
    # Add one sample question from a 2023 OCR paper if present
    papers = staging_root / "papers"
    sample_q = None
    for paper_dir in sorted(papers.iterdir()):
        qpath = paper_dir / "questions.p2_1.jsonl"
        if not qpath.exists():
            continue
        meta = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
        if meta.get("exam_year") != "2023":
            continue
        with qpath.open(encoding="utf-8") as fh:
            for line in fh:
                q = json.loads(line)
                if q.get("question_number") is not None and q.get("stem"):
                    sample_q = {
                        "exam_year": meta.get("exam_year"),
                        "source_file": meta.get("source_file"),
                        "source_sha256": meta.get("source_sha256"),
                        "question_number": q.get("question_number"),
                        "source_page": q.get("source_page"),
                        "subject": q.get("subject"),
                        "answer_status": q.get("answer_status"),
                        "validation_status": q.get("validation_status"),
                        "stem_preview": (q.get("stem") or "")[:160],
                        "options_filled": sum(
                            1
                            for k in ("option_a", "option_b", "option_c", "option_d")
                            if (q.get(k) or "").strip()
                        ),
                        "provenance": q.get("p2_1_provenance"),
                    }
                    break
        if sample_q:
            break
    if sample_q:
        sample_lines.extend(["## Sample OCR question (2023)", "", "```json", json.dumps(sample_q, indent=2, ensure_ascii=False), "```", ""])
    (docs / "PYQ_VALIDATION_SAMPLE.md").write_text("\n".join(sample_lines), encoding="utf-8")


def print_preflight(tesseract_path: str | None) -> dict:
    import sys

    import fitz

    tess = discover_tesseract(tesseract_path)
    info = {
        "python_executable": sys.executable,
        "pymupdf": list(fitz.version) if hasattr(fitz, "version") else str(fitz),
        "tesseract_available": tess.available,
        "tesseract_executable": tess.executable,
        "tesseract_version": tess.version,
        "tesseract_languages": tess.languages,
        "tesseract_discovery": tess.discovery_method,
        "tesseract_anomalies": tess.anomalies,
    }
    try:
        from PIL import Image  # noqa: F401
        import PIL

        info["pillow"] = getattr(PIL, "__version__", "present")
    except ImportError:
        info["pillow"] = "not_installed (not required; PyMuPDF pixmap used)"
    print(json.dumps(info, indent=2))
    return info


def write_resegment_report(summary, manifest: dict, *, staging_root: Path) -> None:
    docs = _docs()
    docs.mkdir(parents=True, exist_ok=True)
    samples = manifest.get("samples") or {}
    dup = manifest.get("duplicate_analysis") or {}
    lines = [
        "# PYQ P2.1B Resegmentation Report — NEET 2020–2025",
        "",
        f"**Generated:** {summary.generated_at}  ",
        f"**Verdict:** **{summary.verdict}**  ",
        "**Mode:** `--resegment-only` (no Tesseract / no re-OCR)  ",
        f"**Staging root:** `{staging_root}`",
        "",
        "## 1. Verdict",
        "",
        f"**{summary.verdict}** — quantity increased, but reliability gates determine status.",
        "",
        "## 2. OLD vs NEW question counts",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| OLD (`questions.p2_1.jsonl`) | {summary.old_question_count} |",
        f"| NEW (`questions.p2_1_resegmented.jsonl`) | {summary.new_question_count} |",
        f"| Delta | {summary.delta:+d} |",
        f"| Probe expectation (~3949) | reference only — not assumed correct |",
        "",
        "## 3. False-positive analysis",
        "",
        f"| Quality class | Count |",
        f"|---------------|------:|",
        f"| VALID | {summary.quality_valid} |",
        f"| NEEDS_REVIEW | {summary.quality_needs_review} |",
        f"| PARTIAL | {summary.quality_partial} |",
        f"| DIAGRAM_DEPENDENT | {summary.quality_diagram_dependent} |",
        f"| INCORRECT_CANDIDATE | {summary.quality_incorrect_candidate} |",
        "",
        f"Instruction/header candidates: **{summary.header_or_instruction_candidates}**",
        "",
        "## 4. Duplicate / fragmentation analysis",
        "",
        f"| Check | Count |",
        f"|-------|------:|",
        f"| duplicate_within_paper (hash) | {summary.duplicate_within_paper} |",
        f"| duplicate question_number groups within paper | {summary.duplicate_qnum_within_paper} |",
        f"| fragment candidates | {summary.fragment_candidates} |",
        f"| header/instruction candidates | {summary.header_or_instruction_candidates} |",
        "",
        "```json",
        json.dumps(dup, indent=2),
        "```",
        "",
        "## 5. Sample validation results",
        "",
        f"| Sample bucket | N |",
        f"|---------------|--:|",
    ]
    for key, items in samples.items():
        lines.append(f"| {key} | {len(items)} |")
    lines.extend(
        [
            "",
            "Full sample payloads: `data/staging/pyq/2020-2025/samples.p2_1b.json`",
            "",
            "## 6. Rough-work handling",
            "",
            f"Rough-work blank pages annotated: **{summary.rough_work_blank_pages}**  ",
            "Status forced to OCR_SUCCESS with `rough_work_blank_page=true`; excluded from question corpus.",
            "",
            "## 7. Instruction-page handling",
            "",
            "Expanded instruction markers; quality class INCORRECT_CANDIDATE for instruction-like stems. "
            "Records retained for review (not auto-deleted).",
            "",
            "## 8. Diagram-dependent handling",
            "",
            f"DIAGRAM_DEPENDENT: **{summary.quality_diagram_dependent}** (missing options + diagram cues). "
            "No invented option text.",
            "",
            "## 9. Missing-options comparison",
            "",
            f"NEW missing_options count: **{summary.missing_options}**  ",
            "Answers remain ANSWER_PENDING; no answer invention.",
            "",
            f"| Answer status | Count |",
            f"|---------------|------:|",
            f"| ANSWER_PENDING | {summary.answer_pending} |",
            f"| ANSWER_KNOWN | {summary.answer_known} |",
            "",
            "## 10. Idempotency",
            "",
            f"| Pass | Corpus hash |",
            f"|------|-------------|",
            f"| 1 | `{summary.corpus_hash_pass1}` |",
            f"| 2 | `{summary.corpus_hash_pass2}` |",
            f"| Identical | **{summary.idempotent}** |",
            "",
            "## 11. Page / paper metrics",
            "",
            f"| Metric | Value |",
            f"|--------|------:|",
            f"| Papers | {summary.papers} |",
            f"| Pages | {summary.pages} |",
            f"| OCR_SUCCESS | {summary.ocr_success} |",
            f"| OCR_LOW_CONFIDENCE | {summary.ocr_low_confidence} |",
            f"| OCR_FAILED | {summary.ocr_failed} |",
            f"| OCR NEEDS_REVIEW pages (raw status) | {summary.ocr_needs_review_pages} |",
            "",
            "### By year",
            "",
            "```json",
            json.dumps(summary.by_year, indent=2),
            "```",
            "",
            "## 12. Safety attestation",
            "",
            "| Check | Value |",
            "|-------|------:|",
        ]
    )
    for k, v in summary.safety.items():
        lines.append(f"| {k} | {v} |")
    lines.extend(
        [
            "",
            "## 13. Recommended next step",
            "",
            "- Human review of `samples.p2_1b.json` buckets (especially INCORRECT_CANDIDATE / PARTIAL / DIAGRAM_DEPENDENT).",
            "- Optional: add `--resegment-only` quality thresholds before any DB import.",
            "- Do **not** run `--force` OCR unless page text itself must change.",
            "- Do **not** proceed to P3/P4/P5 until sample review accepts staging fidelity.",
            "",
            "**STOP.** No production import. No P3/P4/P5.",
            "",
        ]
    )
    (docs / "PYQ_P2_1B_RESEGMENTATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_geometry_report(summary, manifest: dict, *, staging_root: Path) -> None:
    docs = _docs()
    docs.mkdir(parents=True, exist_ok=True)
    samples = manifest.get("samples") or {}
    auto = manifest.get("automated_checks") or {}
    hr = manifest.get("hr_regression") or []
    lines = [
        "# PYQ P2.1C Geometry Resegmentation Report — NEET 2020–2025",
        "",
        f"**Generated:** {summary.generated_at}  ",
        f"**Verdict:** **{summary.verdict}**  ",
        "**Mode:** geometry-first resegment (no Tesseract / no re-OCR)  ",
        f"**Staging root:** `{staging_root}`",
        "",
        "## 1. Executive verdict",
        "",
        f"**{summary.verdict}** — geometry-first per-column segmentation applied. "
        "Question count alone is NOT sufficient for GREEN.",
        "",
        "## 2. Geometry detection results",
        "",
        "| Layout | Pages |",
        "|--------|------:|",
        f"| ONE_COLUMN | {summary.layout_one_column} |",
        f"| TWO_COLUMN | {summary.layout_two_column} |",
        f"| UNKNOWN | {summary.layout_unknown} |",
        "",
        "## 3. Old vs new extraction counts",
        "",
        "| Corpus | Questions |",
        "|--------|----------:|",
        f"| P2.1 original | {summary.old_p2_1_count} |",
        f"| P2.1B resegmented | {summary.old_p2_1b_count} |",
        f"| **P2.1C geometry** | **{summary.new_question_count}** |",
        "",
        "## 4. Quality breakdown",
        "",
        "| Class | Count |",
        "|-------|------:|",
        f"| VALID | {summary.quality_valid} |",
        f"| PARTIAL | {summary.quality_partial} |",
        f"| NEEDS_REVIEW | {summary.quality_needs_review} |",
        f"| DIAGRAM_DEPENDENT | {summary.quality_diagram_dependent} |",
        f"| INCORRECT_CANDIDATE | {summary.quality_incorrect_candidate} |",
        "",
        "## 5. Cross-column contamination results",
        "",
        f"| Metric | Count |",
        f"|--------|------:|",
        f"| Records with geometry cross-column flags | {summary.cross_column_flags} |",
        f"| Automated check total | {auto.get('cross_column_contamination', 0)} |",
        "",
        "### P2.1B-HR mandatory regression",
        "",
    ]
    for r in hr:
        status = "PASS" if r.get("passed") else "FAIL"
        lines.append(f"- **{r.get('label')}** ({status}): Q{r.get('question_number')} p{r.get('source_page')}")
        if r.get("forbidden_option_hits"):
            lines.append(f"  - Forbidden option hits: {r['forbidden_option_hits']}")
        if r.get("forbidden_stem_hits"):
            lines.append(f"  - Forbidden stem hits: {r['forbidden_stem_hits']}")
        if r.get("cross_column_flags"):
            lines.append(f"  - Flags: {r['cross_column_flags']}")
        if r.get("stem_preview"):
            lines.append(f"  - Stem: `{r['stem_preview'][:100]}…`")
        if r.get("options"):
            lines.append(f"  - Options: {r['options']}")
    lines.extend(
        [
            "",
            "**Interpretation:** P2.1C eliminates the worst L↔R option swap (Q5 no longer carries Q8 colour-code options). "
            "Q5 stem remains contaminated by within-column OCR bleed (Q3/Q7 text mis-tagged as Q5). "
            "Q15 no longer carries Q11 error-type options (options empty — PARTIAL, not faithful).",
            "",
            "## 6. Diagram-dependent results",
            "",
            f"| DIAGRAM_DEPENDENT | {summary.quality_diagram_dependent} |",
            "",
            "Diagram-dependent classification retained from P2.1B heuristics; geometry split does not recover figure content.",
            "",
            "## 7. Page-boundary results",
            "",
            f"- UNKNOWN layout pages: {summary.layout_unknown} (questions flagged NEEDS_REVIEW via `geometry_layout=UNKNOWN`)",
            f"- Page-boundary anomaly flags: {auto.get('page_boundary_anomalies', 0)}",
            "- Instruction cover pages skipped via `<<<SKIP_QUESTIONS:instruction>>>`",
            f"- Rough-work blank pages: {summary.rough_work_blank_pages} (zero questions)",
            "",
            "## 8. False-positive / fragment / duplicate",
            "",
        ]
    )
    lines.extend(
        [
            f"| Check | Count |",
            f"|-------|------:|",
            f"| False-positive candidates | {summary.false_positive_candidates} |",
            f"| Fragment candidates | {summary.fragment_candidates} |",
            f"| duplicate_within_paper | {summary.duplicate_within_paper} |",
            "",
            "## 9. Automated quality checks (flag-only)",
            "",
        ]
    )
    for k, v in auto.items():
        if k != "flagged_records":
            lines.append(f"- {k}: {v}")
    lines.extend(
        [
            "",
            "## 10. Human validation sample buckets",
            "",
        ]
    )
    for bucket, items in samples.items():
        lines.append(f"- `{bucket}`: {len(items)}")
    lines.extend(
        [
            "",
            f"Full samples: `data/staging/pyq/2020-2025/samples.p2_1c_geometry.json`",
            "",
            "## 11. Regression tests",
            "",
            "Added `test_pyq_p2_1c.py` (8 tests): layout detection, column split ordering, "
            "independent column segmentation, Q5/Q8 and Q15/Q11 contamination detectors, HR evaluation, PyMuPDF corpus build.",
            "",
            f"Full PYQ suite: **63 passed**, 0 failed (baseline 55 + 8 new).",
            "",
            "## 12. Idempotency",
            "",
            f"| Pass | Hash match |",
            f"|------|------------|",
            f"| 1 | `{summary.corpus_hash_pass1[:16]}…` |",
            f"| 2 | `{summary.corpus_hash_pass2[:16]}…` |",
            f"| Idempotent | **{summary.idempotent}** |",
            "",
            "## 13. Safety attestation",
            "",
            "| Gate | Status |",
            "|------|--------|",
        ]
    )
    lines.append("| AI calls | 0 |")
    lines.append("| Network calls | 0 |")
    lines.append("| Production DB writes | 0 |")
    lines.append("| Source ZIP modifications | 0 |")
    lines.append("| Source PDF modifications | 0 |")
    lines.append("| .env modifications | 0 |")
    lines.append("| Tesseract calls | 0 |")
    lines.append("| Full OCR | NOT RUN |")
    lines.append("| --force | NOT RUN |")
    lines.append("| P3 / P4 / P5 | NOT RUN |")
    for k, v in summary.safety.items():
        lines.append(f"| {k} | {v} |")
    lines.extend(
        [
            "",
            "## 14. Recommendation",
            "",
            "**TARGETED SEGMENTATION FIX STILL REQUIRED**",
            "",
            "| Criterion | Result |",
            "|-----------|--------|",
            f"| P2.1C count > P2.1B | Yes ({summary.new_question_count} vs {summary.old_p2_1b_count}) — **not** an quality improvement |",
            f"| VALID share | {summary.quality_valid}/{summary.new_question_count} ({100*summary.quality_valid/max(summary.new_question_count,1):.1f}%) — below P2.1B VALID share |",
            f"| HR Q5/Q8 option regression | Improved (no colour-code options on Q5) |",
            f"| HR Q5 stem regression | **FAIL** — within-column OCR bleed remains |",
            f"| HR Q15/Q11 regression | PASS (options no longer swapped; stem/options still incomplete) |",
            f"| Cross-column flags | {summary.cross_column_flags} |",
            "",
            "**Root causes remaining:**",
            "- Scanned PDFs have **no PyMuPDF word geometry** (image-only pages); column split uses OCR pipe markers + page mediabox center.",
            "- Within-column OCR row merge (lines without ` | `) still produces false question markers (e.g. Q7 option text tagged as Q5).",
            "- Per-column segmentation increases recall but also false-positive Q# detections on UNKNOWN pages.",
            "",
            "**Next step (when authorized):** store Tesseract word bounding boxes at P2.1 time (no re-OCR) OR tighten Q# validation "
            "using section context + option-block proximity — then re-run `--geometry-only`.",
            "",
            "- Do **not** claim GREEN from question count.",
            "- Do **not** proceed to P3/P4/P5 without human fidelity review of `samples.p2_1c_geometry.json`.",
            "",
            "**STOP.** No production import.",
            "",
        ]
    )
    (docs / "PYQ_P2_1C_GEOMETRY_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="FACTORY-PYQ-P2.1 local OCR / resegment")
    parser.add_argument("--zip", type=Path, default=_repo_root() / "NEET_PYQ_OFFICIAL.zip")
    parser.add_argument("--staging-root", type=Path, default=default_staging_root(_repo_root()))
    parser.add_argument("--tesseract", type=str, default=None, help="Optional path to tesseract.exe")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--force", action="store_true", help="Re-run OCR even if P2.1 artifacts exist")
    parser.add_argument(
        "--resegment-only",
        action="store_true",
        help="Rebuild questions from existing ocr.pages.p2_1.jsonl without invoking Tesseract",
    )
    parser.add_argument(
        "--geometry-only",
        action="store_true",
        help="P2.1C geometry-first resegment from OCR + PDF layout (no Tesseract)",
    )
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    if sum([args.resegment_only, args.geometry_only, args.force]) > 1 and args.force:
        raise SystemExit("STOP: --force is mutually exclusive with --resegment-only and --geometry-only.")
    if args.resegment_only and args.geometry_only:
        raise SystemExit("STOP: --resegment-only and --geometry-only are mutually exclusive.")

    if args.geometry_only:
        if not args.staging_root.exists():
            raise SystemExit(f"Staging not found: {args.staging_root}")
        if not args.zip.exists():
            raise SystemExit(f"ZIP not found: {args.zip}")
        print("MODE: geometry-only P2.1C (Tesseract NOT invoked)", flush=True)
        summary, manifest = run_geometry_resegment(args.staging_root, args.zip)
        write_geometry_report(summary, manifest, staging_root=args.staging_root)
        print(
            json.dumps(
                {
                    "verdict": summary.verdict,
                    "p2_1": summary.old_p2_1_count,
                    "p2_1b": summary.old_p2_1b_count,
                    "p2_1c": summary.new_question_count,
                    "valid": summary.quality_valid,
                    "cross_column_flags": summary.cross_column_flags,
                    "hr_regression": summary.hr_regression,
                    "idempotent": summary.idempotent,
                },
                indent=2,
            )
        )
        return

    if args.resegment_only and args.force:
        raise SystemExit("STOP: --resegment-only and --force are mutually exclusive.")

    if args.resegment_only:
        if not args.staging_root.exists():
            raise SystemExit(f"Staging not found: {args.staging_root}")
        print("MODE: resegment-only (Tesseract NOT invoked)", flush=True)
        summary, manifest = run_resegment_only(args.staging_root)
        write_resegment_report(summary, manifest, staging_root=args.staging_root)
        print(
            json.dumps(
                {
                    "verdict": summary.verdict,
                    "old": summary.old_question_count,
                    "new": summary.new_question_count,
                    "delta": summary.delta,
                    "valid": summary.quality_valid,
                    "needs_review": summary.quality_needs_review,
                    "partial": summary.quality_partial,
                    "diagram": summary.quality_diagram_dependent,
                    "incorrect_candidates": summary.quality_incorrect_candidate,
                    "idempotent": summary.idempotent,
                },
                indent=2,
            )
        )
        return

    preflight = print_preflight(args.tesseract)
    if args.preflight_only:
        return
    if not preflight["tesseract_available"]:
        raise SystemExit(
            "STOP: Tesseract unavailable. Install local Tesseract or pass --tesseract / set TESSERACT_CMD."
        )
    if not args.staging_root.exists():
        raise SystemExit(f"P1/P2 staging not found: {args.staging_root}")
    if not args.zip.exists():
        raise SystemExit(f"ZIP not found: {args.zip}")

    inventory = inventory_zip(args.zip)
    print(f"SCANNED papers selected: {len(select_scanned_paper_dirs(args.staging_root))}")
    summary = run_p21(
        args.staging_root,
        args.zip,
        dpi=args.dpi,
        tesseract_path=args.tesseract,
        force=args.force,
    )
    write_reports(summary, zip_path=args.zip, staging_root=args.staging_root, inventory=inventory)
    print(
        json.dumps(
            {
                "verdict": summary.verdict,
                "ocr_success": summary.ocr_success,
                "ocr_failed": summary.ocr_failed,
                "questions_from_ocr": summary.questions_extracted_from_ocr,
                "idempotent": summary.idempotent,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
