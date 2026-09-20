"""SARVAM-PROVIDER-BENCHMARK-001 — isolated 20-DRAFT factory benchmark."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Process-local routing only. This does not alter .env or another worker.
os.environ["SARVAM_ENABLED"] = "true"
os.environ["SARVAM_MODEL"] = "sarvam-105b"
os.environ["FACTORY_PROVIDER_MODE"] = "fixed"
os.environ["FACTORY_PROVIDER"] = "sarvam"
os.environ["MCQ_PROVIDER"] = "sarvam"
os.environ["FACTORY_PROVIDER_FALLBACK_CHAIN"] = ""
os.environ["MCQ_ALLOW_FALLBACK_CHAIN"] = "false"

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import mcq_controlled_generation_001 as base  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

REPORT = "sarvam_provider_benchmark_001"
CAMPAIGN = "sarvam-provider-benchmark-001"
SOURCE_AUDIT = base.ROOT / "docs/audits/mcq_controlled_generation_001.json"

base.REPORT = REPORT
base.CAMPAIGN = CAMPAIGN
base.PER_SUBJECT = 5
base.TOTAL = 20


def source_blueprint_ids() -> dict[str, list[str]]:
    source = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    selected = source["inputs"]["selected_blueprint_ids"]
    return {subject: list(selected[subject]) for subject in base.SUBJECTS}


def select_exact_source_inputs(
    ready: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Require the exact prior 20 inputs to still pass today's live gates."""
    required = source_blueprint_ids()
    by_id = {row["blueprint_id"]: row for row in ready}
    selected: dict[str, list[dict[str, Any]]] = {}
    for subject in base.SUBJECTS:
        missing = [blueprint_id for blueprint_id in required[subject] if blueprint_id not in by_id]
        if missing:
            raise RuntimeError(
                f"{subject}: source benchmark blueprints no longer GENERATION_READY: {missing}"
            )
        selected[subject] = [by_id[blueprint_id] for blueprint_id in required[subject]]
        if any(row["subject"] != subject for row in selected[subject]):
            raise RuntimeError(f"{subject}: source blueprint subject mismatch")
    return selected


base.pick_five_per_subject = select_exact_source_inputs


def provider_usage(conn) -> dict[str, Any]:
    rows = conn.execute(
        text(
            """
            SELECT gr.id::text AS run_id, gr.execution_metadata
            FROM cms.generation_runs gr
            JOIN cms.generation_jobs gj ON gj.id = gr.job_id
            JOIN cms.content_batches b ON b.id = gj.batch_id
            WHERE b.deleted_at IS NULL
              AND b.batch_key LIKE :prefix
              AND gr.deleted_at IS NULL
            ORDER BY gr.created_at
            """
        ),
        {"prefix": f"{CAMPAIGN}%"},
    ).mappings()
    prompt_tokens = 0
    completion_tokens = 0
    latency_ms = 0
    provider_http_attempts = 0
    content_attempts = 0
    for row in rows:
        metadata = row["execution_metadata"] if isinstance(row["execution_metadata"], dict) else {}
        attempts = metadata.get("provider_attempts") or []
        stats = metadata.get("stats") or {}
        provider_http_attempts += len(attempts)
        content_attempts += int(stats.get("attempted") or 0)
        for attempt in attempts:
            prompt_tokens += int(attempt.get("prompt_tokens") or 0)
            completion_tokens += int(attempt.get("completion_tokens") or 0)
            latency_ms += int(attempt.get("latency_ms") or 0)
    fallback_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM cms.generation_candidates gc
                JOIN cms.content_batches b ON b.id = gc.batch_id
                WHERE b.deleted_at IS NULL
                  AND b.batch_key LIKE :prefix
                  AND gc.deleted_at IS NULL
                  AND gc.is_fallback IS TRUE
                """
            ),
            {"prefix": f"{CAMPAIGN}%"},
        ).scalar()
        or 0
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "provider_http_attempts": provider_http_attempts,
        "transport_retries": max(0, provider_http_attempts - content_attempts),
        "provider_latency_ms_sum": latency_ms,
        "fallback_candidate_count": fallback_count,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    metrics = report["metrics"]
    lines = [
        "# SARVAM-PROVIDER-BENCHMARK-001",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verdict:** **{report['verdict']}**",
        "**Provider/model:** sarvam / sarvam-105b (fixed; no fallback)",
        "",
        "## Metrics",
        "",
        f"- Requested: **{metrics['requested']}**",
        f"- Attempted: **{metrics['attempted']}**",
        f"- Created DRAFTs: **{metrics['created']}**",
        f"- Parse failures: **{metrics['failed_parse']}**",
        f"- Validation failures: **{metrics['rejected_validation']}**",
        f"- Duplicate failures: **{metrics['duplicate']}**",
        f"- Provider failures: **{metrics['failed_provider']}**",
        f"- Syllabus failures: **{metrics['syllabus_gate_failures']}**",
        f"- NCERT grounding failures: **{metrics['ncert_evidence_failures']}**",
        f"- Retries: **{metrics['retries']}**",
        f"- Provider latency ms: **{metrics['latency_ms_sum']}**",
        f"- Tokens: **{metrics['token_usage']}**",
        f"- Estimated cost USD: **{metrics['estimated_cost_usd']}**",
        "",
        "## Subject distribution",
        "",
    ]
    for subject in base.SUBJECTS:
        lines.append(
            f"- {subject}: requested 5, created {metrics['created_by_subject'][subject]}"
        )
    lines += [
        "",
        "## Deterministic safety",
        "",
        f"- Exact source blueprint set: **{report['verification']['exact_source_blueprint_set']}**",
        f"- Provider lineage fixed to Sarvam: **{report['verification']['provider_lineage_sarvam']}**",
        f"- No fallback: **{report['verification']['no_fallback']}**",
        f"- Every created item DRAFT: **{report['verification']['all_created_draft']}**",
        f"- Canonical NCERT path present: **{report['verification']['every_created_has_canonical_ncert_path']}**",
        f"- Syllabus mapping present: **{report['verification']['every_created_has_syllabus_mapping']}**",
        f"- Published delta: **{report['safety']['published_delta']}**",
        f"- Published/review states unchanged: **{report['safety']['published_review_states_unchanged']}**",
        f"- Taxonomy/KU/blueprints unchanged: **{report['safety']['inventory_core_unchanged']}**",
        f"- Frozen unmapped DRAFTs unchanged: **{report['safety']['unmapped_draft_unchanged']}**",
        "",
        "Deterministic benchmark only; no independent editorial certification.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def finalize_report() -> dict[str, Any]:
    path = base.ROOT / "docs/audits" / f"{REPORT}.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    settings = base.get_settings()
    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        usage = provider_usage(conn)

    candidates = report["candidates"]
    expected = source_blueprint_ids()
    selected = report["inputs"]["selected_blueprint_ids"]
    provider_rows = [row for row in candidates if row.get("provider")]
    error_codes = Counter(
        row.get("error_code") for row in candidates if row.get("error_code")
    )
    report["task"] = "SARVAM-PROVIDER-BENCHMARK-001"
    report["source_audit"] = str(SOURCE_AUDIT)
    report["provider_routing"] = {
        "provider": "sarvam",
        "model": "sarvam-105b",
        "mode": "fixed",
        "fallback_allowed": False,
    }
    report["metrics"].update(
        {
            "syllabus_gate_failures": sum(
                count for code, count in error_codes.items() if "SYLLABUS" in code
            ),
            "ncert_evidence_failures": sum(
                count
                for code, count in error_codes.items()
                if "NCERT" in code or "GROUND" in code
            ),
            "retries": max(
                0, int(report["metrics"]["attempted"]) - int(report["metrics"]["requested"])
            )
            + usage["transport_retries"],
            "latency_ms_sum": usage["provider_latency_ms_sum"],
            "provider_http_attempts": usage["provider_http_attempts"],
            "token_usage": {
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
            },
        }
    )
    report["verification"].update(
        {
            "exact_source_blueprint_set": selected == expected,
            "provider_lineage_sarvam": bool(provider_rows)
            and all(row.get("provider") == "sarvam" for row in provider_rows),
            "model_lineage_sarvam_105b": bool(provider_rows)
            and all(row.get("model_used") == "sarvam-105b" for row in provider_rows),
            "no_fallback": usage["fallback_candidate_count"] == 0,
            "fallback_candidate_count": usage["fallback_candidate_count"],
        }
    )
    before = report["database_before"]
    after = report["database_after"]
    report["safety"]["published_review_states_unchanged"] = all(
        before["status"].get(status, 0) == after["status"].get(status, 0)
        for status in ("PUBLISHED", "IN_REVIEW", "SUPERSEDED")
    )
    report["safety"]["concurrent_openai_worker_expected"] = True
    report["safety"]["global_draft_and_factory_record_deltas_are_concurrent"] = True
    report["safety"]["note"] = (
        "The OpenAI 100-MCQ worker ran concurrently. Global DRAFT/job/run/candidate "
        "deltas are reported but not attributed to this benchmark; benchmark batch "
        "candidate IDs and statuses are verified directly."
    )
    complete = (
        report["metrics"]["created"] == 20
        and all(report["metrics"]["created_by_subject"][subject] == 5 for subject in base.SUBJECTS)
    )
    safe = (
        report["safety"]["published_delta"] == 0
        and report["safety"]["published_review_states_unchanged"]
        and report["safety"]["inventory_core_unchanged"]
        and report["safety"]["unmapped_draft_unchanged"]
        and report["verification"]["all_created_draft"]
        and report["verification"]["every_created_has_canonical_ncert_path"]
        and report["verification"]["every_created_has_syllabus_mapping"]
        and report["verification"]["exact_source_blueprint_set"]
        and report["verification"]["provider_lineage_sarvam"]
        and report["verification"]["model_lineage_sarvam_105b"]
        and report["verification"]["no_fallback"]
    )
    report["verdict"] = "GREEN" if complete and safe else ("RED" if not safe else "YELLOW")
    report["acceptance"].update(
        {
            "created_20_5_each": complete,
            "no_publication": report["safety"]["published_delta"] == 0,
            "verification_ok": safe,
        }
    )
    report["limitations"] = [
        "Deterministic gates only; no independent editorial NCERT certification.",
        "Exact blueprint/evidence inputs from MCQ-CONTROLLED-GENERATION-001.",
        "Sarvam was selected process-locally; no .env or OpenAI worker routing change.",
        "Concurrent OpenAI worker makes global DRAFT/job/run/candidate deltas non-attributable.",
    ]
    report["failures"] = []
    if not complete:
        report["failures"].append("created_count_below_20_or_uneven_subjects")
    if not safe:
        report["failures"].append("deterministic_safety_verification_failed")

    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report, base.ROOT / "docs/audits" / f"{REPORT}.md")
    return report


def main() -> int:
    if not SOURCE_AUDIT.is_file():
        raise FileNotFoundError(SOURCE_AUDIT)
    settings = base.get_settings()
    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        prior_batches = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM cms.content_batches
                    WHERE deleted_at IS NULL AND batch_key LIKE :prefix
                    """
                ),
                {"prefix": f"{CAMPAIGN}%"},
            ).scalar()
            or 0
        )
    if prior_batches:
        raise RuntimeError(
            f"Refusing blind rerun: found {prior_batches} existing {CAMPAIGN} batch(es)"
        )
    result = base.main()
    report = finalize_report()
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "metrics": report["metrics"],
                "safety": report["safety"],
            },
            indent=2,
        )
    )
    return 2 if report["verdict"] == "RED" else result


if __name__ == "__main__":
    raise SystemExit(main())
