# MCQ Historical Generation Forensic Audit

**Date:** 2026-09-02  
**Scope:** READ-ONLY investigation of ~5,000 Physics MCQs + local database identity  
**Product:** Trinetra AI Learning OS (TALOS)  
**Read-only:** YES (SELECT / catalog / git / file inspection only)

---

## 1. Executive Verdict

### **PARTIALLY CONFIRMED**

| Claim | Verdict |
|-------|---------|
| ~5,000 Class 11 Physics MCQs were **targeted** | **CONFIRMED** (HIGH) — `.cursorrules`, `physics-question-bank/config.py` `TOTAL_MCQS = 5000` |
| ~5,000 were **generated as files** | **CONFIRMED** (HIGH) — `physics_11_5000_mcqs.json` contains **exactly 5000** unique IDs |
| ~5,000 were **persisted into TALOS `trinetra_db` CMS** | **DISPROVEN** (HIGH) — 0 `PHY11-*` IDs in `cms.content_items`; Physics CMS count = **73** |
| ~5,000 were **persisted into PostgreSQL `physics_mcq_questions`** | **NOT VERIFIED / NOT FOUND** (HIGH for absence under `trinetra_app`) — no such table in any DB reachable with app credentials |
| ~5,000 exist in **local SQLite** | **CONFIRMED** (HIGH) — `physics-question-bank/output/physics_test.db` has **5000** rows |
| `neet_exam_prep_db` is the TALOS MCQ database | **NO** (HIGH) — not referenced by TALOS config; different schema; not `cms.content_items` |

**Strongest evidence of what happened:**  
The 5,000 Physics MCQs were **actually generated** by the standalone `physics-question-bank` pipeline (algorithmic generator) into **file artifacts** (JSON/CSV/ZIP) and a **local SQLite** DB. They were **not imported** into the TALOS CMS (`trinetra_db`). They are a **parallel, unintegrated bank**, not the same inventory as the current **175** CMS QUESTIONs.

---

## 2. Database Identity

### Is `neet_exam_prep_db` the local MCQ database?

### **NO**

**Evidence:**

1. **No repository references** to the string `neet_exam_prep_db` anywhere in this repo (grep = 0 hits).
2. TALOS app / scripts / `.env.example` target **`trinetra_db`** (runtime) and **`trinetra_test_db`** (pytest).
3. Catalog inspection: `neet_exam_prep_db` has a **legacy flat schema** (`public.questions`, `question_options`, `subjects`, `exams`, …) — **no `cms` schema**, no `content_items`.
4. Row access with TALOS role `trinetra_app`: **permission denied** on `public.questions` — cannot prove its row counts; but schema alone proves it is **not** the TALOS CMS store.
5. Live CMS inventory lives in **`trinetra_db`**: 175 QUESTIONs (matches prior production inventory audit).

---

## 3. Database Comparison

| Database | MCQs (QUESTION / equivalent) | Physics | Published | Draft | Purpose | Evidence |
| -------- | ---: | ------: | --------: | ----: | ------- | -------- |
| `trinetra_db` | **175** (`cms.content_items` QUESTION) | **73** | **11** | **153** (+11 IN_REVIEW) | **TALOS live CMS + practice** | `DATABASE_URL`; SELECT counts |
| `trinetra_test_db` | **0** | 0 | 0 | 0 | Pytest / CMS test DB | `DATABASE_URL_SYNC` / test conftest; empty content_items |
| `neet_exam_prep_db` | **UNKNOWN (rows inaccessible)** | UNKNOWN | UNKNOWN | UNKNOWN | **Legacy / other app** schema (`public.questions`) | pg_class lists tables; SELECT denied for `trinetra_app`; **not** TALOS |
| `exam_platform` | **UNKNOWN (likely inaccessible)** | UNKNOWN | UNKNOWN | UNKNOWN | Separate exam platform schema | Has `questions`, `ai_generated_questions`; not TALOS config |
| SQLite `physics_test.db` | **5000** (`physics_mcq_questions`) | **5000** | n/a | n/a | Physics bank local import smoke | File under `physics-question-bank/output/` |

**Runtime config (safe, no secrets):**

| Variable | Database name | Context | Source |
|----------|---------------|---------|--------|
| `DATABASE_URL` | `trinetra_db` | App async | `apps/backend/.env` / Settings |
| `DATABASE_URL_SYNC` | `trinetra_test_db` (as loaded by Settings in this session) | Sync/Alembic/scripts may differ from file | Settings object |
| Test override | `trinetra_test_db` | pytest | `apps/backend/app/modules/cms/tests/conftest.py` |
| Factory/scripts defaults | `trinetra_db` | Content factory pilots | Multiple `apps/backend/scripts/run_factory_*.py` |

---

## 4. Historical 5,000 Reconciliation

| Stage | Count | Evidence |
| ----- | ----: | -------- |
| Reported target | **5000** | `physics-question-bank/config.py` `TOTAL_MCQS=5000`; root + package `.cursorrules` |
| Requested | **5000** (default CLI `--count`) | `physics-question-bank/main.py` |
| Generated (file) | **5000** | `output/physics_11_5000_mcqs.json` list length; IDs `PHY11-CH01-0001` … `PHY11-CH10-5000`; 5000 unique IDs |
| Generated composition | 5000 algorithmic; 1500 with `has_diagram=True` | JSON Counter on `source` / `has_diagram`; 10×500 chapters |
| Persisted (SQLite) | **5000** | `output/physics_test.db` table `physics_mcq_questions` |
| Persisted (PostgreSQL TALOS CMS) | **0** | No `PHY11` in slug/title/stem; Physics CMS=73 unrelated |
| Persisted (PostgreSQL `physics_mcq_questions`) | **0 found** | No such table in any DB accessible as `trinetra_app` |
| Validated | **NOT VERIFIED** as a separate gate in DB | Validator module exists; no persisted validation ledger for the 5k bank found in TALOS |
| Approved / Published (ECAEP) | **0** of the 5k bank | Never entered CMS workflow |

Artifacts timestamps (filesystem): JSON/CSV/ZIP written **2026-09-02 ~05:45–05:55**; SQLite **~05:55**.  
Directory `physics-question-bank/` is currently **untracked** (`git status` shows `?? physics-question-bank/`).

---

## 5. Historical Artifacts

### Files (5k bank)

| Path | Role | Approx records |
|------|------|----------------|
| `physics-question-bank/output/physics_11_5000_mcqs.json` | Primary generation output | **5000** |
| `physics-question-bank/output/physics_11_5000_mcqs.csv` | CSV export | **5000** (file length ~2.7MB) |
| `physics-question-bank/output/physics_11_mcqs.zip` | Zip of outputs | — |
| `physics-question-bank/output/physics_test.db` | SQLite upsert of bank | **5000** |
| `physics-question-bank/config.py` | Target definition | TARGET 5000 |
| `physics-question-bank/scripts/import_to_db.py` | Optional PG/SQLite importer | Import tool only |
| `.cursorrules` (repo + package) | Design directive for 5k engine | TARGET |

### TALOS DB tables with generation lineage (discovered)

- `cms.content_items` / `cms.content_versions` (`model_used`, `prompt_version`, `generation_cost_usd`, `knowledge_unit_id`, `tags`)
- `cms.generation_candidates` (32 rows) — factory candidates, **not** the 5k bank
- `cms.content_batches`, `generation_jobs`, `generation_runs`, `question_blueprints`, …
- `ingestion.ingestion_jobs` (`pilot_run_id`, `target_mcq_count`, …)
- `ingestion.visual_assets`

### Commits

- No git history for `physics-question-bank` (untracked).
- Git log grep for “5000 MCQ” / `neet_exam_prep` did not surface an implementation commit for this bank.

---

## 6. Current 175 Reconciliation

**Are the current 175 CMS QUESTIONs related to the historical 5,000?**

### **NO — unrelated (HIGH confidence)**

| Signal | 5k Physics bank | Current `trinetra_db` 175 |
|--------|-----------------|---------------------------|
| ID scheme | `PHY11-CHxx-####` | UUIDs in `cms.content_items` |
| Storage | JSON / SQLite `physics_mcq_questions` | `cms.content_items` + JSONB body |
| Body shape | `question`, `options` dict A–D, `diagram_svg` | `stem`, `options` array, no `diagram_svg` |
| Overlap search | — | **0** stems/slugs containing `PHY11` |
| Physics count | 5000 | **73** |

Current Physics (73) provenance (tags / `model_used`):

| Provenance | Approx | Evidence |
|------------|-------:|----------|
| AI-generated / ingested | ~40 tagged `ai-generated`; models claude/gemini | tags + `model_used` |
| Human Batch-A | 20 with `origin:human-authored` + `acquisition-batch-A-diversify-p0` | tags + `model_used=human-authored-batch-a` |
| Factory-P3 | 8 tagged `factory-p3` | tags |
| Early practice seeds | Published Ohm’s-law style (Aug 1) | titles / null model_used |

**Phase-D** (`phase-d-30-mcq-authorized-20260825`): **35 DRAFT** in CMS (via ingestion join) — **not** the 5k bank; included in the 175 universe.

---

## 7. Physics Inventory (`trinetra_db` CMS only)

```text
Physics total     = 73
Published         = 6
Draft             = 56
In Review         = 11
Other             = 0
AI-generated      ≈ 40 (tag ai-generated) / model_used claude|gemini
Human-authored    = 20 (Batch-A tags)
Imported (5k bank)= 0
Unknown / early   ≈ 7–13 (null model_used, mixed titles)
```

---

## 8. Evidence Confidence

| Conclusion | Confidence | Why |
|------------|------------|-----|
| 5k TARGET existed | HIGH | Config + cursorrules |
| 5k GENERATED to files | HIGH | Exact JSON count + unique IDs + timestamps |
| 5k in SQLite | HIGH | Direct SELECT count |
| 5k not in TALOS CMS | HIGH | Zero ID overlap; schema mismatch |
| 5k not in PG as physics_mcq table (reachable DBs) | HIGH | Catalog search found no table |
| `neet_exam_prep_db` ≠ TALOS MCQ DB | HIGH | No repo refs; different schema |
| Row counts inside `neet_exam_prep_db.questions` | LOW / UNKNOWN | Permission denied |
| Whether anyone ever imported 5k into some other PG role’s DB | LOW | Would need other credentials |

---

## 9. Data Integrity Findings

1. **Environment confusion:** Two product surfaces — TALOS CMS (`trinetra_db`) vs standalone Physics bank (files/SQLite) vs legacy `neet_exam_prep_db`.
2. **Disconnected generation artifact:** 5k bank never entered ECAEP (`DRAFT→…→PUBLISHED`).
3. **Importer exists but unused for TALOS:** `import_to_db.py` loads into `physics_mcq_questions`, **not** `cms.content_items`.
4. **Untracked code/data:** `physics-question-bank/` not in git — risk of loss / non-reproducible ops history.
5. **DATABASE_URL vs SYNC mismatch:** Settings may point sync at `trinetra_test_db` while app uses `trinetra_db` — inventory tooling must not use the empty test DB.
6. **Orphan factory lineage:** 32 `generation_candidates` — separate from both 5k bank and most of the 175.
7. **No evidence of deletion of 5k from CMS** — they were never there to delete.

---

## 10. Recommended Next Action

**Do not regenerate another 5,000 until the following is decided explicitly:**

1. **Decide product fate of the existing 5k file bank** (keep as offline artifact / validate / map into ECAEP / discard).
2. If importing into TALOS: design a **CMS import + ECAEP** path (new work) — current importer is the wrong schema.
3. Treat **`trinetra_db` as the only authoritative TALOS MCQ database**.
4. Treat **`neet_exam_prep_db` as out-of-scope legacy** unless owners provide credentials and a migration plan.
5. Optionally commit or archive `physics-question-bank/output/*` with checksums so the 5k generation remains auditable.

**Do not** load/publish into production CMS until Class/subject/ECAEP gates from the production inventory audit are addressed.

---

## Appendix A — Known TALOS batches (persisted in `trinetra_db`)

| Batch / pilot | Records (approx) | Physics | Status mix | In current 175? |
|---------------|-----------------:|--------:|------------|-----------------|
| `acquisition-batch-A-diversify-p0` | 74 | 20 | DRAFT + IN_REVIEW | YES |
| `factory-p3` | 11 | 8 | DRAFT | YES |
| `phase-d-30-mcq-authorized-20260825` | 35 | (subset) | DRAFT | YES |
| Physics 5k bank (`PHY11-*`) | 5000 files / SQLite | 5000 | n/a (not CMS) | **NO** |

---

## Appendix B — Q1 answer options (forced choice)

**Primary answer: (4) Persisted in files/exports** — and also **(3) partially in another database** only as **SQLite `physics_test.db`**, not PostgreSQL TALOS.

Also true:

- **(1) Actually generated** — yes (files).
- **(6) Target/plan** — yes, but completed as file generation.
- **Not (7)/(8)** for CMS — never deleted/replaced there.
- **Not (2)** — they were persisted to disk/SQLite.
- **Not verified** as Postgres rows in `neet_exam_prep_db`.
