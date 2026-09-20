#!/usr/bin/env python3
"""P2.3-R1 — provider routing repair + revalidation (no new generation)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/backend"))

from app.modules.cms.mcq.p2_3.r1.pipeline import run_r1_revalidation  # noqa: E402


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
            "--ignore=app/modules/cms/tests/test_mcq_p2_3_r1.py",
        ],
        cwd=backend,
        capture_output=True,
        text=True,
    )
    p23 = subprocess.run(
        [str(py), "-m", "pytest", "app/modules/cms/tests/test_mcq_p2_3.py", "-q"],
        cwd=backend,
        capture_output=True,
        text=True,
    )
    r1 = subprocess.run(
        [str(py), "-m", "pytest", "app/modules/cms/tests/test_mcq_p2_3_r1.py", "-q"],
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

    return (
        *_count(existing.stdout + existing.stderr, existing.returncode),
        *_count(p23.stdout + p23.stderr, p23.returncode),
        *_count(r1.stdout + r1.stderr, r1.returncode),
    )


def print_summary(report: dict) -> None:
    m = report.get("metrics") or {}
    c = report.get("cost") or {}
    print("=" * 60)
    print("P2.3-R1 PROVIDER REPAIR + REVALIDATION")
    print("=" * 60)
    print(f"Generation: NO NEW GENERATION")
    print(f"QA PASS: {m.get('qa_pass')}/{m.get('total_generated')}")
    print(f"Independent validation: {m.get('independently_validated')}/{m.get('qa_pass')}")
    print(f"Previously blocked revalidated: {report.get('revalidated_count', 0)}")
    print(f"AI READY: {m.get('ready')}")
    print(f"MINOR: {m.get('minor_revision')}")
    print(f"MAJOR: {m.get('major_revision')}")
    print(f"REJECT: {m.get('reject')}")
    print(f"INCONCLUSIVE: {m.get('inconclusive')}")
    print(f"Provider failures: {m.get('provider_failures')}")
    print(f"R1 validation cost: ₹{c.get('r1_validation_cost_inr')}")
    print(f"₹/AI-READY: ₹{c.get('cost_per_ai_ready_inr')}")
    print(f"Scale decision: {report.get('scale_decision')}")
    print(f"Reason: {report.get('scale_reason')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="P2.3-R1 provider repair revalidation")
    parser.add_argument("--revalidate", action="store_true", help="Revalidate blocked records")
    parser.add_argument("--resume", action="store_true", help="Resume R1 revalidation")
    parser.add_argument("--test", action="store_true", help="Run test suites")
    args = parser.parse_args()

    if args.test:
        ep, ef, p3p, p3f, r1p, r1f = run_tests()
        print(f"Existing CMS: {ep}/{ep + ef}")
        print(f"P2.3: {p3p}/{p3p + p3f}")
        print(f"P2.3-R1: {r1p}/{r1p + r1f}")
        return 0 if ef == 0 and p3f == 0 and r1f == 0 else 1

    if args.revalidate:
        report = run_r1_revalidation(root=ROOT, resume=args.resume)
        print_summary(report)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
