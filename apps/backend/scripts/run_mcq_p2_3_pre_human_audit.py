#!/usr/bin/env python3
"""P2.3 pre-human gold sample audit — quality screening before human review."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/backend"))

from app.modules.cms.mcq.p2_3.pre_human_audit.pipeline import run_pre_human_audit  # noqa: E402


def run_tests() -> tuple[int, int, int, int]:
    backend = ROOT / "apps/backend"
    py = backend / ".venv/Scripts/python.exe"
    if not py.exists():
        py = Path(sys.executable)
    existing = subprocess.run(
        [
            str(py),
            "-m",
            "pytest",
            "app/modules/cms/tests/",
            "-q",
            "--confcutdir=app/modules/cms/tests",
            "--ignore=app/modules/cms/tests/test_mcq_p2_3_pre_human_audit.py",
        ],
        cwd=backend,
        capture_output=True,
        text=True,
    )
    new = subprocess.run(
        [str(py), "-m", "pytest", "app/modules/cms/tests/test_mcq_p2_3_pre_human_audit.py", "-q"],
        cwd=backend,
        capture_output=True,
        text=True,
    )

    def _count(out: str, code: int) -> tuple[int, int]:
        for line in out.splitlines():
            if " passed" in line:
                parts = line.strip().split()
                return int(parts[0]), 0
        return 0, 1 if code != 0 else 0

    return (*_count(existing.stdout + existing.stderr, existing.returncode), *_count(new.stdout + new.stderr, new.returncode))


def print_summary(report: dict) -> None:
    es = report.get("executive_summary") or {}
    ai = report.get("answer_integrity") or {}
    print("=" * 60)
    print("P2.3 PRE-HUMAN GOLD SAMPLE AUDIT")
    print("=" * 60)
    print(f"Questions audited: {es.get('total_audited', 0)}")
    print(f"CRITICAL: {es.get('critical', 0)}")
    print(f"HIGH: {es.get('high', 0)}")
    print(f"MEDIUM: {es.get('medium', 0)}")
    print(f"LOW: {es.get('low', 0)}")
    print(f"Likely pass (screening): {es.get('likely_pass', 0)}")
    print(f"Flagged: {es.get('flagged', 0)}")
    print(f"Potential wrong answers: {ai.get('potential_wrong_answers', 0)}")
    print(f"Calculation failures: {ai.get('calculation_failures', 0)}")
    print(f"Assertion/Reason concerns: {ai.get('assertion_reason_failures', 0)}")
    print(f"Production DB writes: {report.get('production_db_writes', 0)}")
    print(f"VERDICT: {report.get('verdict', 'PENDING')}")
    print("Human review: PENDING (not human verified)")


def main() -> int:
    parser = argparse.ArgumentParser(description="P2.3 pre-human gold sample audit")
    parser.add_argument("--audit", action="store_true", help="Run pre-human audit on 100 gold questions")
    parser.add_argument("--test", action="store_true", help="Run test suites")
    args = parser.parse_args()

    if args.test:
        ep, ef, np, nf = run_tests()
        print(f"Existing CMS tests: {ep}/{ep + ef}")
        print(f"Pre-human audit tests: {np}/{np + nf}")
        return 0 if ef == 0 and nf == 0 else 1

    if args.audit:
        report = run_pre_human_audit(root=ROOT)
        print_summary(report)
        print(json.dumps(report.get("artifacts") or {}, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
