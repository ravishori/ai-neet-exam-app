"""MCQ-CONTROLLED-GENERATION-002 — 100 DRAFT MCQs, 25 per subject.

Uses the provider-neutral Content Factory and the live GENERATION_READY
population. Provider routing remains fixed to OpenAI; existing Content Factory
retry policy handles transient parse/rate-limit failures. No publication,
certification, taxonomy, KU, mapping, or provenance mutation is performed.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import mcq_controlled_generation_001 as base

REPORT = "mcq_controlled_generation_002"
CAMPAIGN = "mcq-ctrl-gen-002"
PER_SUBJECT = 25
TOTAL = 100

base.REPORT = REPORT
base.CAMPAIGN = CAMPAIGN
base.PER_SUBJECT = PER_SUBJECT
base.TOTAL = TOTAL


def select_slots(ready: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Choose 25 ready slots/subject, maximizing chapter and BP diversity.

    Zoology currently has fewer than 25 ready blueprints, so only after every
    ready Zoology blueprint is used once are ready blueprints reused round-robin.
    """
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bp in ready:
        by_subject[bp["subject"]].append(bp)

    selected: dict[str, list[dict[str, Any]]] = {}
    for subject in base.SUBJECTS:
        pool = by_subject.get(subject, [])
        if not pool:
            raise RuntimeError(f"{subject}: no GENERATION_READY blueprints")

        ordered: list[dict[str, Any]] = []
        seen_chapters: set[str] = set()
        for bp in pool:
            if bp["chapter_code"] not in seen_chapters:
                ordered.append(bp)
                seen_chapters.add(bp["chapter_code"])
        ordered.extend(bp for bp in pool if bp not in ordered)

        slots = ordered[:PER_SUBJECT]
        cursor = 0
        while len(slots) < PER_SUBJECT:
            slots.append(ordered[cursor % len(ordered)])
            cursor += 1
        selected[subject] = slots
    return selected


base.pick_five_per_subject = select_slots


def write_markdown(report: dict[str, Any], path: Path) -> None:
    metrics = report["metrics"]
    lines = [
        "# MCQ-CONTROLLED-GENERATION-002",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verdict:** **{report['verdict']}**",
        f"**Provider/model:** openai / {report['provider_routing']['model_hint']} (fixed; no fallback)",
        "",
        "## Metrics",
        "",
        f"- Requested: **{metrics['requested']}** (25 Physics / 25 Chemistry / 25 Botany / 25 Zoology)",
        f"- Already existing at resume inspection: **{metrics.get('already_existing', 0)}**",
        f"- Remaining at resume inspection: **{metrics.get('remaining_at_resume', metrics['requested'])}**",
        f"- Provider attempts: **{metrics['attempted']}**",
        f"- Created unique DRAFTs: **{metrics['created']}**",
        f"- Parse failures: **{metrics['failed_parse']}**",
        f"- Validation failures: **{metrics['rejected_validation']}**",
        f"- Provider failures: **{metrics['failed_provider']}**",
        f"- Duplicates: **{metrics['duplicate']}**",
        f"- Syllabus failures: **{metrics['syllabus_gate_failures']}**",
        f"- NCERT-evidence failures: **{metrics['ncert_evidence_failures']}**",
        f"- Latency (summed run milliseconds): **{metrics['latency_ms_sum']}**",
        f"- Estimated cost USD: **{metrics['estimated_cost_usd']}**",
        f"- Exact remaining quantity: **{metrics.get('exact_remaining_quantity', max(0, metrics['requested'] - metrics['created']))}**",
        "",
        "## Subject distribution",
        "",
        "| Subject | Requested | Created |",
        "|---|---:|---:|",
    ]
    for subject in base.SUBJECTS:
        result = report["subject_results"][subject]
        lines.append(f"| {subject} | {result['requested']} | {result['created']} |")
    lines += [
        "",
        "## Deterministic verification",
        "",
        f"- Exactly 100 requested: **{report['acceptance']['requested_100']}**",
        f"- Requested distribution 25/25/25/25: **{report['acceptance']['subject_slots_25_each']}**",
        f"- Created distribution 25/25/25/25: **{report['acceptance']['created_100_25_each']}**",
        f"- All created content remains DRAFT: **{report['verification']['all_created_draft']}**",
        f"- Canonical NCERT source on every created candidate: **{report['verification']['every_created_has_canonical_ncert_path']}**",
        f"- Syllabus mapping on every created candidate: **{report['verification']['every_created_has_syllabus_mapping']}**",
        f"- Duplicate created stem hashes: **{report['verification']['duplicate_stem_hashes_among_created']}**",
        f"- Candidate/attempt records: **{len(report['candidates'])}**",
        "",
        "## Database safety",
        "",
        f"- Published delta: **{report['safety']['published_delta']}**",
        f"- Any wave candidate published: **{report['safety']['any_candidate_published']}**",
        f"- Taxonomy/KU/blueprint counts unchanged: **{report['safety']['inventory_core_unchanged']}**",
        f"- Existing unmapped DRAFT inventory unchanged: **{report['safety']['unmapped_draft_unchanged']}**",
        "",
        "## Boundary",
        "",
        "- Deterministic gates only; this task does not independently certify NCERT correctness.",
        "- No manual correction, publication, certification, provider fallback, or backlog resumption.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def normalize_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    report["task"] = "MCQ-CONTROLLED-GENERATION-002"
    report["source_audits"] = [
        str(base.ROOT / "docs/audits/mcq_controlled_generation_001.json"),
        str(base.ROOT / "docs/audits/mcq_ncert_verify_002.json"),
    ]
    report["provider_routing"] = {
        "FACTORY_PROVIDER": "openai",
        "MCQ_PROVIDER": "openai",
        "FACTORY_PROVIDER_MODE": "fixed",
        "fallback_allowed": False,
        "model_hint": base.get_settings().openai_model,
    }
    report["record_semantics"] = (
        "candidates contains one machine-readable record per persisted provider "
        "attempt/candidate, including failed parse/validation/provider/duplicate attempts"
    )
    report["verification"]["exactly_100_requested"] = report["metrics"]["requested"] == TOTAL
    report["verification"]["subject_distribution_requested_25_25_25_25"] = all(
        report["subject_results"][s]["requested"] == PER_SUBJECT for s in base.SUBJECTS
    )
    report["verification"].pop("exactly_20_requested", None)
    report["verification"].pop("subject_distribution_requested_5_5_5_5", None)
    report["acceptance"] = {
        "requested_100": report["metrics"]["requested"] == TOTAL,
        "subject_slots_25_each": all(
            report["subject_results"][s]["requested"] == PER_SUBJECT for s in base.SUBJECTS
        ),
        "created_100_25_each": (
            report["metrics"]["created"] == TOTAL
            and all(report["metrics"]["created_by_subject"][s] == PER_SUBJECT for s in base.SUBJECTS)
        ),
        "no_publication": (
            report["safety"]["published_delta"] == 0
            and not report["safety"]["any_candidate_published"]
        ),
        "inventory_freeze": report["safety"]["inventory_core_unchanged"],
        "verification_ok": report["acceptance"].get("verification_ok", False),
        "note": "Generation success is not independent NCERT certification.",
    }
    report["limitations"] = [
        "Deterministic generation gates only; no independent NCERT correctness certification.",
        "Live GENERATION_READY population used (syllabus + canonical NCERT evidence ready).",
        "Provider fixed to OpenAI; no silent provider switch or fallback.",
        "Zoology ready population is below 25, so ready blueprints are reused only after all are used once.",
    ]
    report["failures"] = []
    if not report["acceptance"]["created_100_25_each"]:
        report["failures"].append("created_count_below_100_or_uneven_subjects")
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    # Required inputs must exist before any provider call.
    for audit in (
        base.ROOT / "docs/audits/mcq_controlled_generation_001.json",
        base.ROOT / "docs/audits/mcq_ncert_verify_002.json",
    ):
        if not audit.is_file():
            raise FileNotFoundError(audit)

    result = base.main()
    json_path = base.ROOT / "docs/audits" / f"{REPORT}.json"
    md_path = base.ROOT / "docs/audits" / f"{REPORT}.md"
    report = normalize_report(json_path)
    write_markdown(report, md_path)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
