# FACTORY-P4 Implementation — Automated QA + Dedupe + Sampling Prep

**Status:** COMPLETE · 2026-09-01  
**Scope:** Versioned `QAResult`, DB-backed fingerprints, GREEN/YELLOW/RED, reproducible sampling eligibility.  
**Non-goals:** Auto-submit / approve / publish · AI scientific judge · pgvector semantic dedupe · mass generation · P5 SME workflow UI.

---

## Architecture

```
GenerationCandidate (CREATED + DRAFT ContentItem)
        ↓
ContentFactoryQAService (gates A–G, deterministic)
        ↓
QAResult (qa_version + evaluation_no, is_latest)
        ↓ classification
GREEN → sampling_eligible
YELLOW → 100% human-review eligibility
RED → factory quarantine (qa_quarantined) — still DRAFT in ECAEP
        ↓
ReviewSample (seeded stratified GREEN + all YELLOW + RED list)
```

**Factory QA state ≠ ECAEP status.** RED does not change `ContentItem.status`.

---

## QAResult model

| Field | Notes |
|-------|--------|
| `candidate_id` / `content_item_id` / `content_version_id` | Lineage |
| `qa_version` | e.g. `factory_qa_v1` |
| `evaluation_no` + `is_latest` | Historical evidence preserved |
| `classification` | GREEN / YELLOW / RED |
| `gate_results` JSONB | Per-gate pass/fail/detail |
| `failed_checks` / `warnings` | Arrays |
| `duplicate_class` | UNIQUE / NORMALIZED_DUPLICATE / POSSIBLE_DUPLICATE / … |
| `sampling_eligible` / `quarantine` | Factory flags |
| `scientific_certification` | Always `false` |
| `disclaimer` | AUTOMATED_QA_ONLY |

**Idempotency:** Re-run with same `qa_version` + same `content_version_id` returns latest row (`idempotent: true`). `force_new=true` supersedes (`is_latest=false`) and increments `evaluation_no`.

---

## QA gates (`factory_qa_v1`)

| Gate | Checks | Fail → |
|------|--------|--------|
| A Structure | 4 unique options, answer, stem, explanation, difficulty | RED |
| B Blueprint | Pin, concept/subject/difficulty/format/objective/family | RED |
| C Hierarchy | subject→chapter→topic→concept resolvable | RED |
| D Provenance | model, prompt_version, batch/job/run, blueprint pin; no official claims | RED / YELLOW soft |
| E Answer | Deterministic answer↔explanation contradiction | RED; always warns NO_SCIENTIFIC_CERTIFICATION |
| F Duplicate | Indexed stem / option-stem fingerprints | RED / YELLOW |
| G Safety | Official impersonation, injection/secrets, internal leak | RED |

No AI judge in P4.

---

## GREEN / YELLOW / RED policy

| Tier | Meaning |
|------|---------|
| **GREEN** | Critical gates pass, not a known duplicate → **eligible for GREEN sample only** |
| **YELLOW** | Possible duplicate / soft metadata / short explanation → **100% human-review eligibility** |
| **RED** | Structural/blueprint/hierarchy/provenance/safety/hard duplicate → **factory quarantine** |

GREEN ≠ scientifically correct ≠ approved ≠ publishable.

---

## Duplicate architecture

- Table `cms.question_fingerprints` (`stem_hash`, `option_stem_hash`, indexed)
- Queries by hash — **no full-bank Python load**; concept-scoped fallback ≤500 rows only if fingerprint missing
- Classes: `UNIQUE`, `NORMALIZED_DUPLICATE`, `POSSIBLE_DUPLICATE`, plus warning `SEMANTIC_DEDUPE_NOT_AVAILABLE`
- **Not implemented:** embedding / pgvector semantic similarity

---

## Sampling architecture

- Table `cms.review_samples`
- Policy `factory_sample_v1`
- GREEN draw: stratified round-robin by subject|family|difficulty|blueprint; size \(n=\min(N,\max(n_{min},\lceil k\sqrt{N}\rceil))\)
- YELLOW: 100% listed for review
- RED: listed for quarantine review — **excluded from GREEN sample**
- Reproducible via `seed` + idempotent `sample_key`

---

## Quarantine

`GenerationCandidate.qa_quarantined` + `QAResult.quarantine` — factory-level only. ECAEP remains DRAFT.

---

## API

| Method | Path | Permission |
|--------|------|------------|
| POST | `/api/v1/cms/content-batches/{id}/qa` | `content.factory.execute` |
| POST | `/api/v1/cms/generation-candidates/{id}/qa` | `content.factory.execute` |
| GET | `/api/v1/cms/content-batches/{id}/qa-summary` | `content.factory.view` |
| POST | `/api/v1/cms/content-batches/{id}/sample` | `content.factory.execute` |

Editorial review packet includes `factory_qa` evidence block (assistive).

---

## Migration

`b8c9d0e1f2a3_cms_factory_qa_p4.py` — apply on **dev and test** DBs:

```bash
# trinetra_db
alembic upgrade head
# trinetra_test_db
$env:DATABASE_URL_SYNC="...trinetra_test_db"; alembic upgrade head
```

---

## Live pilot commands (do not auto-run)

After Anthropic credits restored:

```powershell
cd apps/backend
# 1) Generate ~100 DRAFTs
Remove-Item Env:FACTORY_P3_SMOKE -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe scripts\run_factory_p3_pilot.py

# 2) QA + sample via API (CONTENT_MANAGER) or thin script:
# POST /api/v1/cms/content-batches/{batch_id}/qa
# POST /api/v1/cms/content-batches/{batch_id}/sample  {"seed": 42}
```

Capture checksums before/after. Never auto-submit.

---

## Known limitations

1. `SEMANTIC_DEDUPE_NOT_AVAILABLE`
2. No AI judge / no scientific certification
3. Soft YELLOW signals are heuristic
4. Fingerprint backfill for legacy bank is concept-scoped on miss
5. Does not auto-transition batch beyond QA/SAMPLING orchestration statuses

---

## Recommended FACTORY-P5

Controlled human sampling UX + exception queues wired to editorial review — optional assistive AI judge later. **Not** 1k/10k generation.
