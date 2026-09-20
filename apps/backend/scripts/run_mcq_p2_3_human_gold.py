#!/usr/bin/env python3
"""P2.3 human-gold validation gate CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/backend"))

from app.modules.cms.mcq.p2_3.human_gold_gate.pipeline import (  # noqa: E402
    prepare_human_gold_review,
    report_human_gold,
    run_all,
    validate_human_gold,
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
            "--ignore=app/modules/cms/tests/test_mcq_p2_3_human_gold_gate.py",
        ],
        cwd=backend,
        capture_output=True,
        text=True,
    )
    new = subprocess.run(
        [str(py), "-m", "pytest", "app/modules/cms/tests/test_mcq_p2_3_human_gold_gate.py", "-q"],
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
                        if p == "failed":
                            failed = int(parts[i - 1])
                            break
                return int(parts[0]), failed
        return 0, 1 if code != 0 else 0

    ep, ef = _count(existing.stdout + existing.stderr, existing.returncode)
    np, nf = _count(new.stdout + new.stderr, new.returncode)
    return ep, ef, np, nf


def print_gate_summary(manifest: dict) -> None:
    print("=" * 60)
    print("P2.3 HUMAN-GOLD VALIDATION GATE")
    print("=" * 60)
    print(f"Sample size: {manifest.get('sample_size')}")
    print(f"Human reviewed: {manifest.get('human_reviewed')}")
    print(f"Pending: {manifest.get('pending')}")
    print(f"Partial: {manifest.get('partial')}")
    print(f"Completion rate: {manifest.get('completion_rate')}")
    print(f"Overall agreement: {manifest.get('overall_agreement_rate')}")
    print(f"Answer-key agreement: {manifest.get('answer_key_agreement_rate')}")
    print(f"False-pass: {manifest.get('false_pass_count')} (rate {manifest.get('false_pass_rate')})")
    print(f"False-reject: {manifest.get('false_reject_count')} (rate {manifest.get('false_reject_rate')})")
    print(f"10K recommendation: {manifest.get('ten_k_recommendation')}")
    print(f"FINAL GATE: {manifest.get('gate_status')} — {manifest.get('gate_reason')}")
    print(f"Production DB writes: {manifest.get('production_db_writes', 0)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="P2.3 human-gold validation gate")
    parser.add_argument("--prepare", action="store_true", help="Create reviewer-ready CSV")
    parser.add_argument("--validate", action="store_true", help="Validate human fields and compute metrics")
    parser.add_argument("--report", action="store_true", help="Generate gate reports")
    parser.add_argument("--all", action="store_true", help="Prepare + validate + report")
    parser.add_argument("--test", action="store_true", help="Run test suites")
    args = parser.parse_args()

    if args.test:
        ep, ef, np, nf = run_tests()
        print(f"Existing CMS tests: {ep} passed, {ef} failed")
        print(f"Human-gold gate tests: {np} passed, {nf} failed")
        return 0 if ef == 0 and nf == 0 else 1

    if args.prepare:
        manifest = prepare_human_gold_review(root=ROOT)
        print(json.dumps(manifest, indent=2))
        return 0

    if args.validate:
        result = validate_human_gold(root=ROOT)
        print(json.dumps(result["summary"], indent=2))
        return 0

    if args.report:
        manifest = report_human_gold(root=ROOT)
        print_gate_summary(manifest)
        print(json.dumps(manifest.get("artifacts") or {}, indent=2))
        return 0

    if args.all:
        manifest = run_all(root=ROOT)
        print_gate_summary(manifest)
        print(json.dumps(manifest.get("artifacts") or {}, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
