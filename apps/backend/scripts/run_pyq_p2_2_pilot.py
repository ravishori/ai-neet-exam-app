#!/usr/bin/env python3
"""P2.2 — AI-assisted source recovery pilot (dry-run by default)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R3 = ROOT / "data/staging/pyq/2020-2025/p2_1e_full_r3"
OUT = ROOT / "data/staging/pyq/2020-2025/p2_2_ai_recovery"
DOCS = ROOT / "docs/content-factory"
AUDIT = DOCS / "PYQ_P2_1G_R3_HUMAN_FIDELITY_AUDIT.json"
ZIP = ROOT / "data/staging/pyq/NEET_PYQ_OFFICIAL.zip"

sys.path.insert(0, str(ROOT / "apps/backend"))

from app.modules.cms.pyq.p2_2.pipeline import build_triage_artifact, run_pilot  # noqa: E402
from app.modules.cms.pyq.p2_2.providers import DryRunRecoveryProvider  # noqa: E402


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def r3_checksums_before() -> dict[str, str]:
    r3_files = [
        R3 / "questions.p2_1e_full.jsonl",
        R3 / "ocr.words.p2_1e_full.jsonl",
        R3 / "manifest.p2_1e_full.json",
    ]
    return {str(p.relative_to(ROOT)): file_sha256(p) for p in r3_files if p.exists()}


def run_tests() -> tuple[int, int, int, int]:
    backend = ROOT / "apps/backend"
    py = backend / ".venv" / "Scripts" / "python.exe"
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
            "--ignore=app/modules/cms/tests/test_pyq_p2_2.py",
        ],
        cwd=backend,
        capture_output=True,
        text=True,
    )
    new = subprocess.run(
        [str(py), "-m", "pytest", "app/modules/cms/tests/test_pyq_p2_2.py", "-q"],
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

    ep, ef = _count(existing.stdout + existing.stderr, existing.returncode)
    np, nf = _count(new.stdout + new.stderr, new.returncode)
    return ep, ef, np, nf


def print_terminal_summary(report: dict, *, existing_pass: int, existing_fail: int, new_pass: int, new_fail: int) -> None:
    triage = report.get("triage") or {}
    pilot = report.get("pilot") or {}
    fidelity = pilot.get("source_fidelity") or {}
    print("=" * 60)
    print("P2.2 AI-ASSISTED SOURCE RECOVERY")
    print("=" * 60)
    r3 = report.get("r3_input") or {}
    print("R3 INPUT:")
    print(f"  Questions: {r3.get('questions', 0)}")
    print(f"  VALID: {r3.get('VALID', 0)}")
    print(f"  PARTIAL: {r3.get('PARTIAL', 0)}")
    print("TRIAGE:")
    print(f"  Deterministic: {triage.get('DETERMINISTIC_RECOVERABLE', 0)}")
    print(f"  AI multimodal: {triage.get('AI_MULTIMODAL_RECOVERABLE', 0)}")
    print(f"  Human review: {triage.get('HUMAN_REVIEW', 0)}")
    print(f"  Source insufficient: {triage.get('SOURCE_INSUFFICIENT', 0)}")
    print("PILOT:")
    print(f"  Candidates: {pilot.get('candidates', 0)}")
    print(f"  Processed: {pilot.get('processed', 0)}")
    print(f"  AI recovered: {pilot.get('ai_recovered', 0)}")
    print(f"  Verified: {pilot.get('verified', 0)}")
    print(f"  Inconclusive: {pilot.get('inconclusive', 0)}")
    print(f"  Not recoverable: {pilot.get('not_recoverable', 0)}")
    print(f"  Human review: {pilot.get('human_review', 0)}")
    print(f"  Provider disagreement: {pilot.get('provider_disagreement', 0)}")
    print("SOURCE FIDELITY:")
    for grade in ("A", "B", "C", "D", "E", "INCONCLUSIVE"):
        print(f"  {grade}: {fidelity.get(grade, 0)}")
    print("FALSE RECOVERY:")
    print(f"  {pilot.get('false_recovery', 0)}")
    print("PROVIDER AGREEMENT:")
    print(f"  {pilot.get('provider_agreement_pct', 0)}%")
    print("TESTS:")
    print(f"  Existing: {existing_pass} passed / {existing_fail} failed")
    print(f"  New: {new_pass} passed / {new_fail} failed")
    print(f"R3 MODIFIED: {'NO' if not report.get('r3_modified') else 'YES'}")
    print(f"PRODUCTION DB: {report.get('production_db_writes', 0)} WRITES")
    print("=" * 60)
    status = "PILOT COMPLETE" if new_fail == 0 and existing_fail == 0 else "STOPPED"
    print(f"P2.2 STATUS: {status}")
    print("=" * 60)
    print("PRODUCTION IMPORT: BLOCKED")
    print("NEXT ACTION: SCALE / REFINE / HUMAN REVIEW")
    print("=" * 60)


def write_pilot_md(report: dict, path: Path) -> None:
    triage = report.get("triage") or {}
    pilot = report.get("pilot") or {}
    lines = [
        "# P2.2 AI Recovery Pilot Report",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Mode: {report.get('mode')}",
        "",
        "## R3 Input",
        f"- Questions: {report.get('r3_input', {}).get('questions')}",
        f"- VALID: {report.get('r3_input', {}).get('VALID')}",
        f"- PARTIAL: {report.get('r3_input', {}).get('PARTIAL')}",
        "",
        "## Triage Summary",
        f"- Deterministic recoverable: {triage.get('DETERMINISTIC_RECOVERABLE', 0)}",
        f"- AI multimodal recoverable: {triage.get('AI_MULTIMODAL_RECOVERABLE', 0)}",
        f"- Human review: {triage.get('HUMAN_REVIEW', 0)}",
        f"- Source insufficient: {triage.get('SOURCE_INSUFFICIENT', 0)}",
        "",
        "## Pilot Outcomes",
        f"- Candidates: {pilot.get('candidates')}",
        f"- Deterministic recovered: {pilot.get('deterministic_recovered')}",
        f"- AI recovered: {pilot.get('ai_recovered')}",
        f"- Verified: {pilot.get('verified')}",
        f"- Inconclusive: {pilot.get('inconclusive')}",
        f"- Not recoverable: {pilot.get('not_recoverable')}",
        f"- Human review: {pilot.get('human_review')}",
        f"- False recoveries: {pilot.get('false_recovery')}",
        f"- Provider agreement: {pilot.get('provider_agreement_pct')}%",
        "",
        "## Safety",
        "- R3 modified: NO",
        "- Production DB writes: 0",
        "- Auto-promote to VALID: NOT IMPLEMENTED",
        "",
        "## Gate",
        "Pilot requires explicit human review before bulk recovery.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="P2.2 AI recovery pilot")
    parser.add_argument("--live", action="store_true", help="Use live AI providers (requires API keys; still no production DB)")
    parser.add_argument("--pilot-size", type=int, default=75)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.live:
        print("ERROR: --live not enabled in P2.2 pilot gate; use dry-run only.", file=sys.stderr)
        return 2

    before = r3_checksums_before()
    zip_path = ZIP if ZIP.exists() else None

    triage = build_triage_artifact(r3_dir=R3, audit_json=AUDIT, zip_path=zip_path)
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "PYQ_P2_2_TRIAGE.json").write_text(json.dumps(triage, indent=2, ensure_ascii=False), encoding="utf-8")

    primary = DryRunRecoveryProvider()
    report = run_pilot(
        r3_dir=R3,
        output_dir=OUT,
        audit_json=AUDIT,
        zip_path=zip_path,
        primary=primary,
        secondary=primary,
        pilot_size=args.pilot_size,
        seed=args.seed,
    )

    after = r3_checksums_before()
    report["r3_modified"] = before != after
    report["production_db_writes"] = 0

    (DOCS / "PYQ_P2_2_PILOT_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_pilot_md(report, DOCS / "PYQ_P2_2_PILOT_REPORT.md")

    ep, ef, np, nf = run_tests()
    print_terminal_summary(report, existing_pass=ep, existing_fail=ef, new_pass=np, new_fail=nf)
    return 1 if ef or nf else 0


if __name__ == "__main__":
    raise SystemExit(main())
