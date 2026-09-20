#!/usr/bin/env python3
"""READ-ONLY post-pilot audit for batch_key=pilot-400-subjectquota-20260919b.

SELECTs only. Never writes, never touches content_items status, never
starts/restarts a generation job. Safe to re-run at any time.
"""

from __future__ import annotations

import json
import sys

import psycopg

DSN_SYNC = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
BATCH_KEY = "pilot-400-subjectquota-20260919b"
PROD_5K_BATCH_KEYS = ("prod-5k-20260915", "prod-5k-20260916")


def main() -> int:
    report: dict = {"batch_key": BATCH_KEY}

    with psycopg.connect(DSN_SYNC) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status, target_count, created_at FROM cms.content_batches WHERE batch_key=%s", (BATCH_KEY,))
            row = cur.fetchone()
            if row is None:
                print(f"NOT FOUND: no batch with batch_key={BATCH_KEY}", file=sys.stderr)
                return 1
            batch_id, batch_status, target_count, created_at = row
            report["batch_id"] = str(batch_id)
            report["batch_status"] = batch_status
            report["target_count"] = target_count
            report["created_at"] = str(created_at)

            tag = f"batch:{batch_id}"

            # 1. Accepted count.
            cur.execute("SELECT count(*) FROM cms.content_items WHERE %s = ANY(tags) AND deleted_at IS NULL", (tag,))
            report["accepted_count"] = cur.fetchone()[0]

            # 2. Subject x class distribution.
            cur.execute(
                """
                SELECT s.name, ch.class_level, COUNT(*)
                FROM cms.content_items ci
                JOIN academic.concepts co ON co.id = ci.concept_id
                JOIN academic.topics t ON t.id = co.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE %s = ANY(ci.tags) AND ci.deleted_at IS NULL
                GROUP BY 1, 2 ORDER BY 1, 2
                """,
                (tag,),
            )
            report["subject_class_distribution"] = [
                {"subject": r[0], "class_level": r[1], "count": r[2]} for r in cur.fetchall()
            ]

            # 3. Blueprint coverage — content_items has no direct blueprint_id
            # column, so coverage is derived from generation_jobs (authoritative).
            cur.execute(
                """
                SELECT COUNT(DISTINCT j.blueprint_id)
                FROM cms.generation_jobs j
                WHERE j.batch_id = %s
                """,
                (batch_id,),
            )
            report["distinct_blueprints_attempted"] = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(DISTINCT j.blueprint_id)
                FROM cms.generation_jobs j
                WHERE j.batch_id = %s AND j.status = 'SUCCEEDED'
                """,
                (batch_id,),
            )
            report["distinct_blueprints_succeeded"] = cur.fetchone()[0]

            # 4. Job outcomes / syllabus-gate rejection rate.
            cur.execute("SELECT status, COUNT(*) FROM cms.generation_jobs WHERE batch_id=%s GROUP BY 1", (batch_id,))
            job_status = dict(cur.fetchall())
            report["job_status"] = job_status
            total_jobs = sum(job_status.values())

            cur.execute(
                """
                SELECT r.error_summary, COUNT(*)
                FROM cms.generation_runs r
                JOIN cms.generation_jobs j ON j.id = r.job_id
                WHERE j.batch_id = %s AND r.status = 'FAILED'
                GROUP BY 1 ORDER BY 2 DESC
                """,
                (batch_id,),
            )
            failure_reasons = cur.fetchall()
            report["failure_reasons"] = [{"reason": r[0], "count": r[1]} for r in failure_reasons]
            syllabus_gate_failures = sum(c for r, c in failure_reasons if r == "SYLLABUS_MAPPING_REVIEW_REQUIRED")
            report["syllabus_gate_rejection_count"] = syllabus_gate_failures
            report["syllabus_gate_rejection_rate"] = round(syllabus_gate_failures / total_jobs, 4) if total_jobs else None

            # 5. Provider success/failure (aggregate from run success/failure counts).
            cur.execute(
                """
                SELECT SUM(r.success_count), SUM(r.failure_count), r.status, COUNT(*)
                FROM cms.generation_runs r
                JOIN cms.generation_jobs j ON j.id = r.job_id
                WHERE j.batch_id = %s
                GROUP BY r.status
                """,
                (batch_id,),
            )
            report["run_outcomes"] = [
                {"status": r[2], "run_count": r[3], "success_count_sum": r[0] or 0, "failure_count_sum": r[1] or 0}
                for r in cur.fetchall()
            ]

            # 6. Validation / duplicate / provenance failures.
            # No per-item rejection ledger table found; rejection detail lives
            # in error_summary on FAILED runs (already captured above) and in
            # the driver's own JSONL log (not queried here — DB-only audit).
            report["validation_duplicate_failures_note"] = (
                "No dedicated rejection-ledger table in DB; validation/duplicate/"
                "diversity rejection counts are only in the driver's JSONL log "
                "(scratchpad/prod_5k_run_002.log.jsonl), not persisted to DB per-item."
            )

            # 7. NCERT/source metadata presence on accepted items.
            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE v.body ? 'ncert_reference' OR v.body ? 'ncert_evidence'
                                        OR v.body ? 'ncert_source_path' OR v.body ? 'source_reference') AS with_ncert_field,
                  COUNT(*) AS total
                FROM cms.content_items ci
                JOIN cms.content_versions v ON v.id = ci.latest_version_id
                WHERE %s = ANY(ci.tags) AND ci.deleted_at IS NULL
                """,
                (tag,),
            )
            ncert_row = cur.fetchone()
            report["ncert_evidence_field_present"] = ncert_row[0]
            report["ncert_evidence_field_total"] = ncert_row[1]

            cur.execute(
                """
                SELECT COUNT(*) FILTER (WHERE co.ncert_reference IS NOT NULL AND co.ncert_reference <> '')
                FROM cms.content_items ci
                JOIN academic.concepts co ON co.id = ci.concept_id
                WHERE %s = ANY(ci.tags) AND ci.deleted_at IS NULL
                """,
                (tag,),
            )
            report["concept_level_ncert_reference_present"] = cur.fetchone()[0]

            # 8. DB persistence integrity — status breakdown of accepted items.
            cur.execute(
                "SELECT status, COUNT(*) FROM cms.content_items ci WHERE %s = ANY(ci.tags) AND ci.deleted_at IS NULL GROUP BY 1",
                (tag,),
            )
            report["content_item_status_breakdown"] = dict(cur.fetchall())

            # 9. Duplicate question detection (stem text) within this pilot batch.
            cur.execute(
                """
                SELECT v.body->>'stem' AS stem, COUNT(*)
                FROM cms.content_items ci
                JOIN cms.content_versions v ON v.id = ci.latest_version_id
                WHERE %s = ANY(ci.tags) AND ci.deleted_at IS NULL
                GROUP BY 1 HAVING COUNT(*) > 1
                """,
                (tag,),
            )
            dupes = cur.fetchall()
            report["duplicate_stem_groups_within_pilot"] = len(dupes)

            # Cross-check against the whole DB (not just this batch) for stem collisions.
            cur.execute(
                """
                WITH pilot_stems AS (
                  SELECT ci.id, v.body->>'stem' AS stem
                  FROM cms.content_items ci
                  JOIN cms.content_versions v ON v.id = ci.latest_version_id
                  WHERE %s = ANY(ci.tags) AND ci.deleted_at IS NULL
                )
                SELECT COUNT(*)
                FROM pilot_stems p
                JOIN cms.content_versions v2 ON v2.body->>'stem' = p.stem
                JOIN cms.content_items ci2 ON ci2.latest_version_id = v2.id AND ci2.id <> p.id
                WHERE ci2.deleted_at IS NULL AND NOT (%s = ANY(ci2.tags))
                """,
                (tag, tag),
            )
            report["duplicate_stem_collisions_with_rest_of_db"] = cur.fetchone()[0]

            # 10. Existing 1,236 prod-5k-* DRAFT preservation.
            cur.execute(
                """
                SELECT count(*) FROM cms.content_items ci
                WHERE ci.tags && (ARRAY[
                    (SELECT 'batch:'||id::text FROM cms.content_batches WHERE batch_key=%s),
                    (SELECT 'batch:'||id::text FROM cms.content_batches WHERE batch_key=%s)
                ])::varchar[]
                """,
                PROD_5K_BATCH_KEYS,
            )
            report["prod_5k_combined_count"] = cur.fetchone()[0]
            report["prod_5k_preserved"] = report["prod_5k_combined_count"] == 1236

            # 11. Runtime and cost — from generation_runs timestamps.
            cur.execute(
                """
                SELECT MIN(r.started_at), MAX(COALESCE(r.completed_at, r.started_at))
                FROM cms.generation_runs r
                JOIN cms.generation_jobs j ON j.id = r.job_id
                WHERE j.batch_id = %s
                """,
                (batch_id,),
            )
            t0, t1 = cur.fetchone()
            report["first_run_started_at"] = str(t0)
            report["last_run_ended_at"] = str(t1)
            report["runtime_seconds_from_db"] = (t1 - t0).total_seconds() if t0 and t1 else None
            report["runtime_note"] = "DB-derived runtime is a lower bound (first job start to last job end); driver's own reported elapsed_s=2722.5 includes setup/queries."

    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
