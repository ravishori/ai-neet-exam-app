# P2.3 Human Gold Review Sandbox

Isolated web environment for human review of the 100-question P2.3-R1 gold sample.

## Architecture

```text
CSV Upload → Validation → review_sandbox schema (PostgreSQL)
                              ↓
                    AI Assistance (pre_human_audit)
                              ↓
                    Human Gold fields (separate table)
                              ↓
                    Export → Existing Human-Gold Gate
```

**REVIEW SANDBOX ≠ PRODUCTION MCQ DATABASE**

Production `cms.content_items` / assessment tables are never written.

## Database schema

PostgreSQL schema: `review_sandbox`

| Table | Purpose |
|-------|---------|
| `sessions` | 7-day TTL review sessions |
| `uploads` | CSV upload metadata + SHA-256 |
| `questions` | Immutable original AI fields |
| `human_reviews` | Human gold decisions |
| `ai_reviews` | Advisory AI/pre-audit results |
| `audit_events` | Session audit trail |

Migration: `alembic/versions/e1f2a3b4c5d6_review_sandbox_p2_3_human_gold.py`

## API

Base: `/api/v1/cms/human-gold-sandbox/`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload` | Validate CSV, return preview |
| POST | `/import` | Import into sandbox session |
| GET | `/sessions/{id}/dashboard` | Progress + expiry |
| GET | `/sessions/{id}/queue` | Filterable review queue |
| GET | `/sessions/{id}/questions/{qid}` | Review packet |
| PATCH | `/sessions/{id}/questions/{qid}/human-review` | Save draft/complete |
| POST | `/sessions/{id}/ai-check` | Run deterministic AI assist |
| POST | `/sessions/{id}/export` | Export CSV/JSON/JSONL |
| POST | `/sessions/{id}/run-gate` | Export + Human-Gold Gate |
| DELETE | `/sessions/{id}` | Manual session delete |

Auth: `content.review` permission + CSRF on mutations.

## Frontend

Route: `/admin/p2-3/human-gold`

Workflow:

1. Upload CSV (`human_gold_sample_r1_annotated.csv`)
2. Preview validation
3. Import to sandbox
4. Run AI checks (optional)
5. Review CRITICAL → HIGH → MEDIUM → LOW
6. Export / Run Human-Gold Gate

## Human gold semantics

- AI never writes `human_*` fields
- `DRAFT` vs `COMPLETE` — autosave/draft does not complete review
- `PENDING` preserved from source CSV
- Labels: ORIGINAL AI DATA | PRE-HUMAN AUDIT | AI ASSISTANCE — NOT GOLD | HUMAN GOLD DECISION

## Gate integration

Export writes canonical CSV to `data/staging/mcq/p2_3_human_gold/human_gold_review.csv` then invokes:

```bash
python apps/backend/scripts/run_mcq_p2_3_human_gold.py --report
```

## Expiry & cleanup

- Sessions expire `created_at + 7 days`
- Cleanup: `python apps/backend/scripts/cleanup_mcq_review_sandbox.py`
- Idempotent, transactional, does not touch production MCQs

## Local run

```bash
# Backend
cd apps/backend
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd apps/web
npm run dev
```

Open: http://localhost:3000/admin/p2-3/human-gold

## Tests

```bash
cd apps/backend
pytest app/modules/cms/tests/test_human_gold_sandbox.py -q
pytest app/modules/cms/tests/test_mcq_p2_3_human_gold_gate.py -q
python scripts/cleanup_mcq_review_sandbox.py --test
```

## Production-write guarantee

All sandbox writes target `review_sandbox.*` only. Gate export writes staging files only. **Production DB writes = 0** for MCQ promotion.
