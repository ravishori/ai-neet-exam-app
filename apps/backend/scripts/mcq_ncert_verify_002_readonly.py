"""MCQ-NCERT-VERIFY-002 — READ-ONLY extract of 20 CREATED DRAFTs + NCERT PDF text.

Does NOT mutate DB, generate MCQs, call LLM providers, or write final verdicts.
Produces scratch pack for independent human verification against NCERT Books.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)

from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

GEN = ROOT / "docs" / "audits" / "mcq_controlled_generation_001.json"
SCRATCH = ROOT / "docs" / "audits" / "_mcq_ncert_verify_002_scratch.json"
NCERT_ROOT = ROOT / "NCERT Books"
SYLLABUS = ROOT / "NEETSyllabus.txt"


def snapshot(conn) -> dict[str, Any]:
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
        ).all()
    }
    return {
        "chapters": conn.execute(
            text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")
        ).scalar(),
        "topics": conn.execute(
            text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")
        ).scalar(),
        "concepts": conn.execute(
            text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")
        ).scalar(),
        "kus": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "status": status,
        "unmapped_draft": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                  AND status = 'DRAFT' AND concept_id IS NULL
                """
            )
        ).scalar(),
        "candidates": conn.execute(text("SELECT COUNT(*) FROM cms.generation_candidates")).scalar(),
        "jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
        "published": status.get("PUBLISHED", 0),
        "review_required_mappings": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.question_blueprints bp
                WHERE bp.deleted_at IS NULL
                  AND (
                    bp.constraints::text ILIKE '%REVIEW_REQUIRED%'
                    OR bp.constraints::text ILIKE '%SYLLABUS_MAPPING_REVIEW%'
                  )
                """
            )
        ).scalar(),
    }


def extract_pages(pdf_path: Path, pages: list[int], max_chars: int = 14000) -> dict[str, Any]:
    import fitz

    if not pdf_path.is_file():
        return {"error": f"missing_pdf:{pdf_path}", "pages": {}}
    doc = fitz.open(str(pdf_path))
    out: dict[str, str] = {}
    total = 0
    for p in pages:
        if p < 1 or p > doc.page_count:
            out[str(p)] = f"[PAGE_OUT_OF_RANGE page={p} page_count={doc.page_count}]"
            continue
        txt = doc.load_page(p - 1).get_text("text") or ""
        if total + len(txt) > max_chars:
            remain = max(0, max_chars - total)
            out[str(p)] = txt[:remain] + "\n…[truncated]"
            total = max_chars
            break
        out[str(p)] = txt
        total += len(txt)
    meta = {"page_count": doc.page_count, "extracted_chars": total}
    doc.close()
    return {"meta": meta, "pages": out}


def normalize_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {}
    opts = body.get("options") or body.get("choices") or []
    if isinstance(opts, dict):
        opts = [{"key": k, "text": v} for k, v in opts.items()]
    normalized_opts = []
    for o in opts:
        if isinstance(o, dict):
            key = o.get("key") or o.get("label") or o.get("id")
            text_v = o.get("text") or o.get("option_text") or o.get("value") or ""
            normalized_opts.append({"key": str(key), "text": str(text_v)})
        else:
            normalized_opts.append({"key": "?", "text": str(o)})
    return {
        "stem": body.get("stem") or body.get("question") or "",
        "options": normalized_opts,
        "correct_option": body.get("correct_option")
        or body.get("correct_answer")
        or body.get("answer")
        or body.get("correct_key"),
        "explanation": body.get("explanation") or body.get("solution") or "",
        "difficulty": body.get("difficulty"),
        "raw_keys": sorted(body.keys()),
    }


def main() -> int:
    assert GEN.is_file()
    assert NCERT_ROOT.is_dir()
    assert SYLLABUS.is_file()
    gen = json.loads(GEN.read_text(encoding="utf-8"))
    created = [c for c in gen["candidates"] if c.get("candidate_status") == "CREATED"]
    assert len(created) == 20, f"expected 20 CREATED, got {len(created)}"

    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    packs: list[dict[str, Any]] = []

    with engine.connect() as conn:
        before = snapshot(conn)
        for c in created:
            item_id = c["lineage"]["content_item_id"]
            row = conn.execute(
                text(
                    """
                    SELECT ci.id::text AS content_item_id,
                           ci.status,
                           ci.title,
                           ci.concept_id::text AS concept_id,
                           cv.id::text AS version_id,
                           cv.body,
                           cv.model_used,
                           cv.generation_cost_usd
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                    WHERE ci.id = CAST(:id AS uuid)
                    """
                ),
                {"id": item_id},
            ).mappings().one()
            body = normalize_body(row["body"])
            pdf = Path(c["ncert_source_path"])
            pages = list(c.get("evidence_pages") or [])
            expanded = sorted(set(int(p) for p in pages)) if pages else [1, 2, 3, 4, 5]
            pdf_pack = extract_pages(pdf, expanded)
            packs.append(
                {
                    "candidate_id": c["candidate_id"],
                    "batch_id": c.get("batch_id"),
                    "job_id": c.get("job_id"),
                    "run_id": c.get("run_id"),
                    "blueprint_id": c.get("blueprint_id"),
                    "subject": c.get("subject"),
                    "chapter": c.get("chapter"),
                    "topic": c.get("topic"),
                    "concept": c.get("concept"),
                    "ncert_source_path": c.get("ncert_source_path"),
                    "ncert_relative": c.get("ncert_relative"),
                    "syllabus_mapping": c.get("syllabus_mapping"),
                    "evidence_pages": pages,
                    "provider": c.get("provider"),
                    "model_used": c.get("model_used") or row.get("model_used"),
                    "content_item_id": row["content_item_id"],
                    "content_status": row["status"],
                    "version_id": row["version_id"],
                    "title": row["title"],
                    "mcq": body,
                }
            )
            packs[-1]["ncert_excerpt"] = pdf_pack
        after = snapshot(conn)

    out = {
        "task": "MCQ-NCERT-VERIFY-002-SCRATCH",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_audit": str(GEN),
        "ncert_root": str(NCERT_ROOT),
        "syllabus_path": str(SYLLABUS),
        "database_before": before,
        "database_after": after,
        "mutation_detected": before != after,
        "items": packs,
    }
    SCRATCH.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({"scratch": str(SCRATCH), "count": len(packs), "mutation": before != after}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
