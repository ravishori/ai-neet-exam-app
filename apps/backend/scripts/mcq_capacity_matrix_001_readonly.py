"""MCQ-CAPACITY-MATRIX-001 — deterministic capacity plan from syllabus + measured telemetry.

No MCQ generation. No DB mutation. No publication.
Loss rates are cited from project audits only — never invented.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

SYLLABUS_PATH = ROOT / "NEETSyllabus.txt"
EVIDENCE_PATH = ROOT / "docs" / "audits" / "mcq_evidence_coverage_001.json"
REPORT_STEM = "mcq_capacity_matrix_001"

# ---------------------------------------------------------------------------
# Measured telemetry (sources cited; do not invent)
# ---------------------------------------------------------------------------
TELEMETRY = {
    "factory_p3_forensic_100": {
        "source": "docs/audits/TALOS_FACTORY_P3_100_FORENSIC_PILOT_REPORT_20260902.json",
        "attempted": 143,
        "created": 95,
        "rejected_validation": 6,
        "rejected_duplicate": 24,
        "failed_parse": 18,
        "provider_fail": 0,
    },
    "historical_factory_candidates_pre_pilot001": {
        "source": "docs/audits/mcq_pilot_001_generation_20260913.md (historical baseline)",
        "total_candidates": 392,
        "created": 262,
        "failed_parse": 51,
        "rejected_validation": 31,
        "failed_provider": 24,
        "rejected_duplicate": 24,
    },
    "mcq_pilot_001": {
        "source": "docs/audits/mcq_pilot_001_generation_20260913.json",
        "requested": 400,
        "created": 129,
        "created_rate": 0.3225,
        "parse_success_rate": 0.9972,
        "validation_reject_rate": 0.0169,
        "duplicate_rate": 0.0,
        "provider_fail_rate": 0.6158,
    },
    "ncert_verify_001": {
        "source": "docs/audits/mcq_ncert_verify_001_20260914.json",
        "sample_created": 5,
        "ncert_pass": 3,
        "ncert_fail": 2,
        "ncert_pass_rate_among_created": 0.6,
        "note": "Small independent sample (n=5); post-GROUNDING-001 factory rates not yet re-measured at scale.",
    },
    "p2_3_offline_pilot": {
        "source": "docs/content-factory/P2_3_MCQ_PILOT_REPORT.json",
        "attempted": 1000,
        "structurally_valid": 614,
        "ncert_supported": 614,
        "independently_validated": 316,
        "validation_ready": 70,
        "duplicates": 1,
    },
    "evidence_coverage_001": {
        "source": "docs/audits/mcq_evidence_coverage_001.json",
        "latest_blueprint_keys": 445,
        "generation_ready": 278,
        "needs_ncert_source": 137,
        "needs_syllabus_review": 30,
    },
    "cms_inventory_20260914": {
        "source": "docs/audits/mcq_evidence_coverage_001.json db snapshot + pastq freeze",
        "PUBLISHED": 1479,
        "DRAFT": 5444,
        "IN_REVIEW": 111,
        "SUPERSEDED": 6,
        "published_by_subject_20260913": {
            "source": "docs/audits/content_readiness_inventory_20260913.json",
            "PHYSICS": 1089,
            "CHEMISTRY": 46,
            "BOTANY": 321,
            "ZOOLOGY": 23,
            "BIOLOGY_combined_published": 344,
        },
    },
}

TARGET_USABLE = {"PHYSICS": 10000, "CHEMISTRY": 10000, "BIOLOGY": 10000}

# Planning allocations (policy, not measured yield)
DIFFICULTY_PLAN = {"easy": 0.30, "medium": 0.50, "hard": 0.20}

ARCHETYPE_PLAN = {
    "PHYSICS": {
        "conceptual": 0.18,
        "numerical": 0.28,
        "application": 0.14,
        "graph_table": 0.08,
        "experimental_practical": 0.08,
        "comparison": 0.06,
        "statement_based": 0.06,
        "diagram_based": 0.05,
        "multi_concept_integration": 0.05,
        "sequence_order": 0.02,
    },
    "CHEMISTRY": {
        "conceptual": 0.22,
        "application": 0.16,
        "numerical": 0.18,
        "comparison": 0.10,
        "statement_based": 0.08,
        "experimental_practical": 0.08,
        "diagram_based": 0.06,
        "graph_table": 0.04,
        "multi_concept_integration": 0.05,
        "sequence_order": 0.03,
    },
    "BIOLOGY": {
        "conceptual": 0.24,
        "statement_based": 0.14,
        "application": 0.14,
        "diagram_based": 0.12,
        "comparison": 0.10,
        "sequence_order": 0.08,
        "experimental_practical": 0.06,
        "multi_concept_integration": 0.06,
        "graph_table": 0.04,
        "numerical": 0.02,
    },
}


def _rate(n: int, d: int) -> float:
    return (n / d) if d else 0.0


def build_loss_model() -> dict[str, Any]:
    """Compose measured funnels into planning scenarios. No invented rates."""
    p3 = TELEMETRY["factory_p3_forensic_100"]
    hist = TELEMETRY["historical_factory_candidates_pre_pilot001"]
    pilot = TELEMETRY["mcq_pilot_001"]
    ncert = TELEMETRY["ncert_verify_001"]

    p3_created_given_attempt = _rate(p3["created"], p3["attempted"])
    p3_val_loss_given_attempt = _rate(p3["rejected_validation"], p3["attempted"])
    p3_dup_loss_given_attempt = _rate(p3["rejected_duplicate"], p3["attempted"])
    p3_parse_loss_given_attempt = _rate(p3["failed_parse"], p3["attempted"])

    hist_created_given_cand = _rate(hist["created"], hist["total_candidates"])
    hist_val = _rate(hist["rejected_validation"], hist["total_candidates"])
    hist_dup = _rate(hist["rejected_duplicate"], hist["total_candidates"])
    hist_parse = _rate(hist["failed_parse"], hist["total_candidates"])

    ncert_pass_among_created = ncert["ncert_pass_rate_among_created"]
    ncert_loss_among_created = 1.0 - ncert_pass_among_created

    # Scenario A: content gates when provider delivers (P3 forensic, provider_fail=0)
    # usable ≈ attempts * created_rate * ncert_pass_among_created
    # Note: NCERT rate measured on separate n=5 verify sample — flagged provisional.
    a_yield = p3_created_given_attempt * ncert_pass_among_created

    # Scenario B: include pilot-001 operational provider failures
    b_yield = pilot["created_rate"] * ncert_pass_among_created

    # Scenario C: historical created * ncert (pre-pilot-001 mix)
    c_yield = hist_created_given_cand * ncert_pass_among_created

    def reserve_for(target: int, yield_rate: float) -> dict[str, Any]:
        if yield_rate <= 0:
            return {"required_attempts": None, "reserve_multiplier": None}
        required = math.ceil(target / yield_rate)
        return {
            "target_usable": target,
            "expected_usable_yield_per_attempt": round(yield_rate, 6),
            "required_generation_attempts": required,
            "reserve_multiplier": round(required / target, 4),
            "expected_surplus_attempts": required - target,
        }

    return {
        "measured_component_rates": {
            "p3_created_given_attempt": round(p3_created_given_attempt, 6),
            "p3_validation_reject_given_attempt": round(p3_val_loss_given_attempt, 6),
            "p3_duplicate_reject_given_attempt": round(p3_dup_loss_given_attempt, 6),
            "p3_parse_fail_given_attempt": round(p3_parse_loss_given_attempt, 6),
            "historical_created_given_candidate": round(hist_created_given_cand, 6),
            "historical_validation_reject_given_candidate": round(hist_val, 6),
            "historical_duplicate_reject_given_candidate": round(hist_dup, 6),
            "historical_parse_fail_given_candidate": round(hist_parse, 6),
            "pilot001_created_rate": pilot["created_rate"],
            "pilot001_provider_fail_rate": pilot["provider_fail_rate"],
            "pilot001_validation_reject_rate": pilot["validation_reject_rate"],
            "pilot001_duplicate_rate": pilot["duplicate_rate"],
            "ncert_pass_among_created_verify001": ncert_pass_among_created,
            "ncert_loss_among_created_verify001": round(ncert_loss_among_created, 6),
            "ncert_sample_size": ncert["sample_created"],
            "ncert_rate_confidence": "LOW — n=5 independent verify; post-GROUNDING-001 scale rate unknown",
        },
        "scenarios": {
            "A_content_gates_provider_ok_p3_x_ncert_verify": {
                "description": "P3 forensic created/attempt × VERIFY-001 NCERT pass among created",
                "yield_per_attempt": round(a_yield, 6),
                "per_subject_10000": reserve_for(10000, a_yield),
                "all_subjects_30000": reserve_for(30000, a_yield),
            },
            "B_operational_pilot001_x_ncert_verify": {
                "description": "PILOT-001 created rate (incl. provider outages) × VERIFY-001 NCERT pass",
                "yield_per_attempt": round(b_yield, 6),
                "per_subject_10000": reserve_for(10000, b_yield),
                "all_subjects_30000": reserve_for(30000, b_yield),
            },
            "C_historical_created_x_ncert_verify": {
                "description": "Historical CREATED/392 × VERIFY-001 NCERT pass",
                "yield_per_attempt": round(c_yield, 6),
                "per_subject_10000": reserve_for(10000, c_yield),
                "all_subjects_30000": reserve_for(30000, c_yield),
            },
        },
        "primary_planning_scenario": "A_content_gates_provider_ok_p3_x_ncert_verify",
        "caveats": [
            "NCERT grounding loss uses VERIFY-001 (n=5). Do not treat as high-confidence until a larger post-GROUNDING-001 audit.",
            "PILOT-001 yield was dominated by provider failures, not content gates — use scenario B for ops capacity, A for content-quality sizing when provider is healthy.",
            "No measured assertion/reasoning or archetype-specific yield rates exist yet.",
        ],
    }


def parse_syllabus(path: Path) -> dict[str, list[dict[str, Any]]]:
    text_body = path.read_text(encoding="utf-8", errors="replace")
    subjects: dict[str, list[dict[str, Any]]] = {"PHYSICS": [], "CHEMISTRY": [], "BIOLOGY": []}
    current: str | None = None
    unit: dict[str, Any] | None = None
    unit_re = re.compile(r"\*\*\s*UNIT\s+(\d+)\s*:\s*([^*]+?)\s*\*\*", re.I)
    subject_re = re.compile(r"^##\s+\d+\.\s+(PHYSICS|CHEMISTRY|BIOLOGY)\s+SYLLABUS", re.I)
    for raw in text_body.splitlines():
        line = raw.strip()
        sm = subject_re.match(line)
        if sm:
            current = sm.group(1).upper()
            unit = None
            continue
        if not current:
            continue
        um = unit_re.search(line)
        if um:
            unit = {
                "unit_number": int(um.group(1)),
                "unit_title": um.group(2).strip(),
                "topics": [],
            }
            subjects[current].append(unit)
            continue
        if not unit:
            continue
        if line.startswith("*") and not line.startswith("**"):
            b = line.lstrip("* ").strip()
            if b:
                unit["topics"].append({"topic_text": b, "topic_index": len(unit["topics"]) + 1})
        elif re.match(r"^\d+\.", line):
            unit["topics"].append({"topic_text": line, "topic_index": len(unit["topics"]) + 1})
    return subjects


def allocate_counts(weights: list[int], total: int) -> list[int]:
    """Largest-remainder allocation; every positive weight gets ≥1 when total ≥ len(positive)."""
    n = len(weights)
    if n == 0:
        return []
    positive = [i for i, w in enumerate(weights) if w > 0]
    if not positive:
        return [0] * n
    if total < len(positive):
        # Still distribute what we can (capacity target always >> units)
        out = [0] * n
        for i, idx in enumerate(positive[:total]):
            out[idx] = 1
        return out
    # Floor 1 for each positive weight, distribute remainder by weight
    base = [0] * n
    for i in positive:
        base[i] = 1
    rem = total - len(positive)
    wsum = sum(weights[i] for i in positive)
    fracs = []
    for i in positive:
        exact = rem * (weights[i] / wsum)
        add = int(math.floor(exact))
        base[i] += add
        fracs.append((exact - add, i))
    used = sum(base[i] for i in positive) - len(positive)
    left = rem - used
    fracs.sort(reverse=True)
    for k in range(left):
        base[fracs[k % len(fracs)][1]] += 1
    return base


def build_matrix(
    syllabus: dict[str, list[dict[str, Any]]],
    evidence: dict[str, Any] | None,
    loss: dict[str, Any],
) -> dict[str, Any]:
    # Map GENERATION_READY blueprints to syllabus units
    ready_by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ready_concepts: dict[str, set[str]] = defaultdict(set)
    if evidence:
        for bp in evidence.get("blueprints", []):
            if bp.get("coverage_status") != "GENERATION_READY":
                continue
            syl = bp.get("syllabus") or {}
            subj = syl.get("syllabus_subject")
            unit = syl.get("unit_number")
            if not subj or unit is None:
                continue
            key = f"{subj}:U{unit}"
            ready_by_unit[key].append(
                {
                    "blueprint_key": bp["blueprint_key"],
                    "concept_code": bp["concept_code"],
                    "concept_name": bp["concept_name"],
                    "academic_subject": bp["subject_code"],
                    "chapter_code": bp["chapter_code"],
                    "ncert_path": bp.get("ncert_relative_path"),
                }
            )
            ready_concepts[key].add(bp["concept_code"])

    primary = loss["scenarios"][loss["primary_planning_scenario"]]
    per_subj_attempts = primary["per_subject_10000"]["required_generation_attempts"]

    subjects_out: dict[str, Any] = {}
    uncovered: list[dict[str, Any]] = []

    for subj, units in syllabus.items():
        target = TARGET_USABLE[subj]
        unit_weights = [max(1, len(u["topics"])) for u in units]
        unit_targets = allocate_counts(unit_weights, target)

        unit_rows = []
        topic_rows = []
        concept_rows = []
        for u, u_target in zip(units, unit_targets):
            ukey = f"{subj}:U{u['unit_number']}"
            topics = u["topics"] or [{"topic_text": u["unit_title"], "topic_index": 1}]
            t_weights = [1] * len(topics)
            t_targets = allocate_counts(t_weights, u_target)
            bps = ready_by_unit.get(ukey, [])
            concepts = sorted(ready_concepts.get(ukey, set()))

            # Split unit target across known GENERATION_READY concepts when present;
            # else mark topics as needing blueprint/concept coverage.
            if concepts:
                c_targets = allocate_counts([1] * len(concepts), u_target)
                for code, ct in zip(concepts, c_targets):
                    concept_rows.append(
                        {
                            "subject": subj,
                            "unit_number": u["unit_number"],
                            "unit_title": u["unit_title"],
                            "concept_code": code,
                            "target_usable": ct,
                            "coverage": "HAS_GENERATION_READY_BLUEPRINT",
                        }
                    )
            else:
                uncovered.append(
                    {
                        "subject": subj,
                        "unit_number": u["unit_number"],
                        "unit_title": u["unit_title"],
                        "target_usable_assigned": u_target,
                        "reason": "no_GENERATION_READY_blueprint_mapped_to_unit",
                    }
                )
                for t, tt in zip(topics, t_targets):
                    concept_rows.append(
                        {
                            "subject": subj,
                            "unit_number": u["unit_number"],
                            "unit_title": u["unit_title"],
                            "concept_code": None,
                            "topic_text": t["topic_text"][:200],
                            "target_usable": tt,
                            "coverage": "UNCOVERED_CONCEPT_BLUEPRINT",
                        }
                    )

            for t, tt in zip(topics, t_targets):
                topic_rows.append(
                    {
                        "subject": subj,
                        "unit_number": u["unit_number"],
                        "unit_title": u["unit_title"],
                        "topic_index": t["topic_index"],
                        "topic_text": t["topic_text"][:240],
                        "target_usable": tt,
                    }
                )

            # Difficulty / archetype for unit (planning)
            diff = {k: int(round(u_target * v)) for k, v in DIFFICULTY_PLAN.items()}
            # Fix rounding
            diff_fix = u_target - sum(diff.values())
            if diff_fix:
                diff["medium"] = diff.get("medium", 0) + diff_fix
            arch = {k: int(round(u_target * v)) for k, v in ARCHETYPE_PLAN[subj].items()}
            arch_fix = u_target - sum(arch.values())
            if arch_fix:
                # add to largest archetype
                top = max(arch, key=arch.get)
                arch[top] += arch_fix

            unit_rows.append(
                {
                    "unit_number": u["unit_number"],
                    "unit_title": u["unit_title"],
                    "syllabus_topic_bullets": len(u["topics"]),
                    "target_usable": u_target,
                    "generation_ready_blueprints": len(bps),
                    "generation_ready_concepts": len(concepts),
                    "required_generation_attempts_scenario_A": (
                        math.ceil(u_target / primary["yield_per_attempt"])
                        if primary["yield_per_attempt"]
                        else None
                    ),
                    "difficulty_plan": diff,
                    "archetype_plan": arch,
                    "sample_blueprints": [b["blueprint_key"] for b in bps[:5]],
                }
            )

        subjects_out[subj] = {
            "target_usable": target,
            "units": len(units),
            "syllabus_topic_bullets": sum(len(u["topics"]) for u in units),
            "generation_ready_blueprints_mapped": sum(r["generation_ready_blueprints"] for r in unit_rows),
            "required_generation_attempts_scenario_A": per_subj_attempts,
            "unit_totals": unit_rows,
            "topic_totals": topic_rows,
            "concept_totals": concept_rows,
            "difficulty_distribution_plan": {
                k: int(round(target * v)) for k, v in DIFFICULTY_PLAN.items()
            },
            "archetype_distribution_plan": {
                k: int(round(target * v)) for k, v in ARCHETYPE_PLAN[subj].items()
            },
        }
        # Fix subject-level rounding
        d = subjects_out[subj]["difficulty_distribution_plan"]
        d["medium"] += target - sum(d.values())
        a = subjects_out[subj]["archetype_distribution_plan"]
        top = max(a, key=a.get)
        a[top] += target - sum(a.values())

    return {
        "subjects": subjects_out,
        "uncovered_units_or_concepts": uncovered,
        "totals": {
            "target_usable_all_subjects": sum(TARGET_USABLE.values()),
            "required_generation_attempts_scenario_A_all": primary["all_subjects_30000"][
                "required_generation_attempts"
            ],
            "required_generation_attempts_scenario_B_all": loss["scenarios"][
                "B_operational_pilot001_x_ncert_verify"
            ]["all_subjects_30000"]["required_generation_attempts"],
            "required_generation_attempts_scenario_C_all": loss["scenarios"][
                "C_historical_created_x_ncert_verify"
            ]["all_subjects_30000"]["required_generation_attempts"],
        },
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    loss = report["loss_model"]
    matrix = report["capacity_matrix"]
    lines = [
        "# MCQ-CAPACITY-MATRIX-001 — Verified-usable capacity plan",
        "",
        f"**Generated:** {report['generated_at']}",
        "**Mode:** planning / read-only (no generation, no publish, no DB mutation)",
        f"**Syllabus:** `{report['syllabus_path']}`",
        f"**NCERT root:** `{report['ncert_root']}`",
        "",
        "## Objective",
        "",
        "Final **verified usable** targets (not raw generation):",
        "",
        "| Subject | Target usable |",
        "|---|---:|",
        "| Physics | 10,000 |",
        "| Chemistry | 10,000 |",
        "| Biology | 10,000 |",
        "| **Total** | **30,000** |",
        "",
        "## Loss model (measured telemetry only)",
        "",
        "Primary planning scenario: **A** = P3 forensic `created/attempt` × VERIFY-001 NCERT pass among created.",
        "",
        "| Scenario | Yield / attempt | Attempts for 10k usable | Attempts for 30k usable | Reserve × |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, sc in loss["scenarios"].items():
        p = sc["per_subject_10000"]
        a = sc["all_subjects_30000"]
        lines.append(
            f"| `{key}` | {sc['yield_per_attempt']:.4f} | "
            f"{p['required_generation_attempts']} | {a['required_generation_attempts']} | "
            f"{p['reserve_multiplier']}× |"
        )
    lines += [
        "",
        "### Measured component rates",
        "",
        "```json",
        json.dumps(loss["measured_component_rates"], indent=2),
        "```",
        "",
        "### Caveats",
        "",
    ]
    for c in loss["caveats"]:
        lines.append(f"- {c}")

    lines += [
        "",
        "## Subject / unit capacity (usable targets)",
        "",
    ]
    for subj, block in matrix["subjects"].items():
        lines += [
            f"### {subj}",
            "",
            f"- Target usable: **{block['target_usable']}**",
            f"- Syllabus units: **{block['units']}**",
            f"- Syllabus topic bullets: **{block['syllabus_topic_bullets']}**",
            f"- GENERATION_READY blueprints mapped to units: **{block['generation_ready_blueprints_mapped']}**",
            f"- Required generation attempts (scenario A): **{block['required_generation_attempts_scenario_A']}**",
            "",
            "| Unit | Title | Topics | Usable target | Ready BPs | Ready concepts |",
            "|---:|---|---:|---:|---:|---:|",
        ]
        for u in block["unit_totals"]:
            lines.append(
                f"| {u['unit_number']} | {u['unit_title']} | {u['syllabus_topic_bullets']} | "
                f"{u['target_usable']} | {u['generation_ready_blueprints']} | "
                f"{u['generation_ready_concepts']} |"
            )
        lines += [
            "",
            "**Difficulty plan (policy, not measured):** "
            + ", ".join(f"{k}={v}" for k, v in block["difficulty_distribution_plan"].items()),
            "",
            "**Archetype plan (policy; only fit archetypes — do not force):**",
            "",
            "| Archetype | Target usable |",
            "|---|---:|",
        ]
        for k, v in block["archetype_distribution_plan"].items():
            lines.append(f"| {k} | {v} |")
        lines.append("")

    unc = matrix["uncovered_units_or_concepts"]
    lines += [
        "## Uncovered concepts / units",
        "",
        f"Units with usable target but **no** `GENERATION_READY` blueprint mapped: **{len(unc)}**",
        "",
    ]
    for row in unc[:30]:
        lines.append(
            f"- {row['subject']} Unit {row['unit_number']}: {row['unit_title']} "
            f"(assigned usable {row['target_usable_assigned']}) — {row['reason']}"
        )
    if len(unc) > 30:
        lines.append(f"- … +{len(unc) - 30} more (see JSON)")

    lines += [
        "",
        "## Hierarchy used",
        "",
        "NEET-2026 syllabus → unit → topic/subtopic (syllabus bullets) → "
        "canonical NCERT chapter (via GENERATION_READY blueprints) → concept → "
        "archetype/difficulty plan → target count",
        "",
        "## Diversity / anti-paraphrase rule",
        "",
        "- Every blueprint must identify the underlying concept.",
        "- Do not create 100 near-paraphrases or trivial number swaps.",
        "- Track diversity across difficulty, archetype, concept, and question pattern.",
        "",
        "## Estimated raw generation requirement (summary)",
        "",
        f"- Scenario A (primary): **{matrix['totals']['required_generation_attempts_scenario_A_all']}** attempts for 30k usable",
        f"- Scenario B (ops / provider outages): **{matrix['totals']['required_generation_attempts_scenario_B_all']}**",
        f"- Scenario C (historical mix): **{matrix['totals']['required_generation_attempts_scenario_C_all']}**",
        "",
        "## Safety",
        "",
        "- No MCQs generated",
        "- No publication",
        "- No database mutation",
        "- No commit/push",
        "",
        "## Next steps",
        "",
        "1. Remediate uncovered units (see also MCQ-EVIDENCE-COVERAGE-001).",
        "2. Re-measure NCERT grounding pass rate post-GROUNDING-001 at n≥50 before locking reserves.",
        "3. Only run factory on `GENERATION_READY` blueprints under dual gates.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    syllabus = parse_syllabus(SYLLABUS_PATH)
    evidence = None
    if EVIDENCE_PATH.exists():
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    loss = build_loss_model()
    matrix = build_matrix(syllabus, evidence, loss)

    report = {
        "task": "MCQ-CAPACITY-MATRIX-001",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "PLANNING_READONLY",
        "syllabus_path": str(SYLLABUS_PATH),
        "syllabus_sha256": __import__("hashlib").sha256(SYLLABUS_PATH.read_bytes()).hexdigest(),
        "ncert_root": str(ROOT / "NCERT Books"),
        "target_usable": TARGET_USABLE,
        "telemetry_sources": TELEMETRY,
        "loss_model": loss,
        "planning_policy": {
            "difficulty": DIFFICULTY_PLAN,
            "archetypes": ARCHETYPE_PLAN,
            "note": "Difficulty/archetype mixes are planning policy, not measured yield rates.",
            "allocation_rule": "Unit weights = max(1, syllabus bullet count); largest-remainder; floor 1 per positive weight.",
        },
        "capacity_matrix": matrix,
        "evidence_coverage_ref": str(EVIDENCE_PATH) if evidence else None,
    }

    out_json = ROOT / "docs" / "audits" / f"{REPORT_STEM}.json"
    out_md = ROOT / "docs" / "audits" / f"{REPORT_STEM}.md"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report, out_md)
    print(
        json.dumps(
            {
                "json": str(out_json),
                "md": str(out_md),
                "scenario_A_attempts_30k": matrix["totals"]["required_generation_attempts_scenario_A_all"],
                "uncovered_units": len(matrix["uncovered_units_or_concepts"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
