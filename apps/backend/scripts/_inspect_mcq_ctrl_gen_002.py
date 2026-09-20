"""Read-only inspection of MCQ-CONTROLLED-GENERATION-002 state."""

import json

from sqlalchemy import create_engine, text

from app.core.config import get_settings

engine = create_engine(get_settings().database_url_sync)
with engine.connect() as conn:
    rows = conn.execute(
        text(
            """
            SELECT b.id::text AS batch_id, b.batch_key, s.code AS subject,
                   b.created_at,
                   COUNT(gc.id)::int AS candidate_attempts,
                   COUNT(DISTINCT gc.content_item_id) FILTER (
                     WHERE gc.status = 'CREATED' AND ci.status = 'DRAFT'
                       AND ci.deleted_at IS NULL
                   )::int AS valid_drafts
            FROM cms.content_batches b
            JOIN academic.subjects s ON s.id = b.subject_id
            LEFT JOIN cms.generation_candidates gc
              ON gc.batch_id = b.id AND gc.deleted_at IS NULL
            LEFT JOIN cms.content_items ci ON ci.id = gc.content_item_id
            WHERE b.deleted_at IS NULL
              AND b.batch_key LIKE 'mcq-ctrl-gen-002%'
            GROUP BY b.id, b.batch_key, s.code, b.created_at
            ORDER BY b.created_at
            """
        )
    ).mappings().all()
print(json.dumps([dict(row) for row in rows], indent=2, default=str))

with engine.connect() as conn:
    details = conn.execute(
        text(
            """
            SELECT gc.id::text AS candidate_id, s.code AS subject,
                   gc.status, gc.error_code, gc.provider, gc.model_used,
                   gc.cost_usd, gc.attempt_no, gc.provider_attempt_no,
                   gc.blueprint_id::text, gc.content_item_id::text,
                   ci.status AS content_status, gr.execution_metadata
            FROM cms.generation_candidates gc
            JOIN cms.content_batches b ON b.id = gc.batch_id
            JOIN academic.subjects s ON s.id = b.subject_id
            LEFT JOIN cms.content_items ci ON ci.id = gc.content_item_id
            LEFT JOIN cms.generation_runs gr ON gr.id = gc.run_id
            WHERE b.batch_key LIKE 'mcq-ctrl-gen-002%'
              AND gc.deleted_at IS NULL
            ORDER BY gc.created_at
            """
        )
    ).mappings().all()
print(json.dumps([dict(row) for row in details], indent=2, default=str))
