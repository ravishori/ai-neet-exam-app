# Cursor task protocol (TALOS)

Permanent policy lives in `.cursor/rules/`. Measured state lives in `docs/audits/*.json`.
Task prompts should contain **only** task-specific instructions.

## Authority stack

1. **Repository rules** (`.cursor/rules/*.mdc`) — permanent safety/policy.
2. **Architecture docs** (`docs/architecture/`, ADRs) — durable design decisions.
3. **Audit artifacts** (`docs/audits/*.json`) — measured populations, IDs, classifications.
4. **Task prompt** — objective, allowed mutation, verify, output, stop.

Do not paste permanent safety policy into every prompt.
Do not paste entire ID lists when an audit JSON already defines the population.
Do not hard-code stale DB counts; measure before/after.

## Compact task template

```text
TASK: <ID>

READ:
- docs/audits/<prior>.json
- (optional) docs/architecture/<note>.md

OBJECTIVE:
<one concise paragraph>

ALLOWED:
<exact permitted mutation; or READ-ONLY>

FORBIDDEN:
<task-specific prohibitions only>

VERIFY:
- before/after inventory freeze (measure)
- gate expectations
- provider_call_count == 0 unless generation authorized
- idempotency if write

OUTPUT:
- docs/audits/<task_id>.md
- docs/audits/<task_id>.json

STOP:
<explicit stop; typically no commit/push/generation>
```

## Prompt compression principles

### DO
- “Read `docs/audits/X.json` and modify only records classified `SAFE_FOR_SURGICAL_*`.”
- “Capture actual before/after counts.”
- “Follow applicable project rules.”
- Reference existing scripts/tests/artifacts by path.

### DO NOT
- Paste every blueprint/question record into the prompt.
- Hard-code stale PUBLISHED/DRAFT/unmapped counts.
- Repeat all permanent syllabus/NCERT/ECAEP safety rules.
- Re-specify an existing script’s full implementation unless deliberately changing it.

## Rule map (compact)

| Rule | Role |
|------|------|
| `project-core.mdc` | Accuracy, verification, source honesty |
| `neet-2026-syllabus-boundary.mdc` | Hard NEET-UG-2026 syllabus + dual-gate order |
| `ncert-source-boundary.mdc` | `NCERT Books/` factual root; exclusions |
| `studymaterial-archive.mdc` | Legacy StudyMaterial archive path (non-evidence) |
| `content-safety.mdc` | No generate/publish/provider by default |
| `content-factory.mdc` | Pipeline order, constraint merges |
| `mcq-quality.mdc` | Item quality + status discipline |
| `database-safety.mdc` | Surgical/idempotent DB writes |
| `audit-protocol.mdc` | Measure → mutate → verify → artifact |

## Example compressed prompt (illustrative)

**Before (verbose):** multi-page paste of safety policy + 14 blueprint IDs + stale counts + full gate essays.

**After:**

```text
TASK: NCERT-EVIDENCE-WRITE-002
READ: docs/audits/ncert_evidence_write_review_001.json
OBJECTIVE: Surgical constraints write for exact SAFE_FOR_SURGICAL_EVIDENCE_WRITE IDs.
ALLOWED: merge ncert_source_path, ncert_source_relative, ku_id only; keep provenance_tier=ai; omit ncert_derived.
FORBIDDEN: generation, publish, taxonomy/provenance_tier changes, non-target IDs.
VERIFY: 14 NCERT_EVIDENCE_READY; 248 REVIEW_REQUIRED blocked; provider_call_count==0; idempotent second run; inventory freeze.
OUTPUT: docs/audits/ncert_evidence_write_002.{md,json}
STOP: no commit/push/generation.
```

Approximate token reduction for that class of task: large (often well over half) because permanent policy and ID lists move to rules + JSON artifacts. Do not treat this as a measured percentage for every task.
