#!/usr/bin/env python3
"""P2.3 NCERT MCQ Content Factory pilot CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/backend"))

from app.modules.cms.mcq.p2_3.pipeline import (  # noqa: E402
    dry_run_preflight,
    run_generation,
    run_gold_sample,
    run_report,
    run_validation,
)


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
            "--ignore=app/modules/cms/tests/test_mcq_p2_3.py",
        ],
        cwd=backend,
        capture_output=True,
        text=True,
    )
    new = subprocess.run(
        [str(py), "-m", "pytest", "app/modules/cms/tests/test_mcq_p2_3.py", "-q"],
        cwd=backend,
        capture_output=True,
        text=True,
    )

    def _count(out: str, code: int) -> tuple[int, int]:
        for line in out.splitlines():
            if " passed" in line:
                parts = line.strip().split()
                passed = int(parts[0])
                failed = 0
                if "failed" in line:
                    for i, p in enumerate(parts):
                        if p == "failed,":
                            failed = int(parts[i - 1])
                return passed, failed
        return 0, 1 if code != 0 else 0

    return (*_count(existing.stdout + existing.stderr, existing.returncode), *_count(new.stdout + new.stderr, new.returncode))


def print_summary(report: dict) -> None:
    es = report.get("executive_summary") or {}
    cost = report.get("cost_analysis") or {}
    print("=" * 60)
    print("P2.3 NCERT MCQ CONTENT FACTORY PILOT")
    print("=" * 60)
    print(f"New MCQs attempted: {es.get('new_mcqs_attempted', 0)}")
    print(f"Structurally valid: {es.get('structurally_valid', 0)}")
    print(f"NCERT-supported: {es.get('ncert_supported', 0)}")
    print(f"Independently validated: {es.get('independently_validated', 0)}")
    print(f"Validation READY: {es.get('validation_ready', 0)}")
    print(f"P2.2 protected: {es.get('p2_2_protected', 0)} (not regenerated)")
    print(f"Production DB writes: {es.get('production_db_writes', 0)}")
    print(f"Total cost: ₹{cost.get('total_cost_inr', 0)}")
    print(f"₹/usable MCQ: {cost.get('cost_per_usable_mcq_inr', 'N/A')}")
    print(f"Scale decision: {report.get('scale_decision', 'PENDING')}")
    print(f"Next action: {report.get('next_action', '')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="P2.3 NCERT MCQ Content Factory pilot")
    parser.add_argument("--dry-run", action="store_true", help="Preflight without API spend")
    parser.add_argument("--generate", action="store_true", help="Generate new MCQs")
    parser.add_argument("--validate", action="store_true", help="Run independent validation")
    parser.add_argument("--gold-sample", action="store_true", help="Select human gold sample")
    parser.add_argument("--report", action="store_true", help="Generate pilot report")
    parser.add_argument("--resume", action="store_true", help="Resume incomplete run")
    parser.add_argument("--count", type=int, default=None, help="Generation or gold-sample count")
    parser.add_argument("--test", action="store_true", help="Run test suites")
    args = parser.parse_args()

    if args.test:
        ep, ef, np, nf = run_tests()
        print(f"Existing tests: {ep}/{ep + ef} passed")
        print(f"P2.3 tests: {np}/{np + nf} passed")
        return 0 if ef == 0 and nf == 0 else 1

    if args.dry_run and not any([args.generate, args.validate, args.gold_sample, args.report]):
        pre = dry_run_preflight(ROOT)
        print(json.dumps(pre, indent=2))
        gen = run_generation(root=ROOT, count=args.count or 10, dry_run=True, resume=args.resume)
        val = run_validation(root=ROOT, dry_run=True, resume=args.resume)
        gold = run_gold_sample(root=ROOT, count=args.count or 100, dry_run=True)
        report = run_report(root=ROOT)
        print_summary(report)
        print(f"Dry-run generation: {gen}")
        print(f"Dry-run validation: {val}")
        print(f"Gold sample: {gold}")
        return 0

    if args.generate:
        result = run_generation(root=ROOT, count=args.count, dry_run=False, resume=args.resume)
        print(json.dumps(result, indent=2))
    if args.validate:
        result = run_validation(root=ROOT, resume=args.resume, dry_run=False)
        print(json.dumps(result, indent=2))
    if args.gold_sample:
        result = run_gold_sample(root=ROOT, count=args.count or 100)
        print(json.dumps(result, indent=2))
    if args.report:
        report = run_report(root=ROOT)
        print_summary(report)
    if not any([args.dry_run, args.generate, args.validate, args.gold_sample, args.report, args.test]):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
