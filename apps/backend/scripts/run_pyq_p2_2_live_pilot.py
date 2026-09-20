#!/usr/bin/env python3
"""P2.2 LIVE AI pilot — Track A recovery + Track B NCERT MCQ generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R3 = ROOT / "data/staging/pyq/2020-2025/p2_1e_full_r3"
OUT = ROOT / "data/staging/pyq/2020-2025/p2_2_live_pilot"
DOCS = ROOT / "docs/content-factory"

sys.path.insert(0, str(ROOT / "apps/backend"))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.pyq.p2_2.live_pilot import (  # noqa: E402
    LIVE_SEED,
    estimate_preflight_cost,
    run_live_pilot,
)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def r3_checksums() -> dict[str, str]:
    files = [R3 / "questions.p2_1e_full.jsonl", R3 / "manifest.p2_1e_full.json"]
    return {str(p.relative_to(ROOT)): file_sha256(p) for p in files if p.exists()}


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
            "--ignore=app/modules/cms/tests/test_pyq_p2_2_live.py",
        ],
        cwd=backend,
        capture_output=True,
        text=True,
    )
    new = subprocess.run(
        [str(py), "-m", "pytest", "app/modules/cms/tests/test_pyq_p2_2_live.py", "-q"],
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


def print_summary(report: dict, *, ep: int, ef: int, np: int, nf: int) -> None:
    inr = report.get("usd_inr") or 83.0
    budget = report.get("budget") or {}
    spent = budget.get("spent_usd") or 0.0
    ta = report.get("track_a") or {}
    tb = report.get("track_b") or {}
    verdicts = report.get("verdicts") or {}
    cmp_ = report.get("provider_comparison") or {}

    def rs(name: str) -> dict:
        return (cmp_.get("mcq") or {}).get(name) or {}

    print("=" * 60)
    print("P2.2 LIVE AI PILOT")
    print("=" * 60)
    print("TRACK A — PYQ RECOVERY")
    print(f"Candidates: {ta.get('candidates', 0)}")
    for prov in ("gemini", "openai", "anthropic"):
        bp = (ta.get("by_provider") or {}).get(prov) or {}
        print(f"{prov.capitalize()}:")
        print(f"  Processed: {bp.get('processed', 0)}")
        print(f"  Recovered: {bp.get('recovered', 0)}")
        print(f"  Validated: {ta.get('verified', 0)}")
    print(f"Human accepted: PENDING (human review CSV)")
    print(f"Failed: {ta.get('failed', 0)}")
    print(f"Inconclusive: {ta.get('inconclusive', 0)}")
    print(f"Provider agreement: {(cmp_.get('recovery') or {}).get('mean_field_agreement', 0)}")
    print(f"False recovery: {ta.get('false_recovery', 0)}")
    print(f"Cost: ₹{_inr(spent * 0.35, inr)} (Track A ~35% est.)")
    print("---")
    print("TRACK B — NCERT MCQ GENERATION")
    print(f"Generated: {tb.get('generated', 0)}")
    print(f"Structurally valid: {tb.get('validated', 0) + tb.get('inconclusive', 0)}")
    print(f"NCERT supported: {round((tb.get('source_support_rate') or 0) * tb.get('generated', 0))}")
    print(f"Answer validated: {tb.get('validated', 0)}")
    print(f"Duplicate-free: {tb.get('generated', 0) - (tb.get('exact_duplicate_count', 0) + tb.get('near_duplicate_count', 0))}")
    print(f"Human sample size: {tb.get('human_sample_size', 0)}")
    print(f"Human accepted: PENDING")
    print("Provider comparison:")
    for prov in ("gemini", "openai", "anthropic"):
        p = rs(prov)
        if p:
            print(f"  {prov}: validated={p.get('validated', 0)} rejected={p.get('rejected', 0)} cost_usd={p.get('cost_usd', 0)}")
    print(f"Cost: ₹{_inr(spent * 0.65, inr)} (Track B ~65% est.)")
    print(f"Cost / human-accepted MCQ: PENDING")
    print("---")
    print("TESTS")
    print(f"Existing: {ep} passed / {ef} failed")
    print(f"New: {np} passed / {nf} failed")
    print(f"R3 modified: {'NO' if not report.get('r3_modified') else 'YES'}")
    print(f"Production DB writes: {report.get('production_db_writes', 0)}")
    print(f"Total API spend: ${spent:.4f} / ₹{_inr(spent, inr)}")
    print("=" * 60)
    print(f"TRACK A VERDICT: {verdicts.get('track_a', 'RED')}")
    print(f"TRACK B VERDICT: {verdicts.get('track_b', 'RED')}")
    print(f"OVERALL P2.2 LIVE PILOT: {verdicts.get('overall', 'RED')}")
    print(f"NEXT ACTION: {report.get('next_action', 'REFINE')}")
    print("PRODUCTION IMPORT: BLOCKED")
    print("=" * 60)


def _inr(usd: float, rate: float) -> float:
    return round(usd * rate, 2)


def write_report_md(report: dict, path: Path) -> None:
    lines = [
        "# P2.2 Live AI Pilot Report",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Seed: {report.get('seed')}",
        "",
        "## Budget",
        json.dumps(report.get("budget"), indent=2),
        "",
        "## Track A — PYQ Recovery",
        json.dumps(report.get("track_a"), indent=2),
        "",
        "## Track B — NCERT MCQ",
        json.dumps(report.get("track_b"), indent=2),
        "",
        "## Verdicts",
        json.dumps(report.get("verdicts"), indent=2),
        "",
        "Production import: BLOCKED",
        "Human review: see PYQ_P2_2_HUMAN_REVIEW.csv",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="P2.2 live AI pilot")
    parser.add_argument("--recovery-count", type=int, default=None)
    parser.add_argument("--mcq-count", type=int, default=None)
    parser.add_argument("--seed", type=int, default=LIVE_SEED)
    parser.add_argument("--max-cost-usd", type=float, default=None)
    parser.add_argument("--mcq-concurrency", type=int, default=6)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-recovery", action="store_true", help="Skip Track A if recovery results exist")
    parser.add_argument("--confirm", action="store_true", help="Required to spend live API budget")
    args = parser.parse_args()

    settings = get_settings()
    recovery_count = args.recovery_count or settings.p2_2_live_recovery_count
    mcq_count = args.mcq_count or settings.p2_2_live_mcq_count
    max_cost = args.max_cost_usd or settings.p2_2_live_max_cost_usd

    preflight = estimate_preflight_cost(
        recovery_count=recovery_count,
        mcq_count=mcq_count,
        providers_available=3,
    )
    print("Estimated maximum API cost:")
    print(f"  ${preflight['estimated_max_api_cost_usd']}")
    print(f"Budget configured: ${max_cost}")
    print(f"Pilot limits: recovery={recovery_count}, mcq={mcq_count}, seed={args.seed}")

    if not args.confirm:
        print("ERROR: Pass --confirm to run live API pilot.", file=sys.stderr)
        return 2

    before = r3_checksums()
    if not args.skip_tests:
        ep, ef, np, nf = run_tests()
        if ef or nf:
            print(f"STOP: tests failed existing={ef} new={nf}", file=sys.stderr)
            return 1
    else:
        ep = ef = np = nf = 0

    report = run_live_pilot(
        root=ROOT,
        output_dir=OUT,
        docs_dir=DOCS,
        recovery_count=recovery_count,
        mcq_count=mcq_count,
        seed=args.seed,
        max_cost_usd=max_cost,
        mcq_concurrency=args.mcq_concurrency,
        skip_recovery=args.skip_recovery,
    )
    after = r3_checksums()
    report["r3_modified"] = before != after
    report["tests"] = {"existing_pass": ep, "existing_fail": ef, "new_pass": np, "new_fail": nf}
    (DOCS / "PYQ_P2_2_LIVE_PILOT_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_report_md(report, DOCS / "PYQ_P2_2_LIVE_PILOT_REPORT.md")
    print_summary(report, ep=ep, ef=ef, np=np, nf=nf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
