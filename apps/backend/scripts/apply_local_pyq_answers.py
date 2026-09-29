"""Phase 7 — apply the locally-resolved, quality-gated VERIFIED answers
(recovery/pyq_local_answer_recovery.csv) to the LOCAL trinetra_db only.

NEVER targets production — this script has no DSN argument at all; it
always uses app.core.config.get_settings() (local .env DATABASE_URL).

Single atomic transaction, all-or-nothing, same safety pattern as
recovery/migrate_87_safe_candidates.py:
  - immediate per-row conflict check right before each INSERT (no
    ON CONFLICT DO NOTHING — a real conflict must raise, not be absorbed)
  - rowcount == 1 required after every UPDATE
  - CONFLICT rows are never written, never marked ANSWER_VERIFIED
  - UNRESOLVED/INVALID rows are left untouched (stay ANSWER_PENDING)
  - resumable/idempotent: rows whose question is no longer ANSWER_PENDING
    (e.g. already applied in a prior run) are skipped, not re-applied
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.database import AsyncSessionLocal  # noqa: E402

RECOVERY_DIR = Path(__file__).parent.parent.parent.parent / "recovery"
DEFAULT_CSV_PATH = RECOVERY_DIR / "pyq_local_answer_recovery.csv"
DEFAULT_ASSERTION_SOURCE = "pyq_local_ncert_recovery:2026-09-28"
RESOLVER_VERSION = "pyq-local-ncert-resolver-v1"
VALID_OPTIONS = {"A", "B", "C", "D"}


class AbortImport(Exception):
    pass


def load_verified_rows(csv_path: Path) -> list[dict]:
    rows = [r for r in csv.DictReader(csv_path.open(encoding="utf-8")) if r["resolution_status"] == "VERIFIED"]
    for r in rows:
        if r["correct_option"] not in VALID_OPTIONS:
            sys.exit(f"Row {r['production_question_id']} has invalid correct_option {r['correct_option']!r} — aborting before any DB work.")
    return rows


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULT_CSV_PATH, help="CSV path (same schema as pyq_local_answer_recovery.csv)")
    ap.add_argument("--assertion-source", default=DEFAULT_ASSERTION_SOURCE, help="Distinct assertion_source label for this batch's provenance")
    ap.add_argument("--dry-run", action="store_true", help="Report what would happen; performs zero writes")
    return ap.parse_args()


async def main() -> None:
    args = parse_args()
    assertion_source = args.assertion_source
    targets = load_verified_rows(args.input)
    print(f"Loaded {len(targets)} VERIFIED rows from {args.input}")

    async with AsyncSessionLocal() as session:
        inserted = 0
        skipped_already_applied = 0
        would_insert = 0
        would_skip = 0
        rejected: list[str] = []
        try:
            if args.dry_run:
                for r in targets:
                    qid = r["production_question_id"]
                    row = (await session.execute(text("SELECT state FROM pyq.questions WHERE id = :id"), {"id": qid})).fetchone()
                    if row is None:
                        rejected.append(f"{qid}: not found in pyq.questions")
                        continue
                    state = row[0]
                    existing_count = (
                        await session.execute(
                            text("SELECT count(*) FROM pyq.answer_assertions WHERE question_id = :id"), {"id": qid}
                        )
                    ).scalar()
                    if state == "ANSWER_PENDING" and existing_count == 0:
                        would_insert += 1
                    else:
                        would_skip += 1
                        rejected.append(f"{qid}: state={state!r} existing_assertions={existing_count}")
                await session.rollback()
                print(f"DRY RUN — would insert {would_insert}, would skip/reject {would_skip}, of {len(targets)} total.")
                for reason in rejected[:20]:
                    print(f"  rejected: {reason}")
                return

            for r in targets:
                qid = r["production_question_id"]

                row = (
                    await session.execute(
                        text("SELECT state FROM pyq.questions WHERE id = :id"), {"id": qid}
                    )
                ).fetchone()
                if row is None:
                    raise AbortImport(f"{qid}: question not found in local pyq.questions")
                state = row[0]

                if state == "ANSWER_VERIFIED":
                    # Idempotent re-run: check whether it's already this
                    # batch's own prior write; if so, skip cleanly.
                    existing = (
                        await session.execute(
                            text(
                                "SELECT count(*) FROM pyq.answer_assertions "
                                "WHERE question_id = :id AND assertion_source = :src"
                            ),
                            {"id": qid, "src": assertion_source},
                        )
                    ).scalar()
                    if existing:
                        skipped_already_applied += 1
                        continue
                    raise AbortImport(f"{qid}: state is ANSWER_VERIFIED but not from this batch — will not overwrite")

                if state != "ANSWER_PENDING":
                    raise AbortImport(f"{qid}: state is {state!r}, expected ANSWER_PENDING")

                existing_count = (
                    await session.execute(
                        text("SELECT count(*) FROM pyq.answer_assertions WHERE question_id = :id"), {"id": qid}
                    )
                ).scalar()
                if existing_count != 0:
                    raise AbortImport(f"{qid}: {existing_count} existing answer_assertions found immediately before INSERT")

                # Local trinetra_db is one Alembic revision behind
                # c6cfdf360a4b (which adds resolver_version/explanation) —
                # flagged in recovery/PYQ_87_SAFE_CANDIDATE_MIGRATION_SPEC.md.
                # Fold that provenance into evidence_note instead of relying
                # on columns this local schema doesn't have yet.
                evidence_note = (
                    f"resolver_version={RESOLVER_VERSION}; method=deterministic_ncert_term_phrase_grounding; "
                    f"source={r['evidence_source']} page={r['evidence_page']}; "
                    f"excerpt={r['evidence_excerpt'][:200]}"
                )
                await session.execute(
                    text(
                        "INSERT INTO pyq.answer_assertions "
                        "(question_id, asserted_option, assertion_source, verification_status, evidence_note) "
                        "VALUES (:qid, :opt, :src, 'VERIFIED', :note)"
                    ),
                    {
                        "qid": qid,
                        "opt": r["correct_option"],
                        "src": assertion_source,
                        "note": evidence_note,
                    },
                )

                result = await session.execute(
                    text("UPDATE pyq.questions SET state = 'ANSWER_VERIFIED', updated_at = now() WHERE id = :id AND state = 'ANSWER_PENDING'"),
                    {"id": qid},
                )
                if result.rowcount != 1:
                    raise AbortImport(f"{qid}: UPDATE affected {result.rowcount} rows, expected exactly 1")

                inserted += 1

            # Final in-transaction verification
            count_check = (
                await session.execute(
                    text("SELECT count(*) FROM pyq.answer_assertions WHERE assertion_source = :src"),
                    {"src": assertion_source},
                )
            ).scalar()
            expected = inserted + skipped_already_applied
            if count_check != expected:
                raise AbortImport(f"Post-insert assertion count is {count_check}, expected {expected}")

            await session.commit()
            print(f"COMMIT — inserted {inserted} new assertions, skipped {skipped_already_applied} already-applied (idempotent re-run).")

        except AbortImport as exc:
            await session.rollback()
            sys.exit(f"ABORTED — ROLLBACK, zero writes committed.\n{exc}")
        except Exception:
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
