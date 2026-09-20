from __future__ import annotations

import argparse
import sys

from . import config

config.install_network_guard()  # must run before any other project import

from .db import (  # noqa: E402
    apply_classification,
    audit_table_exists,
    connect,
    fetch_remaining_null_subject,
    fetch_unanswered_null_subject,
)
from .ncert_index import build_index  # noqa: E402
from .ncert_manifest import load_or_build_manifest  # noqa: E402
from .normalize import combined_question_text  # noqa: E402
from .phase2_index import build_phase2_index  # noqa: E402
from .phase2_reports import write_phase2_csv, write_phase2_review_csv, write_phase2_summary  # noqa: E402
from .phase2_scoring import classify_phase2  # noqa: E402
from .reports import write_classification_csv, write_review_csv, write_summary_json  # noqa: E402
from .scoring import classify_text  # noqa: E402


def run(apply: bool) -> int:
    manifest = load_or_build_manifest()
    print(f"NCERT files indexed: {manifest['file_count']} (verified={manifest['verified_count']}, unverified={manifest['unverified_count']})")

    idx = build_index(manifest)
    print(f"NCERT term index built: {sum(len(v) for v in idx.exclusive_words.values())} subject-exclusive terms "
          f"(Physics={len(idx.exclusive_words['Physics'])}, Chemistry={len(idx.exclusive_words['Chemistry'])}, Biology={len(idx.exclusive_words['Biology'])})")

    conn = connect(read_only=not apply)
    try:
        questions = fetch_unanswered_null_subject(conn)
        print(f"Unanswered NULL-subject questions fetched: {len(questions)}")

        rows = []
        for q in questions:
            text = combined_question_text(q["question"], q["options"])
            result = classify_text(text, idx)
            rows.append({**q, "result": result})

        write_classification_csv(rows)
        write_review_csv(rows)

        applied = 0
        existing_verified_changed = 0
        if apply:
            if not audit_table_exists(conn):
                print("ERROR: pyq.subject_classification_audit does not exist — run `alembic upgrade head` first.", file=sys.stderr)
                return 2
            for r in rows:
                res = r["result"]
                if res.status != "RESOLVED":
                    continue
                updated = apply_classification(
                    conn,
                    question_id=r["question_id"],
                    new_subject=res.predicted_subject,
                    previous_subject=r["subject"],
                    status=res.status,
                    confidence=res.confidence,
                    method="ncert_exclusive_vocabulary_overlap",
                    ncert_source="; ".join(f"{e['book']}#p{e['page']}" for e in res.evidence[:3]),
                    classifier_version=config.CLASSIFIER_VERSION,
                )
                if updated:
                    applied += 1
                elif r["subject"] is not None:
                    existing_verified_changed += 0  # never happens: query only selects subject IS NULL
            conn.commit()
        else:
            conn.rollback()

        summary = write_summary_json(rows, applied=applied, existing_verified_changed=existing_verified_changed, dry_run=not apply)
    finally:
        conn.close()

    print()
    print("=== SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


def run_phase2(apply: bool, pass_name: str | None) -> int:
    manifest = load_or_build_manifest()
    print(f"NCERT files indexed: {manifest['file_count']} (verified={manifest['verified_count']}, unverified={manifest['unverified_count']})")

    term_idx = build_index(manifest)  # Phase 1 index — reused, not rebuilt from PDFs
    phase2_idx = build_phase2_index(manifest)  # chapter-level index, from cached page text
    print(f"Phase 2 chapter index: {len(phase2_idx.chapters)} chapters "
          f"(pass={pass_name or 'default'})")

    conn = connect(read_only=not apply)
    try:
        questions = fetch_remaining_null_subject(conn)
        print(f"Remaining NULL-subject questions fetched: {len(questions)}")

        rows = []
        for q in questions:
            result = classify_phase2(q["question"], q["options"], term_idx, phase2_idx)
            rows.append({**q, "result": result})

        write_phase2_csv(rows)
        write_phase2_review_csv(rows)

        applied = 0
        if apply:
            if not audit_table_exists(conn):
                print("ERROR: pyq.subject_classification_audit does not exist — run `alembic upgrade head` first.", file=sys.stderr)
                return 2
            for r in rows:
                res = r["result"]
                if res.classification_status != "RESOLVED":
                    continue
                updated = apply_classification(
                    conn,
                    question_id=r["question_id"],
                    new_subject=res.predicted_subject,
                    previous_subject=r["subject"],
                    status=res.classification_status,
                    confidence=res.confidence,
                    method="ncert_phase2_deep_retrieval",
                    ncert_source="; ".join(
                        f"{e.get('ncert_book','')}#{e.get('ncert_chapter','')}" for e in res.evidence[:3]
                    ),
                    classifier_version=config.CLASSIFIER_VERSION_PHASE2,
                )
                if updated:
                    applied += 1
            conn.commit()
        else:
            conn.rollback()

        summary = write_phase2_summary(rows, applied=applied)
    finally:
        conn.close()

    print()
    print("=== PHASE 2 SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="pyq_subject_classifier")
    parser.add_argument("--apply", action="store_true", help="Persist subject updates (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Explicit dry-run (default behavior)")
    parser.add_argument("--phase2", action="store_true", help="Run the Phase 2 deep-resolution pipeline")
    parser.add_argument(
        "--phase2-pass", choices=["high", "cross-chapter", "conservative"], default=None,
        help="Phase 2 confidence-threshold profile (default: the unified conservative-by-default scorer)",
    )
    args = parser.parse_args(argv)

    if args.apply and args.dry_run:
        print("ERROR: --apply and --dry-run are mutually exclusive", file=sys.stderr)
        return 2

    if args.phase2:
        return run_phase2(apply=args.apply, pass_name=args.phase2_pass)

    return run(apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
