#!/usr/bin/env python3
"""Read-only dump of academic hierarchy for Seed V2 Phase 1 planning."""
from __future__ import annotations

import json
import sys

import psycopg

DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"


def main() -> int:
    with psycopg.connect(DSN) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.id::text, s.code, s.name,
                   ch.id::text, ch.code, ch.name,
                   t.id::text, t.code, t.name,
                   c.id::text, c.code, c.name
            FROM academic.subjects s
            LEFT JOIN academic.chapters ch ON ch.subject_id = s.id AND ch.deleted_at IS NULL
            LEFT JOIN academic.topics t ON t.chapter_id = ch.id AND t.deleted_at IS NULL
            LEFT JOIN academic.concepts c ON c.topic_id = t.id AND c.deleted_at IS NULL
            WHERE s.deleted_at IS NULL
            ORDER BY s.name, ch.name, t.name, c.name
            """
        )
        rows = cur.fetchall()
        tree = []
        for r in rows:
            tree.append(
                {
                    "subject_id": r[0],
                    "subject_code": r[1],
                    "subject": r[2],
                    "chapter_id": r[3],
                    "chapter_code": r[4],
                    "chapter": r[5],
                    "topic_id": r[6],
                    "topic_code": r[7],
                    "topic": r[8],
                    "concept_id": r[9],
                    "concept_code": r[10],
                    "concept": r[11],
                }
            )
        print(json.dumps({"n": len(tree), "rows": tree}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
