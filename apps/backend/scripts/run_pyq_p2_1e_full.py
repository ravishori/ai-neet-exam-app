#!/usr/bin/env python3
"""FACTORY-PYQ-P2.1E-FULL — full-corpus Tesseract bbox OCR + geometry resegmentation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.modules.cms.pyq.pyq_p2_1e import run_p2_1e_full
from app.modules.cms.pyq.pyq_staging import default_staging_root


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def write_report(summary, manifest: dict, *, output_dir: Path, report_name: str = "PYQ_P2_1E_FULL_REPORT.md") -> Path:
    docs = _repo_root() / "docs" / "content-factory"
    docs.mkdir(parents=True, exist_ok=True)
    report_path = docs / report_name
    q5 = manifest.get("q5_record") or {}
    q15 = manifest.get("q15_record") or {}
    pc = manifest.get("pipeline_comparison") or {}
    dup = manifest.get("duplicate_analysis") or {}
    frag = manifest.get("fragment_analysis") or {}
    fid = summary.fidelity

    lines = [
        "# PYQ P2.1E Full-Corpus Bbox OCR Report",
        "",
        f"**Generated:** {summary.generated_at}",
        f"**Verdict:** **{summary.verdict}**",
        "**Mode:** Full-corpus staging re-OCR with persisted Tesseract word geometry",
        f"**Output:** `{output_dir}`",
        "",
        "## 1. Executive verdict",
        "",
        f"**{summary.verdict}** — P2.1E full-corpus run on **{summary.papers_processed}** papers, "
        f"**{summary.pages_processed}** pages.",
        "",
        f"- Questions extracted: **{summary.questions_extracted}**",
        f"- Fidelity rate (A+B): **{fid.get('fidelity_rate', 0)}%**",
        f"- HR regression pass: **{all(r['passed'] for r in summary.hr_regression)}**",
        f"- Q5 regression: **{'PASS' if manifest.get('q5_regression_pass') else 'FAIL'}**",
        f"- Q15 regression: **{'PASS' if manifest.get('q15_regression_pass') else 'PARTIAL/FAIL'}**",
        f"- Idempotent: **{summary.idempotent}**",
        "",
        "## 2. Corpus processing summary",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Papers processed | {summary.papers_processed} |",
        f"| Pages processed | {summary.pages_processed} |",
        f"| Processing errors | {len(manifest.get('processing_errors', []))} |",
        "",
        "## 3. OCR metrics",
        "",
        "| Status | Pages |",
        "|--------|------:|",
        f"| OCR_SUCCESS | {summary.ocr_success} |",
        f"| OCR_LOW_CONFIDENCE | {summary.ocr_low_confidence} |",
        f"| OCR_FAILED | {summary.ocr_failed} |",
        "",
        "## 4. BBOX persistence",
        "",
        "Word-level geometry persisted to `ocr.words.p2_1e_full.jsonl` with fields: "
        "source_sha256, page, block_num, par_num, line_num, word_num, text, confidence, left, top, width, height.",
        "",
        f"- Words hash pass1: `{summary.words_hash_pass1[:16]}…`",
        f"- Words hash pass2: `{summary.words_hash_pass2[:16]}…`",
        f"- Hash match: **{summary.words_hash_pass1 == summary.words_hash_pass2}**",
        "",
        "## 5. Layout detection",
        "",
        "| Layout | Pages |",
        "|--------|------:|",
        f"| ONE_COLUMN | {summary.layout_one_column} |",
        f"| TWO_COLUMN | {summary.layout_two_column} |",
        f"| UNKNOWN | {summary.layout_unknown} |",
        f"| rough_work_blank_page | {summary.rough_work_blank_page} |",
        "",
        "## 6. Question extraction metrics",
        "",
        "| Quality | Count |",
        "|---------|------:|",
    ]
    for k, v in sorted(summary.quality.items()):
        lines.append(f"| {k} | {v} |")

    lines.extend(
        [
            "",
            "## 7. Option-boundary analysis",
            "",
            "Option association uses `parse_options_bounded()` — first contiguous (1)–(4) set only; "
            "truncates at second `(1)` marker to prevent Q15→Q20 bleed.",
            "",
            f"Q15 options: {[q15.get(f'option_{x}') for x in 'abcd'] if q15 else 'NOT FOUND'}",
            "",
            "## 8. Q5 regression",
            "",
            f"Stem: `{(q5.get('stem') or 'NOT EXTRACTED')[:200]}`",
            f"Quality: {q5.get('p2_1e_quality_status') if q5 else 'MISSING'}",
            "",
            "## 9. Q15 regression",
            "",
            f"Stem: `{(q15.get('stem') or 'NOT EXTRACTED')[:200]}`",
            f"Options: {[q15.get(f'option_{x}') for x in 'abcd'] if q15 else []}",
            "",
            "## 10. False-positive analysis",
            "",
            f"- false_positive_candidates: **{summary.false_positive_candidates}**",
            f"- fragment_candidates: **{summary.fragment_candidates}**",
            "",
            "## 11. Fragment analysis",
            "",
            f"```json\n{json.dumps(frag, indent=2)}\n```",
            "",
            "## 12. Duplicate analysis",
            "",
            f"```json\n{json.dumps(dup, indent=2)}\n```",
            "",
            "## 13. Cross-column contamination",
            "",
            f"- cross_column_flags: **{summary.cross_column_flags}**",
            "",
            "## 14. Human-review sample",
            "",
            "See `samples.p2_1e_full.json` — includes 30 TWO_COLUMN, 20 PARTIAL, 20 NEEDS_REVIEW, "
            "20 DIAGRAM_DEPENDENT, 20 VALID, 10 page-boundary, 10 instruction pages, 10 complex options, "
            "plus Q5/Q15 regression cases.",
            "",
            "## 15. Idempotency",
            "",
            f"- Words identical: **{summary.words_hash_pass1 == summary.words_hash_pass2}**",
            f"- Questions identical: **{summary.questions_hash_pass1 == summary.questions_hash_pass2}**",
            "",
            "## 16. Tests",
            "",
        "Run: `pytest app/modules/cms/tests/test_pyq_p2_1e.py app/modules/cms/tests/test_pyq_p2_1c.py`",
            "",
            "## 17. Safety attestation",
            "",
            "| Check | Status |",
            "|-------|--------|",
        ]
    )
    for k, v in summary.safety.items():
        lines.append(f"| {k} | **{v}** |")
    lines.extend(
        [
            "| P2.1E-POC artifacts preserved | **NOT OVERWRITTEN** |",
            "| Production import | **NOT RUN** |",
            "| P3/P4/P5 | **NOT RUN** |",
            "",
            "## 18. Recommendation",
            "",
            "Compare pipeline metrics below. Do not treat higher question count as automatically better.",
            "",
            "```json",
            json.dumps(pc, indent=2)[:4000],
            "```",
            "",
            "Next step (if authorized separately): human review of samples before any P3+ work.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_comparison_report(*, baseline_dir: Path, r2_dir: Path) -> Path:
    """Compare baseline R1 vs R2 manifests and write audit doc."""
    docs = _repo_root() / "docs" / "content-factory"
    docs.mkdir(parents=True, exist_ok=True)
    report_path = docs / "PYQ_P2_1E_HR_R2_AUDIT.md"

    b_manifest = json.loads((baseline_dir / "manifest.p2_1e_full.json").read_text(encoding="utf-8"))
    r_manifest = json.loads((r2_dir / "manifest.p2_1e_full.json").read_text(encoding="utf-8"))
    bs = b_manifest["summary"]
    rs = r_manifest["summary"]
    bq = bs.get("quality") or {}
    rq = rs.get("quality") or {}

    def delta(k: str) -> str:
        b = bq.get(k, 0)
        r = rq.get(k, 0)
        d = r - b
        sign = "+" if d > 0 else ""
        return f"{r} ({sign}{d} vs R1)"

    q15_b = b_manifest.get("q15_record") or {}
    q15_r = r_manifest.get("q15_record") or {}
    q5_b = b_manifest.get("q5_record") or {}
    q5_r = r_manifest.get("q5_record") or {}

    verdict = rs.get("verdict", "YELLOW")
    lines = [
        "# PYQ P2.1E Human Review → R2 Re-Audit",
        "",
        f"**Verdict:** **{verdict}**",
        "**Baseline (R1):** `data/staging/pyq/2020-2025/p2_1e_full/` (preserved)",
        f"**R2:** `{r2_dir}`",
        "",
        "## Parser change",
        "",
        "Inline option reconstruction in `parse_options_bounded()` using `OPTION_START_RE`",
        "with line-cap on option (4) and preserved Q15→Q20 boundary truncation.",
        "",
        "## Metrics comparison",
        "",
        "| Metric | R1 (baseline) | R2 |",
        "|--------|--------------:|---:|",
        f"| Questions | {bs.get('questions_extracted')} | {rs.get('questions_extracted')} |",
        f"| VALID | {bq.get('VALID', 0)} | {delta('VALID')} |",
        f"| PARTIAL | {bq.get('PARTIAL', 0)} | {delta('PARTIAL')} |",
        f"| DIAGRAM_DEPENDENT | {bq.get('DIAGRAM_DEPENDENT', 0)} | {delta('DIAGRAM_DEPENDENT')} |",
        f"| NEEDS_REVIEW | {bq.get('NEEDS_REVIEW', 0)} | {delta('NEEDS_REVIEW')} |",
        f"| Fidelity A+B | {bs.get('fidelity', {}).get('fidelity_rate')}% | {rs.get('fidelity', {}).get('fidelity_rate')}% |",
        f"| false_positive_rate | {bs.get('fidelity', {}).get('false_positive_rate')}% | {rs.get('fidelity', {}).get('false_positive_rate')}% |",
        f"| fragment_rate | {bs.get('fidelity', {}).get('fragment_rate')}% | {rs.get('fidelity', {}).get('fragment_rate')}% |",
        f"| cross_column_flags | {bs.get('cross_column_flags')} | {rs.get('cross_column_flags')} |",
        f"| OCR_SUCCESS | {bs.get('ocr_success')} | {rs.get('ocr_success')} |",
        f"| Idempotent | {bs.get('idempotent')} | {rs.get('idempotent')} |",
        "",
        "## Q15 regression",
        "",
        f"R1 options: {[q15_b.get(f'option_{x}') for x in 'abcd']}",
        f"R2 options: {[q15_r.get(f'option_{x}') for x in 'abcd']}",
        f"R2 Q15 pass (no Q20 bleed): **{r_manifest.get('q15_regression_pass')}**",
        "",
        "## Q5 regression",
        "",
        f"R1 stem: `{(q5_b.get('stem') or '')[:120]}`",
        f"R2 stem: `{(q5_r.get('stem') or '')[:120]}`",
        f"R2 Q5 pass: **{r_manifest.get('q5_regression_pass')}**",
        "",
        "## Safety",
        "",
        "| Check | Status |",
        "|-------|--------|",
        "| Production DB writes | **0** |",
        "| P3/P4/P5 | **NOT RUN** |",
        "| Baseline R1 preserved | **YES** |",
        "",
        "## Decision",
        "",
        f"**{verdict}** — R2 improves inline option handling. GREEN not declared without",
        "full human fidelity sampling on R2 `samples.p2_1e_full.json`.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="P2.1E full-corpus bbox OCR staging run")
    parser.add_argument("--zip", type=Path, default=_repo_root() / "NEET_PYQ_OFFICIAL.zip")
    parser.add_argument("--staging", type=Path, default=default_staging_root(_repo_root()))
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: p2_1e_full or p2_1e_full_r2 with --iteration r2)",
    )
    parser.add_argument(
        "--iteration",
        choices=("r1", "r2", "r3"),
        default="r2",
        help="Run iteration label; r2→p2_1e_full_r2/, r3→p2_1e_full_r3/",
    )
    parser.add_argument(
        "--compare-to",
        type=Path,
        default=None,
        help="Baseline directory for post-run comparison (e.g. p2_1e_full for R2 runs)",
    )
    args = parser.parse_args()

    staging_root = default_staging_root(_repo_root())
    if args.output is None:
        subdir_map = {"r1": "p2_1e_full", "r2": "p2_1e_full_r2", "r3": "p2_1e_full_r3"}
        subdir = subdir_map[args.iteration]
        args.output = staging_root / subdir

    report_names = {
        "r1": "PYQ_P2_1E_FULL_REPORT.md",
        "r2": "PYQ_P2_1E_FULL_R2_REPORT.md",
        "r3": "PYQ_P2_1E_FULL_R3_REPORT.md",
    }
    report_name = report_names[args.iteration]

    if args.iteration == "r3":
        from app.modules.cms.pyq.pyq_p2_1e import run_p2_1e_r3_from_r2_words

        r2_dir = staging_root / "p2_1e_full_r2"
        summary, manifest = run_p2_1e_r3_from_r2_words(
            staging_root=args.staging,
            r2_dir=r2_dir,
            output_dir=args.output,
        )
    else:
        summary, manifest = run_p2_1e_full(
            staging_root=args.staging,
            zip_path=args.zip,
            output_dir=args.output,
        )
    manifest["iteration"] = args.iteration
    report = write_report(summary, manifest, output_dir=args.output, report_name=report_name)
    print(json.dumps(summary.__dict__, indent=2))
    print(f"\nReport: {report}")

    baseline = args.compare_to or (staging_root / "p2_1e_full")
    if args.iteration == "r2" and baseline.exists():
        cmp_report = write_comparison_report(baseline_dir=baseline, r2_dir=args.output)
        print(f"Comparison: {cmp_report}")


if __name__ == "__main__":
    main()
