"""PASTQ-OCR-002 — DB after snapshot + pilot refresh (read-only CMS)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
import sys

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.acquisition.pastq.ocr_pipeline import DEFAULT_STAGING, select_pilot_sample  # noqa: E402


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        status = {
            r[0]: r[1]
            for r in conn.execute(
                text(
                    """
                    SELECT status, COUNT(*) FROM cms.content_items
                    WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                    GROUP BY status
                    """
                )
            )
        }
        unmapped = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                  AND status = 'DRAFT' AND concept_id IS NULL
                """
            )
        ).scalar()
        pastq = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                  AND tags::text LIKE '%import:pastq-001%'
                """
            )
        ).scalar()

    staging = Path(DEFAULT_STAGING)
    recs = [
        json.loads(line)
        for line in (staging / "questions_all.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pilot = select_pilot_sample(recs, limit=5)
    summary = json.loads((staging / "summary.json").read_text(encoding="utf-8"))
    summary["pilot_sample"] = pilot
    (staging / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (staging / "pilot_sample.json").write_text(json.dumps(pilot, indent=2, ensure_ascii=False), encoding="utf-8")

    no_year = sum(1 for r in recs if r["paper"].get("year") is None)
    no_subj = sum(1 for r in recs if not r["question"].get("subject"))
    incomplete_opts = sum(
        1
        for r in recs
        if sum(1 for k in "ABCD" if (r["question"].get("options") or {}).get(k)) < 4
    )

    out = {
        "after": {"status": status, "unmapped": unmapped, "pastq_pilot": pastq},
        "meta_gaps": {
            "no_year": no_year,
            "no_subject": no_subj,
            "incomplete_options": incomplete_opts,
        },
        "pilot_sample": pilot,
    }
    Path(r"D:\ravishori\AI Neet Exam App\docs\audits\_pastq_ocr_002_after.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, indent=2, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
