#!/usr/bin/env python3
"""FACTORY-PYQ-P2.1E — targeted Tesseract bbox proof-of-concept."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.modules.cms.pyq.pyq_p2_1e import TARGET_PAGE_SELECTION, run_p2_1e_poc
from app.modules.cms.pyq.pyq_staging import default_staging_root


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def write_report(summary, manifest: dict, *, output_dir: Path) -> Path:
    docs = _repo_root() / "docs" / "content-factory"
    docs.mkdir(parents=True, exist_ok=True)
    report_path = docs / "PYQ_P2_1E_BBOX_POC_REPORT.md"
    q5 = manifest.get("q5_record") or {}
    q15 = manifest.get("q15_record") or {}
    q5_cmp = manifest.get("q5_before_after") or {}
    q15_cmp = manifest.get("q15_before_after") or {}
    if not q5_cmp:
        q5_cmp = (manifest.get("samples") or {}).get("q5_before_after", {})
    pc = manifest.get("pipeline_comparison") or {}
    fid = summary.fidelity

    lines = [
        "# PYQ P2.1E Bbox OCR Proof-of-Concept Report",
        "",
        f"**Generated:** {summary.generated_at}",
        f"**Verdict:** **{summary.verdict}**",
        "**Mode:** Targeted re-OCR with persisted Tesseract word geometry (POC only)",
        f"**Output:** `{output_dir}`",
        "",
        "## 1. Executive verdict",
        "",
        f"**{summary.verdict}** — P2.1E bbox POC on **{summary.pages_targeted}** targeted pages.",
        "",
        f"- Geometry-valid pages: **{summary.pages_geometry_valid}/{summary.pages_targeted}**",
        f"- Questions extracted (target pages): **{summary.questions_extracted}**",
        f"- Fidelity rate (A+B): **{fid.get('fidelity_rate', 0)}%** vs P2.1B-HR baseline **1.8%**",
        f"- HR regression pass: **{all(r['passed'] for r in summary.hr_regression)}**",
        f"- Idempotent: **{summary.idempotent}**",
        "",
        "## 2. Target page selection",
        "",
        "| SHA (prefix) | Page | Category | Reason |",
        "|--------------|-----:|----------|--------|",
    ]
    for t in TARGET_PAGE_SELECTION:
        lines.append(
            f"| `{t['sha'][:12]}…` | {t['page']} | {t['category']} | {t['reason']} |"
        )

    lines.extend(
        [
            "",
            "## 3. Tesseract configuration",
            "",
            "| Setting | Value |",
            "|---------|-------|",
            "| Engine | Local Tesseract CLI |",
            "| Language | eng |",
            "| PSM | 6 |",
            "| Output | TSV (full word geometry) |",
            "| DPI | 200 (matches P2.1 staging) |",
            "",
            "## 4. BBOX persistence validation",
            "",
            f"| Metric | Value |",
            f"|--------|------:|",
            f"| Word records persisted | {len(manifest.get('page_geometry_diagnostics', []))} pages |",
            f"| Pages geometry-valid | {summary.pages_geometry_valid} |",
            "",
            "## 5. Geometry detection results",
            "",
        ]
    )
    layout_counts = {}
    for d in manifest.get("page_geometry_diagnostics", []):
        layout_counts[d.get("layout", "?")] = layout_counts.get(d.get("layout", "?"), 0) + 1
    lines.append("| Layout | Pages |")
    lines.append("|--------|------:|")
    for k, v in sorted(layout_counts.items()):
        lines.append(f"| {k} | {v} |")

    lines.extend(
        [
            "",
            "## 6. Q5 before/after",
            "",
            "### P2.1C (before)",
            "",
            f"Stem: `{(q5_cmp.get('p2_1c') or {}).get('stem', 'N/A')[:200]}`",
            "",
            "### P2.1E (after)",
            "",
            f"Stem: `{(q5.get('stem') or 'NOT EXTRACTED')[:200]}`",
            f"Options: {[q5.get(f'option_{x}') for x in 'abcd'] if q5 else []}",
            f"Quality: {q5.get('p2_1e_quality_status') if q5 else 'MISSING'}",
            "",
            "## 7. Q15/Q11 before/after",
            "",
            f"P2.1C Q15 options: {[ (q15_cmp.get('p2_1c') or {}).get(f'option_{x}') for x in 'abcd']}",
            f"P2.1E Q15 options: {[q15.get(f'option_{x}') if q15 else '' for x in 'abcd']}",
            "",
            "## 8. HR regression results",
            "",
        ]
    )
    for r in summary.hr_regression:
        lines.append(f"- **{r['label']}**: {'PASS' if r['passed'] else 'FAIL'}")
        if not r["passed"]:
            lines.append(f"  - {r.get('forbidden_stem_hits', r.get('forbidden_option_hits', []))}")

    lines.extend(
        [
            "",
            "## 9. Fidelity metrics",
            "",
            f"| Metric | P2.1E POC | P2.1B-HR baseline |",
            f"|--------|----------:|------------------:|",
            f"| fidelity_rate (A+B) | {fid.get('fidelity_rate')}% | 1.8% |",
            f"| false_positive_rate (E) | {fid.get('false_positive_rate')}% | 9.1% |",
            f"| fragment_rate (D) | {fid.get('fragment_rate')}% | 9.1% |",
            "",
            f"Class counts: `{fid.get('counts', {})}`",
            "",
            "## 10–12. Pipeline comparison / cross-column / idempotency",
            "",
            "```json",
            json.dumps(pc, indent=2)[:3000],
            "```",
            "",
            f"**Idempotent:** words={summary.words_hash_pass1 == summary.words_hash_pass2}, "
            f"questions={summary.questions_hash_pass1 == summary.questions_hash_pass2}",
            "",
            "## 13. Tests",
            "",
            "Run: `pytest app/modules/cms/tests/test_pyq_p2_1e.py app/modules/cms/tests/test_pyq_p2_1c.py`",
            "",
            "## 14. Safety attestation",
            "",
            "| Check | Status |",
            "|-------|--------|",
        ]
    )
    for k, v in summary.safety.items():
        lines.append(f"| {k} | **{v}** |")
    lines.extend(
        [
            "| Full 1,008-page OCR | **NOT RUN** |",
            "| Full --force OCR | **NOT RUN** |",
            "",
            "## 15. Recommendation",
            "",
            "If Q5 stem fidelity and fidelity_rate improve materially on this sample, authorize "
            "**full-corpus P2.1E** with persisted `ocr.words.p2_1e.jsonl` per paper — still staging-only, "
            "no P2.1 artifact overwrite.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="P2.1E bbox OCR proof-of-concept")
    parser.add_argument("--zip", type=Path, default=_repo_root() / "NEET_PYQ_OFFICIAL.zip")
    parser.add_argument("--staging", type=Path, default=default_staging_root(_repo_root()))
    parser.add_argument(
        "--output",
        type=Path,
        default=default_staging_root(_repo_root()) / "p2_1e",
    )
    args = parser.parse_args()

    summary, manifest = run_p2_1e_poc(
        staging_root=args.staging,
        zip_path=args.zip,
        output_dir=args.output,
    )
    # Attach before/after to manifest for report
    from app.modules.cms.pyq.pyq_p2_1e import _q15_before_after, _q5_before_after

    manifest["q5_before_after"] = _q5_before_after(args.staging, manifest.get("q5_record"))
    manifest["q15_before_after"] = _q15_before_after(args.staging, manifest.get("q15_record"))
    report = write_report(summary, manifest, output_dir=args.output)
    print(json.dumps(summary.__dict__, indent=2))
    print(f"\nReport: {report}")


if __name__ == "__main__":
    main()
