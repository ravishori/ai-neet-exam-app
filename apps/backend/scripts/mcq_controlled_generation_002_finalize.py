"""Finalize and deterministically verify MCQ-CONTROLLED-GENERATION-002.

Read-only with respect to the database. Updates only the requested audit files
after the dedicated generation worker exits.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
SCRIPTS = Path(__file__).resolve().parent
for path in (BACKEND, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.core.config import get_settings  # noqa: E402
from mcq_controlled_generation_001 import snapshot  # noqa: E402
from mcq_controlled_generation_002 import write_markdown  # noqa: E402

AUDIT_JSON = ROOT / "docs/audits/mcq_controlled_generation_002.json"
AUDIT_MD = ROOT / "docs/audits/mcq_controlled_generation_002.md"
CAMPAIGN_PREFIX = "mcq-ctrl-gen-002%"
TARGET = 100
PER_SUBJECT = 25
SUBJECTS = ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY")

# Measured immediately after the user requested resume. The original Python
# worker was found still alive, so these are continuity—not regenerated—counts.
RESUME_OBSERVED_AT = "2026-09-14T13:13:00+05:30"
ALREADY_EXISTING_AT_RESUME = 9
ATTEMPTS_EXISTING_AT_RESUME = 13


def load_wave_rows(conn) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT gc.id::text AS candidate_id,
                       gc.batch_id::text AS batch_id,
                       gc.job_id::text AS job_id,
                       gc.run_id::text AS run_id,
                       gc.blueprint_id::text AS blueprint_id,
                       gc.attempt_no,
                       gc.status AS candidate_status,
                       gc.error_code,
                       left(coalesce(gc.error_summary, ''), 300) AS error_summary,
                       gc.provider,
                       gc.model_used,
                       gc.cost_usd,
                       gc.cost_status,
                       gc.provider_attempt_no,
                       gc.provider_request_id,
                       gc.routing_policy,
                       gc.is_fallback,
                       gc.stem_hash,
                       gc.content_item_id::text AS content_item_id,
                       ci.status AS content_status,
                       ci.concept_id::text AS concept_id,
                       ci.latest_version_id::text AS latest_version_id,
                       s.code AS subject,
                       bp.blueprint_key,
                       ch.name AS chapter,
                       t.name AS topic,
                       co.name AS concept,
                       bp.constraints,
                       gr.execution_metadata,
                       gc.created_at
                FROM cms.generation_candidates gc
                JOIN cms.content_batches b ON b.id = gc.batch_id
                JOIN academic.subjects s ON s.id = b.subject_id
                JOIN cms.question_blueprints bp ON bp.id = gc.blueprint_id
                JOIN academic.chapters ch ON ch.id = bp.chapter_id
                JOIN academic.topics t ON t.id = bp.topic_id
                JOIN academic.concepts co ON co.id = bp.concept_id
                LEFT JOIN cms.content_items ci ON ci.id = gc.content_item_id
                LEFT JOIN cms.generation_runs gr ON gr.id = gc.run_id
                WHERE b.deleted_at IS NULL
                  AND b.batch_key LIKE :prefix
                  AND gc.deleted_at IS NULL
                ORDER BY gc.created_at, gc.id
                """
            ),
            {"prefix": CAMPAIGN_PREFIX},
        ).mappings()
    ]


def main() -> int:
    if not AUDIT_JSON.is_file():
        raise RuntimeError("Generation worker exited without writing mcq_controlled_generation_002.json")

    report = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    engine = create_engine(get_settings().database_url_sync)
    with engine.connect() as conn:
        final_snapshot = snapshot(conn)
        rows = load_wave_rows(conn)

    valid = [
        row
        for row in rows
        if row["candidate_status"] == "CREATED"
        and row["content_status"] == "DRAFT"
        and row["content_item_id"]
    ]
    valid_ids = {row["content_item_id"] for row in valid}
    by_subject = Counter(row["subject"] for row in valid)
    statuses = Counter(row["candidate_status"] for row in rows)
    models = Counter(row["model_used"] for row in rows if row["model_used"])
    providers = Counter(row["provider"] for row in rows if row["provider"])

    distinct_run_metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["run_id"] and isinstance(row["execution_metadata"], dict):
            distinct_run_metadata[row["run_id"]] = row["execution_metadata"]

    provider_http_attempts = 0
    summed_latency_ms = 0
    transport_retries = 0
    for metadata in distinct_run_metadata.values():
        attempts = metadata.get("provider_attempts") or []
        provider_http_attempts += len(attempts)
        transport_retries += max(0, len(attempts) - int((metadata.get("stats") or {}).get("attempted") or 0))
        summed_latency_ms += sum(int(attempt.get("latency_ms") or 0) for attempt in attempts)

    candidate_attempts = len(rows)
    created = len(valid_ids)
    content_retries = max(0, candidate_attempts - created)
    exact_remaining = max(0, TARGET - created)
    duplicate_stem_hashes = len(
        [row["stem_hash"] for row in valid if row["stem_hash"]]
    ) != len({row["stem_hash"] for row in valid if row["stem_hash"]})

    before = report["database_before"]
    protected_keys = ("chapters", "topics", "concepts", "kus", "blueprints", "unmapped_draft", "published")
    protected_unchanged = all(before[key] == final_snapshot[key] for key in protected_keys)
    review_status_unchanged = all(
        before["status"].get(status, 0) == final_snapshot["status"].get(status, 0)
        for status in ("PUBLISHED", "IN_REVIEW", "SUPERSEDED")
    )
    draft_delta = final_snapshot["status"].get("DRAFT", 0) - before["status"].get("DRAFT", 0)

    # Every row must remain fixed to the configured provider; failed attempts
    # without a provider response are still represented in the candidate list.
    provider_consistent = set(providers).issubset({"openai"}) and all(
        not row["is_fallback"] for row in rows
    )
    canonical_paths = all(
        row.get("ncert_source_path")
        and "StudyMaterial" not in str(row["ncert_source_path"]).replace("\\", "/")
        for row in report.get("candidates", [])
        if row.get("candidate_status") == "CREATED"
    )
    syllabus_mapped = all(
        (row.get("syllabus_mapping") or {}).get("unit_number")
        for row in report.get("candidates", [])
        if row.get("candidate_status") == "CREATED"
    )

    report["generated_at"] = datetime.now(UTC).isoformat()
    report["resume"] = {
        "observed_at": RESUME_OBSERVED_AT,
        "worker_continuity_detected": True,
        "second_worker_started": False,
        "already_existing_valid_drafts": ALREADY_EXISTING_AT_RESUME,
        "candidate_attempts_already_existing": ATTEMPTS_EXISTING_AT_RESUME,
        "remaining_at_resume": TARGET - ALREADY_EXISTING_AT_RESUME,
        "note": "The terminal wrapper ended, but its Python child survived; the same worker continued. No blind regeneration occurred.",
    }
    report["metrics"].update(
        {
            "requested": TARGET,
            "already_existing": ALREADY_EXISTING_AT_RESUME,
            "remaining_at_resume": TARGET - ALREADY_EXISTING_AT_RESUME,
            "attempted": candidate_attempts,
            "provider_http_attempts": provider_http_attempts,
            "created": created,
            "failed_parse": statuses["FAILED_PARSE"],
            "rejected_validation": statuses["REJECTED_VALIDATION"],
            "duplicate": statuses["REJECTED_DUPLICATE"],
            "failed_provider": statuses["FAILED_PROVIDER"] + statuses["FAILED_BUDGET"],
            "retries": content_retries + transport_retries,
            "content_candidate_retries": content_retries,
            "transport_retries": transport_retries,
            "latency_ms_sum": summed_latency_ms,
            "estimated_cost_usd": round(sum(float(row["cost_usd"] or 0) for row in rows), 6),
            "created_by_subject": {subject: by_subject[subject] for subject in SUBJECTS},
            "exact_remaining_quantity": exact_remaining,
            "providers": dict(providers),
            "models": dict(models),
        }
    )
    report["database_after"] = final_snapshot
    original_candidates = {
        row["candidate_id"]: row for row in report.get("candidates", [])
    }
    report["candidates"] = [
        {
            **original_candidates.get(row["candidate_id"], {}),
            **{
                key: value
                for key, value in row.items()
                if key not in {"constraints", "execution_metadata"}
            },
        }
        for row in rows
    ]
    report["verification"].update(
        {
            "created_count": created,
            "created_content_items": len(valid_ids),
            "created_by_subject": {subject: by_subject[subject] for subject in SUBJECTS},
            "all_created_draft": len(valid) == created,
            "any_non_draft_item": any(
                row["candidate_status"] == "CREATED" and row["content_status"] != "DRAFT"
                for row in rows
            ),
            "duplicate_stem_hashes_among_created": duplicate_stem_hashes,
            "every_created_has_canonical_ncert_path": canonical_paths,
            "every_created_has_syllabus_mapping": syllabus_mapped,
            "provider_metadata_consistent": provider_consistent,
            "protected_database_counts_unchanged": protected_unchanged,
            "review_and_published_counts_unchanged": review_status_unchanged,
            "draft_delta_equals_wave_created": draft_delta == created,
        }
    )
    complete = created == TARGET and all(by_subject[subject] == PER_SUBJECT for subject in SUBJECTS)
    safe = (
        protected_unchanged
        and review_status_unchanged
        and draft_delta == created
        and provider_consistent
        and not duplicate_stem_hashes
        and canonical_paths
        and syllabus_mapped
        and not report["verification"]["any_non_draft_item"]
    )
    report["acceptance"].update(
        {
            "requested_100": True,
            "subject_slots_25_each": True,
            "created_100_25_each": complete,
            "no_publication": final_snapshot["published"] == before["published"],
            "inventory_freeze": protected_unchanged,
            "verification_ok": complete and safe,
        }
    )
    report["safety"].update(
        {
            "published_delta": final_snapshot["published"] - before["published"],
            "inventory_core_unchanged": protected_unchanged,
            "unmapped_draft_unchanged": final_snapshot["unmapped_draft"] == before["unmapped_draft"],
            "draft_delta": draft_delta,
            "intended_draft_delta": created,
            "review_status_unchanged": review_status_unchanged,
        }
    )
    report["verdict"] = "GREEN" if complete and safe else ("RED" if not safe else "YELLOW")
    report["failures"] = []
    if not complete:
        report["failures"].append(f"remaining_quantity:{exact_remaining}")
    if not safe:
        report["failures"].append("database_or_deterministic_safety_invariant_failed")

    AUDIT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_markdown(report, AUDIT_MD)
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "created": created,
                "created_by_subject": report["metrics"]["created_by_subject"],
                "attempted": candidate_attempts,
                "retries": report["metrics"]["retries"],
                "remaining": exact_remaining,
                "safe": safe,
            },
            indent=2,
        )
    )
    return 0 if report["verdict"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
