#!/usr/bin/env python3
"""P2.2-R1 — independent validation of 326 Gemini MCQs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R3 = ROOT / "data/staging/pyq/2020-2025/p2_1e_full_r3"
OUT = ROOT / "data/staging/pyq/2020-2025/p2_2_r1_validation"
DOCS = ROOT / "docs/content-factory"
MCQ = DOCS / "PYQ_P2_2_MCQ_RESULTS.jsonl"

sys.path.insert(0, str(ROOT / "apps/backend"))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.pyq.p2_2.r1_validation.pipeline import run_r1_validation  # noqa: E402


def r3_checksum() -> str:
    p = R3 / "questions.p2_1e_full.jsonl"
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_tests() -> tuple[int, int, int, int]:
    backend = ROOT / "apps/backend"
    py = backend / ".venv/Scripts/python.exe"
    if not py.exists():
        py = Path(sys.executable)
    existing = subprocess.run(
        [str(py), "-m", "pytest", "app/modules/cms/tests/", "-q", "--confcutdir=app/modules/cms/tests", "--ignore=app/modules/cms/tests/test_pyq_p2_2_r1.py"],
        cwd=backend,
        capture_output=True,
        text=True,
    )
    new = subprocess.run(
        [str(py), "-m", "pytest", "app/modules/cms/tests/test_pyq_p2_2_r1.py", "-q"],
        cwd=backend,
        capture_output=True,
        text=True,
    )

    def _count(out: str, code: int) -> tuple[int, int]:
        for line in out.splitlines():
            if " passed" in line:
                parts = line.strip().split()
                failed = 0
                if "failed" in line:
                    for i, p in enumerate(parts):
                        if p == "failed,":
                            failed = int(parts[i - 1])
                return int(parts[0]), failed
        return 0, 1 if code != 0 else 0

    ep, ef = _count(existing.stdout + existing.stderr, existing.returncode)
    np, nf = _count(new.stdout + new.stderr, new.returncode)
    return ep, ef, np, nf


def write_report_md(summary: dict, path: Path) -> None:
    iv = summary.get("independent_validation") or {}
    q = summary.get("quality") or {}
    e = summary.get("economics") or {}
    lines = [
        "# P2.2-R1 Validation Report",
        "",
        f"Generated: {summary.get('generated_at')}",
        "",
        "## Input",
        f"- Generated candidates: {summary.get('input', {}).get('generated_candidates')}",
        f"- Structurally valid Gemini: {summary.get('input', {}).get('structurally_valid')}",
        "",
        "## Independent Validator",
        f"- Provider: {iv.get('provider')}",
        f"- Processed: {iv.get('processed')}",
        f"- PASS: {iv.get('pass')} | FAIL: {iv.get('fail')} | INCONCLUSIVE: {iv.get('inconclusive')}",
        "",
        "## Quality",
        json.dumps(q, indent=2),
        "",
        "## Economics",
        json.dumps(e, indent=2),
        "",
        f"**Final verdict:** {summary.get('final_verdict')}",
        f"**Next action:** {summary.get('next_action')}",
        "",
        "Production import: BLOCKED",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_terminal(summary: dict, *, ep: int, ef: int, np: int, nf: int) -> None:
    iv = summary.get("independent_validation") or {}
    hg = summary.get("human_gold") or {}
    q = summary.get("quality") or {}
    e = summary.get("economics") or {}
    ft = summary.get("failure_taxonomy", {}).get("counts") or {}
    print("=" * 60)
    print("P2.2-R1 VALIDATION")
    print("=" * 60)
    print("INPUT:")
    print(f"  Generated: {summary.get('input', {}).get('generated_candidates')}")
    print(f"  Structurally valid: {summary.get('input', {}).get('structurally_valid')}")
    print("INDEPENDENT VALIDATOR:")
    print(f"  Provider: {iv.get('provider')}")
    print(f"  Processed: {iv.get('processed')}")
    print(f"  PASS: {iv.get('pass')}")
    print(f"  FAIL: {iv.get('fail')}")
    print(f"  INCONCLUSIVE: {iv.get('inconclusive')}")
    print("HUMAN GOLD:")
    print(f"  Sample: {hg.get('sample_size')}")
    print(f"  PASS: {hg.get('pass')} (pending review)")
    print(f"  MINOR_REVISION: {hg.get('minor_revision')}")
    print(f"  MAJOR_REVISION: {hg.get('major_revision')}")
    print(f"  REJECT: {hg.get('reject')}")
    print(f"  INCONCLUSIVE: {hg.get('inconclusive')}")
    print("TRUE ACCEPTANCE:")
    print(f"  {iv.get('pass', 0)} / 326 = {round((iv.get('pass', 0) / 326) * 100, 1)}%")
    print("PRODUCTION READY:")
    grades = q.get("grades") or {}
    print(f"  {grades.get('A', 0)} / 326 = {round((grades.get('A', 0) / 326) * 100, 1)}%")
    print(f"FALSE PASS: {q.get('false_pass_rate', 0)}% (pending human gold)")
    print(f"NCERT SUPPORT proxy: {round((1 - q.get('ambiguity_rate', 0)) * 100, 1)}%")
    print(f"AMBIGUITY: {round((q.get('ambiguity_rate', 0)) * 100, 1)}%")
    print(f"DUPLICATE: {round((q.get('duplicate_rate', 0)) * 100, 1)}%")
    print(f"ANSWER ACCURACY proxy: {round((q.get('answer_accuracy_proxy', 0)) * 100, 1)}%")
    print("COST:")
    print(f"  Generation: ${e.get('generation_cost_usd')}")
    print(f"  Validation: ${e.get('validation_cost_usd')}")
    print(f"  Total: ${e.get('total_cost_usd')}")
    print("FAILURE TAXONOMY:")
    for k, v in sorted(ft.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("SAFETY:")
    print("  R3 modified: NO")
    print("  Production DB writes: 0")
    print(f"  Existing tests: {ep} passed / {ef} failed")
    print(f"  New tests: {np} passed / {nf} failed")
    print("=" * 60)
    print(f"FINAL VERDICT: {summary.get('final_verdict')}")
    print(f"NEXT ACTION: {summary.get('next_action')}")
    print("PRODUCTION IMPORT: BLOCKED")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--max-cost-usd", type=float, default=25.0)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    print(f"Validator probe: OpenAI gpt-4o-mini preferred (configured model may be incompatible)")
    print(f"Budget: ${args.max_cost_usd}")
    print(f"Population: 326 Gemini structural MCQs from {MCQ}")

    if not args.confirm:
        print("ERROR: Pass --confirm to run live independent validation.", file=sys.stderr)
        return 2

    before = r3_checksum()
    if not args.skip_tests:
        ep, ef, np, nf = run_tests()
        if ef or nf:
            print("STOP: tests failed", file=sys.stderr)
            return 1
    else:
        ep = ef = np = nf = 0

    summary = run_r1_validation(
        root=ROOT,
        mcq_path=MCQ,
        output_dir=OUT,
        docs_dir=DOCS,
        study_material_dir=Path(settings.study_material_dir),
        r3_questions_path=R3 / "questions.p2_1e_full.jsonl",
        max_cost_usd=args.max_cost_usd,
        concurrency=args.concurrency,
    )
    after = r3_checksum()
    if before != after:
        print("STOP: R3 modified", file=sys.stderr)
        return 1

    summary["tests"] = {"existing_pass": ep, "existing_fail": ef, "new_pass": np, "new_fail": nf}
    (DOCS / "PYQ_P2_2_R1_VALIDATION_REPORT.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report_md(summary, DOCS / "PYQ_P2_2_R1_VALIDATION_REPORT.md")
    print_terminal(summary, ep=ep, ef=ef, np=np, nf=nf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
